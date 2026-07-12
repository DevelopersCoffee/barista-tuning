//! Runtime-level planner and domain service contracts.

use std::collections::BTreeMap;
use std::future::Future;
use std::pin::Pin;

use edge_kernel::{CapabilitySet, Context, EdgeResult};
use edge_search::{RankedCandidate, SearchQuery};

pub type RuntimeFuture<'a, T> = Pin<Box<dyn Future<Output = EdgeResult<T>> + Send + 'a>>;

#[derive(Debug, Clone, PartialEq)]
pub struct RecommendationRequest {
    pub constraints: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ResolveRequest {
    pub item_id: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ResolvedItem {
    pub item_id: String,
    pub title: String,
    pub uri: String,
    pub headers: BTreeMap<String, String>,
    pub metadata: BTreeMap<String, String>,
}

pub trait DomainService: Send + Sync {
    fn capabilities(&self) -> CapabilitySet;

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

    fn resolve<'a>(
        &'a self,
        context: &'a Context,
        request: ResolveRequest,
    ) -> RuntimeFuture<'a, ResolvedItem>;
}

