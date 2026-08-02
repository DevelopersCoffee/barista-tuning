from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from slm_train_eval_publish.enterprise_knowledge import validate_metadata_catalog

SCHEMA_VERSION = "1.0"
SYMBOL_KINDS = {
    "api_operation",
    "class",
    "event",
    "function",
    "method",
    "rule",
    "schema",
    "service",
    "workflow",
}
RELATIONSHIP_PREDICATES = {
    "IMPLEMENTS",
    "EXPOSES",
    "INVOKES",
    "READS_FROM",
    "WRITES_TO",
    "COMPUTES",
    "PRODUCES",
    "CONSUMES",
}
VERIFICATION_STATUSES = {"verified", "inferred"}
_EXPORT_FIELDS = {
    "schema_version",
    "knowledge_release",
    "source_revision",
    "extractor",
    "symbols",
    "relationships",
}
_SYMBOL_FIELDS = {
    "symbol_id",
    "kind",
    "name",
    "qualified_name",
    "language",
    "path",
    "line_start",
    "line_end",
    "owner_team_id",
    "verification_status",
}
_RELATIONSHIP_FIELDS = {
    "subject_id",
    "predicate",
    "object_id",
    "source_path",
    "line_start",
    "line_end",
    "confidence",
    "verification_status",
}


def compile_code_index_export(export_path: Path, output_dir: Path) -> Path:
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    _validate_export(payload)
    catalog = _compile_catalog(payload)
    validate_metadata_catalog(catalog)

    output_path = output_dir / "metadata_catalog.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_export(payload: Any) -> None:
    _require_exact_mapping(payload, _EXPORT_FIELDS, "code index export")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    for field in ("knowledge_release", "source_revision"):
        _require_string(payload[field], field)
    _require_exact_mapping(payload["extractor"], {"id", "version"}, "extractor")
    _require_string(payload["extractor"]["id"], "extractor.id")
    _require_string(payload["extractor"]["version"], "extractor.version")

    symbols = payload["symbols"]
    relationships = payload["relationships"]
    if not isinstance(symbols, list) or not symbols:
        raise ValueError("symbols must be a non-empty list")
    if not isinstance(relationships, list) or not relationships:
        raise ValueError("relationships must be a non-empty list")

    symbol_ids: set[str] = set()
    for index, symbol in enumerate(symbols, start=1):
        context = f"symbol {index}"
        _require_exact_mapping(symbol, _SYMBOL_FIELDS, context)
        for field in (
            "symbol_id",
            "kind",
            "name",
            "qualified_name",
            "language",
            "owner_team_id",
            "verification_status",
        ):
            _require_string(symbol[field], f"{context}.{field}")
        if symbol["kind"] not in SYMBOL_KINDS:
            raise ValueError(f"{context} has unsupported kind")
        if symbol["verification_status"] not in VERIFICATION_STATUSES:
            raise ValueError(f"{context} has invalid verification_status")
        _validate_location(symbol["path"], symbol["line_start"], symbol["line_end"], context)
        if symbol["symbol_id"] in symbol_ids:
            raise ValueError(f"duplicate symbol_id: {symbol['symbol_id']}")
        symbol_ids.add(symbol["symbol_id"])

    relationship_keys: set[tuple[str, str, str]] = set()
    for index, relationship in enumerate(relationships, start=1):
        context = f"relationship {index}"
        _require_exact_mapping(relationship, _RELATIONSHIP_FIELDS, context)
        for field in ("subject_id", "predicate", "object_id", "verification_status"):
            _require_string(relationship[field], f"{context}.{field}")
        if relationship["subject_id"] not in symbol_ids:
            raise ValueError(f"{context} has unknown subject_id")
        if relationship["object_id"] not in symbol_ids:
            raise ValueError(f"{context} has unknown object_id")
        if relationship["predicate"] not in RELATIONSHIP_PREDICATES:
            raise ValueError(f"{context} has unsupported predicate")
        if relationship["verification_status"] not in VERIFICATION_STATUSES:
            raise ValueError(f"{context} has invalid verification_status")
        confidence = relationship["confidence"]
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            raise ValueError(f"{context} confidence must be between 0 and 1")
        _validate_location(
            relationship["source_path"],
            relationship["line_start"],
            relationship["line_end"],
            context,
        )
        key = (
            relationship["subject_id"],
            relationship["predicate"],
            relationship["object_id"],
        )
        if key in relationship_keys:
            raise ValueError(f"duplicate relationship: {key}")
        relationship_keys.add(key)


