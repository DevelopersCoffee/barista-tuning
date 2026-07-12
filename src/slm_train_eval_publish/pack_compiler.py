from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


@dataclass(frozen=True)
class PackCompileResult:
    pack_path: Path
    manifest_path: Path
    asset_count: int


def compile_media_pack(
    media_ir: Path,
    output: Path,
    pack_id: str,
    pack_name: str,
    version: str = "0.1.0",
    domain: str = "media",
    provider: str = "iptv",
    compile_report: Path | None = None,
) -> PackCompileResult:
    assets = _read_media_ir(media_ir)
    output.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "indexes").mkdir()
        (root / "metadata").mkdir()
        (root / "assets").mkdir()
        (root / "thumbnails").mkdir()

        db_path = root / "media.db"
        search_idx = root / "indexes" / "search.idx"
        recommendation_idx = root / "indexes" / "recommendation.idx"
        signature_path = root / "signature.json"
        manifest_path = root / "manifest.json"

        _write_media_db(db_path, assets)
        _write_search_index(search_idx, assets)
        _write_recommendation_index(recommendation_idx, assets)
        if compile_report is not None and compile_report.exists():
            shutil.copyfile(compile_report, root / "metadata" / "compile-report.json")
        else:
            (root / "metadata" / "compile-report.json").write_text(
                json.dumps({"asset_count": len(assets)}, indent=2),
                encoding="utf-8",
            )

        signature_path.write_text(
            json.dumps({"signature": None, "algorithm": None}, indent=2),
            encoding="utf-8",
        )

        checksum = _content_checksum(root)
        manifest = _manifest(
            pack_id=pack_id,
            pack_name=pack_name,
            version=version,
            domain=domain,
            provider=provider,
            checksum=checksum,
            asset_count=len(assets),
        )
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())

    return PackCompileResult(pack_path=output, manifest_path=output, asset_count=len(assets))


def _read_media_ir(media_ir: Path) -> list[dict[str, Any]]:
    assets = [
        json.loads(line)
        for line in media_ir.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if not assets:
        raise ValueError("media_ir must contain at least one asset")
    return assets


def _write_media_db(db_path: Path, assets: list[dict[str, Any]]) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            create table media_assets (
                id text primary key,
                title text not null,
                provider text not null,
                type text not null,
                stream_uri text,
                json text not null
            )
            """
        )
        connection.execute(
            """
            create table media_terms (
                term text not null,
                asset_id text not null,
                weight real not null,
                primary key (term, asset_id)
            )
            """
        )
        for asset in assets:
            connection.execute(
                """
                insert into media_assets (id, title, provider, type, stream_uri, json)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    asset["id"],
                    asset["title"],
                    asset["provider"],
                    asset["type"],
                    asset.get("stream_uri"),
                    json.dumps(asset, sort_keys=True),
                ),
            )
            for term in _terms(asset):
                connection.execute(
                    """
                    insert or replace into media_terms (term, asset_id, weight)
                    values (?, ?, ?)
                    """,
                    (term, asset["id"], 1.0),
                )
        connection.execute("create index media_terms_asset_idx on media_terms(asset_id)")
        connection.commit()
    finally:
        connection.close()


def _write_search_index(path: Path, assets: list[dict[str, Any]]) -> None:
    index: dict[str, list[str]] = defaultdict(list)
    for asset in assets:
        for term in _terms(asset):
            index[term].append(asset["id"])
    path.write_text(json.dumps(index, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _write_recommendation_index(path: Path, assets: list[dict[str, Any]]) -> None:
    genres = Counter((asset.get("genres") or ["unknown"])[0] for asset in assets)
    languages = Counter(language for asset in assets for language in asset.get("language", []))
    payload = {
        "genre_counts": dict(sorted(genres.items())),
        "language_counts": dict(sorted(languages.items())),
    }
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _manifest(
    pack_id: str,
    pack_name: str,
    version: str,
    domain: str,
    provider: str,
    checksum: str,
    asset_count: int,
) -> dict[str, Any]:
    return {
        "pack": {
            "id": pack_id,
            "name": pack_name,
            "version": version,
            "domain": domain,
            "provider": provider,
        },
        "compiler": {
            "name": "edge-pack-compiler",
            "version": "0.1.0",
        },
        "runtime": {
            "minimum_sdk": "0.1.0",
        },
        "schema": {
            "pack_schema": "1.0.0",
            "domain_ir": "1.0.0",
            "migration": 1,
        },
        "capabilities": [
            "search",
            "recommendation",
            "playback",
            "live",
            "favorites",
            "history",
        ],
        "permissions": ["network_streaming"],
        "dependencies": [],
        "checksum": checksum,
        "signature": None,
        "metadata": {"asset_count": asset_count},
    }


def _content_checksum(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _terms(asset: dict[str, Any]) -> set[str]:
    values = [
        asset.get("title", ""),
        *(asset.get("keywords") or []),
        *(asset.get("genres") or []),
        *(asset.get("subgenres") or []),
        *(asset.get("language") or []),
        asset.get("country") or "",
        asset.get("region") or "",
    ]
    terms: set[str] = set()
    for value in values:
        for term in str(value).lower().replace("_", " ").split():
            normalized = "".join(ch for ch in term if ch.isalnum())
            if normalized:
                terms.add(normalized)
    return terms
