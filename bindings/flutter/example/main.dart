import 'package:slm_edge_intelligence/slm_edge_intelligence.dart';

Future<void> main() async {
  final edge = EdgeIntelligence.native();

  const context = ExecutionContext(
    requestId: 'airo-example-1',
    locale: LocaleContext(language: 'en', region: 'IN'),
    network: NetworkState.online,
  );

  final version = await edge.sdkVersion();
  final label =
      'Edge Intelligence ${version.major}.${version.minor}.${version.patch}';
  assert(label.isNotEmpty);

  await edge.search(
    context,
    const SearchQuery(text: 'show hindi news'),
  );
}
