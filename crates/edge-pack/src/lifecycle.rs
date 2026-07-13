use std::fs::{self, File};
use std::future::Future;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::pin::Pin;

use edge_kernel::{Context, EdgeError, EdgeResult, Version};
use serde::Deserialize;
use zip::ZipArchive;

use crate::manifest::{PackManifest, PackSchema};

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

#[derive(Debug, Clone)]
pub struct LocalPackManager {
    cache_dir: PathBuf,
}

#[derive(Debug, Clone)]
pub struct InstalledPack {
    pub manifest: PackManifest,
    pub root: PathBuf,
    pub media_db: PathBuf,
}

impl LocalPackManager {
    pub fn new(cache_dir: impl Into<PathBuf>) -> Self {
        Self {
            cache_dir: cache_dir.into(),
        }
    }

    pub fn default_cache_dir() -> PathBuf {
        if let Ok(value) = std::env::var("EDGE_INTELLIGENCE_PACK_CACHE") {
            if !value.trim().is_empty() {
                return PathBuf::from(value);
            }
        }
        std::env::temp_dir().join("edge-intelligence").join("packs")
    }

    pub fn install_pack_sync(
        &self,
        pack_path: impl AsRef<Path>,
        activate: bool,
    ) -> EdgeResult<InstalledPack> {
        let pack_path = pack_path.as_ref();
        let file = File::open(pack_path).map_err(|error| {
            edge_error(
                edge_kernel::errors::EdgeErrorKind::NotFound,
                format!("pack archive not found: {error}"),
            )
        })?;
        let mut archive = ZipArchive::new(file).map_err(|error| {
            edge_error(
                edge_kernel::errors::EdgeErrorKind::VerificationFailed,
                format!("pack archive is not a valid zip: {error}"),
            )
        })?;

        let manifest_text = read_zip_text(&mut archive, "manifest.json")?;
        let raw_manifest: RawPackManifest =
            serde_json::from_str(&manifest_text).map_err(|error| {
                edge_error(
                    edge_kernel::errors::EdgeErrorKind::VerificationFailed,
                    format!("manifest.json is invalid: {error}"),
                )
            })?;
        let manifest = raw_manifest.into_manifest()?;
        require_pack_entry(&mut archive, "media.db")?;
        require_pack_entry(&mut archive, "indexes/search.idx")?;
        require_pack_entry(&mut archive, "indexes/recommendation.idx")?;
        require_pack_entry(&mut archive, "metadata/compile-report.json")?;

        let checksum = content_checksum(&mut archive)?;
        if checksum != manifest.checksum {
            return Err(edge_error(
                edge_kernel::errors::EdgeErrorKind::VerificationFailed,
                "pack checksum does not match manifest",
            ));
        }

        let install_root = self
            .cache_dir
            .join(safe_segment(&manifest.id))
            .join(manifest.version.to_string());
        if install_root.exists() {
            fs::remove_dir_all(&install_root).map_err(storage_error)?;
        }
        fs::create_dir_all(&install_root).map_err(storage_error)?;
        extract_archive(&mut archive, &install_root)?;

        let media_db = install_root.join("media.db");
        validate_media_db(&media_db)?;
        if activate {
            self.activate_sync(&manifest.domain, &install_root)?;
        }

        Ok(InstalledPack {
            manifest,
            root: install_root,
            media_db,
        })
    }

    pub fn active_pack_root(&self, domain: &str) -> EdgeResult<Option<PathBuf>> {
        let marker = self.active_marker(domain);
        if !marker.exists() {
            return Ok(None);
        }
        let value = fs::read_to_string(marker).map_err(storage_error)?;
        let path = PathBuf::from(value.trim());
        if path.exists() {
            Ok(Some(path))
        } else {
            Ok(None)
        }
    }

    pub fn active_media_db(&self) -> EdgeResult<Option<PathBuf>> {
        Ok(self
            .active_pack_root("media")?
            .map(|root| root.join("media.db"))
            .filter(|path| path.exists()))
    }

    pub fn activate_sync(&self, domain: &str, install_root: &Path) -> EdgeResult<()> {
        let marker = self.active_marker(domain);
        if let Some(parent) = marker.parent() {
            fs::create_dir_all(parent).map_err(storage_error)?;
        }
        fs::write(marker, install_root.to_string_lossy().as_bytes()).map_err(storage_error)
    }

    fn active_marker(&self, domain: &str) -> PathBuf {
        self.cache_dir
            .join("active")
            .join(format!("{}.pack", safe_segment(domain)))
    }
}

impl Default for LocalPackManager {
    fn default() -> Self {
        Self::new(Self::default_cache_dir())
    }
}

