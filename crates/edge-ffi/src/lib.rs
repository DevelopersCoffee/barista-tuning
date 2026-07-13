//! C ABI boundary consumed by Flutter/Dart FFI bindings.
//!
//! The FFI surface stays smaller than the Rust domain APIs. Flutter consumes
//! use cases through the Dart package and does not call engines or repositories.

use std::collections::BTreeMap;
use std::ffi::{CStr, CString};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::os::raw::c_char;
use std::sync::{Mutex, OnceLock};

use edge_intent::{ConfiguredIntentBackend, IntentBackendConfig, IntentBackendKind, IntentRequest};
use edge_media::{PackMediaService, PlayRequest};
use edge_pack::LocalPackManager;
use edge_search::SearchQuery;
use serde::Deserialize;
use serde_json::{json, Map, Value};

pub const EDGE_INTELLIGENCE_ABI_VERSION: u32 = 1;

#[no_mangle]
pub extern "C" fn edge_intelligence_abi_version() -> u32 {
    EDGE_INTELLIGENCE_ABI_VERSION
}

#[no_mangle]
pub extern "C" fn edge_intelligence_sdk_version_major() -> u16 {
    0
}

#[no_mangle]
pub extern "C" fn edge_intelligence_sdk_version_minor() -> u16 {
    1
}

#[no_mangle]
pub extern "C" fn edge_intelligence_sdk_version_patch() -> u16 {
    0
}

/// Executes one SDK use case encoded as JSON and returns an allocated JSON response.
///
/// # Safety
///
/// `request` must be either null or a valid, NUL-terminated C string that remains
/// alive for the duration of the call. The returned pointer must be released by
/// calling [`edge_intelligence_string_free`] exactly once.
#[no_mangle]
pub unsafe extern "C" fn edge_intelligence_execute_json(request: *const c_char) -> *mut c_char {
    if request.is_null() {
        return string_to_c(json_response(
            false,
            Some("request pointer is null"),
            json!({}),
        ));
    }

    let request = match CStr::from_ptr(request).to_str() {
        Ok(value) => value,
        Err(_) => {
            return string_to_c(json_response(
                false,
                Some("request is not valid UTF-8"),
                json!({}),
            ));
        }
    };

    string_to_c(execute_json_request(request))
}

/// Frees a string returned by the Edge Intelligence FFI boundary.
///
/// # Safety
///
/// `value` must be null or a pointer previously returned by this library via
/// `CString::into_raw`. Passing any other pointer, or freeing the same pointer
/// more than once, is undefined behavior.
#[no_mangle]
pub unsafe extern "C" fn edge_intelligence_string_free(value: *mut c_char) {
    if !value.is_null() {
        drop(CString::from_raw(value));
    }
}

pub fn execute_json_request(request: &str) -> String {
    match execute_json_request_inner(request) {
        Ok(data) => json_response(true, None, data),
        Err(error) => json_response(false, Some(&error), json!({})),
    }
}

fn execute_json_request_inner(request: &str) -> Result<Value, String> {
    let request = serde_json::from_str::<FfiRequest>(request)
        .map_err(|error| format!("invalid JSON request: {error}"))?;
    match request.use_case.as_str() {
        "installPack" => install_pack(request.payload),
        "parseIntent" => parse_intent(request.payload),
        "search" => search(request.payload),
        "recommend" => recommend(request.payload),
        "resolve" => resolve(request.payload),
        "play" => play(request.payload),
        "resume" => resume(),
        other => Err(format!("unknown use case: {other}")),
    }
}

fn install_pack(payload: Value) -> Result<Value, String> {
    let payload = serde_json::from_value::<InstallPackPayload>(payload)
        .map_err(|error| format!("invalid installPack payload: {error}"))?;
    let manager = LocalPackManager::default();
    let installed = manager
        .install_pack_sync(&payload.pack_path, payload.activate)
        .map_err(|error| error.to_string())?;
    if installed.manifest.domain == "media" {
        set_media_service(PackMediaService::new(installed.media_db.clone()))?;
    }
    Ok(json!({
        "packId": installed.manifest.id,
        "version": installed.manifest.version.to_string(),
        "activated": payload.activate,
    }))
}

fn parse_intent(payload: Value) -> Result<Value, String> {
    let payload = serde_json::from_value::<ParseIntentPayload>(payload)
        .map_err(|error| format!("invalid parseIntent payload: {error}"))?;
    let result = intent_backend()?
        .parse_sync(IntentRequest {
            utterance: payload.utterance.clone(),
        })
        .map_err(|error| error.to_string())?;
    if result.confidence < 0.5 || result.clarification_required {
        log_failed_query(&payload.utterance, &result);
    }
    Ok(json!({
        "intent": result.intent,
        "tool": result.tool,
        "confidence": result.confidence,
        "constraints": constraints_json(result.constraints),
        "missingFields": result.missing_fields,
        "clarificationRequired": result.clarification_required,
    }))
}

