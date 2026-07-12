//! Storage abstractions. Concrete SQLite/cache/blob-store implementations stay hidden here.

use edge_kernel::EdgeResult;

pub trait UnitOfWork: Send {
    fn commit(self: Box<Self>) -> EdgeResult<()>;
    fn rollback(self: Box<Self>) -> EdgeResult<()>;
}

pub trait UnitOfWorkFactory: Send + Sync {
    fn begin(&self) -> EdgeResult<Box<dyn UnitOfWork>>;
}
