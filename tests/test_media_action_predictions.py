from __future__ import annotations

from slm_train_eval_publish.media_action_predictions import (
    INVALID_MEDIA_ACTION,
    extract_first_json_object,
    media_action_prompt,
    parse_media_action_completion,
    validate_media_action_payload,
)


def test_media_action_prompt_omits_expected_output() -> None:
    prompt = media_action_prompt(
        {
            "instruction": "Return JSON only.",
            "input": "Show Hindi news",
            "output": '{"tool":"media.search"}',
        }
    )

    assert prompt.endswith("### Response\n")
    assert '{"tool"' not in prompt


def test_extract_first_json_object_handles_nested_strings() -> None:
    completion = 'Here: {"constraints":{"query":"A {B} channel"},"tool":"media.play"} done'

    assert (
        extract_first_json_object(completion)
        == '{"constraints":{"query":"A {B} channel"},"tool":"media.play"}'
    )


def test_parse_media_action_completion_returns_invalid_placeholder() -> None:
    payload, error = parse_media_action_completion("not json")

    assert payload == INVALID_MEDIA_ACTION
    assert error == "no JSON object found"


def test_parse_media_action_completion_requires_media_action_schema() -> None:
    payload, error = parse_media_action_completion('{"title":"Airo TV"}')

    assert payload == INVALID_MEDIA_ACTION
    assert error == "missing or invalid intent"


def test_validate_media_action_payload_accepts_contract_shape() -> None:
    error = validate_media_action_payload(
        {
            "intent": "search",
            "tool": "media.search",
            "confidence": 0.92,
            "constraints": {"genre": "news"},
            "missing_fields": [],
            "clarification_required": False,
        }
    )

    assert error is None
