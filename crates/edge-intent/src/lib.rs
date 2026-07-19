//! Intent backend contract. Implementations may be rules, llama.cpp, ONNX, remote, or hybrid.

pub mod command;

use std::collections::BTreeMap;
use std::future::Future;
use std::pin::Pin;
use std::process::Command;

use edge_kernel::{Context, EdgeError, EdgeResult};
use serde_json::Value;

pub type IntentFuture<'a, T> = Pin<Box<dyn Future<Output = EdgeResult<T>> + Send + 'a>>;

#[derive(Debug, Clone, PartialEq)]
pub struct IntentRequest {
    pub utterance: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct IntentResult {
    pub intent: String,
    pub tool: Option<String>,
    pub confidence: f32,
    pub constraints: BTreeMap<String, String>,
    pub missing_fields: Vec<String>,
    pub clarification_required: bool,
}

pub trait IntentBackend: Send + Sync {
    fn parse<'a>(
        &'a self,
        context: &'a Context,
        request: IntentRequest,
    ) -> IntentFuture<'a, IntentResult>;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IntentBackendKind {
    Rule,
    LlamaCpp,
    LlamaCppWithRuleFallback,
}

impl IntentBackendKind {
    pub fn parse(value: &str) -> EdgeResult<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "" | "rule" | "rules" => Ok(Self::Rule),
            "llama" | "llama.cpp" | "llamacpp" | "slm" => Ok(Self::LlamaCpp),
            "hybrid" | "llama+rule" | "llama.cpp+rule" | "llamacpp+rule" | "slm+rule" => {
                Ok(Self::LlamaCppWithRuleFallback)
            }
            other => Err(EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::Unsupported,
                format!("unsupported intent backend: {other}"),
            )),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IntentBackendConfig {
    pub kind: IntentBackendKind,
    pub model_path: Option<String>,
    pub executable_path: Option<String>,
    pub lora_path: Option<String>,
}

impl Default for IntentBackendConfig {
    fn default() -> Self {
        Self {
            kind: IntentBackendKind::Rule,
            model_path: None,
            executable_path: None,
            lora_path: None,
        }
    }
}

#[derive(Debug, Clone)]
pub enum ConfiguredIntentBackend {
    Rule(RuleIntentBackend),
    LlamaCpp(LlamaCppIntentBackend),
    LlamaCppWithRuleFallback {
        primary: LlamaCppIntentBackend,
        fallback: RuleIntentBackend,
    },
}

impl ConfiguredIntentBackend {
    pub fn from_config(config: IntentBackendConfig) -> Self {
        match config.kind {
            IntentBackendKind::Rule => Self::Rule(RuleIntentBackend),
            IntentBackendKind::LlamaCpp => Self::LlamaCpp(llama_backend_from_config(config)),
            IntentBackendKind::LlamaCppWithRuleFallback => Self::LlamaCppWithRuleFallback {
                primary: llama_backend_from_config(config),
                fallback: RuleIntentBackend,
            },
        }
    }

    pub fn parse_sync(&self, request: IntentRequest) -> EdgeResult<IntentResult> {
        match self {
            Self::Rule(backend) => Ok(backend.parse_sync(request)),
            Self::LlamaCpp(backend) => backend.parse_sync(request),
            Self::LlamaCppWithRuleFallback { primary, fallback } => {
                match primary.parse_sync(request.clone()) {
                    Ok(result) if result.confidence >= 0.5 => Ok(result),
                    Ok(_) | Err(_) => Ok(fallback.parse_sync(request)),
                }
            }
        }
    }
}

impl IntentBackend for ConfiguredIntentBackend {
    fn parse<'a>(
        &'a self,
        _context: &'a Context,
        request: IntentRequest,
    ) -> IntentFuture<'a, IntentResult> {
        Box::pin(async move { self.parse_sync(request) })
    }
}

#[derive(Debug, Clone, Default)]
pub struct RuleIntentBackend;

impl RuleIntentBackend {
    pub fn parse_sync(&self, request: IntentRequest) -> IntentResult {
        parse_rule_intent(&request.utterance)
    }
}

