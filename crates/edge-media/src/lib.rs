//! Media domain contracts built on the generic Edge Intelligence runtime.

pub mod vocab;

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

use edge_kernel::{Context, EdgeError, EdgeResult};
use edge_runtime::{RecommendationRequest, ResolveRequest, ResolvedItem, RuntimeFuture};
use edge_search::{Candidate, RankedCandidate, SearchQuery};
use rusqlite::{params, Connection};
use serde_json::Value;

#[derive(Debug, Clone, PartialEq)]
pub struct MediaAsset {
    pub id: String,
    pub title: String,
    pub provider: String,
    pub asset_type: String,
    pub languages: Vec<String>,
    pub genres: Vec<String>,
    pub keywords: Vec<String>,
    pub stream_uri: Option<String>,
    pub metadata: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct PlayRequest {
    pub query: Option<String>,
    pub item_id: Option<String>,
}

pub trait MediaService: Send + Sync {
    fn search<'a>(
        &'a self,
        context: &'a Context,
        query: SearchQuery,
    ) -> RuntimeFuture<'a, Vec<RankedCandidate>>;

    fn recommend<'a>(
        &'a self,
        context: &'a Context,
        request: RecommendationRequest,
    ) -> RuntimeFuture<'a, Vec<RankedCandidate>>;

    fn play<'a>(
        &'a self,
        context: &'a Context,
        request: PlayRequest,
    ) -> RuntimeFuture<'a, ResolvedItem>;

    fn resume<'a>(&'a self, context: &'a Context) -> RuntimeFuture<'a, Option<ResolvedItem>>;

    fn resolve<'a>(
        &'a self,
        context: &'a Context,
        request: ResolveRequest,
    ) -> RuntimeFuture<'a, ResolvedItem>;

    fn history<'a>(&'a self, context: &'a Context) -> RuntimeFuture<'a, Vec<MediaAsset>>;
    fn favorites<'a>(&'a self, context: &'a Context) -> RuntimeFuture<'a, Vec<MediaAsset>>;
}

pub fn ensure_media_asset_has_identity(asset: &MediaAsset) -> EdgeResult<()> {
    if asset.id.trim().is_empty() || asset.title.trim().is_empty() {
        return Err(edge_kernel::EdgeError::new(
            edge_kernel::errors::EdgeErrorKind::InvalidArgument,
            "media asset requires non-empty id and title",
        ));
    }
    Ok(())
}

#[derive(Debug, Clone)]
pub struct PackMediaService {
    db_path: PathBuf,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ScoredMediaAsset {
    pub asset: MediaAsset,
    pub score: f32,
    pub explanation: Vec<String>,
}

impl PackMediaService {
    pub fn new(db_path: impl Into<PathBuf>) -> Self {
        Self {
            db_path: db_path.into(),
        }
    }

    pub fn db_path(&self) -> &Path {
        &self.db_path
    }

    pub fn search_assets_sync(
        &self,
        query: &SearchQuery,
        limit: usize,
    ) -> EdgeResult<Vec<ScoredMediaAsset>> {
        let assets = self.load_assets()?;
        let terms = normalize_terms(&query.text);
        let constraints = normalize_constraints(&query.constraints);
        let mut scored = assets
            .into_iter()
            .filter_map(|asset| score_asset(asset, &terms, &constraints))
            .collect::<Vec<_>>();
        scored.sort_by(|left, right| {
            right
                .score
                .partial_cmp(&left.score)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| left.asset.title.cmp(&right.asset.title))
        });
        scored.truncate(limit.max(1));
        Ok(scored)
    }

    pub fn recommend_assets_sync(
        &self,
        constraints: &BTreeMap<String, String>,
        limit: usize,
    ) -> EdgeResult<Vec<ScoredMediaAsset>> {
        self.search_assets_sync(
            &SearchQuery {
                text: String::new(),
                constraints: constraints.clone(),
            },
            limit,
        )
    }

