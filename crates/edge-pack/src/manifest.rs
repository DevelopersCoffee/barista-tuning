use edge_kernel::Version;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PackManifest {
    pub id: String,
    pub name: String,
    pub version: Version,
    pub domain: String,
    pub provider: String,
    pub compiler_version: Version,
    pub minimum_sdk: Version,
    pub schema: PackSchema,
    pub capabilities: Vec<String>,
    pub permissions: Vec<String>,
    pub dependencies: Vec<PackDependency>,
    pub checksum: String,
    pub signature: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PackSchema {
    pub pack_schema: Version,
    pub domain_ir: Version,
    pub migration: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PackDependency {
    pub id: String,
    pub version_requirement: String,
}

