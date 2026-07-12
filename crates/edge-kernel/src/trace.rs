use std::time::SystemTime;

use crate::errors::EdgeResult;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct TraceId(pub String);

#[derive(Debug, Clone)]
pub struct TraceEvent {
    pub trace_id: TraceId,
    pub name: String,
    pub timestamp: SystemTime,
}

pub trait TraceRecorder: Send + Sync {
    fn record(&self, event: TraceEvent) -> EdgeResult<()>;
}
