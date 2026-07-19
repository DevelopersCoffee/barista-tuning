//! IntentCommand v1 — Rust mirror of schemas/intent/v1/schema.json.
//! Additive-only within v1.x (ADR 0014).

use serde::{Deserialize, Serialize};

pub const SCHEMA_VERSION: &str = "1.0";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct IntentCommand {
    pub intent: Intent,
    pub entities: Vec<Entity>,
    pub filters: Vec<Filter>,
    /// `schema.json` lists `sort` in its top-level `required` array: the key
    /// must be present (its value may be `null`). Serde's derive treats a
    /// plain `Option<T>` field as implicitly optional-to-omit, which would
    /// silently accept a payload missing the `sort` key entirely — the
    /// opposite of the schema. `deserialize_with` opts out of that implicit
    /// default handling so a missing key is a deserialization error while
    /// `"sort": null` still deserializes to `None`.
    #[serde(deserialize_with = "require_present_nullable")]
    pub sort: Option<Sort>,
    pub confidence: f64,
    pub schema_version: String,
}

/// Deserializes an `Option<T>` field that must be *present* in the JSON
/// object (its value may still be `null`). Plain `Option<T>` fields let
/// serde's derive skip missing keys silently; routing through this function
/// disables that implicit behavior without otherwise changing semantics.
fn require_present_nullable<'de, D, T>(deserializer: D) -> Result<Option<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: Deserialize<'de>,
{
    Option::<T>::deserialize(deserializer)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Intent {
    Browse,
    Play,
    Resume,
    Similar,
    Search,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entity {
    #[serde(rename = "type")]
    pub entity_type: EntityType,
    pub value: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub grounded_id: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum EntityType {
    Team,
    Sport,
    League,
    Genre,
    Language,
    Channel,
    Title,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Filter {
    pub field: String,
    pub op: FilterOp,
    pub value: serde_json::Value,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FilterOp {
    Eq,
    Neq,
    Lt,
    Lte,
    Gt,
    Gte,
    Range,
    In,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Sort {
    pub field: String,
    pub order: SortOrder,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SortOrder {
    Asc,
    Desc,
}

/// Terminal non-command outcome. Airo maps every variant to deterministic
/// search; the variant is telemetry, not a UX branch (spec: Adoption req. 3).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "reason", rename_all = "snake_case", deny_unknown_fields)]
pub enum FallbackReason {
    InvalidOutput { detail: String },
    LowConfidence { confidence: f64, threshold: f64 },
    Timeout,
    BackendError { detail: String },
}

/// The total output type of `resolve()`: command or explicit fallback, never
/// free text.
pub type ResolveOutcome = Result<IntentCommand, FallbackReason>;
