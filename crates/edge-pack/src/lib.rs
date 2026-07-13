//! Installable immutable knowledge pack contracts.

pub mod lifecycle;
pub mod manifest;

pub use lifecycle::{InstalledPack, LocalPackManager, PackLifecycle, PackManager};
pub use manifest::{PackDependency, PackManifest, PackSchema};
