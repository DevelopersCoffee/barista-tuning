use std::path::PathBuf;
use std::sync::{Mutex, OnceLock};

use serde_json::{json, Value};
use tempfile::TempDir;

#[test]
fn compiled_iptv_pack_supports_airo_definition_of_done_queries() {
    let _guard = env_lock().lock().unwrap();
    std::env::remove_var("EDGE_INTELLIGENCE_INTENT_BACKEND");
    let temp = TempDir::new().unwrap();
    std::env::set_var("EDGE_INTELLIGENCE_PACK_CACHE", temp.path().join("cache"));

    let pack_path = fixture_pack_path();
    let install = call(json!({
        "useCase": "installPack",
        "payload": {"packPath": pack_path, "activate": true}
    }));
    assert_eq!(install["ok"], true);
    assert_eq!(install["data"]["packId"], "media.iptv.airo-sample");

    let hindi_news = resolve_query("Show Hindi news");
    assert_eq!(
        hindi_news["streamUri"],
        "https://example.test/aajtak/master.m3u8"
    );

    let aaj_tak = call(json!({
        "useCase": "play",
        "payload": {"query": "Play Aaj Tak"}
    }));
    assert_eq!(aaj_tak["ok"], true);
    assert_eq!(
        aaj_tak["data"]["streamUri"],
        "https://example.test/aajtak/master.m3u8"
    );

    let marathi_movies = resolve_query("Marathi movies");
    assert_eq!(
        marathi_movies["streamUri"],
        "https://example.test/marathi/movies.m3u8"
    );

    let sports_hd = resolve_query("Sports in HD only");
    assert_eq!(
        sports_hd["streamUri"],
        "https://example.test/sports/hd.m3u8"
    );

    let resume = resolve_query("Continue yesterday's movie");
    assert_eq!(
        resume["streamUri"],
        "https://example.test/marathi/movies.m3u8"
    );

    std::env::remove_var("EDGE_INTELLIGENCE_PACK_CACHE");
}

fn resolve_query(utterance: &str) -> Value {
    let intent = call(json!({
        "useCase": "parseIntent",
        "payload": {"utterance": utterance}
    }));
    assert_eq!(intent["ok"], true, "{intent}");

    match intent["data"]["intent"].as_str().unwrap() {
        "play" => {
            let play = call(json!({
                "useCase": "play",
                "payload": {"query": utterance}
            }));
            assert_eq!(play["ok"], true, "{play}");
            play["data"].clone()
        }
        "search" | "browse" => {
            let search = call(json!({
                "useCase": "search",
                "payload": {
                    "text": utterance,
                    "constraints": intent["data"]["constraints"].clone(),
                    "limit": 5
                }
            }));
            assert_eq!(search["ok"], true, "{search}");
            let item_id = search["data"]["candidates"][0]["id"].as_str().unwrap();
            let resolve = call(json!({
                "useCase": "resolve",
                "payload": {"itemId": item_id}
            }));
            assert_eq!(resolve["ok"], true, "{resolve}");
            resolve["data"].clone()
        }
        "resume" => {
            let resume = call(json!({
                "useCase": "resume",
                "payload": {}
            }));
            assert_eq!(resume["ok"], true, "{resume}");
            resume["data"]["item"].clone()
        }
        _ => {
            let recommend = call(json!({
                "useCase": "recommend",
                "payload": {
                    "constraints": intent["data"]["constraints"].clone(),
                    "limit": 5
                }
            }));
            assert_eq!(recommend["ok"], true, "{recommend}");
            let item_id = recommend["data"]["candidates"][0]["id"].as_str().unwrap();
            let resolve = call(json!({
                "useCase": "resolve",
                "payload": {"itemId": item_id}
            }));
            assert_eq!(resolve["ok"], true, "{resolve}");
            resolve["data"].clone()
        }
    }
}

fn call(request: Value) -> Value {
    serde_json::from_str(&edge_ffi::execute_json_request(&request.to_string())).unwrap()
}

fn fixture_pack_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/fixtures/airo_iptv/media.iptv.airo-sample-0.1.0.pack")
}

fn env_lock() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}
