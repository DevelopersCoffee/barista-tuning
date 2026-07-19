//! Entity vocabulary for intent slot grounding and dataset generation.
//! Canonical data: crates/edge-media/data/entities_v1.json.

use std::collections::BTreeMap;

use edge_kernel::errors::EdgeErrorKind;
use edge_kernel::{EdgeError, EdgeResult};
use serde::Deserialize;

const EMBEDDED_VOCAB: &str = include_str!("../data/entities_v1.json");

#[derive(Debug, Deserialize)]
struct VocabFile {
    #[allow(dead_code)]
    vocab_version: String,
    entities: BTreeMap<String, Vec<VocabEntry>>,
}

#[derive(Debug, Deserialize)]
struct VocabEntry {
    id: String,
    name: String,
    aliases: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct EntityVocab {
    /// entity_type -> normalized alias -> canonical id
    alias_index: BTreeMap<String, BTreeMap<String, String>>,
    /// entity_type -> (canonical id, display name), file order
    entries: BTreeMap<String, Vec<(String, String)>>,
}

fn normalize(surface: &str) -> String {
    surface
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase()
}

impl EntityVocab {
    pub fn load_default() -> EdgeResult<Self> {
        Self::from_json(EMBEDDED_VOCAB)
    }

    pub fn from_json(json: &str) -> EdgeResult<Self> {
        let file: VocabFile = serde_json::from_str(json).map_err(|e| {
            EdgeError::new(EdgeErrorKind::InvalidArgument, format!("vocab parse: {e}"))
        })?;
        let mut alias_index: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
        let mut entries: BTreeMap<String, Vec<(String, String)>> = BTreeMap::new();
        for (entity_type, list) in file.entities {
            let type_aliases = alias_index.entry(entity_type.clone()).or_default();
            let type_entries = entries.entry(entity_type).or_default();
            for entry in list {
                type_aliases.insert(normalize(&entry.name), entry.id.clone());
                for alias in &entry.aliases {
                    type_aliases.insert(normalize(alias), entry.id.clone());
                }
                type_entries.push((entry.id, entry.name));
            }
        }
        Ok(Self {
            alias_index,
            entries,
        })
    }

    /// Canonical id for a surface form, or None if ungrounded.
    pub fn ground(&self, entity_type: &str, surface: &str) -> Option<&str> {
        self.alias_index
            .get(entity_type)?
            .get(&normalize(surface))
            .map(String::as_str)
    }

    /// (canonical_id, display_name) pairs for one entity type.
    pub fn entries(&self, entity_type: &str) -> Vec<(&str, &str)> {
        self.entries
            .get(entity_type)
            .map(|list| {
                list.iter()
                    .map(|(id, name)| (id.as_str(), name.as_str()))
                    .collect()
            })
            .unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn load_default_succeeds() {
        let vocab = EntityVocab::load_default().expect("embedded vocab loads");
        assert!(!vocab.entries("team").is_empty());
    }

    #[test]
    fn grounds_exact_alias() {
        let vocab = EntityVocab::load_default().unwrap();
        assert_eq!(vocab.ground("team", "india"), Some("team:india"));
        assert_eq!(
            vocab.ground("league", "indian premier league"),
            Some("league:ipl")
        );
    }

    #[test]
    fn grounds_hinglish_alias() {
        let vocab = EntityVocab::load_default().unwrap();
        assert_eq!(vocab.ground("team", "india ka"), Some("team:india"));
        assert_eq!(vocab.ground("genre", "bacchon ka"), Some("genre:kids"));
    }

    #[test]
    fn normalizes_case_and_whitespace() {
        let vocab = EntityVocab::load_default().unwrap();
        assert_eq!(vocab.ground("team", "  Team   INDIA "), Some("team:india"));
    }

    #[test]
    fn unknown_surface_returns_none() {
        let vocab = EntityVocab::load_default().unwrap();
        assert_eq!(vocab.ground("team", "atlantis"), None);
        assert_eq!(vocab.ground("nonsense_type", "india"), None);
    }

    #[test]
    fn rejects_malformed_json() {
        assert!(EntityVocab::from_json("{\"vocab_version\": \"1.0\"}").is_err());
        assert!(EntityVocab::from_json("not json").is_err());
    }

    #[test]
    fn entries_lists_canonical_pairs() {
        let vocab = EntityVocab::load_default().unwrap();
        let teams = vocab.entries("team");
        assert!(teams.contains(&("team:india", "India")));
    }
}
