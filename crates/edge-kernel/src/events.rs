use crate::errors::EdgeResult;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    PackDiscovered { pack_id: String },
    PackDownloaded { pack_id: String },
    PackVerified { pack_id: String },
    PackInstalled { pack_id: String },
    PackActivated { pack_id: String },
    PackUpdated { pack_id: String },
    PackDeactivated { pack_id: String },
    PackRemoved { pack_id: String },
    IntentParsed { intent: String },
    SearchCompleted { candidate_count: usize },
    PlaybackResolved { item_id: String },
    PlaybackStarted { item_id: String },
    PlaybackFinished { item_id: String },
    HistoryUpdated,
    ProfileChanged,
}

pub trait EventSink: Send + Sync {
    fn emit(&self, event: Event) -> EdgeResult<()>;
}

pub trait EventBus: EventSink {
    fn subscribe(&self, sink: Box<dyn EventSink>) -> EdgeResult<()>;
}
