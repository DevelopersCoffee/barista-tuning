from __future__ import annotations

from slm_train_eval_publish.compiler.ir import DomainIR


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

    return errors
