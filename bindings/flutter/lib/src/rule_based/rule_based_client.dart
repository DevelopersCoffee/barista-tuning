import '../client.dart';
import '../models.dart';

final class RuleBasedEdgeIntelligence implements EdgeIntelligence {
  RuleBasedEdgeIntelligence({this.latency = Duration.zero});

  final Duration latency;

  static final List<MediaCandidate> _catalog = [
    const MediaCandidate(
      id: 'rule_aaj_tak',
      title: 'Aaj Tak',
      provider: 'rule_iptv',
      type: 'live_channel',
      score: 0.97,
      metadata: {'genre': 'news', 'language': 'hi', 'live': true},
    ),
    const MediaCandidate(
      id: 'rule_sony_max',
      title: 'Sony Max',
      provider: 'rule_iptv',
      type: 'live_channel',
      score: 0.91,
      metadata: {
        'genre': 'movies',
        'subgenre': 'bollywood',
        'language': 'hi',
        'live': true,
        'quality': 'hd',
      },
    ),
    const MediaCandidate(
      id: 'rule_pbs_kids',
      title: 'PBS Kids',
      provider: 'rule_iptv',
      type: 'live_channel',
      score: 0.86,
      metadata: {'genre': 'kids', 'language': 'en', 'live': true},
    ),
    const MediaCandidate(
      id: 'rule_cricket_live',
      title: 'India Cricket Live',
      provider: 'rule_live',
      type: 'live_event',
      score: 0.84,
      metadata: {
        'genre': 'sports',
        'subgenre': 'cricket',
        'language': 'en',
        'live': true,
        'quality': 'hd',
      },
    ),
    const MediaCandidate(
      id: 'rule_marathi_movies',
      title: 'Marathi Movies',
      provider: 'rule_iptv',
      type: 'live_channel',
      score: 0.82,
      metadata: {'genre': 'movies', 'language': 'mr', 'live': true},
    ),
    const MediaCandidate(
      id: 'rule_devotional',
      title: 'Devotional India',
      provider: 'rule_iptv',
      type: 'live_channel',
      score: 0.78,
      metadata: {'genre': 'religious', 'language': 'hi', 'live': true},
    ),
    const MediaCandidate(
      id: 'rule_education',
      title: 'Education Class 8',
      provider: 'rule_iptv',
      type: 'video',
      score: 0.76,
      metadata: {'genre': 'education', 'audience': 'students'},
    ),
  ];

  @override
  Future<SdkVersion> sdkVersion() async {
    await _wait();
    return const SdkVersion(major: 0, minor: 1, patch: 0, abi: 0);
  }

  @override
  Future<PackInstallResult> installPack(
    ExecutionContext context,
    InstallPackCommand command,
  ) async {
    await _wait();
    final fileName = command.packPath.split('/').last;
    final packId = fileName.replaceAll('.pack', '');
    return PackInstallResult(
      packId: packId.isEmpty ? 'rule.media.pack' : packId,
      version: '0.1.0',
      activated: command.activate,
    );
  }

  @override
  Future<IntentResult> parseIntent(
    ExecutionContext context,
    ParseIntentQuery query,
  ) async {
    await _wait();
    return _parseIntent(query.utterance);
  }

  @override
  Future<SearchResult> search(
    ExecutionContext context,
    SearchQuery query,
  ) async {
    await _wait();
    final candidates = _rankCandidates(
      query.text,
      query.constraints,
    ).take(query.limit).toList();
    return SearchResult(candidates: candidates, traceId: context.requestId);
  }

  @override
  Future<RecommendationResult> recommend(
    ExecutionContext context,
    RecommendationQuery query,
  ) async {
    await _wait();
    final candidates = _rankCandidates(
      '',
      query.constraints,
    ).take(query.limit).toList();
    return RecommendationResult(
      candidates: candidates.isEmpty
          ? _catalog.take(query.limit).toList()
          : candidates,
      traceId: context.requestId,
    );
  }

  @override
  Future<ResolvedMedia> play(
    ExecutionContext context,
    PlayCommand command,
  ) async {
    await _wait();
    final candidate = _candidateFor(command.itemId, command.query);
    return _resolveCandidate(candidate);
  }

  @override
  Future<ResolvedMedia?> resume(
    ExecutionContext context,
    ResumeQuery query,
  ) async {
    await _wait();
    return _resolveCandidate(_catalog[1]);
  }

  @override
  Future<ResolvedMedia> resolve(
    ExecutionContext context,
    ResolveQuery query,
  ) async {
    await _wait();
    return _resolveCandidate(_candidateFor(query.itemId, null));
  }

