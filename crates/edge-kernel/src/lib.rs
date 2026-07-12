//! Boring kernel primitives shared by every Edge Intelligence domain.
//!
//! This crate must not contain media, restaurant, retail, banking, or other
//! domain-specific behavior.

pub mod capabilities;
pub mod context;
pub mod errors;
pub mod events;
pub mod trace;
pub mod version;

pub use capabilities::{Capability, CapabilitySet};
pub use context::{Context, DeviceContext, LocaleContext, NetworkState, UserContext};
pub use errors::{EdgeError, EdgeResult};
pub use events::{Event, EventBus, EventSink};
pub use trace::{TraceEvent, TraceId, TraceRecorder};
pub use version::Version;
