from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from slm_train_eval_publish.compiler.ddl import DomainDefinition


@dataclass(frozen=True)
class DomainIR:
    ir_version: str
    domain: str
    version: str
    entities: list[dict[str, Any]]
    decisions: list[dict[str, Any]] = field(default_factory=list)
    policies: list[dict[str, Any]] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_domain_ir(definition: DomainDefinition) -> DomainIR:
    entities = []
    for entity in definition.entities:
        entity_capabilities = sorted(set(entity.capabilities))
        entity_policies = sorted(set(definition.policies + entity.policies))
        entities.append(
            {
                "kind": "Entity",
                "name": entity.name,
                "attributes": [
                    {
                        "kind": "Attribute",
                        "name": attribute.name,
                        "type": attribute.type,
                        "required": attribute.required,
                        "items": attribute.items,
                        "description": attribute.description,
                    }
                    for attribute in entity.attributes
                ],
                "relationships": [
                    {
                        "kind": "Relationship",
                        "name": relationship.name,
                        "target": relationship.target,
                        "cardinality": relationship.cardinality,
                    }
                    for relationship in entity.relationships
                ],
                "policies": entity_policies,
                "capabilities": entity_capabilities,
            }
        )

    decisions = []
    for decision in definition.decisions:
        dec_dict: dict[str, Any] = {
            "kind": "Decision",
            "id": decision.id,
            "type": decision.kind,
            "options": decision.options,
        }
        if decision.escalation_threshold is not None or decision.escalation_target is not None:
            dec_dict["escalation"] = {
                "threshold": decision.escalation_threshold,
                "target": decision.escalation_target,
            }
        decisions.append(dec_dict)

    return DomainIR(
        ir_version=definition.ir_version,
        domain=definition.domain,
        version=definition.version,
        entities=entities,
        decisions=decisions,
        policies=[{"kind": "Policy", "name": policy} for policy in definition.policies],
        capabilities=sorted(set(definition.capabilities)),
    )
