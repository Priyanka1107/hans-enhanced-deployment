from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CORPUS_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "multimodel_corpus.json"
)

RESULTS_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
)


def load_corpus() -> dict:
    return json.loads(
        CORPUS_PATH.read_text(encoding="utf-8")
    )


def classify_case(case: dict) -> str:
    route = case["expected_route"]
    generation = case["expected_generation"]

    if route == "SKIP":
        return "HOP_SKIP"

    if route == "HANS" and generation is False:
        return "HANS_SAFETY_NO_GENERATION"

    if route == "HANS" and generation is True:
        return "HANS_MODEL_EVALUATION"

    raise RuntimeError(
        f"Unsupported case configuration: {case['case_id']}"
    )


def dry_run(data: dict) -> None:
    cases = data["cases"]

    print("=" * 100)
    print("HANS MULTIMODEL EVALUATION - DRY RUN")
    print("=" * 100)

    print("Corpus:", CORPUS_PATH)
    print("Version:", data.get("corpus_version"))
    print("Cases:", len(cases))
    print()

    model_cases = 0
    hans_safety_cases = 0
    hop_skip_cases = 0

    previous_thread = None

    for index, case in enumerate(cases, start=1):
        action = classify_case(case)

        if action == "HANS_MODEL_EVALUATION":
            model_cases += 1
        elif action == "HANS_SAFETY_NO_GENERATION":
            hans_safety_cases += 1
        elif action == "HOP_SKIP":
            hop_skip_cases += 1

        print(
            f"{index:02}. "
            f"{case['case_id']:35} "
            f"| {action}"
        )

        print(
            f"    language={case['language']} "
            f"thread={case['thread_id']} "
            f"sequence={case['sequence']}"
        )

        if case["scenario"] == "followup_sequence":
            if case["sequence"] == 2:
                if previous_thread != case["thread_id"]:
                    raise RuntimeError(
                        "Follow-up sequence is not contiguous."
                    )

        previous_thread = case["thread_id"]

    print()
    print("=" * 100)
    print("EXECUTION PLAN")
    print("=" * 100)

    print(
        "Normal model-comparison cases:",
        model_cases,
    )
    print(
        "HANS safety/no-generation cases:",
        hans_safety_cases,
    )
    print(
        "Hop-only SKIP cases:",
        hop_skip_cases,
    )

    print()
    print("DRY RUN: PASS")
    print("No HANS requests were sent.")
    print("No LLM requests were sent.")


def http_json(
    *,
    method: str,
    url: str,
    headers: dict | None = None,
    payload: dict | None = None,
    timeout: int = 300,
) -> tuple[int, dict]:
    body = None

    if payload is not None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

    request = Request(
        url=url,
        data=body,
        headers=headers or {},
        method=method,
    )

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw = response.read().decode("utf-8")

            return (
                response.status,
                json.loads(raw),
            )

    except HTTPError as exc:
        raw = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"HTTP {exc.code} from {url}: {raw}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"Could not reach {url}: {exc}"
        ) from exc


def safe_label(value: str) -> str:
    return re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        value.strip(),
    ).strip("-")


def generation_metrics_present(
    generation: dict,
) -> bool:
    metric_names = [
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "model_total_seconds",
        "load_seconds",
        "prompt_eval_seconds",
        "completion_eval_seconds",
        "generation_total_seconds",
    ]

    return any(
        generation.get(name) is not None
        for name in metric_names
    )


