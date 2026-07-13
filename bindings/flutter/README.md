# SLM Edge Intelligence Flutter Binding

This package is the importable Flutter/Dart SDK surface for Edge Intelligence.
Apps such as Airo should depend on this package, not on Rust crates, SQLite,
M3U files, packs, or model runtimes directly.

Public surface:

```dart
final edge = EdgeIntelligence.ruleBased();

await edge.installPack(context, command);
await edge.parseIntent(context, query);
await edge.search(context, query);
await edge.recommend(context, query);
await edge.play(context, command);
await edge.resume(context, query);
await edge.resolve(context, query);
```

Use `EdgeIntelligence.ruleBased()` for the first Airo TV integration when the
app only needs the public Dart SDK contract. Use `EdgeIntelligence.native()`
when the Rust `edge-ffi` artifact is bundled and the app should install/query a
compiled `.pack`.

## Consume From Airo

Use this repo as a Git dependency until the package is published:

```yaml
dependencies:
  slm_edge_intelligence:
    git:
      url: https://github.com/DevelopersCoffee/barista-tuning.git
      path: bindings/flutter
      ref: slm_edge_intelligence-v0.2.1
```

For local development:

```yaml
dependencies:
  slm_edge_intelligence:
    path: ../slm/bindings/flutter
```

## Airo Query Flow

The Flutter app should route natural language through the SDK and pass only the
resolved stream URI to the player:

```dart
final intent = await edge.parseIntent(context, ParseIntentQuery(utterance));

final media = switch (intent.intent) {
  'resume' => await edge.resume(context, const ResumeQuery()),
  'play' => await edge.play(context, PlayCommand(query: utterance)),
  'search' || 'browse' => await edge.search(
      context,
      SearchQuery(text: utterance, constraints: intent.constraints),
    ).then((result) => edge.resolve(context, ResolveQuery(result.candidates.first.id))),
  _ => await edge.recommend(
      context,
      RecommendationQuery(constraints: intent.constraints),
    ).then((result) => edge.resolve(context, ResolveQuery(result.candidates.first.id))),
};

airoPlayer.play(media!.streamUri);
```

For the native path, install a pack before the first query:

```dart
await edge.installPack(context, InstallPackCommand(packPath: mediaPackPath));
```

Airo's feature package can switch backends without changing UI code:

```bash
flutter run \
  --dart-define=AIRO_EDGE_INTELLIGENCE_BACKEND=native \
  --dart-define=AIRO_MEDIA_PACK=/absolute/path/to/media.pack
```

For Android TV/release builds, Airo can bundle the pack as a Flutter asset and
copy it to app support storage before calling `installPack()`:

```bash
flutter run \
  --dart-define=AIRO_EDGE_INTELLIGENCE_BACKEND=native \
  --dart-define=AIRO_MEDIA_PACK_ASSET=assets/packs/media.pack
```

Omit those defines, or set `AIRO_EDGE_INTELLIGENCE_BACKEND=rule`, to use the
public Dart rule backend.

For SLM intent parsing, the Rust runtime can be configured without Flutter UI
changes:

```bash
EDGE_INTELLIGENCE_INTENT_BACKEND=llama.cpp \
EDGE_INTELLIGENCE_LLAMA_CPP_BIN=/absolute/path/to/llama-cli \
EDGE_INTELLIGENCE_INTENT_MODEL=/absolute/path/to/base-model.gguf \
EDGE_INTELLIGENCE_INTENT_LORA=/absolute/path/to/airo-media-actions-lora.gguf
```

`EDGE_INTELLIGENCE_INTENT_LORA` is optional.

The native artifact produced by the Rust `edge-ffi` crate must be bundled with
the app for `EdgeIntelligence.native()` calls. The Flutter app does not need to
know about M3U parsing, SQLite, ranking indexes, Rust internals, or future SLM
backend selection.

For Android Airo builds, package `libedge_ffi.so` into the host app's
`android/app/src/main/jniLibs/<abi>/` directory. With `cargo-ndk` installed:

```bash
slm package-edge-ffi-android \
  --airo-app /absolute/path/to/airo/app \
  --build \
  --abi arm64-v8a
```

For CI or release jobs that build the Rust artifacts separately:

```bash
slm package-edge-ffi-android \
  --airo-app /absolute/path/to/airo/app \
  --artifact arm64-v8a=/artifacts/arm64-v8a/libedge_ffi.so
```

## Native FFI Verification

From the repository root, run the SDK-to-Rust-to-pack integration test:

```bash
make flutter-native-ffi-test
```

This builds `edge-ffi`, loads it from Dart FFI, installs the sample IPTV pack,
and resolves the Airo definition-of-done queries to stream URIs through the
same `NativeEdgeIntelligence` client Airo will use.
