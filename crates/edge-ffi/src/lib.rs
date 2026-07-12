//! C ABI boundary consumed by Flutter/Dart FFI bindings.
//!
//! The FFI surface stays smaller than the Rust domain APIs. Flutter consumes
//! use cases through the Dart package and does not call engines or repositories.

use std::ffi::{CStr, CString};
use std::os::raw::c_char;

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

#[no_mangle]
pub unsafe extern "C" fn edge_intelligence_execute_json(request: *const c_char) -> *mut c_char {
    if request.is_null() {
        return json_response(false, "request pointer is null", "{}");
    }

    let request = match CStr::from_ptr(request).to_str() {
        Ok(value) => value,
        Err(_) => return json_response(false, "request is not valid UTF-8", "{}"),
    };

    let data = if request.contains("\"useCase\":\"installPack\"") {
        r#"{"packId":"mock.media.pack","version":"0.1.0","activated":true}"#
    } else if request.contains("\"useCase\":\"parseIntent\"") {
        r#"{"intent":"recommend","confidence":0.86,"constraints":{"genre":"news"},"missingFields":[],"clarificationRequired":false}"#
    } else if request.contains("\"useCase\":\"search\"") {
        r#"{"candidates":[{"id":"native_mock_aaj_tak","title":"Aaj Tak","provider":"native_mock","type":"live_channel","score":0.97,"metadata":{"genre":"news","language":"hi"}}],"traceId":"native-trace"}"#
    } else if request.contains("\"useCase\":\"recommend\"") {
        r#"{"candidates":[{"id":"native_mock_sony_max","title":"Sony Max","provider":"native_mock","type":"live_channel","score":0.91,"metadata":{"genre":"movies","language":"hi"}}],"traceId":"native-trace"}"#
    } else if request.contains("\"useCase\":\"resume\"") {
        r#"{"item":{"id":"native_mock_resume","title":"Resume Movie","streamUri":"https://example.invalid/resume.m3u8","headers":{},"subtitles":[],"thumbnail":null,"metadata":{}}}"#
    } else if request.contains("\"useCase\":\"play\"") || request.contains("\"useCase\":\"resolve\"") {
        r#"{"id":"native_mock_aaj_tak","title":"Aaj Tak","streamUri":"https://example.invalid/native_mock_aaj_tak.m3u8","headers":{},"subtitles":[],"thumbnail":null,"metadata":{"genre":"news","language":"hi"}}"#
    } else {
        return json_response(false, "unknown use case", "{}");
    };

    json_response(true, "", data)
}

#[no_mangle]
pub unsafe extern "C" fn edge_intelligence_string_free(value: *mut c_char) {
    if !value.is_null() {
        drop(CString::from_raw(value));
    }
}

fn json_response(ok: bool, error: &str, data: &str) -> *mut c_char {
    let response = if ok {
        format!(r#"{{"ok":true,"data":{data}}}"#)
    } else {
        format!(r#"{{"ok":false,"error":"{}","data":{data}}}"#, escape_json(error))
    };

    CString::new(response)
        .expect("JSON response must not contain NUL bytes")
        .into_raw()
}

fn escape_json(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}