impl IntentBackend for RuleIntentBackend {
    fn parse<'a>(
        &'a self,
        _context: &'a Context,
        request: IntentRequest,
    ) -> IntentFuture<'a, IntentResult> {
        Box::pin(async move { Ok(self.parse_sync(request)) })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LlamaCppIntentBackend {
    pub model_path: Option<String>,
    pub executable_path: Option<String>,
    pub lora_path: Option<String>,
}

fn llama_backend_from_config(config: IntentBackendConfig) -> LlamaCppIntentBackend {
    LlamaCppIntentBackend {
        model_path: config.model_path,
        executable_path: config.executable_path,
        lora_path: config.lora_path,
    }
}

impl LlamaCppIntentBackend {
    pub fn parse_sync(&self, request: IntentRequest) -> EdgeResult<IntentResult> {
        let executable = required_config(
            self.executable_path.as_deref(),
            "llama.cpp executable path is required",
        )?;
        let model = required_config(
            self.model_path.as_deref(),
            "llama.cpp model path is required",
        )?;
        let prompt = llama_prompt(&request.utterance);
        let mut command = Command::new(executable);
        command.args([
            "-m",
            model,
            "-p",
            &prompt,
            "-n",
            "256",
            "--temp",
            "0",
            "--no-display-prompt",
        ]);
        if let Some(lora_path) = self.lora_path.as_deref().map(str::trim) {
            if !lora_path.is_empty() {
                command.args(["--lora", lora_path]);
            }
        }
        let output = command.output().map_err(|error| {
            EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::Internal,
                format!("failed to launch llama.cpp intent backend: {error}"),
            )
        })?;

        if !output.status.success() {
            return Err(EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::Internal,
                format!(
                    "llama.cpp intent backend exited with status {}: {}",
                    output.status,
                    String::from_utf8_lossy(&output.stderr).trim()
                ),
            ));
        }

        let stdout = String::from_utf8(output.stdout).map_err(|error| {
            EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::Internal,
                format!("llama.cpp intent output is not UTF-8: {error}"),
            )
        })?;
        parse_llama_intent_json(&stdout)
    }
}

impl IntentBackend for LlamaCppIntentBackend {
    fn parse<'a>(
        &'a self,
        _context: &'a Context,
        request: IntentRequest,
    ) -> IntentFuture<'a, IntentResult> {
        Box::pin(async move { self.parse_sync(request) })
    }
}

fn required_config<'a>(value: Option<&'a str>, message: &str) -> EdgeResult<&'a str> {
    value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::Unsupported,
                format!("{message}; set EDGE_INTELLIGENCE_LLAMA_CPP_BIN and EDGE_INTELLIGENCE_INTENT_MODEL"),
            )
        })
}

fn llama_prompt(utterance: &str) -> String {
    format!(
        concat!(
            "### Instruction\n",
            "Translate the Airo TV user request into a media action JSON object. Output JSON only. Do not answer conversationally.\n\n",
            "### Input\n",
            "{}\n\n",
            "### Response\n"
        ),
        utterance
    )
}

fn parse_llama_intent_json(output: &str) -> EdgeResult<IntentResult> {
    let json_text = extract_first_json_object(output).ok_or_else(|| {
        EdgeError::new(
            edge_kernel::errors::EdgeErrorKind::Internal,
            "llama.cpp intent backend did not return a JSON object",
        )
    })?;
    let value = serde_json::from_str::<Value>(json_text).map_err(|error| {
        EdgeError::new(
            edge_kernel::errors::EdgeErrorKind::Internal,
            format!("llama.cpp intent JSON is invalid: {error}"),
        )
    })?;
    intent_result_from_json(value)
}

