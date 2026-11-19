from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "evaluation" / "results"


def _latest(pattern: str) -> Path:
    matches = sorted(
        RESULTS_DIR.glob(pattern),
        key=lambda path: path.stat().st_mtime,
    )
    if not matches:
        raise FileNotFoundError(
            f"No result file matched {pattern!r} in {RESULTS_DIR}"
        )
    return matches[-1]


def _case(payload: dict, case_id: str) -> dict:
    for item in payload.get("cases") or []:
        if item.get("test_case_id") == case_id:
            return item
    raise KeyError(f"Case {case_id!r} not found")


def _summary(label: str, item: dict) -> None:
    generation = item.get("generation_observability") or {}
    print(f"\n=== {label} ===")
    print("Sources:", item.get("final_source_count_returned"))
    print(
        "Tokens:",
        "input=", generation.get("prompt_tokens"),
        "output=", generation.get("completion_tokens"),
        "reasoning=", generation.get("reasoning_tokens"),
        "total=", generation.get("total_tokens"),
    )
    print(
        "Generation seconds:",
        generation.get("generation_total_seconds"),
    )
    print("Validation:", item.get("validation"))
    print("Quality:", item.get("quality"))
    print("Draft words:", item.get("draft_words"))
    print("\n--- STAFF DRAFT ---\n")
    print(item.get("staff_draft") or "")
    print("\n--- END DRAFT ---")


def main() -> int:
    case_id = "PROFILE-CONTROL-MM008-DUAL-CITIZEN"

    default_path = _latest(
        "qwen_runtime_profile_qwen-default-controls_*.json"
    )
    off_path = _latest(
        "qwen_runtime_profile_qwen-thinking-off-control-real_*.json"
    )

    default_payload = json.loads(
        default_path.read_text(encoding="utf-8")
    )
    off_payload = json.loads(
        off_path.read_text(encoding="utf-8")
    )

    print("Default result:", default_path)
    print("Thinking-off result:", off_path)

    _summary(
        "QWEN PROVIDER DEFAULT",
        _case(default_payload, case_id),
    )
    _summary(
        "QWEN THINKING OFF",
        _case(off_payload, case_id),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
