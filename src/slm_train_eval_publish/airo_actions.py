from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROUTE_TARGETS = [
    "money",
    "budget",
    "expenses",
    "split",
    "assistant",
    "models",
    "music",
    "tv",
    "games",
    "chess",
    "quest",
]

GOOGLE_REFUSAL_RESPONSE = (
    "I can open Wi-Fi, the map, mail, contacts, the flashlight, and calendar events "
    "with the Mobile Actions model. This model opens Airo screens, reminders, and LifeTrack."
)

GENERAL_REFUSAL_RESPONSE = (
    "I can only help with Airo navigation, reminders, calendar lookups, and LifeTrack goals."
)


@dataclass(frozen=True)
class AiroActionExample:
    instruction: str
    input: str
    output: str
    tool: str | None
    args: dict[str, Any]

    def to_jsonl_row(self) -> dict[str, str]:
        return {
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
        }


def format_tool_call(tool_name: str, args: dict[str, Any]) -> str:
    if not args:
        return f"<{tool_name}>{{}}</{tool_name}>"
    arg_parts = []
    for k, v in args.items():
        if isinstance(v, bool):
            val_str = "true" if v else "false"
        else:
            val_str = str(v)
        arg_parts.append(f"{k}:{val_str}")
    return f"<{tool_name}>{{{','.join(arg_parts)}}}</{tool_name}>"


_TOOL_CALL_REGEX = re.compile(r"^<([a-z_]+)>\{(.*)\}</\1>$", re.DOTALL)


def parse_tool_call(text: str) -> tuple[str | None, dict[str, Any], bool]:
    """Parse output string.

    Returns:
        (tool_name, arguments_dict, is_tool_call)
    """
    text = text.strip()
    match = _TOOL_CALL_REGEX.match(text)
    if not match:
        return None, {}, False

    tool_name = match.group(1)
    args_str = match.group(2).strip()
    if not args_str:
        return tool_name, {}, True

    args: dict[str, Any] = {}
    for part in _split_arg_pairs(args_str):
        if ":" in part:
            k, v = part.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v.lower() == "true":
                args[k] = True
            elif v.lower() == "false":
                args[k] = False
            elif v.isdigit() and k in {"hour", "minute"}:
                args[k] = int(v)
            else:
                args[k] = v
    return tool_name, args, True


def _split_arg_pairs(args_str: str) -> list[str]:
    # Handles comma-separated key:value where message or query might contain commas if any
    parts: list[str] = []
    current: list[str] = []
    known_keys = {
        "date", "end_date", "query", "target", "title", "message", "hour", "minute", "repeat_daily"
    }
    tokens = args_str.split(",")
    for tok in tokens:
        if any(tok.strip().startswith(f"{kk}:") for kk in known_keys) and current:
            parts.append(",".join(current))
            current = [tok]
        else:
            current.append(tok)
    if current:
        parts.append(",".join(current))
    return parts


