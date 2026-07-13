# Changelog

## 0.2.1

- Add optional `llama.cpp` LoRA adapter configuration for local SLM intent
  parsing via `EDGE_INTELLIGENCE_INTENT_LORA`.

## 0.2.0

- Add native Rust FFI runtime dispatch for pack install, intent parsing, search,
  recommendation, resolve, play, and resume.
- Add pack-backed SQLite media repository support for compiled IPTV `.pack`
  archives.
- Add native FFI integration tests against compiled Airo IPTV pack fixtures.
- Add Android `libedge_ffi.so` packaging helpers for Airo app builds.

## 0.1.0

- Add public Edge Intelligence Flutter SDK contracts.
- Add offline rule-based media intent backend for Airo TV v0 integration.
- Add mock backend and native FFI client skeleton.
- Add SDK tests for search, play, recommendation, resume, favorites, live browse,
  parental control, education, devotional, language, quality, and clarification
  scenarios.
