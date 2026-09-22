from __future__ import annotations

from slm_train_eval_publish.compiler.ir import DomainIR

VALID_DECISION_TYPES = {"choice", "score", "boolean"}
VALID_ESCALATION_TARGETS = {"intent_model", "generative_model", "human", "reject"}


def verify_domain_ir(ir: DomainIR) -> list[str]:
    errors: list[str] = []
    entity_names = [entity["name"] for entity in ir.entities]
    entity_name_set = set(entity_names)

    if not ir.domain:
        errors.append("domain is required")
    if not ir.version:
        errors.append("version is required")
    if not ir.entities:
        errors.append("at least one entity is required")
    if len(entity_names) != len(entity_name_set):
        errors.append("entity names must be unique")

    for entity in ir.entities:
        attribute_names = [attribute["name"] for attribute in entity["attributes"]]
        if len(attribute_names) != len(set(attribute_names)):
            errors.append(f"attributes for entity '{entity['name']}' must be unique")

        for relationship in entity["relationships"]:
            target = relationship["target"]
            if target not in entity_name_set:
                errors.append(
                    f"relationship '{entity['name']}.{relationship['name']}' "
                    f"targets unknown entity '{target}'"
                )

    decision_ids = [dec["id"] for dec in ir.decisions]
    if len(decision_ids) != len(set(decision_ids)):
        errors.append("decision IDs must be unique")

    for dec in ir.decisions:
        dec_id = dec.get("id", "")
        questions = dec.get("questions", [])
        if not questions:
            errors.append(f"decision '{dec_id}' requires at least one question")
            continue

        for q in questions:
            q_id = q.get("id", dec_id)
            q_type = q.get("type", "").lower()
            if q_type not in VALID_DECISION_TYPES:
                errors.append(
                    f"question '{q_id}' in decision '{dec_id}' type '{q_type}' is invalid, must be one of {sorted(VALID_DECISION_TYPES)}"
                )

            if q_type == "choice" and not q.get("options"):
                errors.append(f"question '{q_id}' in decision '{dec_id}' of type 'choice' requires at least one option")

            escalation = q.get("escalation")
            if isinstance(escalation, dict):
                threshold = escalation.get("threshold")
                if threshold is not None and not (0.0 <= float(threshold) <= 1.0):
                    errors.append(
                        f"question '{q_id}' in decision '{dec_id}' escalation threshold must be between 0.0 and 1.0, got {threshold}"
                    )

                target = escalation.get("target")
                if target is not None and target not in VALID_ESCALATION_TARGETS:
                    errors.append(
                        f"question '{q_id}' in decision '{dec_id}' escalation target '{target}' is invalid, must be one of {sorted(VALID_ESCALATION_TARGETS)}"
                    )

    return errors
