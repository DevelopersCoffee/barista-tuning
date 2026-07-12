import '../client.dart';
import '../models.dart';

final class MockEdgeIntelligence implements EdgeIntelligence {
  MockEdgeIntelligence({this.latency = Duration.zero});

  final Duration latency;

  static final List<MediaCandidate> _catalog = [
    const MediaCandidate(
      id: 'mock_aaj_tak',
      title: 'Aaj Tak',
      provider: 'mock_iptv',
      type: 'live_channel',
      score: 0.97,
      metadata: {'genre': 'news', 'language': 'hi', 'live': true},
    ),
    const MediaCandidate(
      id: 'mock_sony_max',
      title: 'Sony Max',
      provider: 'mock_iptv',
      type: 'live_channel',
      score: 0.91,
      metadata: {'genre': 'movies', 'language': 'hi', 'live': true},
    ),
    const MediaCandidate(
      id: 'mock_pbs_kids',
      title: 'PBS Kids',
      provider: 'mock_iptv',
      type: 'live_channel',
      score: 0.86,
      metadata: {'genre': 'kids', 'language': 'en', 'live': true},
    ),
    const MediaCandidate(
      id: 'mock_cricket_live',
      title: 'India Cricket Live',
      provider: 'mock_live',
      type: 'live_event',
      score: 0.84,
      metadata: {
        'genre': 'sports',
        'subgenre': 'cricket',
        'language': 'en',
        'live': true,
      },
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
      packId: packId.isEmpty ? 'mock.media.pack' : packId,
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
    final text = query.utterance.toLowerCase();
    final constraints = <String, Object?>{};

    if (text.contains('news')) {
      constraints['genre'] = 'news';
    } else if (text.contains('kid') || text.contains('cartoon')) {
      constraints['audience'] = 'kids';
      constraints['genre'] = 'kids';
    } else if (text.contains('cricket') || text.contains('match')) {
      constraints['genre'] = 'sports';
      constraints['subgenre'] = 'cricket';
      constraints['live'] = true;
    } else if (text.contains('funny') || text.contains('comedy')) {
      constraints['mood'] = 'funny';
      constraints['genre'] = 'comedy';
    }

    if (text.contains('hindi')) {
      constraints['language'] = 'hi';
    }

    return IntentResult(
      intent: text.contains('play') ? 'play' : 'recommend',
      tool: text.contains('play') ? 'media.play' : 'media.recommend',
      confidence: constraints.isEmpty ? 0.58 : 0.86,
      constraints: constraints,
      missingFields: const [],
      clarificationRequired: false,
    );
  }

  @override
  Future<SearchResult> search(
    ExecutionContext context,
    SearchQuery query,
  ) async {
    await _wait();
    final text = query.text.toLowerCase();
    final candidates = _catalog
        .where((candidate) {
          final haystack = '${candidate.title} ${candidate.metadata}'
              .toLowerCase();
          return text.isEmpty ||
              text
                  .split(' ')
                  .where((token) => token.isNotEmpty)
                  .any(haystack.contains);
        })
        .take(query.limit)
        .toList();

    return SearchResult(
      candidates: candidates.isEmpty
          ? _catalog.take(query.limit).toList()
          : candidates,
      traceId: context.requestId,
    );
  }

  @override
  Future<RecommendationResult> recommend(
    ExecutionContext context,
    RecommendationQuery query,
  ) async {
    await _wait();
    return RecommendationResult(
      candidates: _catalog.take(query.limit).toList(),
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
      orElse: () => _catalog.first,
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