    pub fn resolve_sync(&self, item_id: &str) -> EdgeResult<ResolvedItem> {
        let asset = self.load_asset(item_id)?;
        resolved_from_asset(&asset)
    }

    pub fn play_sync(&self, request: &PlayRequest) -> EdgeResult<ResolvedItem> {
        if let Some(item_id) = request
            .item_id
            .as_deref()
            .filter(|value| !value.trim().is_empty())
        {
            return self.resolve_sync(item_id);
        }
        let query = request.query.as_deref().unwrap_or_default();
        let matches = self.search_assets_sync(
            &SearchQuery {
                text: query.to_string(),
                constraints: BTreeMap::new(),
            },
            1,
        )?;
        let best = matches.into_iter().next().ok_or_else(|| {
            edge_error(
                edge_kernel::errors::EdgeErrorKind::NotFound,
                "no playable media matched the request",
            )
        })?;
        resolved_from_asset(&best.asset)
    }

    pub fn resume_sync(&self) -> EdgeResult<Option<ResolvedItem>> {
        let movie_constraints = BTreeMap::from([("genre".to_string(), "movies".to_string())]);
        if let Some(candidate) = self
            .recommend_assets_sync(&movie_constraints, 1)?
            .into_iter()
            .next()
        {
            return resolved_from_asset(&candidate.asset).map(Some);
        }

        self.recommend_assets_sync(&BTreeMap::new(), 1)?
            .into_iter()
            .next()
            .map(|candidate| resolved_from_asset(&candidate.asset))
            .transpose()
    }

    pub fn load_asset(&self, item_id: &str) -> EdgeResult<MediaAsset> {
        let connection = self.connection()?;
        let mut statement = connection
            .prepare(
                "select id, title, provider, type, stream_uri, json \
                 from media_assets where id = ?1",
            )
            .map_err(storage_error)?;
        statement
            .query_row(params![item_id], row_to_asset)
            .map_err(|error| match error {
                rusqlite::Error::QueryReturnedNoRows => edge_error(
                    edge_kernel::errors::EdgeErrorKind::NotFound,
                    format!("media item not found: {item_id}"),
                ),
                other => storage_error(other),
            })
    }

    fn load_assets(&self) -> EdgeResult<Vec<MediaAsset>> {
        let connection = self.connection()?;
        let mut statement = connection
            .prepare(
                "select id, title, provider, type, stream_uri, json \
                 from media_assets",
            )
            .map_err(storage_error)?;
        let rows = statement
            .query_map([], row_to_asset)
            .map_err(storage_error)?;
        rows.collect::<Result<Vec<_>, _>>().map_err(storage_error)
    }

    fn connection(&self) -> EdgeResult<Connection> {
        Connection::open(&self.db_path).map_err(storage_error)
    }
}

impl MediaService for PackMediaService {
    fn search<'a>(
        &'a self,
        _context: &'a Context,
        query: SearchQuery,
    ) -> RuntimeFuture<'a, Vec<RankedCandidate>> {
        Box::pin(async move {
            Ok(self
                .search_assets_sync(&query, 20)?
                .into_iter()
                .enumerate()
                .map(|(index, scored)| ranked_candidate(scored, index + 1))
                .collect())
        })
    }

    fn recommend<'a>(
        &'a self,
        _context: &'a Context,
        request: RecommendationRequest,
    ) -> RuntimeFuture<'a, Vec<RankedCandidate>> {
        Box::pin(async move {
            Ok(self
                .recommend_assets_sync(&request.constraints, 20)?
                .into_iter()
                .enumerate()
                .map(|(index, scored)| ranked_candidate(scored, index + 1))
                .collect())
        })
    }

    fn play<'a>(
        &'a self,
        _context: &'a Context,
        request: PlayRequest,
    ) -> RuntimeFuture<'a, ResolvedItem> {
        Box::pin(async move { self.play_sync(&request) })
    }

    fn resume<'a>(&'a self, _context: &'a Context) -> RuntimeFuture<'a, Option<ResolvedItem>> {
        Box::pin(async move { self.resume_sync() })
    }

    fn resolve<'a>(
        &'a self,
        _context: &'a Context,
        request: ResolveRequest,
    ) -> RuntimeFuture<'a, ResolvedItem> {
        Box::pin(async move { self.resolve_sync(&request.item_id) })
    }

    fn history<'a>(&'a self, _context: &'a Context) -> RuntimeFuture<'a, Vec<MediaAsset>> {
        Box::pin(async move { Ok(Vec::new()) })
    }

    fn favorites<'a>(&'a self, _context: &'a Context) -> RuntimeFuture<'a, Vec<MediaAsset>> {
        Box::pin(async move { Ok(Vec::new()) })
    }
}

