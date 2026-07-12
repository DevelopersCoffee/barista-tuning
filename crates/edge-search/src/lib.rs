//! Provider-agnostic retrieval and ranking contracts.

use std::collections::BTreeMap;

use edge_kernel::{Context, EdgeResult};

#[derive(Debug, Clone, PartialEq)]
pub struct SearchQuery {
    pub text: String,
    pub constraints: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Candidate {
    pub id: String,
    pub domain: String,
    pub score: f32,
    pub features: BTreeMap<String, f32>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RankedCandidate {
    pub candidate: Candidate,
    pub rank: usize,
    pub explanation: Vec<String>,
}

pub trait CandidateRetriever: Send + Sync {
    fn retrieve(&self, context: &Context, query: &SearchQuery) -> EdgeResult<Vec<Candidate>>;
}

pub trait CandidateRanker: Send + Sync {
    fn rank(
        &self,
        context: &Context,
        query: &SearchQuery,
        candidates: Vec<Candidate>,
    ) -> EdgeResult<Vec<RankedCandidate>>;
}
