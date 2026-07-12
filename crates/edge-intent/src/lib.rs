//! Intent backend contract. Implementations may be rules, llama.cpp, ONNX, remote, or hybrid.

use std::collections::BTreeMap;
use std::future::Future;
use std::pin::Pin;

use edge_kernel::{Context, EdgeResult};

pub type IntentFuture<'a, T> = Pin<Box<dyn Future<Output = EdgeResult<T>> + Send + 'a>>;

#[derive(Debug, Clone, PartialEq)]
pub struct IntentRequest {
    pub utterance: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct IntentResult {
    pub intent: String,
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