impl PackManager for LocalPackManager {
    fn install<'a>(
        &'a self,
        _context: &'a Context,
        pack_path: &'a str,
    ) -> PackFuture<'a, PackManifest> {
        Box::pin(async move {
            self.install_pack_sync(pack_path, true)
                .map(|pack| pack.manifest)
        })
    }

    fn activate<'a>(&'a self, _context: &'a Context, pack_id: &'a str) -> PackFuture<'a, ()> {
        Box::pin(async move {
            let pack_root = find_pack_root(&self.cache_dir, pack_id)?;
            self.activate_sync("media", &pack_root)
        })
    }

    fn deactivate<'a>(&'a self, _context: &'a Context, _pack_id: &'a str) -> PackFuture<'a, ()> {
        Box::pin(async move {
            let marker = self.active_marker("media");
            if marker.exists() {
                fs::remove_file(marker).map_err(storage_error)?;
            }
            Ok(())
        })
    }

    fn remove<'a>(&'a self, _context: &'a Context, pack_id: &'a str) -> PackFuture<'a, ()> {
        Box::pin(async move {
            let root = self.cache_dir.join(safe_segment(pack_id));
            if root.exists() {
                fs::remove_dir_all(root).map_err(storage_error)?;
            }
            Ok(())
        })
    }
}

#[derive(Debug, Deserialize)]
struct RawPackManifest {
    pack: RawPackInfo,
    compiler: RawCompilerInfo,
    runtime: RawRuntimeInfo,
    schema: RawSchemaInfo,
    #[serde(default)]
    capabilities: Vec<String>,
    #[serde(default)]
    permissions: Vec<String>,
    #[serde(default)]
    dependencies: Vec<RawDependency>,
    checksum: String,
    signature: Option<String>,
}

#[derive(Debug, Deserialize)]
struct RawPackInfo {
    id: String,
    name: String,
    version: String,
    domain: String,
    provider: String,
}

#[derive(Debug, Deserialize)]
struct RawCompilerInfo {
    version: String,
}

#[derive(Debug, Deserialize)]
struct RawRuntimeInfo {
    minimum_sdk: String,
}

#[derive(Debug, Deserialize)]
struct RawSchemaInfo {
    pack_schema: String,
    domain_ir: String,
    migration: u32,
}

#[derive(Debug, Deserialize)]
struct RawDependency {
    id: String,
    version_requirement: String,
}

impl RawPackManifest {
    fn into_manifest(self) -> EdgeResult<PackManifest> {
        Ok(PackManifest {
            id: require_non_empty(self.pack.id, "pack.id")?,
            name: require_non_empty(self.pack.name, "pack.name")?,
            version: parse_version(&self.pack.version, "pack.version")?,
            domain: require_non_empty(self.pack.domain, "pack.domain")?,
            provider: require_non_empty(self.pack.provider, "pack.provider")?,
            compiler_version: parse_version(&self.compiler.version, "compiler.version")?,
            minimum_sdk: parse_version(&self.runtime.minimum_sdk, "runtime.minimum_sdk")?,
            schema: PackSchema {
                pack_schema: parse_version(&self.schema.pack_schema, "schema.pack_schema")?,
                domain_ir: parse_version(&self.schema.domain_ir, "schema.domain_ir")?,
                migration: self.schema.migration,
            },
            capabilities: self.capabilities,
            permissions: self.permissions,
            dependencies: self
                .dependencies
                .into_iter()
                .map(|dependency| crate::manifest::PackDependency {
                    id: dependency.id,
                    version_requirement: dependency.version_requirement,
                })
                .collect(),
            checksum: require_non_empty(self.checksum, "checksum")?,
            signature: self.signature,
        })
    }
}

fn read_zip_text(archive: &mut ZipArchive<File>, name: &str) -> EdgeResult<String> {
    let mut file = archive.by_name(name).map_err(|_| {
        edge_error(
            edge_kernel::errors::EdgeErrorKind::VerificationFailed,
            format!("pack is missing {name}"),
        )
    })?;
    let mut value = String::new();
    file.read_to_string(&mut value).map_err(storage_error)?;
    Ok(value)
}

fn require_pack_entry(archive: &mut ZipArchive<File>, name: &str) -> EdgeResult<()> {
    let file = archive.by_name(name).map_err(|_| {
        edge_error(
            edge_kernel::errors::EdgeErrorKind::VerificationFailed,
            format!("pack is missing {name}"),
        )
    })?;
    if !file.is_file() {
        return Err(edge_error(
            edge_kernel::errors::EdgeErrorKind::VerificationFailed,
            format!("pack entry is not a file: {name}"),
        ));
    }
    Ok(())
}

