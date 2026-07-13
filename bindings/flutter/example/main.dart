import 'package:slm_edge_intelligence/slm_edge_intelligence.dart';

Future<void> main() async {
  final packPath = const String.fromEnvironment('AIRO_MEDIA_PACK');
  final edge = packPath.isEmpty
      ? EdgeIntelligence.ruleBased()
      : EdgeIntelligence.native();

  const context = ExecutionContext(
    requestId: 'airo-example-1',
    locale: LocaleContext(language: 'en', region: 'IN'),
    network: NetworkState.online,
  );

  if (packPath.isNotEmpty) {
    await edge.installPack(context, InstallPackCommand(packPath: packPath));
  }

  final streamUri = await resolveAiroInput(edge, context, 'Show Hindi news');

  await playInAiroPlayer(streamUri);
}

Future<Uri> resolveAiroInput(
  EdgeIntelligence edge,
  ExecutionContext context,
  String utterance,
) async {
  final intent = await edge.parseIntent(context, ParseIntentQuery(utterance));

  if (intent.intent == 'resume') {
    final item = await edge.resume(context, const ResumeQuery());
    if (item != null) {
      return item.streamUri;
    }
  }

  if (intent.intent == 'play') {
    final item = await edge.play(context, PlayCommand(query: utterance));
    return item.streamUri;
  }

  if (intent.intent == 'search' || intent.intent == 'browse') {
    final result = await edge.search(
      context,
      SearchQuery(text: utterance, constraints: intent.constraints),
    );
    if (result.candidates.isNotEmpty) {
      final item = await edge.resolve(
        context,
        ResolveQuery(result.candidates.first.id),
      );
      return item.streamUri;
    }
  }

  final recommendations = await edge.recommend(
    context,
    RecommendationQuery(constraints: intent.constraints),
  );
  if (recommendations.candidates.isEmpty) {
    throw StateError('No playable media matched: $utterance');
  }

  final item = await edge.resolve(
    context,
    ResolveQuery(recommendations.candidates.first.id),
  );
  return item.streamUri;
}

Future<void> playInAiroPlayer(Uri streamUri) async {
  assert(streamUri.toString().isNotEmpty);
}
