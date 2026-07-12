from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from slm_train_eval_publish.compiler.ir import DomainIR


def write_artifacts(ir: DomainIR, output_dir: Path) -> dict[str, str]:
    root = output_dir / ir.domain / ir.version
    knowledge_dir = root / "knowledge-pack"
    blueprint_dir = root / "blueprint-pack"
    ir_dir = root / "domain-ir"

    for directory in (knowledge_dir, blueprint_dir, ir_dir):
        directory.mkdir(parents=True, exist_ok=True)

    ir_path = ir_dir / "domain_ir.json"
    schema_path = knowledge_dir / "schema.json"
    validators_path = knowledge_dir / "validators.json"
    docs_path = knowledge_dir / "README.md"
    blueprint_path = blueprint_dir / "blueprints.yaml"

    _write_json(ir_path, ir.to_dict())
    _write_json(schema_path, _json_schema(ir))
    _write_json(validators_path, _validators(ir))
    docs_path.write_text(_documentation(ir))
    blueprint_path.write_text(yaml.safe_dump(_blueprints(ir), sort_keys=False))

    return {
        "root": str(root),
        "domain_ir": str(ir_path),
        "knowledge_pack": str(knowledge_dir),
        "blueprint_pack": str(blueprint_dir),
        "json_schema": str(schema_path),
        "validators": str(validators_path),
        "documentation": str(docs_path),
        "blueprints": str(blueprint_path),
    }


def _json_schema(ir: DomainIR) -> dict[str, Any]:
    definitions: dict[str, Any] = {}
    for entity in ir.entities:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for attribute in entity["attributes"]:
            properties[attribute["name"]] = _attribute_schema(attribute)
            if attribute["required"]:
                required.append(attribute["name"])
        definitions[entity["name"]] = {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": required,
        }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://developerscoffee.dev/domain-ir/{ir.domain}/{ir.version}/schema.json",
        "title": f"{ir.domain} knowledge schema",
        "type": "object",
        "$defs": definitions,
    }


def _attribute_schema(attribute: dict[str, Any]) -> dict[str, Any]:
    attribute_type = attribute["type"]
    if attribute_type == "array":
        return {"type": "array", "items": {"type": attribute.get("items") or "string"}}
    if attribute_type in {"string", "number", "integer", "boolean", "object"}:
        return {"type": attribute_type}
    return {"type": "string", "description": f"Original declared type: {attribute_type}"}


def _validators(ir: DomainIR) -> dict[str, Any]:
    validators = []
    for entity in ir.entities:
        validators.append(
            {
                "name": f"{entity['name']}.required_attributes",
                "type": "schema",
                "description": f"Validate required attributes for {entity['name']}.",
            }
        )
        for policy in entity["policies"]:
            validators.append(
                {
                    "name": f"{entity['name']}.{policy}",
                    "type": "policy",
                    "description": f"Apply policy '{policy}' for {entity['name']}.",
                }
            )

    return {"domain": ir.domain, "version": ir.version, "validators": validators}


def _blueprints(ir: DomainIR) -> dict[str, Any]:
    blueprints = []
    for entity in ir.entities:
        entity_name = entity["name"]
        capabilities = set(entity["capabilities"])
        blueprints.append(
            {
                "name": f"{entity_name}.structured_extraction",
                "capability": "structured_extraction",
                "objective": f"Extract {entity_name} fields into schema-valid JSON.",
                "input": "natural language, table row, or document snippet",
                "output": f"{entity_name} JSON object",
                "validators": [f"{entity_name}.required_attributes"],
            }
        )
        if "qa" in capabilities or "retrieval" in capabilities:
            blueprints.append(
                {
                    "name": f"{entity_name}.grounded_qa",
                    "capability": "qa",
                    "objective": f"Answer questions using only {entity_name} knowledge.",
                    "input": "question and retrieved knowledge records",
                    "output": "grounded answer with no unsupported claims",
                    "validators": [f"{entity_name}.required_attributes"],
                }
            )
        if "intent_extraction" in capabilities:
            blueprints.append(
                {
                    "name": f"{entity_name}.intent_to_business_query",
                    "capability": "intent_extraction",
                    "objective": (
                        "Translate customer language into structured business-query JSON. "
                        "Do not answer from memory."
                    ),
                    "input": "customer utterance and optional customer profile",
                    "output": f"{entity_name} JSON object for deterministic business execution",
                    "validators": [f"{entity_name}.required_attributes"],
                }
            )
        if "entity_normalization" in capabilities:
            blueprints.append(
                {
                    "name": f"{entity_name}.entity_normalization",
                    "capability": "entity_normalization",
                    "objective": (
                        "Normalize natural language mentions, aliases, and regional names "
                        "to canonical entity identifiers."
                    ),
                    "input": "customer phrase, alias, transliteration, or regional term",
                    "output": f"canonical {entity_name} identifier",
                    "validators": [f"{entity_name}.required_attributes"],
                }
            )
        if "recommendation" in capabilities:
            blueprints.append(
                {
                    "name": f"{entity_name}.recommendation_filters",
                    "capability": "recommendation",
                    "objective": (
                        "Extract recommendation filters such as budget, diet, spice level, "
                        "prep time, excluded ingredients, and party size."
                    ),
                    "input": "customer recommendation request",
                    "output": "structured filters for deterministic recommendation ranking",
                    "validators": [f"{entity_name}.required_attributes"],
                }
            )
        if "tool_calling" in capabilities:
            blueprints.append(
                {
                    "name": f"{entity_name}.tool_call",
                    "capability": "tool_calling",
                    "objective": "Produce a safe tool-call payload for the business layer.",
                    "input": "customer request and available tools",
                    "output": "tool-call JSON for validation before execution",
                    "validators": [f"{entity_name}.required_attributes"],
                }
            )
        if "policy_checking" in capabilities:
            blueprints.append(
                {
                    "name": f"{entity_name}.policy_check",
                    "capability": "policy_checking",
                    "objective": "Evaluate deterministic business policies before response.",
                    "input": "candidate result and active policies",
                    "output": "policy decision with reason and customer-facing message",
                    "validators": [f"{entity_name}.required_attributes"],
                }
            )

    return {"domain": ir.domain, "version": ir.version, "blueprints": blueprints}


def _documentation(ir: DomainIR) -> str:
    lines = [
        f"# {ir.domain} Knowledge Pack",
        "",
        f"Version: `{ir.version}`",
        f"Domain IR: `{ir.ir_version}`",
        "",
        "## Entities",
        "",
    ]
    for entity in ir.entities:
        lines.extend([f"### {entity['name']}", ""])
        if entity["attributes"]:
            lines.extend(["Attributes:", ""])
            for attribute in entity["attributes"]:
                required = " required" if attribute["required"] else ""
                lines.append(f"- `{attribute['name']}`: `{attribute['type']}`{required}")
            lines.append("")
        if entity["relationships"]:
            lines.extend(["Relationships:", ""])
            for relationship in entity["relationships"]:
                lines.append(
                    f"- `{relationship['name']}` -> `{relationship['target']}` "
                    f"({relationship['cardinality']})"
                )
            lines.append("")
        if entity["policies"]:
            lines.extend(["Policies:", ""])
            for policy in entity["policies"]:
                lines.append(f"- `{policy}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
