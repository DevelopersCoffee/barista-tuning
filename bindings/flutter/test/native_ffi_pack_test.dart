import 'dart:ffi';
import 'dart:io';

import 'package:slm_edge_intelligence/slm_edge_intelligence.dart';
import 'package:slm_edge_intelligence/src/native/native_client_ffi.dart';
import 'package:test/test.dart';

void main() {
  test('native FFI installs pack and resolves Airo queries', () async {
    final libraryPath = Platform.environment['EDGE_FFI_LIBRARY'];
    final packPath = Platform.environment['EDGE_FFI_PACK'];
    final cacheDir = Platform.environment['EDGE_INTELLIGENCE_PACK_CACHE'];
    if (libraryPath == null || packPath == null || cacheDir == null) {
      markTestSkipped(
        'Set EDGE_FFI_LIBRARY, EDGE_FFI_PACK, and '
        'EDGE_INTELLIGENCE_PACK_CACHE to run native FFI integration.',
      );
      return;
    }

    final edge = NativeEdgeIntelligence(
      library: DynamicLibrary.open(libraryPath),
    );
    const context = ExecutionContext(
      requestId: 'native-ffi-pack-test',
      locale: LocaleContext(language: 'en', region: 'IN'),
      network: NetworkState.online,
    );

    final version = await edge.sdkVersion();
    expect(version.abi, 1);

    final install = await edge.installPack(
      context,
      InstallPackCommand(packPath: packPath),
    );
    expect(install.packId, 'media.iptv.airo-sample');
    expect(install.activated, isTrue);

    await expectStream(
      edge,
      context,
      'Show Hindi news',
      'https://example.test/aajtak/master.m3u8',
    );
    await expectStream(
      edge,
      context,
      'Marathi movies',
      'https://example.test/marathi/movies.m3u8',
    );
    await expectStream(
      edge,
      context,
      'Sports in HD only',
      'https://example.test/sports/hd.m3u8',
    );

    final aajTak = await edge.play(
      context,
      const PlayCommand(query: 'Play Aaj Tak'),
    );
    expect(aajTak.streamUri.toString(), 'https://example.test/aajtak/master.m3u8');

    final resume = await edge.resume(context, const ResumeQuery());
    expect(resume, isNotNull);
    expect(
      resume!.streamUri.toString(),
      'https://example.test/marathi/movies.m3u8',
    );
  });
}

Future<void> expectStream(
  EdgeIntelligence edge,
  ExecutionContext context,
  String utterance,
  String expectedStreamUri,
) async {
  final intent = await edge.parseIntent(context, ParseIntentQuery(utterance));

  final ResolvedMedia resolved;
  if (intent.intent == 'play') {
    resolved = await edge.play(context, PlayCommand(query: utterance));
  } else {
    final result = await edge.search(
      context,
      SearchQuery(text: utterance, constraints: intent.constraints),
    );
    expect(result.candidates, isNotEmpty);
    resolved = await edge.resolve(
      context,
      ResolveQuery(result.candidates.first.id),
    );
  }

  expect(resolved.streamUri.toString(), expectedStreamUri);
}
