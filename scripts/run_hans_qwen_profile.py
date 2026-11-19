from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

API_BASE = os.getenv(
    "HANS_UI_API_URL",
    os.getenv("HANS_API_BASE", "http://127.0.0.1:8009"),
).rstrip("/")
API_KEY = os.getenv("HANS_INTERNAL_API_KEY", "").strip()
CASES_PATH = ROOT / "evaluation" / "qwen_runtime_profile_cases.json"
RESULTS_DIR = ROOT / "evaluation" / "results"
PROFILE_LABEL = os.getenv(
    "HANS_QWEN_PROFILE_LABEL",
    "provider-default-thinking",
).strip() or "provider-default-thinking"
CASE_FILTER = {
    value.strip()
    for value in os.getenv("HANS_QWEN_PROFILE_CASES", "").split(",")
    if value.strip()
}


def _rate(tokens, seconds):
    if not isinstance(tokens, int) or not seconds:
        return None
    return round(tokens / float(seconds), 3)


def main() -> int:
    if not API_KEY:
        raise RuntimeError("HANS_INTERNAL_API_KEY is not configured in .env")

    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []

    if CASE_FILTER:
        cases = [
            case for case in cases
            if str(case.get("test_case_id") or "") in CASE_FILTER
        ]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_results = []

    for case in cases:
        case_id = str(case["test_case_id"])
        print(f"\n=== {case_id}: {case['name']} ===")

        request_payload = {
            "email_text": case["email_text"],
            "student_email": case.get("student_email"),
            "subject": case.get("subject"),
            "thread_id": f"profile-{case_id.lower()}-{uuid.uuid4().hex[:8]}",
            "email_id": f"profile-email-{uuid.uuid4().hex[:8]}",
            "language": case.get("language"),
            "top_k": int(case.get("top_k") or 6),
        }

        started = time.perf_counter()
        try:
            response = requests.post(
                f"{API_BASE}/email",
                headers={"X-HANS-API-Key": API_KEY},
                json=request_payload,
                timeout=720,
            )
            client_seconds = round(time.perf_counter() - started, 3)
            response.raise_for_status()
            result = response.json()

            generation = (
                result.get("observability", {})
                .get("generation", {})
            )
            timing = result.get("timing") or {}
            topics = result.get("detected_topics") or []
            draft = result.get("staff_draft") or ""
            generation_seconds = generation.get("generation_total_seconds")
            completion_tokens = generation.get("completion_tokens")

            topic_source_counts = [
                {
                    "topic_id": str(topic.get("topic_id") or ""),
                    "official_source_count": topic.get("official_source_count"),
                    "retrieved_source_count": topic.get("retrieved_source_count"),
                    "selected_source_count": topic.get("source_count"),
                }
                for topic in topics
                if isinstance(topic, dict)
            ]

            summary = {
                "test_case_id": case_id,
                "group": case.get("group"),
                "name": case.get("name"),
                "historical_reference": case.get("historical_reference"),
                "detected_topics": [
                    str(topic.get("topic_id") or "")
                    for topic in topics
                    if isinstance(topic, dict)
                ],
                "topic_source_counts": topic_source_counts,
                "final_source_count_returned": len(result.get("sources") or []),
                "generation_observability": generation,
                "generation_tokens_per_second": _rate(
                    completion_tokens,
                    generation_seconds,
                ),
                "timing": timing,
                "client_total_seconds": client_seconds,
                "validation": result.get("validation") or {},
                "quality": result.get("quality") or {},
                "draft_chars": len(draft),
                "draft_words": len(draft.split()),
                "staff_draft": draft,
                "automatic_send": result.get("automatic_send"),
            }

            print("Topics:", ", ".join(summary["detected_topics"]) or "none")
            print(
                "Sources:",
                generation.get("final_document_count"),
                "final docs to generation;",
                len(result.get("sources") or []),
                "returned to staff UI",
            )
            print(
                "Tokens:",
                "input=", generation.get("prompt_tokens"),
                "output=", generation.get("completion_tokens"),
                "reasoning=", generation.get("reasoning_tokens"),
                "total=", generation.get("total_tokens"),
            )
            print(
                "Prompt chars:",
                generation.get("prompt_chars_total"),
                "| raw completion chars:",
                generation.get("raw_completion_chars"),
                "| visible completion chars:",
                generation.get("visible_completion_chars"),
                "| removed thinking chars:",
                generation.get("removed_thinking_chars"),
                "| separate reasoning chars:",
                generation.get("reasoning_content_chars"),
            )
            print(
                "Generation:",
                generation_seconds,
                "seconds | output tokens/sec:",
                summary["generation_tokens_per_second"],
            )
            if case.get("historical_reference"):
                print(
                    "Historical reference:",
                    case["historical_reference"],
                )

        except Exception as exc:
            summary = {
                "test_case_id": case_id,
                "group": case.get("group"),
                "name": case.get("name"),
                "error": str(exc),
            }
            print("FAILED:", exc)

        run_results.append(summary)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = (
        RESULTS_DIR
        / f"qwen_runtime_profile_{PROFILE_LABEL}_{timestamp}.json"
    )
    output_path.write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(),
                "api_base": API_BASE,
                "profile_label": PROFILE_LABEL,
                "case_filter": sorted(CASE_FILTER),
                "cases": run_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved Qwen profile result: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
