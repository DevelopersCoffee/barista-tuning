from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AttributeDefinition:
    name: str
    type: str = "string"
    required: bool = False
    items: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class RelationshipDefinition:
    name: str
    target: str
    cardinality: str = "many"


@dataclass(frozen=True)
class EntityDefinition:
    name: str
    attributes: list[AttributeDefinition] = field(default_factory=list)
    relationships: list[RelationshipDefinition] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DecisionDefinition:
    id: str
    kind: str = "choice"
    options: list[str] = field(default_factory=list)
    backend_type: str | None = None
    escalation_threshold: float | None = None
    escalation_target: str | None = None


@dataclass(frozen=True)
class DomainDefinition:
    domain: str
    version: str
    ir_version: str = "1.0.0"
    description: str | None = None
    entities: list[EntityDefinition] = field(default_factory=list)
    decisions: list[DecisionDefinition] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)


def load_domain_definition(path: str | Path) -> DomainDefinition:
    source_path = Path(path)
    raw = yaml.safe_load(source_path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError("Domain DDL must be a YAML mapping")

    domain = _required_string(raw, "domain")
    version = str(raw.get("version", "0.1.0"))
    ir_version = str(raw.get("ir_version", "1.0.0"))
    entities = _parse_entities(raw)
    decisions = _parse_decisions(raw)

    return DomainDefinition(
        domain=domain,
        version=version,
        ir_version=ir_version,
        description=raw.get("description"),
        entities=entities,
        decisions=decisions,
        policies=_string_list(raw.get("policies", []), "policies"),
        capabilities=_string_list(raw.get("capabilities", []), "capabilities"),
    )


def _parse_entities(raw: dict[str, Any]) -> list[EntityDefinition]:
    if "entities" in raw:
        entities_raw = raw["entities"]
        if not isinstance(entities_raw, dict):
            raise ValueError("'entities' must be a mapping")
        return [_parse_entity(name, value or {}) for name, value in entities_raw.items()]

    if "entity" in raw:
        entity_name = _required_string(raw, "entity")
        entity_raw = {
            "attributes": raw.get("attributes", {}),
            "relationships": raw.get("relationships", {}),
            "policies": raw.get("policies", []),
            "capabilities": raw.get("capabilities", []),
        }
        return [_parse_entity(entity_name, entity_raw)]

    raise ValueError("Domain DDL must define 'entity' or 'entities'")


def _parse_entity(name: str, raw: Any) -> EntityDefinition:
    if not isinstance(raw, dict):
        raise ValueError(f"Entity '{name}' must be a mapping")

    return EntityDefinition(
        name=str(name),
        attributes=_parse_attributes(raw.get("attributes", {}), name),
        relationships=_parse_relationships(raw.get("relationships", {}), name),
        policies=_string_list(raw.get("policies", []), f"entities.{name}.policies"),
        capabilities=_string_list(
            raw.get("capabilities", []),
            f"entities.{name}.capabilities",
        ),
    )


def _parse_decisions(raw: dict[str, Any]) -> list[DecisionDefinition]:
    if "decisions" in raw:
        decisions_raw = raw["decisions"]
        if not isinstance(decisions_raw, dict):
            raise ValueError("'decisions' must be a mapping")
        return [_parse_decision(did, value or {}) for did, value in decisions_raw.items()]

    if "decision" in raw:
        decision_raw = raw["decision"]
        if not isinstance(decision_raw, dict):
            raise ValueError("'decision' must be a mapping")
        decision_id = str(decision_raw.get("id", "default.decision"))
        return [_parse_decision(decision_id, decision_raw)]

    return []


def _parse_decision(decision_id: str, raw: Any) -> DecisionDefinition:
    if not isinstance(raw, dict):
        raise ValueError(f"Decision '{decision_id}' must be a mapping")

    kind = str(raw.get("type", raw.get("kind", "choice"))).lower()
    options_raw = raw.get("options", [])
    if isinstance(options_raw, str):
        options = [options_raw]
    elif isinstance(options_raw, list):
        options = [str(opt) for opt in options_raw]
    else:
        options = []

    backend_raw = raw.get("backend")
    backend_type: str | None = None
    if isinstance(backend_raw, str):
        backend_type = backend_raw.lower()
    elif isinstance(backend_raw, dict):
        if "type" in backend_raw:
            backend_type = str(backend_raw["type"]).lower()

    escalation_raw = raw.get("escalation")
    threshold: float | None = None
    target: str | None = None

    if isinstance(escalation_raw, dict):
        if "threshold" in escalation_raw:
            threshold = float(escalation_raw["threshold"])
        if "target" in escalation_raw:
            target = str(escalation_raw["target"]).lower()

    return DecisionDefinition(
        id=str(decision_id),
        kind=kind,
        options=options,
        backend_type=backend_type,
        escalation_threshold=threshold,
        escalation_target=target,
    )


def _parse_attributes(raw: Any, entity_name: str) -> list[AttributeDefinition]:
    if isinstance(raw, list):
        return [AttributeDefinition(name=str(item)) for item in raw]
    if not isinstance(raw, dict):
        raise ValueError(f"attributes for entity '{entity_name}' must be a mapping or list")

    attributes: list[AttributeDefinition] = []
    for name, value in raw.items():
        if value is None:
            value = {}
        if isinstance(value, str):
            value = {"type": value}
        if not isinstance(value, dict):
            raise ValueError(f"attribute '{entity_name}.{name}' must be a mapping or string")
        attributes.append(
            AttributeDefinition(
                name=str(name),
                type=str(value.get("type", "string")),
                required=bool(value.get("required", False)),
                items=str(value["items"]) if value.get("items") else None,
                description=value.get("description"),
            )
        )
    return attributes


def _parse_relationships(raw: Any, entity_name: str) -> list[RelationshipDefinition]:
    if not raw:
        return []
    if not isinstance(raw, dict):
        raise ValueError(f"relationships for entity '{entity_name}' must be a mapping")

    relationships: list[RelationshipDefinition] = []
    for name, value in raw.items():
        if isinstance(value, str):
            value = {"target": value}
        if not isinstance(value, dict):
            raise ValueError(f"relationship '{entity_name}.{name}' must be a mapping or string")
        target = value.get("target")
        if not target:
            raise ValueError(f"relationship '{entity_name}.{name}' requires a target")
        relationships.append(
            RelationshipDefinition(
                name=str(name),
                target=str(target),
                cardinality=str(value.get("cardinality", "many")),
            )
        )
    return relationships


def _required_string(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' is required and must be a non-empty string")
    return value.strip()


def _string_list(raw: Any, field_name: str) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if not isinstance(raw, list):
        raise ValueError(f"'{field_name}' must be a list of strings")
    return [str(item) for item in raw]