fn row_to_asset(row: &rusqlite::Row<'_>) -> rusqlite::Result<MediaAsset> {
    let id: String = row.get(0)?;
    let title: String = row.get(1)?;
    let provider: String = row.get(2)?;
    let asset_type: String = row.get(3)?;
    let stream_uri: Option<String> = row.get(4)?;
    let json_text: String = row.get(5)?;
    let json = serde_json::from_str::<Value>(&json_text).unwrap_or(Value::Null);
    let metadata = metadata_from_json(&json);
    Ok(MediaAsset {
        id,
        title,
        provider,
        asset_type,
        languages: string_array(&json, "language"),
        genres: string_array(&json, "genres"),
        keywords: string_array(&json, "keywords"),
        stream_uri,
        metadata,
    })
}

fn score_asset(
    asset: MediaAsset,
    terms: &BTreeSet<String>,
    constraints: &BTreeMap<String, String>,
) -> Option<ScoredMediaAsset> {
    let searchable = searchable_terms(&asset);
    let mut score = 0.05_f32;
    let mut explanation = Vec::new();

    for term in terms {
        if searchable.contains(term) {
            let weight = if normalize_text(&asset.title).contains(term) {
                4.0
            } else {
                1.5
            };
            score += weight;
            explanation.push(format!("matched term '{term}'"));
        }
    }

    for (key, expected) in constraints {
        if expected.is_empty() {
            continue;
        }
        if constraint_matches(&asset, key, expected) {
            score += 3.0;
            explanation.push(format!("matched {key}={expected}"));
        } else {
            return None;
        }
    }

    if terms.is_empty() && constraints.is_empty() {
        score += 0.5;
        explanation.push("default recommendation".to_string());
    }

    if asset
        .stream_uri
        .as_deref()
        .unwrap_or_default()
        .trim()
        .is_empty()
    {
        return None;
    }

    Some(ScoredMediaAsset {
        asset,
        score: score.min(1_000.0),
        explanation,
    })
}

fn constraint_matches(asset: &MediaAsset, key: &str, expected: &str) -> bool {
    let expected = normalize_alias(expected);
    match key {
        "language" => asset
            .languages
            .iter()
            .map(|value| normalize_alias(value))
            .any(|value| value == expected),
        "genre" | "genres" => asset
            .genres
            .iter()
            .map(|value| normalize_alias(value))
            .any(|value| value == expected),
        "type" => normalize_alias(&asset.asset_type) == expected,
        "quality" => asset
            .metadata
            .get("quality")
            .map(|value| normalize_text(value).contains(&expected))
            .unwrap_or(false),
        "live" | "playable" => asset
            .metadata
            .get(key)
            .map(|value| normalize_alias(value) == expected)
            .or_else(|| {
                asset
                    .metadata
                    .get("availability")
                    .map(|value| value.contains(&format!("\"{key}\":true")))
            })
            .unwrap_or(false),
        other => asset
            .metadata
            .get(other)
            .map(|value| normalize_alias(value) == expected)
            .unwrap_or(false),
    }
}

