import 'package:slm_edge_intelligence/slm_edge_intelligence.dart';
import 'package:test/test.dart';

void main() {
  const context = ExecutionContext(
    requestId: 'rule-test',
    locale: LocaleContext(language: 'en', region: 'IN'),
    network: NetworkState.offline,
  );

  final scenarios = <_IntentScenario>[
    _IntentScenario(
      utterance: 'Show Hindi news',
      intent: 'search',
      tool: 'media.search',
      constraints: {'genre': 'news', 'live': true, 'language': 'hi'},
    ),
    _IntentScenario(
      utterance: 'Marathi movie channels',
      intent: 'search',
      tool: 'media.search',
      constraints: {'genre': 'movies', 'language': 'mr'},
    ),
    _IntentScenario(
      utterance: 'Cartoon for my 5 year old',
      intent: 'recommend',
      tool: 'media.recommend',
      constraints: {'audience': 'kids', 'genre': 'kids', 'age_safe': true},
    ),
    _IntentScenario(
      utterance: 'Sports in HD only',
      intent: 'search',
      tool: 'media.search',
      constraints: {'genre': 'sports', 'quality': 'hd'},
    ),
    _IntentScenario(
      utterance: 'Play Aaj Tak',
      intent: 'play',
      tool: 'media.play',
      constraints: {'query': 'Aaj Tak', 'live': true},
    ),
    _IntentScenario(
      utterance: "Continue yesterday's movie",
      intent: 'resume',
      tool: 'media.resume',
      constraints: {'continue_watching': true},
    ),
    _IntentScenario(
      utterance: "What's live right now?",
      intent: 'browse',
      tool: 'media.browse',
      constraints: {'live': true},
    ),
    _IntentScenario(
      utterance: 'I want something funny',
      intent: 'recommend',
      tool: 'media.recommend',
      constraints: {'mood': 'funny'},
    ),
    _IntentScenario(
      utterance: 'Show business news',
      intent: 'search',
      tool: 'media.search',
      constraints: {'genre': 'business_news', 'live': true},
    ),
    _IntentScenario(
      utterance: 'I want devotional channels',
      intent: 'recommend',
      tool: 'media.recommend',
      constraints: {'genre': 'religious'},
    ),
    _IntentScenario(
      utterance: 'Show something educational for Class 8',
      intent: 'recommend',
      tool: 'media.recommend',
      constraints: {'genre': 'education', 'grade': '8'},
    ),
    _IntentScenario(
      utterance: 'Only free channels',
      intent: 'search',
      tool: 'media.search',
      constraints: {'subscription': 'free'},
    ),
    _IntentScenario(
      utterance: 'Kids should not see violent content',
      intent: 'recommend',
      tool: 'media.recommend',
      constraints: {'parental_control': true, 'avoid': 'violence'},
    ),
    _IntentScenario(
      utterance: 'Latest Marathi movie',
      intent: 'search',
      tool: 'media.search',
      constraints: {'genre': 'movies', 'language': 'mr', 'sort': 'recent'},
    ),
    _IntentScenario(
      utterance: 'Add this to favorites',
      intent: 'favorite',
      tool: 'media.favorite',
      constraints: {'target': 'current'},
    ),
  ];

  for (final scenario in scenarios) {
    test('rule backend parses "${scenario.utterance}"', () async {
      final edge = EdgeIntelligence.ruleBased();

      final result = await edge.parseIntent(
        context,
        ParseIntentQuery(scenario.utterance),
      );

      expect(result.intent, scenario.intent);
      expect(result.tool, scenario.tool);
      expect(result.constraints, scenario.constraints);
      expect(result.clarificationRequired, isFalse);
      expect(result.missingFields, isEmpty);
    });
  }

  test('rule backend requests clarification for ambiguous query', () async {
    final edge = EdgeIntelligence.ruleBased();

    final result = await edge.parseIntent(
      context,
      const ParseIntentQuery('Play Sony'),
    );

    expect(result.intent, 'clarify');
    expect(result.tool, 'media.clarify');
    expect(result.clarificationRequired, isTrue);
    expect(result.missingFields, ['specific_media']);
  });

  test('rule backend can search using parsed constraints', () async {
    final edge = EdgeIntelligence.ruleBased();
    final intent = await edge.parseIntent(
      context,
      const ParseIntentQuery('Marathi movie channels'),
    );

    final result = await edge.search(
      context,
      SearchQuery(text: '', constraints: intent.constraints),
    );

    expect(result.traceId, context.requestId);
    expect(result.candidates.first.title, 'Marathi Movies');
  });

  test('rule backend can play a directly named channel', () async {
    final edge = EdgeIntelligence.ruleBased();

    final resolved = await edge.play(
      context,
      const PlayCommand(query: 'Aaj Tak'),
    );

    expect(resolved.title, 'Aaj Tak');
    expect(resolved.streamUri.toString(), contains('rule_aaj_tak'));
  });
}

final class _IntentScenario {
  const _IntentScenario({
    required this.utterance,
    required this.intent,
    required this.tool,
    required this.constraints,
  });

  final String utterance;
  final String intent;
  final String tool;
  final Map<String, Object?> constraints;
}
