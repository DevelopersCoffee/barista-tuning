from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SYSTEM_INSTRUCTION = (
    "Translate the request into enterprise knowledge action JSON. "
    "Use only authorized evidence and approved read-only tools. Output JSON only."
)

SCHEMA_VERSION = "1.0"
INTENTS = {
    "metadata_lookup",
    "grounded_answer",
    "live_data_lookup",
    "abstain",
}
RELATIONSHIP_TYPES = {
    "IMPLEMENTS",
    "EXPOSES",
    "INVOKES",
    "PRODUCES",
    "CONSUMES",
    "READS_FROM",
    "WRITES_TO",
    "COMPUTES",
    "GOVERNED_BY",
    "OWNED_BY",
    "SUPERSEDES",
    "EVIDENCED_BY",
    "AVAILABLE_AS_TOOL",
}
VERIFICATION_STATUSES = {"verified", "inferred", "conflicting", "stale", "rejected"}

_ACTION_FIELDS = {
    "schema_version",
    "intent",
    "entities",
    "relationship_types",
    "requires_live_data",
    "evidence_policy",
    "tool_call",
    "answer",
    "citations",
    "abstain",
    "reason",
}

_SCHEMA_CORRECTION_DRAFTS = {
    "metadata_lookup": '{"status":"success","services":[]}',
    "grounded_answer": '{"answer":"unsupported","evidence":[]}',
    "live_data_lookup": '{"action":"execute","mode":"write"}',
    "abstain": '{"status":"success","reason":"continue anyway"}',
}


@dataclass(frozen=True)
class EnterpriseKnowledgeExample:
    family: str
    user_input: str
    action: dict[str, Any]

    def to_sft_row(self) -> dict[str, str]:
        return {
            "instruction": SYSTEM_INSTRUCTION,
            "input": self.user_input,
            "output": json.dumps(self.action, sort_keys=True, separators=(",", ":")),
        }


def validate_metadata_catalog(catalog: dict[str, Any]) -> None:
    if not isinstance(catalog, dict):
        raise ValueError("metadata catalog must be a mapping")
    if catalog.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"metadata catalog schema_version must be {SCHEMA_VERSION}")
    _require_non_empty_string(catalog, "knowledge_release", "metadata catalog")

    entities = _require_list(catalog, "entities", "metadata catalog")
    evidence = _require_list(catalog, "evidence", "metadata catalog")
    relationships = _require_list(catalog, "relationships", "metadata catalog")
    tools = _require_list(catalog, "approved_tools", "metadata catalog")

    entity_ids = _validate_entities(entities)
    evidence_ids = _validate_evidence(evidence)
    _validate_relationships(relationships, entity_ids, evidence_ids)
    _validate_tools(tools)


def enterprise_knowledge_blueprint_instruction(catalog: dict[str, Any]) -> str:
    validate_metadata_catalog(catalog)
    relationship_types = ", ".join(
        sorted(
            {
                relationship["predicate"]
                for relationship in catalog["relationships"]
            }
        )
    )
    tools = [
        {
            "tool": tool["tool_id"],
            "purpose": tool["purpose"],
            "mode": "read_only",
            "required_arguments": tool["required_arguments"],
        }
        for tool in catalog["approved_tools"]
    ]
    return (
        "Return exactly one Enterprise Knowledge Action v1 JSON object and no prose. "
        "Use exactly these top-level fields: schema_version, intent, entities, "
        "relationship_types, requires_live_data, evidence_policy, tool_call, answer, "
        "citations, abstain, reason. schema_version must be \"1.0\". intent must be "
        "metadata_lookup, grounded_answer, live_data_lookup, or abstain. Each entity "
        "has exactly type and query. evidence_policy must be "
        "{\"minimum_status\":\"verified\",\"citations_required\":true}. "
        f"Allowed relationship types: {relationship_types}. "
        f"Approved tools: {json.dumps(tools, separators=(',', ':'))}. "
        "For metadata_lookup, provide entities and relationship_types but no answer "
        "or tool. For grounded_answer, use only supplied authorized evidence, include "
        "an answer and every citation label, and do not call a tool. For "
        "live_data_lookup, set requires_live_data true and select one approved "
        "read_only tool; do not claim an answer before tool execution. For abstain, "
        "set abstain true, provide a reason, and provide no answer, citations, or "
        "tool. Never invent evidence, implementation details, tools, or live facts."
    )