fn searchable_terms(asset: &MediaAsset) -> BTreeSet<String> {
    let mut values = vec![
        asset.title.clone(),
        asset.provider.clone(),
        asset.asset_type.clone(),
    ];
    values.extend(asset.languages.clone());
    values.extend(asset.genres.clone());
    values.extend(asset.keywords.clone());
    values.extend(asset.metadata.values().cloned());
    values
        .iter()
        .flat_map(|value| normalize_terms(value).into_iter())
        .collect()
}

fn resolved_from_asset(asset: &MediaAsset) -> EdgeResult<ResolvedItem> {
    ensure_media_asset_has_identity(asset)?;
    let uri = asset
        .stream_uri
        .as_deref()
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| {
            edge_error(
                edge_kernel::errors::EdgeErrorKind::NotFound,
                format!("media item is not playable: {}", asset.id),
            )
        })?;
    Ok(ResolvedItem {
        item_id: asset.id.clone(),
        title: asset.title.clone(),
        uri: uri.to_string(),
        headers: BTreeMap::new(),
        metadata: asset.metadata.clone(),
    })
}

fn ranked_candidate(scored: ScoredMediaAsset, rank: usize) -> RankedCandidate {
    let mut features = BTreeMap::new();
    features.insert("score".to_string(), scored.score);
    RankedCandidate {
        candidate: Candidate {
            id: scored.asset.id,
            domain: "media".to_string(),
            score: scored.score,
            features,
        },
        rank,
        explanation: scored.explanation,
    }
}

fn normalize_constraints(input: &BTreeMap<String, String>) -> BTreeMap<String, String> {
    input
        .iter()
        .map(|(key, value)| (key.to_ascii_lowercase(), normalize_alias(value)))
        .collect()
}

fn normalize_terms(value: &str) -> BTreeSet<String> {
    normalize_text(value)
        .split_whitespace()
        .map(normalize_alias)
        .filter(|value| !value.is_empty() && !STOP_WORDS.contains(&value.as_str()))
        .collect()
}

fn normalize_text(value: &str) -> String {
    value
        .to_ascii_lowercase()
        .replace('_', " ")
        .chars()
        .map(|ch| if ch.is_ascii_alphanumeric() { ch } else { ' ' })
        .collect::<String>()
}

fn normalize_alias(value: &str) -> String {
    match normalize_text(value).trim() {
        "hindi" | "hin" => "hi".to_string(),
        "marathi" | "mar" => "mr".to_string(),
        "english" | "eng" => "en".to_string(),
        "news" => "news".to_string(),
        "movie" | "movies" | "film" | "films" => "movies".to_string(),
        "sport" | "sports" => "sports".to_string(),
        "hd" | "high definition" => "hd".to_string(),
        other => other.to_string(),
    }
}

fn string_array(json: &Value, key: &str) -> Vec<String> {
    json.get(key)
        .and_then(Value::as_array)
        .map(|values| {
            values
                .iter()
                .filter_map(Value::as_str)
                .map(ToString::to_string)
                .collect()
        })
        .unwrap_or_default()
}

fn metadata_from_json(json: &Value) -> BTreeMap<String, String> {
    let mut metadata = BTreeMap::new();
    let Some(object) = json.as_object() else {
        return metadata;
    };
    for (key, value) in object {
        if matches!(key.as_str(), "id" | "title" | "stream_uri") {
            continue;
        }
        let rendered = match value {
            Value::String(value) => value.clone(),
            Value::Number(value) => value.to_string(),
            Value::Bool(value) => value.to_string(),
            Value::Array(values) => values
                .iter()
                .filter_map(Value::as_str)
                .collect::<Vec<_>>()
                .join(","),
            Value::Object(_) => value.to_string(),
            Value::Null => String::new(),
        };
        if !rendered.is_empty() {
            metadata.insert(key.clone(), rendered);
        }
    }
    metadata
}

