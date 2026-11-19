from app.runtime.litellm_api import _completion_shape_metrics


def test_completion_shape_metrics_capture_reasoning_without_changing_text() -> None:
    metrics = _completion_shape_metrics(
        message={
            "reasoning_content": "internal reasoning",
        },
        usage={
            "completion_tokens_details": {
                "reasoning_tokens": 120,
            },
            "prompt_tokens_details": {
                "cached_tokens": 10,
            },
        },
        raw_completion="<think>abc</think>Visible answer",
        visible_completion="Visible answer",
        system_prompt="system",
        user_prompt="user evidence",
    )

    assert metrics["reasoning_tokens"] == 120
    assert metrics["reasoning_content_chars"] == len("internal reasoning")
    assert metrics["raw_completion_chars"] == len(
        "<think>abc</think>Visible answer"
    )
    assert metrics["visible_completion_chars"] == len("Visible answer")
    assert metrics["removed_thinking_chars"] > 0
    assert metrics["prompt_chars_total"] == len("system") + len("user evidence")


def test_completion_shape_metrics_tolerate_missing_provider_details() -> None:
    metrics = _completion_shape_metrics(
        message={},
        usage={},
        raw_completion="Answer",
        visible_completion="Answer",
        system_prompt="S",
        user_prompt="U",
    )

    assert metrics["reasoning_tokens"] is None
    assert metrics["completion_tokens_details"] is None
    assert metrics["prompt_tokens_details"] is None
    assert metrics["reasoning_content_chars"] == 0
    assert metrics["removed_thinking_chars"] == 0