fn extract_first_json_object(value: &str) -> Option<&str> {
    let mut start = None;
    let mut depth = 0usize;
    let mut in_string = false;
    let mut escaped = false;

    for (index, ch) in value.char_indices() {
        if start.is_none() {
            if ch == '{' {
                start = Some(index);
                depth = 1;
            }
            continue;
        }

        if escaped {
            escaped = false;
            continue;
        }
        if ch == '\\' && in_string {
            escaped = true;
            continue;
        }
        if ch == '"' {
            in_string = !in_string;
            continue;
        }
        if in_string {
            continue;
        }
        if ch == '{' {
            depth += 1;
        } else if ch == '}' {
            depth -= 1;
            if depth == 0 {
                return value.get(start.unwrap()..=index);
            }
        }
    }

    None
}

fn intent_result_from_json(value: Value) -> EdgeResult<IntentResult> {
    let object = value.as_object().ok_or_else(|| {
        EdgeError::new(
            edge_kernel::errors::EdgeErrorKind::Internal,
            "llama.cpp intent JSON root must be an object",
        )
    })?;
    let intent_name = required_json_string(object.get("intent"), "intent")?;
    let tool = required_json_string(object.get("tool"), "tool")?;
    let confidence = object
        .get("confidence")
        .and_then(Value::as_f64)
        .ok_or_else(|| {
            EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::Internal,
                "llama.cpp intent JSON missing numeric confidence",
            )
        })? as f32;
    let constraints = object
        .get("constraints")
        .and_then(Value::as_object)
        .map(|values| {
            values
                .iter()
                .map(|(key, value)| (key.clone(), constraint_value_to_string(value)))
                .collect::<BTreeMap<_, _>>()
        })
        .unwrap_or_default();
    let missing_fields = object
        .get("missing_fields")
        .or_else(|| object.get("missingFields"))
        .and_then(Value::as_array)
        .map(|values| {
            values
                .iter()
                .filter_map(Value::as_str)
                .map(ToString::to_string)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let clarification_required = object
        .get("clarification_required")
        .or_else(|| object.get("clarificationRequired"))
        .and_then(Value::as_bool)
        .unwrap_or(false);

    Ok(IntentResult {
        intent: intent_name.to_string(),
        tool: Some(tool.to_string()),
        confidence,
        constraints,
        missing_fields,
        clarification_required,
    })
}

fn required_json_string<'a>(value: Option<&'a Value>, field: &str) -> EdgeResult<&'a str> {
    value.and_then(Value::as_str).ok_or_else(|| {
        EdgeError::new(
            edge_kernel::errors::EdgeErrorKind::Internal,
            format!("llama.cpp intent JSON missing string {field}"),
        )
    })
}