def execute(
    *,
    data: dict,
    label: str,
    expected_provider: str,
    expected_model: str,
) -> None:
    base_url = str(
        os.getenv(
            "HANS_API_URL",
            "http://127.0.0.1:8013",
        )
    ).rstrip("/")

    api_key = str(
        os.getenv(
            "HANS_INTERNAL_API_KEY",
            "",
        )
    ).strip()

    if not api_key:
        raise RuntimeError(
            "HANS_INTERNAL_API_KEY is not set."
        )

    print("=" * 100)
    print("HANS MULTIMODEL EVALUATION - EXECUTE")
    print("=" * 100)
    print("HANS API:", base_url)
    print("Run label:", label)
    print()

    health_status, health = http_json(
        method="GET",
        url=f"{base_url}/health",
        timeout=30,
    )

    if health_status != 200:
        raise RuntimeError(
            f"Health check returned HTTP {health_status}"
        )

    actual_provider = (
        health.get("generation_provider")
        or health.get("provider")
    )

    actual_model = (
        health.get("generation_model")
        or health.get("model")
    )

    print("Health: PASS")
    print("Provider:", actual_provider)
    print("Model:", actual_model)

    if actual_provider != expected_provider:
        raise RuntimeError(
            "Provider mismatch. "
            f"Expected {expected_provider!r}, "
            f"got {actual_provider!r}."
        )

    if actual_model != expected_model:
        raise RuntimeError(
            "Model mismatch. "
            f"Expected {expected_model!r}, "
            f"got {actual_model!r}."
        )

    run_started = datetime.now(
        timezone.utc
    ).isoformat()

    results = []

    headers = {
        "Content-Type": "application/json",
        "X-HANS-API-Key": api_key,
    }

    cases = data["cases"]

    for index, case in enumerate(
        cases,
        start=1,
    ):
        action = classify_case(case)

        print()
        print("-" * 100)
        print(
            f"{index:02}/{len(cases):02} "
            f"{case['case_id']} "
            f"[{action}]"
        )
        print("-" * 100)

        base_result = {
            "case_id": case["case_id"],
            "scenario": case["scenario"],
            "sequence": case["sequence"],
            "language": case["language"],
            "expected_route": case[
                "expected_route"
            ],
            "expected_generation": case[
                "expected_generation"
            ],
            "expected_programme": case.get(
                "expected_programme"
            ),
            "expected_topics": case.get(
                "expected_topics",
                [],
            ),
            "execution_action": action,
        }

        if action == "HOP_SKIP":
            print(
                "Not sent to HANS by design "
                "(Hop-only routing case)."
            )

            base_result.update(
                {
                    "hans_request_sent": False,
                    "http_status": None,
                    "api_elapsed_seconds": None,
                    "response": None,
                }
            )

            results.append(base_result)
            continue

        request_payload = {
            "email_text": case["email_text"],
            "student_email": case["student_email"],
            "subject": case["subject"],
            "thread_id": case["thread_id"],
            "email_id": case["email_id"],
            "language": case["language"],
            "top_k": case["top_k"],
        }

        start = time.perf_counter()

        status, response = http_json(
            method="POST",
            url=f"{base_url}/v1/drafts",
            headers=headers,
            payload=request_payload,
            timeout=300,
        )

        elapsed = round(
            time.perf_counter() - start,
            3,
        )

        generation = (
            response
            .get("observability", {})
            .get("generation", {})
            or {}
        )

        validation = (
            response.get("validation")
            or {}
        )

        quality = (
            response.get("quality")
            or {}
        )

        context = (
            response.get("email_context")
            or {}
        )

        topics = [
            str(
                item.get("topic_id")
                or ""
            )
            for item in response.get(
                "detected_topics",
                [],
            )
        ]

        metrics_present = (
            generation_metrics_present(
                generation
            )
        )

        print("HTTP status:", status)
        print("Elapsed seconds:", elapsed)
        print(
            "Programme:",
            context.get(
                "target_program"
            )
            or context.get(
                "target_programme"
            )
            or context.get(
                "matched_programme"
            ),
        )
        print("Topics:", topics)
        print(
            "Generation metrics present:",
            metrics_present,
        )
        print(
            "Total tokens:",
            generation.get(
                "total_tokens"
            ),
        )
        print(
            "Generation seconds:",
            generation.get(
                "generation_total_seconds"
            ),
        )

        base_result.update(
            {
                "hans_request_sent": True,
                "http_status": status,
                "api_elapsed_seconds": elapsed,
                "actual_programme": (
                    context.get("target_program")
                    or context.get(
                        "target_programme"
                    )
                    or context.get(
                        "matched_programme"
                    )
                ),
                "actual_programme_status": (
                    context.get(
                        "programme_status"
                    )
                    or response.get(
                        "programme_status"
                    )
                ),
                "actual_topics": topics,
                "generation_metrics_present": (
                    metrics_present
                ),
                "provider": generation.get(
                    "provider"
                ),
                "model": generation.get(
                    "model"
                ),
                "prompt_tokens": generation.get(
                    "prompt_tokens"
                ),
                "completion_tokens": generation.get(
                    "completion_tokens"
                ),
                "total_tokens": generation.get(
                    "total_tokens"
                ),
                "model_total_seconds": (
                    generation.get(
                        "model_total_seconds"
                    )
                ),
                "load_seconds": generation.get(
                    "load_seconds"
                ),
                "prompt_eval_seconds": (
                    generation.get(
                        "prompt_eval_seconds"
                    )
                ),
                "completion_eval_seconds": (
                    generation.get(
                        "completion_eval_seconds"
                    )
                ),
                "generation_total_seconds": (
                    generation.get(
                        "generation_total_seconds"
                    )
                ),
                "is_grounded": validation.get(
                    "is_grounded"
                ),
                "citations_valid": validation.get(
                    "citations_valid"
                ),
                "has_hallucinations": (
                    validation.get(
                        "has_hallucinations"
                    )
                ),
                "validation_failure_type": (
                    validation.get(
                        "failure_type"
                    )
                ),
                "quality_score": quality.get(
                    "quality_score"
                ),
                "quality_label": quality.get(
                    "quality_label"
                ),
                "review_required": quality.get(
                    "review_required"
                ),
                "automatic_send": response.get(
                    "automatic_send"
                ),
                "staff_draft": response.get(
                    "staff_draft"
                ),
                "sources": response.get(
                    "sources",
                    [],
                ),
                "response": response,
            }
        )

        results.append(base_result)

    run_finished = datetime.now(
        timezone.utc
    ).isoformat()

    output = {
        "run_metadata": {
            "label": label,
            "corpus_version": data.get(
                "corpus_version"
            ),
            "corpus_case_count": len(cases),
            "started_at_utc": run_started,
            "finished_at_utc": run_finished,
            "hans_api_url": base_url,
            "expected_provider": (
                expected_provider
            ),
            "expected_model": (
                expected_model
            ),
            "health": health,
        },
        "results": results,
    }

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        safe_label(label)
        + ".json"
    )

    output_path = (
        RESULTS_DIR
        / filename
    )

    output_path.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 100)
    print("EVALUATION RUN COMPLETE")
    print("=" * 100)
    print("Results:", output_path)
    print("Cases recorded:", len(results))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen HANS multimodel "
            "evaluation corpus."
        )
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually send HANS API requests. "
            "Without this flag, only a dry run "
            "is performed."
        ),
    )

    parser.add_argument(
        "--label",
        default="",
        help="Unique result label for an execution run.",
    )

    parser.add_argument(
        "--expected-provider",
        default="",
    )

    parser.add_argument(
        "--expected-model",
        default="",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_corpus()

    if not args.execute:
        dry_run(data)
        return

    if not args.label:
        raise RuntimeError(
            "--label is required with --execute."
        )

    if not args.expected_provider:
        raise RuntimeError(
            "--expected-provider is required "
            "with --execute."
        )

    if not args.expected_model:
        raise RuntimeError(
            "--expected-model is required "
            "with --execute."
        )

    execute(
        data=data,
        label=args.label,
        expected_provider=args.expected_provider,
        expected_model=args.expected_model,
    )


if __name__ == "__main__":
    main()
