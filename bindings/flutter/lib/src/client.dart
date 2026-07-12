import 'models.dart';
import 'mock/mock_client.dart';
import 'native/native_client.dart'
    if (dart.library.ffi) 'native/native_client_ffi.dart';
import 'rule_based/rule_based_client.dart';

abstract interface class EdgeIntelligence {
  factory EdgeIntelligence.native() = NativeEdgeIntelligence;
  factory EdgeIntelligence.mock({Duration latency}) = MockEdgeIntelligence;
  factory EdgeIntelligence.ruleBased({Duration latency}) =
      RuleBasedEdgeIntelligence;

  Future<SdkVersion> sdkVersion();

  Future<PackInstallResult> installPack(
    ExecutionContext context,
    InstallPackCommand command,
  );

  Future<IntentResult> parseIntent(
    ExecutionContext context,
    ParseIntentQuery query,
  );

  Future<SearchResult> search(ExecutionContext context, SearchQuery query);

  Future<RecommendationResult> recommend(
    ExecutionContext context,
    RecommendationQuery query,
  );

  Future<ResolvedMedia> play(ExecutionContext context, PlayCommand command);

  Future<ResolvedMedia?> resume(ExecutionContext context, ResumeQuery query);

  Future<ResolvedMedia> resolve(ExecutionContext context, ResolveQuery query);
}