fn constraint_value_to_string(value: &Value) -> String {
    match value {
        Value::String(value) => value.clone(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        Value::Null => String::new(),
        Value::Array(_) | Value::Object(_) => value.to_string(),
    }
}

pub fn parse_rule_intent(utterance: &str) -> IntentResult {
    let text = normalize_text(utterance);
    let language = language(&text);
    let quality = quality(&text);

    if matches!(
        text.as_str(),
        "play sony" | "put on news" | "show the match"
    ) {
        return intent(
            "clarify",
            "media.clarify",
            0.62,
            BTreeMap::new(),
            vec!["specific_media".to_string()],
            true,
        );
    }

    if contains_any(
        &text,
        &[
            "add this to favorites",
            "favorite this channel",
            "save this for later",
        ],
    ) {
        return intent(
            "favorite",
            "media.favorite",
            0.87,
            constraints([("target", "current")]),
            Vec::new(),
            false,
        );
    }

    if contains_any(&text, &["continue", "resume", "yesterday"]) {
        return intent(
            "resume",
            "media.resume",
            0.91,
            constraints([("continue_watching", "true")]),
            Vec::new(),
            false,
        );
    }

    if contains_any(
        &text,
        &[
            "what's live",
            "what is live",
            "show live channels",
            "browse live tv",
        ],
    ) {
        return intent(
            "browse",
            "media.browse",
            0.9,
            constraints([("live", "true")]),
            Vec::new(),
            false,
        );
    }

    if let Some(title) = direct_title(&text) {
        return intent(
            "play",
            "media.play",
            0.94,
            constraints([("query", title), ("live", "true")]),
            Vec::new(),
            false,
        );
    }

    if text.contains("cricket") || text.contains("india match") {
        let mut values = constraints([
            ("genre", "sports"),
            ("subgenre", "cricket"),
            ("live", "true"),
        ]);
        insert_optional(&mut values, "quality", quality);
        return intent("play", "media.play", 0.89, values, Vec::new(), false);
    }

    if text.contains("sports") {
        let mut values = constraints([("genre", "sports")]);
        insert_optional(&mut values, "quality", quality);
        return intent("search", "media.search", 0.86, values, Vec::new(), false);
    }

    if text.contains("violent") || text.contains("violence") {
        return intent(
            "recommend",
            "media.recommend",
            0.82,
            constraints([("parental_control", "true"), ("avoid", "violence")]),
            Vec::new(),
            false,
        );
    }

    if contains_any(&text, &["kid", "cartoon", "5 year old"]) {
        return intent(
            "recommend",
            "media.recommend",
            0.88,
            constraints([
                ("audience", "kids"),
                ("genre", "kids"),
                ("age_safe", "true"),
            ]),
            Vec::new(),
            false,
        );
    }

    if contains_any(&text, &["movie", "movies", "film"]) {
        let mut values = constraints([("genre", "movies")]);
        insert_optional(&mut values, "language", language);
        insert_optional(&mut values, "quality", quality);
        if text.contains("latest") || text.contains("recent") {
            values.insert("sort".to_string(), "recent".to_string());
        }
        let is_play = text.contains("play");
        return intent(
            if is_play { "play" } else { "search" },
            if is_play {
                "media.play"
            } else {
                "media.search"
            },
            0.86,
            values,
            Vec::new(),
            false,
        );
    }

    if text.contains("news") {
        let mut values = constraints([
            (
                "genre",
                if text.contains("business") {
                    "business_news"
                } else {
                    "news"
                },
            ),
            ("live", "true"),
        ]);
        insert_optional(&mut values, "language", language);
        insert_optional(&mut values, "quality", quality);
        return intent("search", "media.search", 0.92, values, Vec::new(), false);
    }

    if contains_any(&text, &["devotional", "religious", "bhajan"]) {
        let mut values = constraints([("genre", "religious")]);
        insert_optional(&mut values, "language", language);
        return intent(
            "recommend",
            "media.recommend",
            0.84,
            values,
            Vec::new(),
            false,
        );
    }

    if contains_any(&text, &["educational", "education", "class 8"]) {
        let mut values = constraints([("genre", "education")]);
        if text.contains("class 8") {
            values.insert("grade".to_string(), "8".to_string());
        }
        return intent(
            "recommend",
            "media.recommend",
            0.84,
            values,
            Vec::new(),
            false,
        );
    }

    if text.contains("free") {
        return intent(
            "search",
            "media.search",
            0.76,
            constraints([("subscription", "free")]),
            Vec::new(),
            false,
        );
    }

    if let Some(mood) = mood(&text) {
        return intent(
            "recommend",
            "media.recommend",
            0.84,
            constraints([("mood", mood)]),
            Vec::new(),
            false,
        );
    }

    intent(
        "recommend",
        "media.recommend",
        0.58,
        BTreeMap::new(),
        vec!["query".to_string()],
        true,
    )
}

fn intent(
    intent_name: &str,
    tool: &str,
    confidence: f32,
    constraints: BTreeMap<String, String>,
    missing_fields: Vec<String>,
    clarification_required: bool,
) -> IntentResult {
    IntentResult {
        intent: intent_name.to_string(),
        tool: Some(tool.to_string()),
        confidence,
        constraints,
        missing_fields,
        clarification_required,
    }
}

fn constraints<const N: usize>(values: [(&str, &str); N]) -> BTreeMap<String, String> {
    values
        .into_iter()
        .map(|(key, value)| (key.to_string(), value.to_string()))
        .collect()
}

fn insert_optional(values: &mut BTreeMap<String, String>, key: &str, value: Option<&'static str>) {
    if let Some(value) = value {
        values.insert(key.to_string(), value.to_string());
    }
}

fn normalize_text(value: &str) -> String {
    value
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_ascii_lowercase()
}

fn contains_any(value: &str, needles: &[&str]) -> bool {
    needles.iter().any(|needle| value.contains(needle))
}

fn direct_title(text: &str) -> Option<&'static str> {
    if !text.starts_with("play ") && !text.starts_with("put on ") && !text.starts_with("open ") {
        return None;
    }
    [
        ("aaj tak", "Aaj Tak"),
        ("sony max", "Sony Max"),
        ("pbs kids", "PBS Kids"),
        ("india cricket live", "India cricket live"),
    ]
    .into_iter()
    .find_map(|(needle, title)| text.contains(needle).then_some(title))
}

