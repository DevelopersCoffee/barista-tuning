from __future__ import annotations

from slm_train_eval_publish.media_action_predictions import (
    INVALID_MEDIA_ACTION,
    extract_first_json_object,
    media_action_prompt,
    parse_media_action_completion,
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
