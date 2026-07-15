from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "runtime_data"
    / "evaluation"
    / "ui_runs"
)


def _enabled() -> bool:
    return os.getenv(
        "HANS_UI_EVAL_LOGGING",
        "false",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _safe_name(value: str) -> str:
    cleaned = re.sub(
        r"[^a-zA-Z0-9_.-]+",
        "-",
        str(value or "").strip(),
    ).strip("-")

    return cleaned or "ui-test"


def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return [
            _json_safe(item)
            for item in value
        ]

    if hasattr(value, "model_dump"):
        return _json_safe(
            value.model_dump()
        )

    if hasattr(value, "dict"):
        return _json_safe(
            value.dict()
        )

    return str(value)


def save_ui_evaluation_run(
    *,
    test_case_id: str,
    request_payload: Mapping[str, Any],
    response_payload: Mapping[str, Any] | None = None,
    error: str | None = None,
) -> Path | None:
    """
    Save one synthetic UI evaluation run.

    Logging is disabled unless HANS_UI_EVAL_LOGGING=true.
    Authentication headers and API keys must never be passed here.
    """
    if not _enabled():
        return None

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(
        timezone.utc
    )

    run_id = (
        f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
        f"-{uuid.uuid4().hex[:8]}"
    )

    record = {
        "run_id": run_id,
        "timestamp_utc": timestamp.isoformat(),
        "test_case_id": test_case_id,
        "request": _json_safe(
            dict(request_payload)
        ),
        "response": _json_safe(
            dict(response_payload or {})
        ),
        "error": error,
    }

    filename = (
        f"{_safe_name(test_case_id)}"
        f"-{run_id}.json"
    )

    run_path = OUTPUT_DIR / filename

    run_path.write_text(
        json.dumps(
            record,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    jsonl_path = (
        OUTPUT_DIR / "ui_runs.jsonl"
    )

    with jsonl_path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )

    return run_path
