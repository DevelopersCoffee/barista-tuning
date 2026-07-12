//! Local profile signals and derived preferences.

use std::collections::BTreeMap;
use std::time::SystemTime;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProfileSignalKind {
    Skipped,
    Completed,
    Repeated,
    Liked,
    Disliked,
    Played,
}

#[derive(Debug, Clone)]
pub struct ProfileSignal {
    pub kind: ProfileSignalKind,
    pub item_id: String,
    pub timestamp: SystemTime,
    pub attributes: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Default)]
pub struct ProfileSnapshot {
    pub preferences: BTreeMap<String, String>,
}