fn language(text: &str) -> Option<&'static str> {
    [
        ("hindi", "hi"),
        ("english", "en"),
        ("marathi", "mr"),
        ("tamil", "ta"),
        ("telugu", "te"),
    ]
    .into_iter()
    .find_map(|(name, code)| text.contains(name).then_some(code))
}

fn quality(text: &str) -> Option<&'static str> {
    if contains_any(text, &["hd", "1080p", "fhd"]) {
        return Some("hd");
    }
    if contains_any(text, &["sd", "480p"]) {
        return Some("sd");
    }
    None
}

fn mood(text: &str) -> Option<&'static str> {
    [
        ("funny", "funny"),
        ("comedy", "funny"),
        ("calm", "calm"),
        ("inspiring", "inspiring"),
        ("educational", "educational"),
        ("relaxing", "relaxing"),
        ("relax", "relaxing"),
        ("bored", "entertainment"),
    ]
    .into_iter()
    .find_map(|(token, mood)| text.contains(token).then_some(mood))
}

#[cfg(test)]
mod tests {
    use std::fs;

    use super::{
        constraints, llama_prompt, parse_rule_intent, ConfiguredIntentBackend, IntentBackendConfig,
        IntentBackendKind, IntentRequest,
    };

    #[test]
    fn parses_core_airo_scenarios() {
        let scenarios = [
            (
                "Show Hindi news",
                "search",
                "media.search",
                constraints([("genre", "news"), ("live", "true"), ("language", "hi")]),
            ),
            (
                "Play Aaj Tak",
                "play",
                "media.play",
                constraints([("query", "Aaj Tak"), ("live", "true")]),
            ),
            (
                "Marathi movies",
                "search",
                "media.search",
                constraints([("genre", "movies"), ("language", "mr")]),
            ),
            (
                "Sports in HD only",
                "search",
                "media.search",
                constraints([("genre", "sports"), ("quality", "hd")]),
            ),
            (
                "Continue yesterday's movie",
                "resume",
                "media.resume",
                constraints([("continue_watching", "true")]),
            ),
        ];

        for (utterance, expected_intent, expected_tool, expected_constraints) in scenarios {
            let result = parse_rule_intent(utterance);
            assert_eq!(result.intent, expected_intent, "{utterance}");
            assert_eq!(result.tool.as_deref(), Some(expected_tool), "{utterance}");
            assert_eq!(result.constraints, expected_constraints, "{utterance}");
            assert!(!result.clarification_required, "{utterance}");
        }
    }

    #[test]
    fn asks_for_clarification_on_ambiguous_requests() {
        let result = parse_rule_intent("Play Sony");

        assert_eq!(result.intent, "clarify");
        assert_eq!(result.tool.as_deref(), Some("media.clarify"));
        assert_eq!(result.missing_fields, vec!["specific_media".to_string()]);
        assert!(result.clarification_required);
    }

    #[test]
    fn selects_rule_backend_by_config() {
        let backend = ConfiguredIntentBackend::from_config(IntentBackendConfig::default());
        let result = backend
            .parse_sync(IntentRequest {
                utterance: "Sports in HD only".to_string(),
            })
            .unwrap();

        assert_eq!(result.intent, "search");
        assert_eq!(
            result.constraints.get("genre").map(String::as_str),
            Some("sports")
        );
        assert_eq!(
            result.constraints.get("quality").map(String::as_str),
            Some("hd")
        );
    }

