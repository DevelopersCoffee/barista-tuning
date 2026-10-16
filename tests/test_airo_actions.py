from __future__ import annotations

import json
from pathlib import Path

import pytest

from slm_train_eval_publish.airo_actions import (
    GENERAL_REFUSAL_RESPONSE,
    GOOGLE_REFUSAL_RESPONSE,
    ROUTE_TARGETS,
    evaluate_airo_actions_predictions,
    format_tool_call,
    parse_tool_call,
)


def test_format_and_parse_tool_call_no_args():
    formatted = format_tool_call("get_current_date_time", {})
    assert formatted == "<get_current_date_time>{}</get_current_date_time>"
    tool, args, is_tool = parse_tool_call(formatted)
    assert is_tool is True
    assert tool == "get_current_date_time"
    assert args == {}


def test_format_and_parse_tool_call_with_args():
    formatted = format_tool_call(
        "schedule_notification",
        {"title": "Medicine", "message": "Take the medicine", "hour": 7, "minute": 30, "repeat_daily": True},
    )
    assert formatted == "<schedule_notification>{title:Medicine,message:Take the medicine,hour:7,minute:30,repeat_daily:true}</schedule_notification>"
    tool, args, is_tool = parse_tool_call(formatted)
    assert is_tool is True
    assert tool == "schedule_notification"
    assert args["title"] == "Medicine"
    assert args["message"] == "Take the medicine"
    assert args["hour"] == 7
    assert args["minute"] == 30
    assert args["repeat_daily"] is True


def test_format_and_parse_open_route():
    for target in ROUTE_TARGETS:
        formatted = format_tool_call("open_route", {"target": target})
        assert formatted == f"<open_route>{{target:{target}}}</open_route>"
        tool, args, is_tool = parse_tool_call(formatted)
        assert is_tool is True
        assert tool == "open_route"
        assert args == {"target": target}


def test_parse_plain_text_refusal():
    tool, args, is_tool = parse_tool_call(GOOGLE_REFUSAL_RESPONSE)
    assert is_tool is False
    assert tool is None
    assert args == {}

    tool, args, is_tool = parse_tool_call(GENERAL_REFUSAL_RESPONSE)
    assert is_tool is False
    assert tool is None
    assert args == {}


def test_dataset_splits_and_gates_thresholds():
    train_path = Path("data/processed/airo_actions_train.jsonl")
    eval_path = Path("data/processed/airo_actions_eval.jsonl")

    assert train_path.exists(), "train dataset file not found"
    assert eval_path.exists(), "eval dataset file not found"

    train_rows = [json.loads(line) for line in train_path.read_text().splitlines() if line.strip()]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    assert len(train_rows) >= 1000
    assert len(eval_rows) >= 300

    train_prompts = {r["instruction"].strip() for r in train_rows}
    eval_prompts = {r["instruction"].strip() for r in eval_rows}

    # Zero leakage requirement
    overlap = train_prompts.intersection(eval_prompts)
    assert not overlap, f"Dataset leakage detected: {overlap}"

    # Verify at least 40 eval prompts per tool and at least 40 refusals
    counts = {}
    for r in eval_rows:
        tool, _, is_tool = parse_tool_call(r["output"])
        key = tool if is_tool else "refusal"
        counts[key] = counts.get(key, 0) + 1

    expected_tools = [
        "get_current_date_time",
        "read_calendar_events",
        "calendar_permission_status",
        "query_lifetrack_status",
        "open_route",
        "schedule_notification",
        "record_lifetrack_facts",
    ]
    for t in expected_tools:
        assert counts.get(t, 0) >= 40, f"Tool {t} has only {counts.get(t, 0)} eval examples (need >= 40)"
    assert counts.get("refusal", 0) >= 40, f"Refusals count is {counts.get('refusal', 0)} (need >= 40)"


def test_evaluator_metrics_and_gates():
    eval_rows = [
        {"instruction": "What time is it?", "input": "", "output": "<get_current_date_time>{}</get_current_date_time>"},
        {"instruction": "Show budget", "input": "", "output": "<open_route>{target:budget}</open_route>"},
        {"instruction": "Turn on torch", "input": "", "output": GOOGLE_REFUSAL_RESPONSE},
    ]
    # Perfect predictions
    perfect_preds = [
        "<get_current_date_time>{}</get_current_date_time>",
        "<open_route>{target:budget}</open_route>",
        GOOGLE_REFUSAL_RESPONSE,
    ]
    report = evaluate_airo_actions_predictions(eval_rows, perfect_preds)
    assert report["all_gates_pass"] is True
    assert report["tool_name_accuracy"] == 1.0
    assert report["required_args_accuracy"] == 1.0
    assert report["refusal_accuracy"] == 1.0

    # Defective predictions
    bad_preds = [
        "I don't know", # failed tool
        "<open_route>{target:chess}</open_route>", # wrong target
        "<turn_on_flashlight>{}</turn_on_flashlight>", # illegal tool on refusal
    ]
    bad_report = evaluate_airo_actions_predictions(eval_rows, bad_preds)
    assert bad_report["all_gates_pass"] is False
    assert bad_report["tool_name_accuracy"] == 0.5
    assert bad_report["required_args_accuracy"] == 0.0
    assert bad_report["refusal_accuracy"] == 0.0


def test_tools_schema_definition():
    schema_path = Path("schemas/airo-actions/v1/tools_schema.json")
    assert schema_path.exists(), "tools_schema.json must exist"
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "tools" in data
    assert len(data["tools"]) == 7

    tool_names = {t["name"] for t in data["tools"]}
    expected_tools = {
        "get_current_date_time",
        "read_calendar_events",
        "calendar_permission_status",
        "query_lifetrack_status",
        "open_route",
        "schedule_notification",
        "record_lifetrack_facts",
    }
    assert tool_names == expected_tools

    for tool in data["tools"]:
        assert "description" in tool
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "object"
        assert "required" in tool["parameters"]


def test_airo_action_prompt():
    from slm_train_eval_publish.airo_action_predictions import airo_action_prompt

    row1 = {"instruction": "What time is it?", "input": ""}
    p1 = airo_action_prompt(row1)
    assert p1 == "### Instruction\nWhat time is it?\n\n### Response\n"

    row2 = {"instruction": "What's on my calendar?", "input": "Today is 2026-10-17"}
    p2 = airo_action_prompt(row2)
    assert p2 == "### Instruction\nWhat's on my calendar?\n\n### Input\nToday is 2026-10-17\n\n### Response\n"