def _compile_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    revision = payload["source_revision"]
    extractor = payload["extractor"]
    entities: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for symbol in sorted(payload["symbols"], key=lambda item: item["symbol_id"]):
        evidence_id = f"evidence:symbol:{_stable_id(symbol['symbol_id'], revision)}"
        entities.append(
            {
                "entity_id": symbol["symbol_id"],
                "entity_type": f"source_{symbol['kind']}",
                "canonical_name": symbol["qualified_name"],
                "display_name": symbol["name"],
                "aliases": sorted({symbol["name"], symbol["qualified_name"]}),
                "owner_team_id": symbol["owner_team_id"],
                "verification_status": symbol["verification_status"],
                "source_revision": revision,
                "evidence_ids": [evidence_id],
            }
        )
        evidence.append(
            _evidence_record(
                evidence_id=evidence_id,
                text=(
                    f"{symbol['kind']} {symbol['qualified_name']} is defined "
                    "at the cited location."
                ),
                path=symbol["path"],
                line_start=symbol["line_start"],
                line_end=symbol["line_end"],
                revision=revision,
                verification_status=symbol["verification_status"],
                extractor=extractor,
            )
        )

    relationships: list[dict[str, Any]] = []
    sorted_relationships = sorted(
        payload["relationships"],
        key=lambda item: (item["subject_id"], item["predicate"], item["object_id"]),
    )
    for relationship in sorted_relationships:
        identity = "|".join(
            [
                relationship["subject_id"],
                relationship["predicate"],
                relationship["object_id"],
                relationship["source_path"],
                str(relationship["line_start"]),
                str(relationship["line_end"]),
                revision,
            ]
        )
        evidence_id = f"evidence:relationship:{_stable_id(identity)}"
        relationships.append(
            {
                "subject_id": relationship["subject_id"],
                "predicate": relationship["predicate"],
                "object_id": relationship["object_id"],
                "evidence_id": evidence_id,
                "confidence": relationship["confidence"],
                "verification_status": relationship["verification_status"],
            }
        )
        evidence.append(
            _evidence_record(
                evidence_id=evidence_id,
                text=(
                    f"{relationship['subject_id']} {relationship['predicate']} "
                    f"{relationship['object_id']} at the cited location."
                ),
                path=relationship["source_path"],
                line_start=relationship["line_start"],
                line_end=relationship["line_end"],
                revision=revision,
                verification_status=relationship["verification_status"],
                extractor=extractor,
            )
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "knowledge_release": payload["knowledge_release"],
        "source_revision": revision,
        "extractor": extractor,
        "entities": entities,
        "evidence": sorted(evidence, key=lambda item: item["evidence_id"]),
        "relationships": relationships,
        "approved_tools": [],
    }


def _evidence_record(
    *,
    evidence_id: str,
    text: str,
    path: str,
    line_start: int,
    line_end: int,
    revision: str,
    verification_status: str,
    extractor: dict[str, str],
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "citation_label": evidence_id.upper(),
        "text": text,
        "source_uri": f"repo://{path}#L{line_start}-L{line_end}",
        "source_revision": revision,
        "verification_status": verification_status,
        "extractor_id": extractor["id"],
        "extractor_version": extractor["version"],
    }


def _validate_location(path: Any, line_start: Any, line_end: Any, context: str) -> None:
    _require_string(path, f"{context}.path")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts or "\\" in path or path in {".", ""}:
        raise ValueError(f"{context} path must be repository-relative")
    if (
        not isinstance(line_start, int)
        or isinstance(line_start, bool)
        or not isinstance(line_end, int)
        or isinstance(line_end, bool)
        or line_start < 1
        or line_end < line_start
    ):
        raise ValueError(f"{context} line range is invalid")


def _require_exact_mapping(value: Any, fields: set[str], context: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{context} fields mismatch")


def _require_string(value: Any, context: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]
