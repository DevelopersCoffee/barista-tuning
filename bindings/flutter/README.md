# SLM Edge Intelligence Flutter Binding

This package is the importable Flutter/Dart SDK surface for Edge Intelligence.
Apps such as Airo should depend on this package, not on Rust crates, SQLite,
M3U files, packs, or model runtimes directly.

Initial public surface:

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

Use `EdgeIntelligence.ruleBased()` for the first Airo TV integration. It runs
fully offline and returns the same intent/result contracts that the future
native Rust and SLM backends will use.

## Consume From Airo

Use this repo as a Git dependency until the package is published:

```yaml
dependencies:
  slm_edge_intelligence:
    git:
      url: https://github.com/DevelopersCoffee/barista-tuning.git
      path: bindings/flutter
      ref: slm_edge_intelligence-v0.1.0
```

For local development:

```yaml
dependencies:
  slm_edge_intelligence:
    path: ../slm/bindings/flutter
```

The native artifact produced by the Rust `edge-ffi` crate must be bundled with
the app for runtime calls. Until the native use cases are wired, the Dart package
provides a rule-based backend, the stable public API, and the FFI version
handshake.
