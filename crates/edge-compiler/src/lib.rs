//! Compiler-stage contracts: ingestion, transformation, compilation.

use edge_kernel::EdgeResult;
use edge_pack::PackManifest;

pub trait IngestionStage<Source, RawIr> {
    fn ingest(&self, source: Source) -> EdgeResult<RawIr>;
}

pub trait TransformationStage<RawIr, DomainIr> {
    fn transform(&self, raw: RawIr) -> EdgeResult<DomainIr>;
}

pub trait CompilationStage<DomainIr> {
    fn compile(&self, ir: DomainIr, output_path: &str) -> EdgeResult<PackManifest>;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompileReport {
    pub source_count: usize,
    pub emitted_items: usize,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationReport {
    pub error_count: usize,
    pub warning_count: usize,
    pub messages: Vec<String>,
}