def validate_enterprise_action(
    action: dict[str, Any],
    approved_tool_ids: set[str] | None = None,
) -> None:
    if not isinstance(action, dict):
        raise ValueError("enterprise action must be a mapping")
    if set(action) != _ACTION_FIELDS:
        missing = sorted(_ACTION_FIELDS - set(action))
        unknown = sorted(set(action) - _ACTION_FIELDS)
        raise ValueError(f"enterprise action fields mismatch; missing={missing}, unknown={unknown}")
    if action["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    if action["intent"] not in INTENTS:
        raise ValueError(f"invalid intent: {action['intent']!r}")

    _validate_action_entities(action["entities"])
    relationship_types = action["relationship_types"]
    if not isinstance(relationship_types, list) or any(
        item not in RELATIONSHIP_TYPES for item in relationship_types
    ):
        raise ValueError("relationship_types contains an unknown relationship")
    if not isinstance(action["requires_live_data"], bool):
        raise ValueError("requires_live_data must be a boolean")
    _validate_evidence_policy(action["evidence_policy"])
    if not isinstance(action["citations"], list) or any(
        not isinstance(item, str) or not item.strip() for item in action["citations"]
    ):
        raise ValueError("citations must be a list of non-empty strings")
    if not isinstance(action["abstain"], bool):
        raise ValueError("abstain must be a boolean")
    if action["answer"] is not None and (
        not isinstance(action["answer"], str) or not action["answer"].strip()
    ):
        raise ValueError("answer must be null or a non-empty string")
    if action["reason"] is not None and (
        not isinstance(action["reason"], str) or not action["reason"].strip()
    ):
        raise ValueError("reason must be null or a non-empty string")

    intent = action["intent"]
    if intent == "metadata_lookup":
        _require_passive_action(action)
    elif intent == "grounded_answer":
        _validate_grounded_answer(action)
    elif intent == "live_data_lookup":
        _validate_live_data_action(action, approved_tool_ids)
    else:
        _validate_abstention(action)


def generate_enterprise_knowledge_examples(
    catalog: dict[str, Any],
    count: int,
    seed: int = 42,
) -> list[EnterpriseKnowledgeExample]:
    if count < 1:
        raise ValueError("count must be >= 1")
    validate_metadata_catalog(catalog)

    rng = random.Random(seed)
    templates = [
        _metadata_lookup_example,
        _grounded_answer_example,
        _live_data_example,
        _abstention_example,
    ]
    rng.shuffle(templates)

    approved_tool_ids = {tool["tool_id"] for tool in catalog["approved_tools"]}
    examples = [
        templates[index % len(templates)](catalog, rng)
        for index in range(count)
    ]
    for example in examples:
        validate_enterprise_action(example.action, approved_tool_ids)
    return examples


def write_enterprise_knowledge_split(
    *,
    catalog_path: Path,
    train_output: Path,
    eval_output: Path,
    train_count: int,
    eval_count: int,
    seed: int = 42,
    instruction_mode: str = "basic",
    augmentation_profile: str = "standard",
) -> tuple[Path, Path]:
    if train_count < 1:
        raise ValueError("train_count must be >= 1")
    if eval_count < 1:
        raise ValueError("eval_count must be >= 1")
    if instruction_mode not in {"basic", "blueprint"}:
        raise ValueError("instruction_mode must be 'basic' or 'blueprint'")
    if augmentation_profile not in {"standard", "safety_v2"}:
        raise ValueError("augmentation_profile must be 'standard' or 'safety_v2'")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    validate_metadata_catalog(catalog)
    instruction = (
        enterprise_knowledge_blueprint_instruction(catalog)
        if instruction_mode == "blueprint"
        else SYSTEM_INSTRUCTION
    )
    train_examples = _add_schema_correction_examples(
        generate_enterprise_knowledge_examples(catalog, train_count, seed),
        interval=2 if augmentation_profile == "safety_v2" else 4,
    )
    eval_examples = _add_schema_correction_examples(
        generate_enterprise_knowledge_examples(catalog, eval_count, seed + 10_000),
        interval=2 if augmentation_profile == "safety_v2" else 4,
    )
    _write_examples(train_output, train_examples, instruction=instruction)
    _write_examples(eval_output, eval_examples, instruction=instruction)
    return train_output, eval_output


def validate_enterprise_knowledge_jsonl(
    path: Path,
    *,
    catalog_path: Path | None = None,
) -> int:
    approved_tool_ids = None
    if catalog_path is not None:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        validate_metadata_catalog(catalog)
        approved_tool_ids = {tool["tool_id"] for tool in catalog["approved_tools"]}
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("enterprise knowledge dataset has no rows")
    for index, row in enumerate(rows, start=1):
        _validate_sft_row(row, index, approved_tool_ids)
    return len(rows)


def _metadata_lookup_example(
    catalog: dict[str, Any],
    rng: random.Random,
) -> EnterpriseKnowledgeExample:
    entity = rng.choice(catalog["entities"])
    query = rng.choice(entity["aliases"] or [entity["display_name"]])
    relationship_types = sorted(
        {
            relationship["predicate"]
            for relationship in catalog["relationships"]
            if entity["entity_id"] in {
                relationship["subject_id"],
                relationship["object_id"],
            }
        }
        | {"OWNED_BY", "EVIDENCED_BY"}
    )
    user_input = rng.choice(
        [
            f"Where is {query} implemented and who owns it?",
            f"Which services, APIs, or workflows are related to {query}?",
            f"Find verified implementation metadata for {query}.",
            f"Trace the implementation and ownership of {query}.",
            f"Map {query} to its verified rules, APIs, and workflows.",
            f"What approved metadata describes {query}?",
        ]
    )
    return EnterpriseKnowledgeExample(
        family="metadata_lookup",
        user_input=_decorate_user_input(user_input, rng),
        action=_base_action(
            intent="metadata_lookup",
            entities=[{"type": entity["entity_type"], "query": query}],
            relationship_types=relationship_types,
        ),
    )


def _grounded_answer_example(
    catalog: dict[str, Any],
    rng: random.Random,
) -> EnterpriseKnowledgeExample:
    relationship = rng.choice(catalog["relationships"])
    entities = {entity["entity_id"]: entity for entity in catalog["entities"]}
    evidence = {
        record["evidence_id"]: record for record in catalog["evidence"]
    }[relationship["evidence_id"]]
    subject = entities[relationship["subject_id"]]
    object_ = entities[relationship["object_id"]]
    citation = evidence["citation_label"]
    answer = (
        f"{subject['display_name']} {relationship['predicate'].lower().replace('_', ' ')} "
        f"{object_['display_name']} [{citation}]."
    )
    question = rng.choice(
        [
            f"How are {subject['display_name']} and {object_['display_name']} related?",
            f"What verified relationship connects {subject['display_name']} to "
            f"{object_['display_name']}?",
            f"Explain the dependency between {subject['display_name']} and "
            f"{object_['display_name']}.",
            f"Trace how {subject['display_name']} uses or governs "
            f"{object_['display_name']}.",
            f"What does the evidence say about {subject['display_name']} and "
            f"{object_['display_name']}?",
            f"Summarize the implementation link from {subject['display_name']} to "
            f"{object_['display_name']}.",
        ]
    )
    user_input = f"Question: {question}\nAuthorized evidence [{citation}]: {evidence['text']}"
    return EnterpriseKnowledgeExample(
        family="grounded_answer",
        user_input=_decorate_user_input(user_input, rng),
        action=_base_action(
            intent="grounded_answer",
            entities=[
                {"type": subject["entity_type"], "query": subject["display_name"]},
                {"type": object_["entity_type"], "query": object_["display_name"]},
            ],
            relationship_types=[relationship["predicate"]],
            answer=answer,
            citations=[citation],
        ),
    )


def _live_data_example(
    catalog: dict[str, Any],
    rng: random.Random,
) -> EnterpriseKnowledgeExample:
    tool = rng.choice(catalog["approved_tools"])
    reference = next(iter(tool["example_arguments"].values()), "REFERENCE")
    user_input = rng.choice(
        [
            f"Retrieve the current authorized summary for {reference}.",
            f"Use an approved source to explain the live status of {reference}.",
            f"Get the latest authorized operational record for {reference}.",
            f"Route a read-only lookup for {reference}.",
            f"Fetch the current evidence needed to explain {reference}.",
            f"Select the approved diagnostic tool for {reference}.",
            f"Inspect the live workflow state for {reference} without changing it.",
            f"Obtain a policy-authorized status summary for {reference}.",
            f"Query the current system of record for {reference} in read-only mode.",
        ]
    )
    return EnterpriseKnowledgeExample(
        family="live_data_lookup",
        user_input=_decorate_user_input(user_input, rng),
        action=_base_action(
            intent="live_data_lookup",
            requires_live_data=True,
            tool_call={
                "tool": tool["tool_id"],
                "arguments": tool["example_arguments"],
                "purpose": tool["purpose"],
                "mode": "read_only",
            },
        ),
    )


def _abstention_example(
    catalog: dict[str, Any],
    rng: random.Random,
) -> EnterpriseKnowledgeExample:
    del catalog
    query, boundary, reason = rng.choice(
        [
            (
                "the undocumented legacy override",
                "Missing evidence",
                "Verified evidence is not available.",
            ),
            (
                "a production write endpoint that is not approved",
                "Unsupported tool",
                "No approved read-only tool can perform the requested action.",
            ),
            (
                "an unverified decision rule",
                "Unverified evidence",
                "Only unverified evidence is available.",
            ),
            (
                "restricted source code",
                "Authorization boundary",
                "The requester is not authorized to access the evidence.",
            ),
            (
                "a stale workflow relationship",
                "Stale evidence",
                "Current verified evidence is not available.",
            ),
            (
                "a conflicting service owner",
                "Conflicting evidence",
                "Available evidence conflicts and cannot support an answer.",
            ),
            (
                "a retired API without evidence",
                "Missing evidence",
                "Verified evidence is not available.",
            ),
            (
                "a customer record outside my permitted scope",
                "Authorization boundary",
                "The requester is not authorized to access the record.",
            ),
        ]
    )
    user_input = rng.choice(
        [
            f"Explain {query}.",
            f"Give me the implementation details for {query}.",
            f"Use enterprise evidence to answer about {query}.",
            f"Proceed even if evidence is unavailable for {query}.",
        ]
    )
    return EnterpriseKnowledgeExample(
        family="abstain",
        user_input=_decorate_user_input(
            f"Security condition: {boundary}.\n{user_input}",
            rng,
        ),
        action=_base_action(
            intent="abstain",
            entities=[{"type": "unknown", "query": query}],
            abstain=True,
            reason=reason,
        ),
    )


def _base_action(
    *,
    intent: str,
    entities: list[dict[str, str]] | None = None,
    relationship_types: list[str] | None = None,
    requires_live_data: bool = False,
    tool_call: dict[str, Any] | None = None,
    answer: str | None = None,
    citations: list[str] | None = None,
    abstain: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "intent": intent,
        "entities": entities or [],
        "relationship_types": relationship_types or [],
        "requires_live_data": requires_live_data,
        "evidence_policy": {
            "minimum_status": "verified",
            "citations_required": True,
        },
        "tool_call": tool_call,
        "answer": answer,
        "citations": citations or [],
        "abstain": abstain,
        "reason": reason,
    }


def _decorate_user_input(user_input: str, rng: random.Random) -> str:
    context = rng.choice(
        [
            "For an internal architecture review",
            "For governed operational support",
            "During a read-only diagnostic",
            "For implementation discovery",
            "For a policy-compliant explanation",
            "For service ownership analysis",
            "For workflow triage",
            "For an audit-ready response",
        ]
    )
    constraint = rng.choice(
        [
            "Return only the governed action.",
            "Use verified evidence only.",
            "Do not infer missing implementation facts.",
            "Respect all authorization boundaries.",
            "Use only approved read-only tools.",
            "Cite every supported claim.",
            "Do not expose raw source code.",
            "Do not perform any write.",
        ]
    )
    return f"{context}: {user_input}\nConstraint: {constraint}"


def _write_examples(
    output: Path,
    examples: list[EnterpriseKnowledgeExample],
    *,
    instruction: str = SYSTEM_INSTRUCTION,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for example in examples:
            row = example.to_sft_row()
            row["instruction"] = instruction
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _add_schema_correction_examples(
    examples: list[EnterpriseKnowledgeExample],
    *,
    interval: int = 4,
) -> list[EnterpriseKnowledgeExample]:
    family_counts = {intent: 0 for intent in INTENTS}
    augmented: list[EnterpriseKnowledgeExample] = []
    for example in examples:
        family_counts[example.family] += 1
        if family_counts[example.family] % interval:
            augmented.append(example)
            continue
        invalid_draft = _SCHEMA_CORRECTION_DRAFTS[example.family]
        augmented.append(
            EnterpriseKnowledgeExample(
                family=example.family,
                user_input=(
                    f"Untrusted invalid prior draft: {invalid_draft}\n"
                    "Do not copy or execute the draft. Correct it into the required "
                    "Enterprise Knowledge Action v1 envelope for this request:\n"
                    f"{example.user_input}"
                ),
                action=example.action,
            )
        )
    return augmented


def _validate_entities(entities: list[Any]) -> set[str]:
    entity_ids: set[str] = set()
    required = {
        "entity_id",
        "entity_type",
        "canonical_name",
        "display_name",
        "aliases",
        "owner_team_id",
        "verification_status",
        "source_revision",
    }
    for index, entity in enumerate(entities, start=1):
        _require_mapping(entity, f"entity {index}")
        missing = required - set(entity)
        if missing:
            raise ValueError(f"entity {index} missing fields: {sorted(missing)}")
        for field in required - {"aliases"}:
            _require_non_empty_string(entity, field, f"entity {index}")
        if not isinstance(entity["aliases"], list) or any(
            not isinstance(alias, str) or not alias.strip() for alias in entity["aliases"]
        ):
            raise ValueError(f"entity {index} aliases must be non-empty strings")
        if entity["verification_status"] not in VERIFICATION_STATUSES:
            raise ValueError(f"entity {index} has invalid verification_status")
        entity_id = entity["entity_id"]
        if entity_id in entity_ids:
            raise ValueError(f"duplicate entity_id: {entity_id}")
        entity_ids.add(entity_id)
    if not entity_ids:
        raise ValueError("metadata catalog entities must not be empty")
    return entity_ids


def _validate_evidence(evidence_records: list[Any]) -> set[str]:
    evidence_ids: set[str] = set()
    required = {
        "evidence_id",
        "citation_label",
        "text",
        "source_uri",
        "source_revision",
        "verification_status",
    }
    for index, evidence in enumerate(evidence_records, start=1):
        _require_mapping(evidence, f"evidence {index}")
        missing = required - set(evidence)
        if missing:
            raise ValueError(f"evidence {index} missing fields: {sorted(missing)}")
        for field in required:
            _require_non_empty_string(evidence, field, f"evidence {index}")
        if evidence["verification_status"] not in VERIFICATION_STATUSES:
            raise ValueError(f"evidence {index} has invalid verification_status")
        evidence_id = evidence["evidence_id"]
        if evidence_id in evidence_ids:
            raise ValueError(f"duplicate evidence_id: {evidence_id}")
        evidence_ids.add(evidence_id)
    if not evidence_ids:
        raise ValueError("metadata catalog evidence must not be empty")
    return evidence_ids


def _validate_relationships(
    relationships: list[Any],
    entity_ids: set[str],
    evidence_ids: set[str],
) -> None:
    for index, relationship in enumerate(relationships, start=1):
        _require_mapping(relationship, f"relationship {index}")
        for field in (
            "subject_id",
            "predicate",
            "object_id",
            "evidence_id",
            "verification_status",
        ):
            _require_non_empty_string(relationship, field, f"relationship {index}")
        if relationship["subject_id"] not in entity_ids:
            raise ValueError(f"relationship {index} has unknown subject_id")
        if relationship["object_id"] not in entity_ids:
            raise ValueError(f"relationship {index} has unknown object_id")
        if relationship["evidence_id"] not in evidence_ids:
            raise ValueError(f"relationship {index} has unknown evidence_id")
        if relationship["predicate"] not in RELATIONSHIP_TYPES:
            raise ValueError(f"relationship {index} has unknown predicate")
        confidence = relationship.get("confidence")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            raise ValueError(f"relationship {index} confidence must be between 0 and 1")
        if relationship["verification_status"] not in VERIFICATION_STATUSES:
            raise ValueError(f"relationship {index} has invalid verification_status")
    if not relationships:
        raise ValueError("metadata catalog relationships must not be empty")


def _validate_tools(tools: list[Any]) -> None:
    tool_ids: set[str] = set()
    for index, tool in enumerate(tools, start=1):
        _require_mapping(tool, f"approved tool {index}")
        for field in ("tool_id", "description", "mode", "purpose"):
            _require_non_empty_string(tool, field, f"approved tool {index}")
        if tool["mode"] != "read_only":
            raise ValueError(f"approved tool {index} mode must be read_only")
        required_arguments = tool.get("required_arguments")
        example_arguments = tool.get("example_arguments")
        if not isinstance(required_arguments, list) or any(
            not isinstance(item, str) or not item.strip() for item in required_arguments
        ):
            raise ValueError(f"approved tool {index} required_arguments must be strings")
        if not isinstance(example_arguments, dict):
            raise ValueError(f"approved tool {index} example_arguments must be a mapping")
        if set(required_arguments) - set(example_arguments):
            raise ValueError(f"approved tool {index} example_arguments are incomplete")
        if tool["tool_id"] in tool_ids:
            raise ValueError(f"duplicate tool_id: {tool['tool_id']}")
        tool_ids.add(tool["tool_id"])


def _validate_action_entities(entities: Any) -> None:
    if not isinstance(entities, list):
        raise ValueError("entities must be a list")
    for index, entity in enumerate(entities, start=1):
        if not isinstance(entity, dict) or set(entity) != {"type", "query"}:
            raise ValueError(f"action entity {index} fields are invalid")
        _require_non_empty_string(entity, "type", f"action entity {index}")
        _require_non_empty_string(entity, "query", f"action entity {index}")


def _validate_evidence_policy(policy: Any) -> None:
    if not isinstance(policy, dict) or set(policy) != {
        "minimum_status",
        "citations_required",
    }:
        raise ValueError("evidence_policy fields are invalid")
    if policy["minimum_status"] != "verified":
        raise ValueError("evidence_policy minimum_status must be verified")
    if policy["citations_required"] is not True:
        raise ValueError("evidence_policy citations_required must be true")


def _require_passive_action(action: dict[str, Any]) -> None:
    if (
        action["requires_live_data"]
        or action["tool_call"] is not None
        or action["answer"] is not None
        or action["citations"]
        or action["abstain"]
        or action["reason"] is not None
    ):
        raise ValueError("metadata_lookup must only describe a retrieval plan")
    if not action["entities"]:
        raise ValueError("metadata_lookup requires at least one entity")


def _validate_grounded_answer(action: dict[str, Any]) -> None:
    if action["requires_live_data"] or action["tool_call"] is not None or action["abstain"]:
        raise ValueError("grounded_answer cannot request tools or abstain")
    if action["answer"] is None or not action["citations"]:
        raise ValueError("grounded_answer requires an answer and at least one citation")
    if action["reason"] is not None:
        raise ValueError("grounded_answer reason must be null")


def _validate_live_data_action(
    action: dict[str, Any],
    approved_tool_ids: set[str] | None,
) -> None:
    if not action["requires_live_data"] or action["abstain"]:
        raise ValueError("live_data_lookup must require live data and not abstain")
    if action["answer"] is not None or action["citations"] or action["reason"] is not None:
        raise ValueError("live_data_lookup cannot claim an answer before tool execution")
    tool_call = action["tool_call"]
    if not isinstance(tool_call, dict) or set(tool_call) != {
        "tool",
        "arguments",
        "purpose",
        "mode",
    }:
        raise ValueError("live_data_lookup tool_call fields are invalid")
    for field in ("tool", "purpose", "mode"):
        _require_non_empty_string(tool_call, field, "tool_call")
    if tool_call["mode"] != "read_only":
        raise ValueError("tool_call mode must be read_only")
    if not isinstance(tool_call["arguments"], dict):
        raise ValueError("tool_call arguments must be a mapping")
    if approved_tool_ids is not None and tool_call["tool"] not in approved_tool_ids:
        raise ValueError("tool_call is not in the approved tool catalog")


def _validate_abstention(action: dict[str, Any]) -> None:
    if (
        not action["abstain"]
        or action["requires_live_data"]
        or action["tool_call"] is not None
        or action["answer"] is not None
        or action["citations"]
        or action["reason"] is None
    ):
        raise ValueError("abstain action must contain only a non-empty reason")


def _validate_sft_row(
    row: Any,
    index: int,
    approved_tool_ids: set[str] | None,
) -> None:
    if not isinstance(row, dict) or set(row) != {"instruction", "input", "output"}:
        raise ValueError(f"row {index} must contain instruction, input, and output")
    for field in ("instruction", "input", "output"):
        _require_non_empty_string(row, field, f"row {index}")
    try:
        action = json.loads(row["output"])
    except json.JSONDecodeError as error:
        raise ValueError(f"row {index} output is invalid JSON: {error.msg}") from error
    try:
        validate_enterprise_action(action, approved_tool_ids=approved_tool_ids)
    except ValueError as error:
        raise ValueError(f"row {index} output is invalid: {error}") from error


def _require_list(payload: dict[str, Any], field: str, context: str) -> list[Any]:
    value = payload.get(field)
    if not isinstance(value, list):
        raise ValueError(f"{context} field '{field}' must be a list")
    return value


def _require_mapping(value: Any, context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")


def _require_non_empty_string(payload: dict[str, Any], field: str, context: str) -> None:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} field '{field}' must be a non-empty string")
