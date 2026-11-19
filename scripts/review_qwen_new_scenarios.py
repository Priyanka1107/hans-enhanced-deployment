from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "evaluation" / "results"
PATTERN = "qwen_runtime_profile_qwen-thinking-off-new-scenarios_*.json"


def main() -> int:
    matches = sorted(
        RESULTS_DIR.glob(PATTERN),
        key=lambda path: path.stat().st_mtime,
    )
    if not matches:
        raise FileNotFoundError(
            f"No result file matched {PATTERN!r} in {RESULTS_DIR}"
        )

    path = matches[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))

    print("Result:", path)

    for item in payload.get("cases") or []:
        print("\n" + "=" * 78)
        print(item.get("test_case_id"))
        print(item.get("name"))
        print("=" * 78)
        print("Detected topics:", item.get("detected_topics"))
        print("Topic source counts:", item.get("topic_source_counts"))
        print(
            "Final sources:",
            item.get("final_source_count_returned"),
        )
        print(
            "Generation observability:",
            item.get("generation_observability"),
        )
        print("Validation:", item.get("validation"))
        print("Quality:", item.get("quality"))
        print("Automatic send:", item.get("automatic_send"))
        print("\n--- STAFF DRAFT ---\n")
        draft = item.get("staff_draft")
        if draft:
            print(draft)
        else:
            print("[No staff draft generated]")
        print("\n--- END DRAFT ---")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
