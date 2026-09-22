from __future__ import annotations

import json
from pathlib import Path

import pytest
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


def test_compile_domain_with_decisions(tmp_path: Path) -> None:
    ddl = tmp_path / "media.yaml"
    ddl.write_text(
        """
domain: media
version: 1.0.0
entities:
  MediaItem:
    attributes:
      title: string
decisions:
  media.route:
    type: choice
    options:
      - live_tv
      - movie
      - series
      - youtube
    backend: laya
    escalation:
      threshold: 0.65
      target: intent_model
  safety.check:
    type: boolean
    escalation:
      threshold: 0.95
      target: reject
""".strip()
    )

    result = compile_domain(ddl, tmp_path / "out")
    ir = json.loads(result.domain_ir.read_text())

    assert "decisions" in ir
    assert len(ir["decisions"]) == 2

    route_dec = next(d for d in ir["decisions"] if d["id"] == "media.route")
    assert route_dec["backend"] == {"type": "laya"}
    assert len(route_dec["questions"]) == 1
    assert route_dec["questions"][0]["type"] == "choice"
    assert route_dec["questions"][0]["options"] == ["live_tv", "movie", "series", "youtube"]
    assert route_dec["questions"][0]["escalation"] == {"threshold": 0.65, "target": "intent_model"}

    safety_dec = next(d for d in ir["decisions"] if d["id"] == "safety.check")
    assert len(safety_dec["questions"]) == 1
    assert safety_dec["questions"][0]["type"] == "boolean"
    assert safety_dec["questions"][0]["escalation"] == {"threshold": 0.95, "target": "reject"}


def test_compile_domain_with_multi_question_jev_backend(tmp_path: Path) -> None:
    ddl = tmp_path / "mobile.yaml"
    ddl.write_text(
        """
domain: mobile
version: 1.0.0
entities:
  Screen:
    attributes:
      name: string
decisions:
  mobile.next_action:
    state:
      fields:
        - screen
        - elements
    questions:
      - id: action
        type: choice
        options: [tap, type, scroll, back, wait]
        escalation:
          threshold: 0.70
          target: intent_model
      - id: is_safe
        type: boolean
        escalation:
          threshold: 0.90
          target: reject
    backend:
      type: jev
""".strip()
    )

    result = compile_domain(ddl, tmp_path / "out")
    ir = json.loads(result.domain_ir.read_text())

    assert "decisions" in ir
    assert len(ir["decisions"]) == 1

    dec = ir["decisions"][0]
    assert dec["id"] == "mobile.next_action"
    assert dec["backend"] == {"type": "jev"}
    assert dec["state"] == {"fields": ["screen", "elements"]}

    assert len(dec["questions"]) == 2
    q1 = dec["questions"][0]
    assert q1["id"] == "action"
    assert q1["type"] == "choice"
    assert q1["options"] == ["tap", "type", "scroll", "back", "wait"]
    assert q1["escalation"] == {"threshold": 0.70, "target": "intent_model"}

    q2 = dec["questions"][1]
    assert q2["id"] == "is_safe"
    assert q2["type"] == "boolean"
    assert q2["escalation"] == {"threshold": 0.90, "target": "reject"}


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

    with pytest.raises(ValueError, match="targets unknown entity"):
        compile_domain(ddl, tmp_path / "out")


def test_compile_rejects_invalid_decision_threshold(tmp_path: Path) -> None:
    ddl = tmp_path / "bad_dec.yaml"
    ddl.write_text(
        """
domain: bad_dec
entities:
  Item:
    attributes:
      name: string
decisions:
  bad.route:
    type: choice
    options:
      - opt1
    escalation:
      threshold: 1.5
      target: intent_model
""".strip()
    )

    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        compile_domain(ddl, tmp_path / "out")