fn intent_backend() -> Result<ConfiguredIntentBackend, String> {
    let backend =
        std::env::var("EDGE_INTELLIGENCE_INTENT_BACKEND").unwrap_or_else(|_| "rule".to_string());
    let kind = IntentBackendKind::parse(&backend).map_err(|error| error.to_string())?;
    Ok(ConfiguredIntentBackend::from_config(IntentBackendConfig {
        kind,
        model_path: std::env::var("EDGE_INTELLIGENCE_INTENT_MODEL").ok(),
        executable_path: std::env::var("EDGE_INTELLIGENCE_LLAMA_CPP_BIN").ok(),
    }))
}

fn search(payload: Value) -> Result<Value, String> {
    let payload = serde_json::from_value::<SearchPayload>(payload)
        .map_err(|error| format!("invalid search payload: {error}"))?;
    let service = media_service()?;
    let query = SearchQuery {
        text: payload.text,
        constraints: object_constraints(payload.constraints),
    };
    let candidates = service
        .search_assets_sync(&query, payload.limit.unwrap_or(20))
        .map_err(|error| error.to_string())?
        .into_iter()
        .map(candidate_json)
        .collect::<Vec<_>>();
    Ok(json!({"candidates": candidates, "traceId": "rust-pack"}))
}

fn recommend(payload: Value) -> Result<Value, String> {
    let payload = serde_json::from_value::<RecommendPayload>(payload)
        .map_err(|error| format!("invalid recommend payload: {error}"))?;
    let service = media_service()?;
    let candidates = service
        .recommend_assets_sync(
            &object_constraints(payload.constraints),
            payload.limit.unwrap_or(20),
        )
        .map_err(|error| error.to_string())?
        .into_iter()
        .map(candidate_json)
        .collect::<Vec<_>>();
    Ok(json!({"candidates": candidates, "traceId": "rust-pack"}))
}

fn resolve(payload: Value) -> Result<Value, String> {
    let payload = serde_json::from_value::<ResolvePayload>(payload)
        .map_err(|error| format!("invalid resolve payload: {error}"))?;
    let service = media_service()?;
    let item = service
        .resolve_sync(&payload.item_id)
        .map_err(|error| error.to_string())?;
    Ok(resolved_json(item))
}

fn play(payload: Value) -> Result<Value, String> {
    let payload = serde_json::from_value::<PlayPayload>(payload)
        .map_err(|error| format!("invalid play payload: {error}"))?;
    let service = media_service()?;
    let item = service
        .play_sync(&PlayRequest {
            query: payload.query,
            item_id: payload.item_id,
        })
        .map_err(|error| error.to_string())?;
    Ok(resolved_json(item))
}

fn resume() -> Result<Value, String> {
    let service = media_service()?;
    let item = service.resume_sync().map_err(|error| error.to_string())?;
    Ok(json!({
        "item": item.map(resolved_json),
    }))
}

fn media_service() -> Result<PackMediaService, String> {
    let state = state();
    if let Some(service) = state
        .lock()
        .map_err(|_| "runtime state lock poisoned".to_string())?
        .media_service
        .clone()
    {
        return Ok(service);
    }

    let db_path = LocalPackManager::default()
        .active_media_db()
        .map_err(|error| error.to_string())?
        .ok_or_else(|| "no active media pack is installed".to_string())?;
    let service = PackMediaService::new(db_path);
    set_media_service(service.clone())?;
    Ok(service)
}

fn set_media_service(service: PackMediaService) -> Result<(), String> {
    state()
        .lock()
        .map_err(|_| "runtime state lock poisoned".to_string())?
        .media_service = Some(service);
    Ok(())
}

fn state() -> &'static Mutex<RuntimeState> {
    static STATE: OnceLock<Mutex<RuntimeState>> = OnceLock::new();
    STATE.get_or_init(|| Mutex::new(RuntimeState::default()))
}

#[derive(Debug, Default)]
struct RuntimeState {
    media_service: Option<PackMediaService>,
}

#[derive(Debug, Deserialize)]
struct FfiRequest {
    #[serde(rename = "useCase")]
    use_case: String,
    #[serde(default)]
    payload: Value,
}

