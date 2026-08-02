from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ENTERPRISE_KNOWLEDGE_PROFILE = "enterprise_knowledge_v1"


def validate_sft_rows(
    rows: Iterable[dict[str, Any]],
    profile: str | None,
    *,
    validation_context_path: str | Path | None = None,
) -> None:
    if profile is None:
        return
    if profile != ENTERPRISE_KNOWLEDGE_PROFILE:
        raise ValueError(f"Unknown data validation profile: {profile}")

    from slm_train_eval_publish.enterprise_knowledge import (
        validate_enterprise_action,
        validate_metadata_catalog,
    )

    approved_tool_ids = None
    if validation_context_path is not None:
        context_path = Path(validation_context_path)
        catalog = json.loads(context_path.read_text(encoding="utf-8"))
        validate_metadata_catalog(catalog)
        approved_tool_ids = {tool["tool_id"] for tool in catalog["approved_tools"]}

    saw_row = False
    for index, row in enumerate(rows, start=1):
        saw_row = True
        output = row.get("output")
        if not isinstance(output, str) or not output.strip():
            raise ValueError(f"row {index}: missing non-empty output")
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as error:
            raise ValueError(f"row {index}: output is invalid JSON: {error.msg}") from error
        try:
            validate_enterprise_action(payload, approved_tool_ids=approved_tool_ids)
        except ValueError as error:
            raise ValueError(f"row {index}: {error}") from error
    if not saw_row:
        raise ValueError("training dataset has no rows")
