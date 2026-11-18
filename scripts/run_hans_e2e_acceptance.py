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
CASES_PATH = ROOT / "evaluation" / "e2e_acceptance_cases.json"
RESULTS_DIR = ROOT / "evaluation" / "results"

E2E_TOP_K_OVERRIDE = os.getenv(
    "HANS_E2E_TOP_K",
    "",
).strip()
E2E_PROFILE = os.getenv(
    "HANS_E2E_PROFILE",
    "default",
).strip() or "default"

E2E_CASE_FILTER = {
    value.strip()
    for value in os.getenv(
        "HANS_E2E_CASES",
        "",
    ).split(",")
    if value.strip()
}


def main() -> int:
    if not API_KEY:
        raise RuntimeError(
            "HANS_INTERNAL_API_KEY is not configured in .env"
        )

    payload = json.loads(
        CASES_PATH.read_text(encoding="utf-8")
    )
    cases = payload.get("cases") or []

    if E2E_CASE_FILTER:
        cases = [
            case
            for case in cases
            if str(
                case.get("test_case_id") or ""
            ) in E2E_CASE_FILTER
        ]

        missing_case_ids = (
            E2E_CASE_FILTER
            - {
                str(
                    case.get("test_case_id")
                    or ""
                )
                for case in cases
            }
        )

        if missing_case_ids:
            raise RuntimeError(
                "Unknown HANS E2E case ID(s): "
                + ", ".join(
                    sorted(missing_case_ids)
                )
            )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_results = []

    for case in cases:
        case_id = str(case["test_case_id"])
        print(f"\n=== {case_id}: {case['name']} ===")

        request_payload = {
            "email_text": case["email_text"],
            "student_email": case.get("student_email"),
            "subject": case.get("subject"),
            "thread_id": (
                f"e2e-{case_id.lower()}-{uuid.uuid4().hex[:8]}"
            ),
            "email_id": (
                f"e2e-email-{uuid.uuid4().hex[:8]}"
            ),
            "language": case.get("language"),
            "top_k": (
                int(E2E_TOP_K_OVERRIDE)
                if E2E_TOP_K_OVERRIDE
                else int(case.get("top_k") or 6)
            ),
        }

        started = time.perf_counter()
        try:
            response = requests.post(
                f"{API_BASE}/email",
                headers={
                    "X-HANS-API-Key": API_KEY,
                },
                json=request_payload,
                timeout=720,
            )
            client_seconds = round(
                time.perf_counter() - started,
                3,
            )
            response.raise_for_status()
            result = response.json()

            detected_topics = [
                str(
                    topic.get("topic_id")
                    or ""
                )
                for topic in (
                    result.get("detected_topics")
                    or []
                )
                if isinstance(topic, dict)
            ]
            expected_topics = [
                str(value)
                for value in (
                    case.get("expected_topics")
                    or []
                )
            ]
            missing_expected_topics = [
                value
                for value in expected_topics
                if value not in detected_topics
            ]

            generation = (
                result.get("observability", {})
                .get("generation", {})
            )
            timing = result.get("timing") or {}
            quality = result.get("quality") or {}
            validation = result.get("validation") or {}

            summary = {
                "test_case_id": case_id,
                "name": case["name"],
                "purpose": case["purpose"],
                "hard_checks": {
                    "http_success": True,
                    "automatic_send_false": (
                        result.get("automatic_send") is False
                    ),
                    "expected_topics_detected": (
                        not missing_expected_topics
                    ),
                    "missing_expected_topics": (
                        missing_expected_topics
                    ),
                },
                "detected_topics": detected_topics,
                "validation": validation,
                "quality": quality,
                "source_count": len(
                    result.get("sources") or []
                ),
                "sources": result.get("sources") or [],
                "timing": timing,
                "client_total_seconds": client_seconds,
                "generation_observability": generation,
                "staff_draft": result.get("staff_draft") or "",
                "manual_review": {
                    "all_questions_answered": None,
                    "indicators_match_draft": None,
                    "sources_are_applicable": None,
                    "citations_support_claims": None,
                    "draft_is_staff_ready": None,
                    "notes": "",
                },
            }

            print(
                "Detected topics:",
                ", ".join(detected_topics) or "none",
            )
            print(
                "Failure type:",
                validation.get("failure_type"),
            )
            print(
                "Review reason:",
                quality.get("review_reason"),
            )
            print(
                "Service timing:",
                timing,
            )
            print(
                "Generation:",
                generation.get(
                    "generation_total_seconds"
                ),
                "seconds",
            )
            print(
                "Client total:",
                client_seconds,
                "seconds",
            )

        except Exception as exc:
            summary = {
                "test_case_id": case_id,
                "name": case.get("name"),
                "purpose": case.get("purpose"),
                "hard_checks": {
                    "http_success": False,
                },
                "error": str(exc),
            }
            print("FAILED:", exc)

        run_results.append(summary)

    timestamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )
    output_path = (
        RESULTS_DIR
        / (
            f"hans_e2e_acceptance_{E2E_PROFILE}_{timestamp}.json"
        )
    )

    output_path.write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(),
                "api_base": API_BASE,
                "profile": E2E_PROFILE,
                "requested_top_k_override": (
                    int(E2E_TOP_K_OVERRIDE)
                    if E2E_TOP_K_OVERRIDE
                    else None
                ),
                "case_filter": sorted(E2E_CASE_FILTER),
                "cases": run_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nSaved E2E result: {output_path}")

    hard_failures = [
        result
        for result in run_results
        if (
            not result.get("hard_checks", {}).get(
                "http_success",
                False,
            )
            or not result.get("hard_checks", {}).get(
                "automatic_send_false",
                False,
            )
            or not result.get("hard_checks", {}).get(
                "expected_topics_detected",
                False,
            )
        )
    ]

    print(
        f"Hard-check result: "
        f"{len(run_results) - len(hard_failures)}/"
        f"{len(run_results)} cases passed"
    )

    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
