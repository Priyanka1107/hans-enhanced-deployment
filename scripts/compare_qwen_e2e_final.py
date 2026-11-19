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


def _index(payload: dict) -> dict[str, dict]:
    return {
        str(item.get("test_case_id")): item
        for item in (payload.get("cases") or [])
    }


def _gen_seconds(item: dict):
    return (
        (item.get("generation_observability") or {})
        .get("generation_total_seconds")
    )


def _reasoning_tokens(item: dict):
    return (
        (item.get("generation_observability") or {})
        .get("reasoning_tokens")
    )


def main() -> int:
    current_path = _latest(
        "hans_e2e_acceptance_qwen-thinking-off-final-validation_*.json"
    )
    baseline_path = _latest(
        "hans_e2e_acceptance_baseline-final-candidate_*.json"
    )

    current = json.loads(
        current_path.read_text(encoding="utf-8")
    )
    baseline = json.loads(
        baseline_path.read_text(encoding="utf-8")
    )

    current_cases = _index(current)
    baseline_cases = _index(baseline)

    print("Baseline:", baseline_path)
    print("Thinking-off:", current_path)

    for case_id in sorted(current_cases):
        cur = current_cases[case_id]
        base = baseline_cases.get(case_id) or {}

        print("\n" + "=" * 88)
        print(case_id, "-", cur.get("name"))
        print("=" * 88)

        print(
            "Generation seconds:",
            "baseline=", _gen_seconds(base),
            "thinking_off=", _gen_seconds(cur),
        )
        print(
            "Reasoning tokens:",
            "baseline=", _reasoning_tokens(base),
            "thinking_off=", _reasoning_tokens(cur),
        )
        print(
            "Failure type:",
            "baseline=", (base.get("validation") or {}).get("failure_type"),
            "thinking_off=", (cur.get("validation") or {}).get("failure_type"),
        )
        print(
            "Quality:",
            "baseline=", base.get("quality"),
            "thinking_off=", cur.get("quality"),
        )

        print("\n--- BASELINE DRAFT ---\n")
        print(base.get("staff_draft") or "[No draft]")
        print("\n--- THINKING-OFF DRAFT ---\n")
        print(cur.get("staff_draft") or "[No draft]")
        print("\n--- END CASE ---")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
