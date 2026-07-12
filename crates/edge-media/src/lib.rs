//! Media domain contracts built on the generic Edge Intelligence runtime.

use std::collections::BTreeMap;

use edge_kernel::{Context, EdgeResult};
use edge_runtime::{RecommendationRequest, ResolveRequest, ResolvedItem, RuntimeFuture};
use edge_search::{RankedCandidate, SearchQuery};

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
