use std::future::Future;
use std::pin::Pin;

use edge_kernel::{Context, EdgeResult};

use crate::manifest::PackManifest;

pub type PackFuture<'a, T> = Pin<Box<dyn Future<Output = EdgeResult<T>> + Send + 'a>>;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PackLifecycle {
    Discovered,
    Downloaded,
    Verified,
    Installed,
    Activated,
    Deactivated,
    Removed,
}

pub trait PackManager: Send + Sync {
    fn install<'a>(
        &'a self,
        context: &'a Context,
        pack_path: &'a str,
    ) -> PackFuture<'a, PackManifest>;
    fn activate<'a>(&'a self, context: &'a Context, pack_id: &'a str) -> PackFuture<'a, ()>;
    fn deactivate<'a>(&'a self, context: &'a Context, pack_id: &'a str) -> PackFuture<'a, ()>;
    fn remove<'a>(&'a self, context: &'a Context, pack_id: &'a str) -> PackFuture<'a, ()>;
}
