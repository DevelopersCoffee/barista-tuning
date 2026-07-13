from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

REQUIRED_ENTRIES = {
    "manifest.json",
    "media.db",
    "indexes/search.idx",
    "indexes/recommendation.idx",
    "metadata/compile-report.json",
}


@dataclass(frozen=True)
class PackValidationResult:
    pack_path: Path
    valid: bool
    errors: list[str]
    manifest: dict[str, Any] | None = None
    asset_count: int = 0


def validate_media_pack(pack_path: Path) -> PackValidationResult:
    errors: list[str] = []
    manifest: dict[str, Any] | None = None
    asset_count = 0

    if not pack_path.exists():
        return PackValidationResult(pack_path, False, [f"pack does not exist: {pack_path}"])

    try:
        with zipfile.ZipFile(pack_path) as archive:
            names = set(archive.namelist())
            missing = sorted(REQUIRED_ENTRIES - names)
            errors.extend(f"missing required entry: {name}" for name in missing)

            manifest = _read_manifest(archive, errors)
            if manifest is not None:
                _validate_manifest_shape(manifest, errors)
                expected_checksum = str(manifest.get("checksum") or "")
                actual_checksum = _content_checksum(archive)
                if expected_checksum != actual_checksum:
                    errors.append("manifest checksum does not match pack contents")

            asset_count = _validate_media_db(archive, errors) if "media.db" in names else 0
            _validate_json_entry(archive, "indexes/search.idx", errors)
            _validate_json_entry(archive, "indexes/recommendation.idx", errors)
            report = _validate_json_entry(archive, "metadata/compile-report.json", errors)
            if isinstance(report, dict) and report.get("asset_count") != asset_count:
                errors.append("compile report asset_count does not match media.db")
            if manifest is not None:
                metadata = manifest.get("metadata")
                if isinstance(metadata, dict) and metadata.get("asset_count") != asset_count:
                    errors.append("manifest metadata.asset_count does not match media.db")
    except zipfile.BadZipFile:
        errors.append("pack is not a valid zip archive")

    return PackValidationResult(
        pack_path=pack_path,
        valid=not errors,
        errors=errors,
        manifest=manifest,
        asset_count=asset_count,
    )


def _read_manifest(
    archive: zipfile.ZipFile,
    errors: list[str],
) -> dict[str, Any] | None:
    try:
        raw = json.loads(archive.read("manifest.json"))
    except KeyError:
        return None
    except json.JSONDecodeError as error:
        errors.append(f"manifest.json is not valid JSON: {error}")
        return None

    if not isinstance(raw, dict):
        errors.append("manifest.json must be a JSON object")
        return None
    return raw


def _validate_manifest_shape(manifest: dict[str, Any], errors: list[str]) -> None:
    required_top_level = ["pack", "compiler", "runtime", "schema", "capabilities", "checksum"]
    for key in required_top_level:
        if key not in manifest:
            errors.append(f"manifest missing required field: {key}")

    pack = manifest.get("pack")
    if not isinstance(pack, dict):
        errors.append("manifest.pack must be an object")
    else:
        for key in ["id", "name", "version", "domain", "provider"]:
            if not str(pack.get(key) or "").strip():
                errors.append(f"manifest.pack.{key} is required")

    for object_key, field_key in [
        ("compiler", "version"),
        ("runtime", "minimum_sdk"),
        ("schema", "pack_schema"),
        ("schema", "domain_ir"),
    ]:
        value = manifest.get(object_key)
        if not isinstance(value, dict) or not str(value.get(field_key) or "").strip():
            errors.append(f"manifest.{object_key}.{field_key} is required")

    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        errors.append("manifest.capabilities must be a non-empty list")

    if not str(manifest.get("checksum") or "").strip():
        errors.append("manifest.checksum is required")


def _validate_media_db(archive: zipfile.ZipFile, errors: list[str]) -> int:
    with TemporaryDirectory() as temp:
        db_path = Path(temp) / "media.db"
        db_path.write_bytes(archive.read("media.db"))
        connection = sqlite3.connect(db_path)
        try:
            for table in ["media_assets", "media_terms"]:
                count = connection.execute(
                    "select count(*) from sqlite_master where type = 'table' and name = ?",
                    (table,),
                ).fetchone()[0]
                if count != 1:
                    errors.append(f"media.db missing required table: {table}")

            asset_count = connection.execute("select count(*) from media_assets").fetchone()[0]
            if asset_count < 1:
                errors.append("media.db must contain at least one asset")
            playable_count = connection.execute(
                """
                select count(*)
                from media_assets
                where stream_uri is not null and trim(stream_uri) != ''
                """
            ).fetchone()[0]
            if playable_count < 1:
                errors.append("media.db must contain at least one playable asset")
            return int(asset_count)
        finally:
            connection.close()


def _validate_json_entry(
    archive: zipfile.ZipFile,
    name: str,
    errors: list[str],
) -> Any:
    try:
        return json.loads(archive.read(name))
    except KeyError:
        return None
    except json.JSONDecodeError as error:
        errors.append(f"{name} is not valid JSON: {error}")
        return None


def _content_checksum(archive: zipfile.ZipFile) -> str:
    digest = hashlib.sha256()
    for name in sorted(archive.namelist()):
        info = archive.getinfo(name)
        if info.is_dir() or name == "manifest.json":
            continue
        digest.update(name.encode("utf-8"))
        digest.update(archive.read(name))
    return digest.hexdigest()