#[derive(Debug, Deserialize)]
struct InstallPackPayload {
    #[serde(rename = "packPath")]
    pack_path: String,
    #[serde(default = "default_true")]
    activate: bool,
}

#[derive(Debug, Deserialize)]
struct ParseIntentPayload {
    utterance: String,
}

#[derive(Debug, Deserialize)]
struct SearchPayload {
    #[serde(default)]
    text: String,
    #[serde(default)]
    constraints: Map<String, Value>,
    limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
struct RecommendPayload {
    #[serde(default)]
    constraints: Map<String, Value>,
    limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
struct ResolvePayload {
    #[serde(rename = "itemId")]
    item_id: String,
}

#[derive(Debug, Deserialize)]
struct PlayPayload {
    query: Option<String>,
    #[serde(rename = "itemId")]
    item_id: Option<String>,
}

fn candidate_json(scored: edge_media::ScoredMediaAsset) -> Value {
    json!({
        "id": scored.asset.id,
        "title": scored.asset.title,
        "provider": scored.asset.provider,
        "type": scored.asset.asset_type,
        "score": scored.score,
        "metadata": scored.asset.metadata,
    })
}

fn resolved_json(item: edge_runtime::ResolvedItem) -> Value {
    let thumbnail = item
        .metadata
        .get("thumbnail")
        .filter(|value| !value.is_empty())
        .cloned();
    json!({
        "id": item.item_id,
        "title": item.title,
        "streamUri": item.uri,
        "headers": item.headers,
        "subtitles": [],
        "thumbnail": thumbnail,
        "metadata": item.metadata,
    })
}

fn object_constraints(values: Map<String, Value>) -> BTreeMap<String, String> {
    values
        .into_iter()
        .filter_map(|(key, value)| value_to_string(value).map(|value| (key, value)))
        .collect()
}

fn constraints_json(values: BTreeMap<String, String>) -> Map<String, Value> {
    values
        .into_iter()
        .map(|(key, value)| {
            let value = match value.as_str() {
                "true" => json!(true),
                "false" => json!(false),
                _ => json!(value),
            };
            (key, value)
        })
        .collect()
}

fn value_to_string(value: Value) -> Option<String> {
    match value {
        Value::String(value) => Some(value),
        Value::Number(value) => Some(value.to_string()),
        Value::Bool(value) => Some(value.to_string()),
        Value::Null => None,
        other => Some(other.to_string()),
    }
}

fn log_failed_query(utterance: &str, result: &edge_intent::IntentResult) {
    let cache_dir = LocalPackManager::default_cache_dir();
    let path = cache_dir.join("logs").join("failed_queries.jsonl");
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) else {
        return;
    };
    let payload = json!({
        "utterance": utterance,
        "intent": &result.intent,
        "confidence": result.confidence,
        "clarificationRequired": result.clarification_required,
    });
    let _ = writeln!(file, "{payload}");
}

fn default_true() -> bool {
    true
}

fn json_response(ok: bool, error: Option<&str>, data: Value) -> String {
    let mut response = Map::new();
    response.insert("ok".to_string(), json!(ok));
    if let Some(error) = error {
        response.insert("error".to_string(), json!(error));
    }
    response.insert("data".to_string(), data);
    Value::Object(response).to_string()
}

fn string_to_c(value: String) -> *mut c_char {
    CString::new(value)
        .expect("JSON response must not contain NUL bytes")
        .into_raw()
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::io::Write;
    use std::path::Path;
    use std::sync::{Mutex, OnceLock};

    use rusqlite::Connection;
    use serde_json::json;
    use tempfile::TempDir;
    use zip::write::SimpleFileOptions;

    use super::execute_json_request;

    #[test]
    fn parse_intent_contract_returns_media_constraints() {
        let _guard = env_lock().lock().unwrap();
        std::env::remove_var("EDGE_INTELLIGENCE_INTENT_BACKEND");
        let response = call(json!({
            "useCase": "parseIntent",
            "payload": {"utterance": "Show Hindi news"}
        }));

        assert_eq!(response["ok"], true);
        assert_eq!(response["data"]["intent"], "search");
        assert_eq!(response["data"]["tool"], "media.search");
        assert_eq!(response["data"]["constraints"]["language"], "hi");
        assert_eq!(response["data"]["constraints"]["genre"], "news");
        assert_eq!(response["data"]["constraints"]["live"], true);
    }

    #[test]
    fn parse_intent_reports_unconfigured_slm_backend_without_flutter_changes() {
        let _guard = env_lock().lock().unwrap();
        std::env::set_var("EDGE_INTELLIGENCE_INTENT_BACKEND", "llama.cpp");
        std::env::set_var("EDGE_INTELLIGENCE_INTENT_MODEL", "models/intent.gguf");
        std::env::remove_var("EDGE_INTELLIGENCE_LLAMA_CPP_BIN");

        let response = call(json!({
            "useCase": "parseIntent",
            "payload": {"utterance": "Show Hindi news"}
        }));

        assert_eq!(response["ok"], false);
        assert!(response["error"]
            .as_str()
            .unwrap()
            .contains("llama.cpp executable path is required"));

        std::env::remove_var("EDGE_INTELLIGENCE_INTENT_BACKEND");
        std::env::remove_var("EDGE_INTELLIGENCE_INTENT_MODEL");
        std::env::remove_var("EDGE_INTELLIGENCE_LLAMA_CPP_BIN");
    }

    #[cfg(unix)]
    #[test]
    fn parse_intent_uses_configured_slm_backend_without_flutter_changes() {
        use std::os::unix::fs::PermissionsExt;

        let _guard = env_lock().lock().unwrap();
        let temp = TempDir::new().unwrap();
        let executable = temp.path().join("llama-cli");
        fs::write(
            &executable,
            "#!/bin/sh\ncat <<'JSON'\n{\"intent\":\"play\",\"tool\":\"media.play\",\"confidence\":0.94,\"constraints\":{\"query\":\"Aaj Tak\",\"live\":true},\"missing_fields\":[],\"clarification_required\":false}\nJSON\n",
        )
        .unwrap();
        let mut permissions = fs::metadata(&executable).unwrap().permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&executable, permissions).unwrap();

        std::env::set_var("EDGE_INTELLIGENCE_INTENT_BACKEND", "llama.cpp");
        std::env::set_var("EDGE_INTELLIGENCE_INTENT_MODEL", "models/intent.gguf");
        std::env::set_var("EDGE_INTELLIGENCE_LLAMA_CPP_BIN", &executable);

        let response = call(json!({
            "useCase": "parseIntent",
            "payload": {"utterance": "Play Aaj Tak"}
        }));

        assert_eq!(response["ok"], true);
        assert_eq!(response["data"]["intent"], "play");
        assert_eq!(response["data"]["tool"], "media.play");
        assert_eq!(response["data"]["constraints"]["query"], "Aaj Tak");
        assert_eq!(response["data"]["constraints"]["live"], true);

        std::env::remove_var("EDGE_INTELLIGENCE_INTENT_BACKEND");
        std::env::remove_var("EDGE_INTELLIGENCE_INTENT_MODEL");
        std::env::remove_var("EDGE_INTELLIGENCE_LLAMA_CPP_BIN");
    }