  IntentResult _parseIntent(String utterance) {
    final text = utterance.toLowerCase().trim().replaceAll(RegExp(r'\s+'), ' ');
    final language = _language(text);
    final quality = _quality(text);

    if (const {'play sony', 'put on news', 'show the match'}.contains(text)) {
      return _intent(
        intent: 'clarify',
        tool: 'media.clarify',
        confidence: 0.62,
        missingFields: const ['specific_media'],
        clarificationRequired: true,
      );
    }

    if (_containsAny(text, const [
      'add this to favorites',
      'favorite this channel',
      'save this for later',
    ])) {
      return _intent(
        intent: 'favorite',
        tool: 'media.favorite',
        confidence: 0.87,
        constraints: const {'target': 'current'},
      );
    }

    if (_containsAny(text, const ['continue', 'resume'])) {
      return _intent(
        intent: 'resume',
        tool: 'media.resume',
        confidence: 0.91,
        constraints: const {'continue_watching': true},
      );
    }

    if (_containsAny(text, const [
      "what's live",
      'what is live',
      'show live channels',
      'browse live tv',
    ])) {
      return _intent(
        intent: 'browse',
        tool: 'media.browse',
        confidence: 0.9,
        constraints: const {'live': true},
      );
    }

    final directTitle = _directTitle(text);
    if (directTitle != null) {
      return _intent(
        intent: 'play',
        tool: 'media.play',
        confidence: 0.94,
        constraints: {'query': directTitle, 'live': true},
      );
    }

    if (text.contains('cricket') || text.contains('india match')) {
      return _intent(
        intent: 'play',
        tool: 'media.play',
        confidence: 0.89,
        constraints: _withOptional({
          'genre': 'sports',
          'subgenre': 'cricket',
          'live': true,
        }, quality: quality),
      );
    }

    if (text.contains('sports')) {
      return _intent(
        intent: 'search',
        tool: 'media.search',
        confidence: 0.86,
        constraints: _withOptional({'genre': 'sports'}, quality: quality),
      );
    }

    if (text.contains('violent') || text.contains('violence')) {
      return _intent(
        intent: 'recommend',
        tool: 'media.recommend',
        confidence: 0.82,
        constraints: const {'parental_control': true, 'avoid': 'violence'},
      );
    }

    if (_containsAny(text, const ['kid', 'cartoon', '5 year old'])) {
      return _intent(
        intent: 'recommend',
        tool: 'media.recommend',
        confidence: 0.88,
        constraints: const {
          'audience': 'kids',
          'genre': 'kids',
          'age_safe': true,
        },
      );
    }

    if (_containsAny(text, const ['movie', 'movies', 'film'])) {
      return _intent(
        intent: text.contains('play') ? 'play' : 'search',
        tool: text.contains('play') ? 'media.play' : 'media.search',
        confidence: 0.86,
        constraints: _withOptional(
          {'genre': 'movies'},
          language: language,
          quality: quality,
          sort: text.contains('latest') || text.contains('recent')
              ? 'recent'
              : null,
        ),
      );
    }

    if (text.contains('news')) {
      final constraints = _withOptional(
        {
          'genre': text.contains('business') ? 'business_news' : 'news',
          'live': true,
        },
        language: language,
        quality: quality,
      );
      return _intent(
        intent: 'search',
        tool: 'media.search',
        confidence: 0.92,
        constraints: constraints,
      );
    }

    if (_containsAny(text, const ['devotional', 'religious', 'bhajan'])) {
      return _intent(
        intent: 'recommend',
        tool: 'media.recommend',
        confidence: 0.84,
        constraints: _withOptional({'genre': 'religious'}, language: language),
      );
    }

    if (_containsAny(text, const ['educational', 'education', 'class 8'])) {
      return _intent(
        intent: 'recommend',
        tool: 'media.recommend',
        confidence: 0.84,
        constraints: {
          'genre': 'education',
          if (text.contains('class 8')) 'grade': '8',
        },
      );
    }

    if (text.contains('free')) {
      return _intent(
        intent: 'search',
        tool: 'media.search',
        confidence: 0.76,
        constraints: const {'subscription': 'free'},
      );
    }

    final mood = _mood(text);
    if (mood != null) {
      return _intent(
        intent: 'recommend',
        tool: 'media.recommend',
        confidence: 0.84,
        constraints: {'mood': mood},
      );
    }

    return _intent(
      intent: 'recommend',
      tool: 'media.recommend',
      confidence: 0.58,
    );
  }