fn edge_error(kind: edge_kernel::errors::EdgeErrorKind, message: impl Into<String>) -> EdgeError {
    EdgeError::new(kind, message)
}

fn storage_error(error: impl std::fmt::Display) -> EdgeError {
    edge_error(
        edge_kernel::errors::EdgeErrorKind::Storage,
        error.to_string(),
    )
}

const STOP_WORDS: &[&str] = &[
    "a", "an", "and", "channel", "continue", "in", "me", "only", "play", "show", "the", "tv",
];

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;
    use std::path::Path;

    use edge_search::SearchQuery;
    use rusqlite::Connection;
    use serde_json::json;
    use tempfile::TempDir;

    use super::{PackMediaService, PlayRequest};

    #[test]
    fn ranks_exact_title_and_constraint_matches_first() {
        let temp = TempDir::new().unwrap();
        let db_path = temp.path().join("media.db");
        write_media_db(&db_path);
        let service = PackMediaService::new(&db_path);

        let results = service
            .search_assets_sync(
                &SearchQuery {
                    text: "Play Aaj Tak".to_string(),
                    constraints: BTreeMap::from([
                        ("genre".to_string(), "news".to_string()),
                        ("language".to_string(), "hi".to_string()),
                    ]),
                },
                5,
            )
            .unwrap();

        assert_eq!(results[0].asset.id, "iptv_aajtak_in");
        assert!(results[0].score > results.get(1).map(|item| item.score).unwrap_or(0.0));
    }

    #[test]
    fn falls_back_to_title_terms_when_optional_metadata_is_missing() {
        let temp = TempDir::new().unwrap();
        let db_path = temp.path().join("media.db");
        write_media_db(&db_path);
        let service = PackMediaService::new(&db_path);

        let resolved = service
            .play_sync(&PlayRequest {
                query: Some("Marathi movies".to_string()),
                item_id: None,
            })
            .unwrap();

        assert_eq!(resolved.item_id, "iptv_marathi_movies");
        assert_eq!(resolved.uri, "https://example.test/marathi.m3u8");
    }

    #[test]
    fn resume_prefers_pack_backed_movie_candidate() {
        let temp = TempDir::new().unwrap();
        let db_path = temp.path().join("media.db");
        write_media_db(&db_path);
        let service = PackMediaService::new(&db_path);

        let resolved = service.resume_sync().unwrap().unwrap();

        assert_eq!(resolved.item_id, "iptv_marathi_movies");
        assert_eq!(resolved.uri, "https://example.test/marathi.m3u8");
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
        insert_asset(
            &connection,
            "iptv_aajtak_in",
            "Aaj Tak",
            "https://example.test/aajtak.m3u8",
            json!({
                "id": "iptv_aajtak_in",
                "title": "Aaj Tak",
                "provider": "iptv",
                "type": "live_channel",
                "language": ["hi"],
                "genres": ["news"],
                "keywords": ["aaj tak", "hindi", "news"],
                "stream_uri": "https://example.test/aajtak.m3u8"
            }),
        );
        insert_asset(
            &connection,
            "iptv_marathi_movies",
            "Marathi Movies",
            "https://example.test/marathi.m3u8",
            json!({
                "id": "iptv_marathi_movies",
                "title": "Marathi Movies",
                "provider": "iptv",
                "type": "live_channel",
                "genres": ["movies"],
                "stream_uri": "https://example.test/marathi.m3u8"
            }),
        );
    }

    fn insert_asset(
        connection: &Connection,
        id: &str,
        title: &str,
        stream_uri: &str,
        json: serde_json::Value,
    ) {
        connection
            .execute(
                "insert into media_assets (id, title, provider, type, stream_uri, json)
                 values (?1, ?2, 'iptv', 'live_channel', ?3, ?4)",
                (id, title, stream_uri, json.to_string()),
            )
            .unwrap();
    }
}