    #[test]
    fn install_search_and_play_pack_contract() {
        let temp = TempDir::new().unwrap();
        std::env::set_var("EDGE_INTELLIGENCE_PACK_CACHE", temp.path().join("cache"));
        let pack_path = temp.path().join("media.pack");
        write_test_pack(&pack_path);

        let install = call(json!({
            "useCase": "installPack",
            "payload": {"packPath": pack_path, "activate": true}
        }));
        assert_eq!(install["ok"], true);
        assert_eq!(install["data"]["packId"], "media.iptv.test");
        assert_eq!(install["data"]["activated"], true);

        let search = call(json!({
            "useCase": "search",
            "payload": {
                "text": "Show Hindi news",
                "constraints": {"genre": "news", "language": "hi"},
                "limit": 5
            }
        }));
        assert_eq!(search["ok"], true);
        assert_eq!(search["data"]["candidates"][0]["id"], "iptv_aajtak_in");

        let play = call(json!({
            "useCase": "play",
            "payload": {"query": "Play Aaj Tak"}
        }));
        assert_eq!(play["ok"], true);
        assert_eq!(
            play["data"]["streamUri"],
            "https://example.test/aajtak.m3u8"
        );

        let resume = call(json!({
            "useCase": "resume",
            "payload": {}
        }));
        assert_eq!(resume["ok"], true);
        assert_eq!(
            resume["data"]["item"]["streamUri"],
            "https://example.test/sony-max.m3u8"
        );
    }

    fn call(request: serde_json::Value) -> serde_json::Value {
        serde_json::from_str(&execute_json_request(&request.to_string())).unwrap()
    }