def evaluate_airo_actions_predictions(
    examples: list[dict[str, Any]],
    predictions: list[str],
) -> dict[str, Any]:
    if len(examples) != len(predictions):
        raise ValueError(f"Length mismatch: {len(examples)} examples vs {len(predictions)} preds")

    total = len(examples)
    tool_total = 0
    refusal_total = 0

    tool_name_correct = 0
    required_args_correct = 0
    exact_args_correct = 0
    refusal_correct = 0

    failures = []

    for i, (ex, pred_str) in enumerate(zip(examples, predictions)):
        expected_output = (ex.get("output") or ex.get("expected") or "").strip()
        expected_tool, expected_args, expected_is_tool = parse_tool_call(expected_output)
        pred_tool, pred_args, pred_is_tool = parse_tool_call(pred_str)

        if expected_is_tool:
            tool_total += 1
            tool_match = (pred_tool == expected_tool)
            if tool_match:
                tool_name_correct += 1

            # Required args check
            req_match = False
            if tool_match:
                req_match = _check_required_args(expected_tool, expected_args, pred_args)
                if req_match:
                    required_args_correct += 1
                if expected_args == pred_args:
                    exact_args_correct += 1

            if not (tool_match and req_match):
                failures.append({
                    "instruction": ex.get("instruction", ""),
                    "input": ex.get("input", ""),
                    "expected": expected_output,
                    "predicted": pred_str,
                    "expected_tool": expected_tool,
                    "predicted_tool": pred_tool,
                    "expected_args": expected_args,
                    "predicted_args": pred_args,
                })
        else:
            refusal_total += 1
            # Expected a refusal/clarification (no tool call)
            if not pred_is_tool:
                refusal_correct += 1
            else:
                failures.append({
                    "instruction": ex.get("instruction", ""),
                    "input": ex.get("input", ""),
                    "expected": expected_output,
                    "predicted": pred_str,
                    "reason": "Expected refusal / clarification, but model emitted a tool call.",
                })

    tool_accuracy = tool_name_correct / tool_total if tool_total > 0 else 1.0
    req_args_accuracy = required_args_correct / tool_total if tool_total > 0 else 1.0
    exact_args_accuracy = exact_args_correct / tool_total if tool_total > 0 else 1.0
    refusal_accuracy = refusal_correct / refusal_total if refusal_total > 0 else 1.0

    gate_tool_name = tool_accuracy >= 0.90
    gate_required_args = req_args_accuracy >= 0.85
    gate_refusal = refusal_accuracy >= 0.90
    all_gates_pass = gate_tool_name and gate_required_args and gate_refusal

    return {
        "total_samples": total,
        "tool_samples": tool_total,
        "refusal_samples": refusal_total,
        "tool_name_correct": tool_name_correct,
        "tool_name_accuracy": tool_accuracy,
        "required_args_correct": required_args_correct,
        "required_args_accuracy": req_args_accuracy,
        "exact_args_correct": exact_args_correct,
        "exact_args_accuracy": exact_args_accuracy,
        "refusal_correct": refusal_correct,
        "refusal_accuracy": refusal_accuracy,
        "gate_tool_name": gate_tool_name,
        "gate_required_args": gate_required_args,
        "gate_refusal": gate_refusal,
        "all_gates_pass": all_gates_pass,
        "failures_count": len(failures),
        "failures_sample": failures[:10],
    }


def _check_required_args(tool: str, expected_args: dict[str, Any], pred_args: dict[str, Any]) -> bool:
    if tool in {"get_current_date_time", "calendar_permission_status"}:
        return True
    elif tool == "read_calendar_events":
        return str(pred_args.get("date", "")).strip() == str(expected_args.get("date", "")).strip()
    elif tool == "query_lifetrack_status":
        # Check query presence and loose match
        p_q = str(pred_args.get("query", "")).lower().strip()
        e_q = str(expected_args.get("query", "")).lower().strip()
        return bool(p_q) and (p_q in e_q or e_q in p_q or len(set(p_q.split()) & set(e_q.split())) >= 1)
    elif tool == "record_lifetrack_facts":
        p_q = str(pred_args.get("query", "")).lower().strip()
        e_q = str(expected_args.get("query", "")).lower().strip()
        return bool(p_q) and (p_q in e_q or e_q in p_q or len(set(p_q.split()) & set(e_q.split())) >= 1)
    elif tool == "open_route":
        return str(pred_args.get("target", "")).lower().strip() == str(expected_args.get("target", "")).lower().strip()
    elif tool == "schedule_notification":
        req = ["title", "message", "hour", "minute"]
        for r in req:
            if r not in pred_args:
                return False
        # hour and minute must match
        try:
            if int(pred_args["hour"]) != int(expected_args["hour"]):
                return False
            if int(pred_args["minute"]) != int(expected_args["minute"]):
                return False
        except (ValueError, TypeError):
            return False
        return bool(pred_args["title"]) and bool(pred_args["message"])
    return False
