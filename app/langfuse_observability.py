from __future__ import annotations

import logging
import os
from typing import Any, Dict


logger = logging.getLogger(__name__)


def _enabled(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _configured() -> bool:
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    )


def start_generation_observation(
    *,
    system_prompt: str,
    user_prompt: str,
):
    """
    Start an optional Langfuse generation observation.

    HANS behaviour must never depend on Langfuse. If tracing is disabled,
    unconfigured, unavailable or temporarily failing, this returns None and
    generation continues unchanged.

    Raw student/prompt content is redacted by default. Set
    LANGFUSE_CAPTURE_CONTENT=true only in an approved environment.
    """
    if not _enabled("LANGFUSE_ENABLED", False):
        return None

    if not _configured():
        logger.warning(
            "LANGFUSE_ENABLED is true but Langfuse credentials are missing; "
            "continuing without external tracing."
        )
        return None

    try:
        from langfuse import get_client
    except Exception:
        logger.exception(
            "Langfuse SDK is unavailable; continuing without external tracing."
        )
        return None

    capture_content = _enabled(
        "LANGFUSE_CAPTURE_CONTENT",
        False,
    )

    if capture_content:
        trace_input: Dict[str, Any] = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }
    else:
        trace_input = {
            "content_redacted": True,
            "system_prompt_characters": len(system_prompt or ""),
            "user_prompt_characters": len(user_prompt or ""),
        }

    try:
        return get_client().start_observation(
            as_type="generation",
            name="hans-email-draft-generation",
            input=trace_input,
        )
    except Exception:
        logger.exception(
            "Langfuse trace start failed; continuing without external tracing."
        )
        return None


def finish_generation_observation(
    observation,
    *,
    output_text: str | None = None,
    metrics: Dict[str, Any] | None = None,
    metadata: Dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    if observation is None:
        return

    metrics = dict(metrics or {})
    metadata_payload = dict(metadata or {})

    if error:
        metadata_payload["error"] = error

    capture_content = _enabled(
        "LANGFUSE_CAPTURE_CONTENT",
        False,
    )

    if capture_content:
        trace_output: Any = output_text or ""
    else:
        trace_output = {
            "content_redacted": True,
            "output_characters": len(output_text or ""),
        }

    usage_details: Dict[str, int] = {}

    prompt_tokens = metrics.get("prompt_tokens")
    completion_tokens = metrics.get("completion_tokens")

    if isinstance(prompt_tokens, int):
        usage_details["input_tokens"] = prompt_tokens

    if isinstance(completion_tokens, int):
        usage_details["output_tokens"] = completion_tokens

    for key in (
        "provider",
        "generation_total_seconds",
        "model_total_seconds",
        "prompt_eval_seconds",
        "completion_eval_seconds",
    ):
        value = metrics.get(key)
        if value is not None:
            metadata_payload[key] = value

    update_kwargs: Dict[str, Any] = {
        "output": trace_output,
        "metadata": metadata_payload,
    }

    model = metrics.get("model")
    if model:
        update_kwargs["model"] = str(model)

    if usage_details:
        update_kwargs["usage_details"] = usage_details

    try:
        observation.update(**update_kwargs)
    except Exception:
        logger.exception(
            "Langfuse trace update failed; HANS result is unaffected."
        )
    finally:
        try:
            observation.end()
        except Exception:
            logger.exception(
                "Langfuse trace end failed; HANS result is unaffected."
            )