fn validate_media_db(path: &Path) -> EdgeResult<()> {
    let connection = rusqlite::Connection::open(path).map_err(storage_error)?;
    for table in ["media_assets", "media_terms"] {
        let count: i64 = connection
            .query_row(
                "select count(*) from sqlite_master where type = 'table' and name = ?1",
                [table],
                |row| row.get(0),
            )
            .map_err(storage_error)?;
        if count != 1 {
            return Err(edge_error(
                edge_kernel::errors::EdgeErrorKind::VerificationFailed,
                format!("media.db is missing required table {table}"),
            ));
        }
    }
    let asset_count: i64 = connection
        .query_row("select count(*) from media_assets", [], |row| row.get(0))
        .map_err(storage_error)?;
    if asset_count < 1 {
        return Err(edge_error(
            edge_kernel::errors::EdgeErrorKind::VerificationFailed,
            "media.db must contain at least one media asset",
        ));
    }
    Ok(())
}

fn content_checksum(archive: &mut ZipArchive<File>) -> EdgeResult<String> {
    let mut entries = Vec::new();
    for index in 0..archive.len() {
        let file = archive.by_index(index).map_err(storage_error)?;
        let name = file.name().to_string();
        if !file.is_file() || name == "manifest.json" {
            continue;
        }
        entries.push(name);
    }
    entries.sort();

    let mut digest = Sha256::new();
    for name in entries {
        let mut file = archive.by_name(&name).map_err(storage_error)?;
        let mut bytes = Vec::new();
        file.read_to_end(&mut bytes).map_err(storage_error)?;
        digest.update(name.as_bytes());
        digest.update(&bytes);
    }
    Ok(digest.finish_hex())
}

fn extract_archive(archive: &mut ZipArchive<File>, install_root: &Path) -> EdgeResult<()> {
    for index in 0..archive.len() {
        let mut file = archive.by_index(index).map_err(storage_error)?;
        if !file.is_file() {
            continue;
        }
        let enclosed = file.enclosed_name().ok_or_else(|| {
            edge_error(
                edge_kernel::errors::EdgeErrorKind::VerificationFailed,
                "pack contains an unsafe path",
            )
        })?;
        let output_path = install_root.join(enclosed);
        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent).map_err(storage_error)?;
        }
        let mut output = File::create(output_path).map_err(storage_error)?;
        io::copy(&mut file, &mut output).map_err(storage_error)?;
    }
    Ok(())
}

fn find_pack_root(cache_dir: &Path, pack_id: &str) -> EdgeResult<PathBuf> {
    let root = cache_dir.join(safe_segment(pack_id));
    let mut versions = fs::read_dir(root)
        .map_err(storage_error)?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.is_dir())
        .collect::<Vec<_>>();
    versions.sort();
    versions.pop().ok_or_else(|| {
        edge_error(
            edge_kernel::errors::EdgeErrorKind::NotFound,
            format!("pack is not installed: {pack_id}"),
        )
    })
}

fn require_non_empty(value: String, field: &str) -> EdgeResult<String> {
    if value.trim().is_empty() {
        Err(edge_error(
            edge_kernel::errors::EdgeErrorKind::VerificationFailed,
            format!("manifest field {field} is required"),
        ))
    } else {
        Ok(value)
    }
}

fn parse_version(value: &str, field: &str) -> EdgeResult<Version> {
    let parts = value.split('.').collect::<Vec<_>>();
    if parts.len() != 3 {
        return Err(edge_error(
            edge_kernel::errors::EdgeErrorKind::VerificationFailed,
            format!("manifest field {field} must be semver major.minor.patch"),
        ));
    }
    let major = parse_version_part(parts[0], field)?;
    let minor = parse_version_part(parts[1], field)?;
    let patch = parse_version_part(parts[2], field)?;
    Ok(Version::new(major, minor, patch))
}

fn parse_version_part(value: &str, field: &str) -> EdgeResult<u16> {
    value.parse::<u16>().map_err(|_| {
        edge_error(
            edge_kernel::errors::EdgeErrorKind::VerificationFailed,
            format!("manifest field {field} contains an invalid version number"),
        )
    })
}

fn safe_segment(value: &str) -> String {
    value
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || ch == '.' || ch == '-' || ch == '_' {
                ch
            } else {
                '_'
            }
        })
        .collect()
}

fn edge_error(kind: edge_kernel::errors::EdgeErrorKind, message: impl Into<String>) -> EdgeError {
    EdgeError::new(kind, message)
}

fn storage_error(error: impl std::fmt::Display) -> EdgeError {
    edge_error(
        edge_kernel::errors::EdgeErrorKind::Storage,
        error.to_string(),
    )
}

struct Sha256 {
    state: sha2::Sha256,
}

impl Sha256 {
    fn new() -> Self {
        Self {
            state: <sha2::Sha256 as sha2::Digest>::new(),
        }
    }

    fn update(&mut self, bytes: &[u8]) {
        sha2::Digest::update(&mut self.state, bytes);
    }

    fn finish_hex(self) -> String {
        let digest = sha2::Digest::finalize(self.state);
        digest.iter().map(|byte| format!("{byte:02x}")).collect()
    }
}