  List<MediaCandidate> _rankCandidates(
    String text,
    Map<String, Object?> constraints,
  ) {
    final normalizedText = text.toLowerCase();
    final tokens = normalizedText
        .split(RegExp(r'\s+'))
        .where((token) => token.isNotEmpty)
        .toList();
    final scored = <({MediaCandidate candidate, double score})>[];

    for (final candidate in _catalog) {
      var score = candidate.score;
      final haystack = '${candidate.title} ${candidate.metadata}'.toLowerCase();
      if (tokens.isNotEmpty && tokens.any(haystack.contains)) {
        score += 0.2;
      }

      var constraintMismatch = false;
      for (final entry in constraints.entries) {
        final value = candidate.metadata[entry.key];
        if (value == entry.value) {
          score += 0.35;
        } else if (entry.key == 'mood' && entry.value == 'funny') {
          score += candidate.metadata['genre'] == 'movies' ? 0.15 : 0;
        } else if (!const {
          'query',
          'sort',
          'age_safe',
          'parental_control',
          'avoid',
          'grade',
          'subscription',
        }.contains(entry.key)) {
          constraintMismatch = true;
        }
      }

      if (!constraintMismatch || tokens.any(haystack.contains)) {
        scored.add((candidate: candidate, score: score));
      }
    }

    scored.sort((a, b) => b.score.compareTo(a.score));
    return scored
        .map(
          (entry) => MediaCandidate(
            id: entry.candidate.id,
            title: entry.candidate.title,
            provider: entry.candidate.provider,
            type: entry.candidate.type,
            score: double.parse(entry.score.toStringAsFixed(3)),
            metadata: entry.candidate.metadata,
          ),
        )
        .toList();
  }

  MediaCandidate _candidateFor(String? itemId, String? query) {
    if (itemId != null) {
      return _catalog.firstWhere(
        (candidate) => candidate.id == itemId,
        orElse: () => _catalog.first,
      );
    }

    final text = query?.toLowerCase() ?? '';
    return _catalog.firstWhere(
      (candidate) => candidate.title.toLowerCase().contains(text),
      orElse: () => _rankCandidates(text, const {}).first,
    );
  }

  ResolvedMedia _resolveCandidate(MediaCandidate candidate) {
    return ResolvedMedia(
      id: candidate.id,
      title: candidate.title,
      streamUri: Uri.parse('https://example.invalid/${candidate.id}.m3u8'),
      metadata: candidate.metadata,
    );
  }

  Future<void> _wait() async {
    if (latency > Duration.zero) {
      await Future<void>.delayed(latency);
    }
  }
}

IntentResult _intent({
  required String intent,
  required String tool,
  required double confidence,
  Map<String, Object?> constraints = const {},
  List<String> missingFields = const [],
  bool clarificationRequired = false,
}) {
  return IntentResult(
    intent: intent,
    tool: tool,
    confidence: confidence,
    constraints: constraints,
    missingFields: missingFields,
    clarificationRequired: clarificationRequired,
  );
}

bool _containsAny(String text, List<String> needles) {
  return needles.any(text.contains);
}

String? _directTitle(String text) {
  const titles = {
    'aaj tak': 'Aaj Tak',
    'sony max': 'Sony Max',
    'pbs kids': 'PBS Kids',
    'india cricket live': 'India cricket live',
  };
  if (!text.startsWith(RegExp(r'(play|put on|open) '))) {
    return null;
  }
  for (final entry in titles.entries) {
    if (text.contains(entry.key)) {
      return entry.value;
    }
  }
  return null;
}

String? _language(String text) {
  const languages = {
    'hindi': 'hi',
    'english': 'en',
    'marathi': 'mr',
    'tamil': 'ta',
    'telugu': 'te',
  };
  for (final entry in languages.entries) {
    if (text.contains(entry.key)) {
      return entry.value;
    }
  }
  return null;
}

String? _quality(String text) {
  if (RegExp(r'\b(hd|1080p|fhd)\b').hasMatch(text)) {
    return 'hd';
  }
  if (RegExp(r'\b(sd|480p)\b').hasMatch(text)) {
    return 'sd';
  }
  return null;
}

String? _mood(String text) {
  const moods = {
    'funny': 'funny',
    'comedy': 'funny',
    'calm': 'calm',
    'inspiring': 'inspiring',
    'educational': 'educational',
    'relax': 'relaxing',
    'relaxing': 'relaxing',
    'bored': 'entertainment',
  };
  for (final entry in moods.entries) {
    if (text.contains(entry.key)) {
      return entry.value;
    }
  }
  return null;
}

Map<String, Object?> _withOptional(
  Map<String, Object?> values, {
  String? language,
  String? quality,
  String? sort,
}) {
  final result = {...values};
  if (language != null) {
    result['language'] = language;
  }
  if (quality != null) {
    result['quality'] = quality;
  }
  if (sort != null) {
    result['sort'] = sort;
  }
  return result;
}
