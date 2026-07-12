import '../client.dart';
import '../models.dart';

final class NativeEdgeIntelligence implements EdgeIntelligence {
  @override
  Future<SdkVersion> sdkVersion() async {
    return const SdkVersion(major: 0, minor: 1, patch: 0, abi: 0);
  }

  @override
  Future<PackInstallResult> installPack(
    ExecutionContext context,
    InstallPackCommand command,
  ) {
    throw UnsupportedError('Native Edge Intelligence FFI is unavailable.');
  }

  @override
  Future<IntentResult> parseIntent(
    ExecutionContext context,
    ParseIntentQuery query,
  ) {
    throw UnsupportedError('Native Edge Intelligence FFI is unavailable.');
  }

  @override
  Future<SearchResult> search(ExecutionContext context, SearchQuery query) {
    throw UnsupportedError('Native Edge Intelligence FFI is unavailable.');
  }

  @override
  Future<RecommendationResult> recommend(
    ExecutionContext context,
    RecommendationQuery query,
  ) {
    throw UnsupportedError('Native Edge Intelligence FFI is unavailable.');
  }

  @override
  Future<ResolvedMedia> play(ExecutionContext context, PlayCommand command) {
    throw UnsupportedError('Native Edge Intelligence FFI is unavailable.');
  }

  @override
  Future<ResolvedMedia?> resume(ExecutionContext context, ResumeQuery query) {
    throw UnsupportedError('Native Edge Intelligence FFI is unavailable.');
  }

  @override
  Future<ResolvedMedia> resolve(ExecutionContext context, ResolveQuery query) {
    throw UnsupportedError('Native Edge Intelligence FFI is unavailable.');
  }
}