    #[test]
    fn reports_llama_cpp_backend_as_unavailable_until_configured() {
        let backend = ConfiguredIntentBackend::from_config(IntentBackendConfig {
            kind: IntentBackendKind::LlamaCpp,
            model_path: Some("models/intent.gguf".to_string()),
            executable_path: None,
            lora_path: None,
        });

        let error = backend
            .parse_sync(IntentRequest {
                utterance: "Show Hindi news".to_string(),
            })
            .unwrap_err();

        assert!(error
            .message
            .contains("llama.cpp executable path is required"));
    }

    #[test]
    fn llama_prompt_matches_media_action_sft_template() {
        assert_eq!(
            llama_prompt("Show Hindi news"),
            "### Instruction\nTranslate the Airo TV user request into a media action JSON object. Output JSON only. Do not answer conversationally.\n\n### Input\nShow Hindi news\n\n### Response\n"
        );
    }

    #[cfg(unix)]
    #[test]
    fn hybrid_llama_cpp_backend_falls_back_to_rules_on_invalid_output() {
        use std::os::unix::fs::PermissionsExt;

        let temp = tempfile::tempdir().unwrap();
        let executable = temp.path().join("llama-cli");
        fs::write(&executable, "#!/bin/sh\nprintf 'not-json'\n").unwrap();
        let mut permissions = fs::metadata(&executable).unwrap().permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&executable, permissions).unwrap();

        let backend = ConfiguredIntentBackend::from_config(IntentBackendConfig {
            kind: IntentBackendKind::LlamaCppWithRuleFallback,
            model_path: Some("models/intent.gguf".to_string()),
            executable_path: Some(executable.to_string_lossy().to_string()),
            lora_path: None,
        });

        let result = backend
            .parse_sync(IntentRequest {
                utterance: "Show Hindi news".to_string(),
            })
            .unwrap();

        assert_eq!(result.intent, "search");
        assert_eq!(result.tool.as_deref(), Some("media.search"));
        assert_eq!(
            result.constraints,
            constraints([("genre", "news"), ("live", "true"), ("language", "hi")])
        );
    }

    #[cfg(unix)]
    #[test]
    fn parses_llama_cpp_backend_json_from_local_process() {
        use std::os::unix::fs::PermissionsExt;

        let temp = tempfile::tempdir().unwrap();
        let executable = temp.path().join("llama-cli");
        fs::write(
            &executable,
            "#!/bin/sh\nprintf '%s ' \"$@\" > \"$(dirname \"$0\")/argv.txt\"\ncat <<'JSON'\n{\"intent\":\"search\",\"tool\":\"media.search\",\"confidence\":0.93,\"constraints\":{\"genre\":\"news\",\"language\":\"hi\",\"live\":true},\"missing_fields\":[],\"clarification_required\":false}\nJSON\n",
        )
        .unwrap();
        let mut permissions = fs::metadata(&executable).unwrap().permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&executable, permissions).unwrap();

        let backend = ConfiguredIntentBackend::from_config(IntentBackendConfig {
            kind: IntentBackendKind::LlamaCpp,
            model_path: Some("models/intent.gguf".to_string()),
            executable_path: Some(executable.to_string_lossy().to_string()),
            lora_path: Some("models/intent-lora.gguf".to_string()),
        });

        let result = backend
            .parse_sync(IntentRequest {
                utterance: "Show Hindi news".to_string(),
            })
            .unwrap();

        assert_eq!(result.intent, "search");
        assert_eq!(result.tool.as_deref(), Some("media.search"));
        assert_eq!(
            result.constraints,
            constraints([("genre", "news"), ("language", "hi"), ("live", "true")])
        );
        assert!(!result.clarification_required);

        let argv = fs::read_to_string(temp.path().join("argv.txt")).unwrap();
        assert!(argv.contains("--lora models/intent-lora.gguf"));
        assert!(!argv.contains("--single-turn"));
        assert!(!argv.contains("--no-conversation"));
        assert!(!argv.contains("--simple-io"));
        assert!(argv.contains("### Instruction"));
        assert!(argv.contains("### Input"));
        assert!(argv.contains("### Response"));
    }
}
