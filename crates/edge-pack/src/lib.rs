//! Installable immutable knowledge pack contracts.

pub mod lifecycle;
pub mod manifest;

pub use lifecycle::{PackLifecycle, PackManager};
pub use manifest::{PackDependency, PackManifest, PackSchema};