    fn env_lock() -> &'static Mutex<()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
    }

    fn write_test_pack(pack_path: &Path) {
        let root = pack_path.parent().unwrap().join("pack-root");
        fs::create_dir_all(root.join("indexes")).unwrap();
        fs::create_dir_all(root.join("metadata")).unwrap();
        write_media_db(&root.join("media.db"));
        fs::write(root.join("indexes/search.idx"), "{}").unwrap();
        fs::write(root.join("indexes/recommendation.idx"), "{}").unwrap();
        fs::write(
            root.join("metadata/compile-report.json"),
            "{\"asset_count\":1}",
        )
        .unwrap();
        fs::write(
            root.join("signature.json"),
            "{\"signature\":null,\"algorithm\":null}",
        )
        .unwrap();

        let checksum = checksum_root(&root);
        fs::write(
            root.join("manifest.json"),
            json!({
                "pack": {
                    "id": "media.iptv.test",
                    "name": "Test IPTV",
                    "version": "0.1.0",
                    "domain": "media",
                    "provider": "iptv"
                },
                "compiler": {"name": "edge-pack-compiler", "version": "0.1.0"},
                "runtime": {"minimum_sdk": "0.1.0"},
                "schema": {
                    "pack_schema": "1.0.0",
                    "domain_ir": "1.0.0",
                    "migration": 1
                },
                "capabilities": ["search", "recommendation", "playback"],
                "permissions": ["network_streaming"],
                "dependencies": [],
                "checksum": checksum,
                "signature": null,
                "metadata": {"asset_count": 1}
            })
            .to_string(),
        )
        .unwrap();

        let file = fs::File::create(pack_path).unwrap();
        let mut archive = zip::ZipWriter::new(file);
        let options = SimpleFileOptions::default();
        for relative in [
            "indexes/recommendation.idx",
            "indexes/search.idx",
            "media.db",
            "metadata/compile-report.json",
            "signature.json",
            "manifest.json",
        ] {
            archive.start_file(relative, options).unwrap();
            archive
                .write_all(&fs::read(root.join(relative)).unwrap())
                .unwrap();
        }
        archive.finish().unwrap();
    }

    fn write_media_db(path: &Path) {
        let connection = Connection::open(path).unwrap();
        connection
            .execute_batch(
                "
                create table media_assets (
                    id text primary key,
                    title text not null,
                    provider text not null,
                    type text not null,
                    stream_uri text,
                    json text not null
                );
                create table media_terms (
                    term text not null,
                    asset_id text not null,
                    weight real not null,
                    primary key (term, asset_id)
                );
                ",
            )
            .unwrap();
        let asset = json!({
            "id": "iptv_aajtak_in",
            "title": "Aaj Tak",
            "provider": "iptv",
            "type": "live_channel",
            "language": ["hi"],
            "genres": ["news"],
            "keywords": ["aaj tak", "news", "hindi"],
            "quality": {"hd": true},
            "stream_uri": "https://example.test/aajtak.m3u8",
            "thumbnail": null
        });
        connection
            .execute(
                "insert into media_assets (id, title, provider, type, stream_uri, json)
                 values (?1, ?2, ?3, ?4, ?5, ?6)",
                (
                    "iptv_aajtak_in",
                    "Aaj Tak",
                    "iptv",
                    "live_channel",
                    "https://example.test/aajtak.m3u8",
                    asset.to_string(),
                ),
            )
            .unwrap();
        let movie = json!({
            "id": "iptv_sony_max",
            "title": "Sony Max",
            "provider": "iptv",
            "type": "live_channel",
            "language": ["hi"],
            "genres": ["movies"],
            "keywords": ["sony max", "movies", "hindi"],
            "stream_uri": "https://example.test/sony-max.m3u8",
            "thumbnail": null
        });
        connection
            .execute(
                "insert into media_assets (id, title, provider, type, stream_uri, json)
                 values (?1, ?2, ?3, ?4, ?5, ?6)",
                (
                    "iptv_sony_max",
                    "Sony Max",
                    "iptv",
                    "live_channel",
                    "https://example.test/sony-max.m3u8",
                    movie.to_string(),
                ),
            )
            .unwrap();
    }

    fn checksum_root(root: &Path) -> String {
        let mut digest = <sha2::Sha256 as sha2::Digest>::new();
        let mut files = [
            "indexes/recommendation.idx",
            "indexes/search.idx",
            "media.db",
            "metadata/compile-report.json",
            "signature.json",
        ];
        files.sort();
        for relative in files {
            sha2::Digest::update(&mut digest, relative.as_bytes());
            sha2::Digest::update(&mut digest, fs::read(root.join(relative)).unwrap());
        }
        let digest = sha2::Digest::finalize(digest);
        digest.iter().map(|byte| format!("{byte:02x}")).collect()
    }
}
