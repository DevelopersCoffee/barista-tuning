from __future__ import annotations

import json
from pathlib import Path

import yaml

from slm_train_eval_publish.compiler import compile_domain


def test_compile_food_domain(tmp_path: Path) -> None:
    result = compile_domain("examples/food/domain.yaml", tmp_path)

    assert result.root == tmp_path / "food" / "1.0.0"
    assert result.domain_ir.exists()
    assert result.compiler_manifest.exists()
    assert result.knowledge_pack.exists()
    assert result.blueprint_pack.exists()

    ir = json.loads(result.domain_ir.read_text())
    assert ir["domain"] == "food"
    assert ir["ir_version"] == "1.0.0"
    assert [entity["name"] for entity in ir["entities"]] == [
        "Dish",
        "Ingredient",
        "BusinessQuery",
        "CustomerProfile",
        "Policy",
    ]

    schema = json.loads((result.knowledge_pack / "schema.json").read_text())
    assert "Dish" in schema["$defs"]
    assert "BusinessQuery" in schema["$defs"]
    assert schema["$defs"]["Dish"]["required"] == ["name", "price", "ingredients"]

    docs = (result.knowledge_pack / "README.md").read_text()
    assert "# food Knowledge Pack" in docs
    assert "### Dish" in docs
    assert "### BusinessQuery" in docs

    blueprints = yaml.safe_load((result.blueprint_pack / "blueprints.yaml").read_text())
    names = [blueprint["name"] for blueprint in blueprints["blueprints"]]
    assert "Dish.structured_extraction" in names
    assert "Dish.grounded_qa" in names
    assert "Ingredient.entity_normalization" in names
    assert "BusinessQuery.intent_to_business_query" in names
    assert "BusinessQuery.recommendation_filters" in names
    assert "Policy.policy_check" in names

    manifest = yaml.safe_load(result.compiler_manifest.read_text())
    assert manifest["compiler"]["name"] == "domain-intelligence-compiler"
    assert manifest["knowledge_pack"] == {"id": "food", "version": "1.0.0"}
    assert manifest["artifacts"]["adapter"] is None
    assert manifest["artifacts"]["runtime"] is None


def test_compile_rejects_unknown_relationship_target(tmp_path: Path) -> None:
    ddl = tmp_path / "bad.yaml"
    ddl.write_text(
        """
domain: bad
entities:
  Thing:
    relationships:
      missing:
        target: MissingEntity
""".strip()
    )

    try:
        compile_domain(ddl, tmp_path / "out")
    except ValueError as error:
        assert "targets unknown entity" in str(error)
    else:
        raise AssertionError("compile_domain should reject invalid relationship targets")
