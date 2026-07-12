enum NetworkState { offline, metered, online }

final class SdkVersion {
  const SdkVersion({
    required this.major,
    required this.minor,
    required this.patch,
    required this.abi,
  });

  final int major;
  final int minor;
  final int patch;
  final int abi;
}

final class ExecutionContext {
  const ExecutionContext({
    required this.requestId,
    required this.locale,
    required this.network,
    this.userId,
    this.profileId,
    this.deviceId,
    this.deviceClass,
    this.capabilities = const [],
    this.time,
    this.attributes = const {},
  });

  final String requestId;
  final String? userId;
  final String? profileId;
  final String? deviceId;
  final String? deviceClass;
  final LocaleContext locale;
  final List<String> capabilities;
  final NetworkState network;
  final DateTime? time;
  final Map<String, String> attributes;
}

final class LocaleContext {
  const LocaleContext({required this.language, this.region});

  final String language;
  final String? region;
}

final class InstallPackCommand {
  const InstallPackCommand({required this.packPath, this.activate = true});

  final String packPath;
  final bool activate;
}

final class PackInstallResult {
  const PackInstallResult({
    required this.packId,
    required this.version,
    required this.activated,
  });

  final String packId;
  final String version;
  final bool activated;
}

final class ParseIntentQuery {
  const ParseIntentQuery(this.utterance);

  final String utterance;
}

final class IntentResult {
  const IntentResult({
    required this.intent,
    this.tool,
    required this.confidence,
    required this.constraints,
    required this.missingFields,
    required this.clarificationRequired,
  });

  final String intent;
  final String? tool;
  final double confidence;
  final Map<String, Object?> constraints;
  final List<String> missingFields;
  final bool clarificationRequired;
}

final class SearchQuery {
  const SearchQuery({
    required this.text,
    this.constraints = const {},
    this.limit = 20,
  });

  final String text;
  final Map<String, Object?> constraints;
  final int limit;
}

final class RecommendationQuery {
  const RecommendationQuery({this.constraints = const {}, this.limit = 20});

  final Map<String, Object?> constraints;
  final int limit;
}

final class ResumeQuery {
  const ResumeQuery();
}

final class ResolveQuery {
  const ResolveQuery(this.itemId);

  final String itemId;
}

final class PlayCommand {
  const PlayCommand({this.query, this.itemId});

  final String? query;
  final String? itemId;
}

final class SearchResult {
  const SearchResult({required this.candidates, this.traceId});

  final List<MediaCandidate> candidates;
  final String? traceId;
}

final class RecommendationResult {
  const RecommendationResult({required this.candidates, this.traceId});

  final List<MediaCandidate> candidates;
  final String? traceId;
}

final class MediaCandidate {
  const MediaCandidate({
    required this.id,
    required this.title,
    required this.provider,
    required this.type,
    required this.score,
    this.metadata = const {},
  });

  final String id;
  final String title;
  final String provider;
  final String type;
  final double score;
  final Map<String, Object?> metadata;
}

final class ResolvedMedia {
  const ResolvedMedia({
    required this.id,
    required this.title,
    required this.streamUri,
    this.headers = const {},
    this.subtitles = const [],
    this.thumbnail,
    this.metadata = const {},
  });

  final String id;
  final String title;
  final Uri streamUri;
  final Map<String, String> headers;
  final List<Uri> subtitles;
  final Uri? thumbnail;
  final Map<String, Object?> metadata;
}
