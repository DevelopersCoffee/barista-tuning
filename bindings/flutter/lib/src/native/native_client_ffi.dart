import 'dart:convert';
import 'dart:ffi';
import 'dart:io';

import 'package:ffi/ffi.dart';

import '../client.dart';
import '../models.dart';

typedef _U32Fn = Uint32 Function();
typedef _U32DartFn = int Function();
typedef _U16Fn = Uint16 Function();
typedef _U16DartFn = int Function();
typedef _ExecuteJsonFn = Pointer<Utf8> Function(Pointer<Utf8>);
typedef _ExecuteJsonDartFn = Pointer<Utf8> Function(Pointer<Utf8>);
typedef _FreeStringFn = Void Function(Pointer<Utf8>);
typedef _FreeStringDartFn = void Function(Pointer<Utf8>);

final class NativeEdgeIntelligence implements EdgeIntelligence {
  NativeEdgeIntelligence({DynamicLibrary? library})
    : _library = library ?? _openDefaultLibrary();

  final DynamicLibrary _library;

  @override
  Future<SdkVersion> sdkVersion() async {
    final abi = _lookupU32('edge_intelligence_abi_version')();
    final major = _lookupU16('edge_intelligence_sdk_version_major')();
    final minor = _lookupU16('edge_intelligence_sdk_version_minor')();
    final patch = _lookupU16('edge_intelligence_sdk_version_patch')();

    return SdkVersion(major: major, minor: minor, patch: patch, abi: abi);
  }

  @override
  Future<PackInstallResult> installPack(
    ExecutionContext context,
    InstallPackCommand command,
  ) async {
    final response = await _execute('installPack', {
      'context': _contextJson(context),
      'packPath': command.packPath,
      'activate': command.activate,
    });
    return PackInstallResult(
      packId: response['packId'] as String,
      version: response['version'] as String,
      activated: response['activated'] as bool,
    );
  }

  @override
  Future<IntentResult> parseIntent(
    ExecutionContext context,
    ParseIntentQuery query,
  ) async {
    final response = await _execute('parseIntent', {
      'context': _contextJson(context),
      'utterance': query.utterance,
    });
    return IntentResult(
      intent: response['intent'] as String,
      tool: response['tool'] as String?,
      confidence: (response['confidence'] as num).toDouble(),
      constraints: Map<String, Object?>.from(response['constraints'] as Map),
      missingFields: List<String>.from(response['missingFields'] as List),
      clarificationRequired: response['clarificationRequired'] as bool,
    );
  }

  @override
  Future<SearchResult> search(
    ExecutionContext context,
    SearchQuery query,
  ) async {
    final response = await _execute('search', {
      'context': _contextJson(context),
      'text': query.text,
      'constraints': query.constraints,
      'limit': query.limit,
    });
    return SearchResult(
      candidates: _candidateList(response['candidates'] as List),
      traceId: response['traceId'] as String?,
    );
  }

  @override
  Future<RecommendationResult> recommend(
    ExecutionContext context,
    RecommendationQuery query,
  ) async {
    final response = await _execute('recommend', {
      'context': _contextJson(context),
      'constraints': query.constraints,
      'limit': query.limit,
    });
    return RecommendationResult(
      candidates: _candidateList(response['candidates'] as List),
      traceId: response['traceId'] as String?,
    );
  }

  @override
  Future<ResolvedMedia> play(
    ExecutionContext context,
    PlayCommand command,
  ) async {
    final response = await _execute('play', {
      'context': _contextJson(context),
      'query': command.query,
      'itemId': command.itemId,
    });
    return _resolvedMedia(response);
  }

  @override
  Future<ResolvedMedia?> resume(
    ExecutionContext context,
    ResumeQuery query,
  ) async {
    final response = await _execute('resume', {
      'context': _contextJson(context),
    });
    if (response['item'] == null) {
      return null;
    }
    return _resolvedMedia(Map<String, Object?>.from(response['item'] as Map));
  }

  @override
  Future<ResolvedMedia> resolve(
    ExecutionContext context,
    ResolveQuery query,
  ) async {
    final response = await _execute('resolve', {
      'context': _contextJson(context),
      'itemId': query.itemId,
    });
    return _resolvedMedia(response);
  }

  _U32DartFn _lookupU32(String name) {
    return _library.lookupFunction<_U32Fn, _U32DartFn>(name);
  }

  _U16DartFn _lookupU16(String name) {
    return _library.lookupFunction<_U16Fn, _U16DartFn>(name);
  }

  Future<Map<String, Object?>> _execute(
    String useCase,
    Map<String, Object?> payload,
  ) async {
    final request = jsonEncode({'useCase': useCase, 'payload': payload});
    final requestPointer = request.toNativeUtf8();
    final execute = _library.lookupFunction<_ExecuteJsonFn, _ExecuteJsonDartFn>(
      'edge_intelligence_execute_json',
    );
    final free = _library.lookupFunction<_FreeStringFn, _FreeStringDartFn>(
      'edge_intelligence_string_free',
    );

    try {
      final responsePointer = execute(requestPointer);
      if (responsePointer == nullptr) {
        throw StateError('Native Edge Intelligence returned null.');
      }
      try {
        final decoded = jsonDecode(responsePointer.toDartString());
        final response = Map<String, Object?>.from(decoded as Map);
        if (response['ok'] != true) {
          throw StateError(
            response['error'] as String? ?? 'Native call failed.',
          );
        }
        return Map<String, Object?>.from(response['data'] as Map);
      } finally {
        free(responsePointer);
      }
    } finally {
      calloc.free(requestPointer);
    }
  }
}

DynamicLibrary _openDefaultLibrary() {
  if (Platform.isMacOS || Platform.isIOS) {
    return DynamicLibrary.open('libedge_ffi.dylib');
  }
  if (Platform.isWindows) {
    return DynamicLibrary.open('edge_ffi.dll');
  }
  return DynamicLibrary.open('libedge_ffi.so');
}

Map<String, Object?> _contextJson(ExecutionContext context) {
  return {
    'requestId': context.requestId,
    'userId': context.userId,
    'profileId': context.profileId,
    'deviceId': context.deviceId,
    'deviceClass': context.deviceClass,
    'locale': {
      'language': context.locale.language,
      'region': context.locale.region,
    },
    'capabilities': context.capabilities,
    'network': context.network.name,
    'time': context.time?.toIso8601String(),
    'attributes': context.attributes,
  };
}

List<MediaCandidate> _candidateList(List<Object?> values) {
  return values.map((value) {
    final json = Map<String, Object?>.from(value as Map);
    return MediaCandidate(
      id: json['id'] as String,
      title: json['title'] as String,
      provider: json['provider'] as String,
      type: json['type'] as String,
      score: (json['score'] as num).toDouble(),
      metadata: Map<String, Object?>.from(json['metadata'] as Map? ?? {}),
    );
  }).toList();
}

ResolvedMedia _resolvedMedia(Map<String, Object?> json) {
  final thumbnail = json['thumbnail'] as String?;
  return ResolvedMedia(
    id: json['id'] as String,
    title: json['title'] as String,
    streamUri: Uri.parse(json['streamUri'] as String),
    headers: Map<String, String>.from(json['headers'] as Map? ?? {}),
    subtitles: (json['subtitles'] as List? ?? [])
        .map((value) => Uri.parse(value as String))
        .toList(),
    thumbnail: thumbnail == null ? null : Uri.parse(thumbnail),
    metadata: Map<String, Object?>.from(json['metadata'] as Map? ?? {}),
  );
}
