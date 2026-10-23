from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4
import sys

# Allow this script to be run directly from the repository root on Windows:
#     python scripts\run_token_efficiency_study.py ...
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg

from app.email.service import EmailAssistantService
from app.langfuse_observability import flush_langfuse
from app.settings import settings


DUAL_CITIZEN_EMAIL = """Dear Admissions Team,

I am a dual citizen (French and Moroccan), currently residing in Morocco and holding a French Baccalauréat diploma.

I want to apply for the English-taught Bachelor’s programme in International Business but am unsure whether I should apply as an EU applicant or international.

Also, would my French diploma fulfill the general university entrance requirements, or would I need to obtain a VPD from Uni-Assist?

Kind regards
"""

SUBJECT = "Business Bachelor application route and diploma recognition"


K_SWEEP = [
    {
        "label": "k_exact_6",
        "requested_top_k": 6,
        "allow_exact_top_k": True,
        "dedupe_urls": False,
        "evidence_char_limit": 1800,
    },
    {
        "label": "k_exact_5",
        "requested_top_k": 5,
        "allow_exact_top_k": True,
        "dedupe_urls": False,
        "evidence_char_limit": 1800,
    },
    {
        "label": "k_exact_4",
        "requested_top_k": 4,
        "allow_exact_top_k": True,
        "dedupe_urls": False,
        "evidence_char_limit": 1800,
    },
    {
        "label": "k_exact_3",
        "requested_top_k": 3,
        "allow_exact_top_k": True,
        "dedupe_urls": False,
        "evidence_char_limit": 1800,
    },
]


PROMPT_VARIANTS = [
    {
        "label": "control_1800",
        "requested_top_k": 6,
        "allow_exact_top_k": False,
        "dedupe_urls": False,
        "evidence_char_limit": 1800,
    },
    {
        "label": "dedupe_1800",
        "requested_top_k": 6,
        "allow_exact_top_k": False,
        "dedupe_urls": True,
        "evidence_char_limit": 1800,
    },
    {
        "label": "compact_1200",
        "requested_top_k": 6,
        "allow_exact_top_k": False,
        "dedupe_urls": False,
        "evidence_char_limit": 1200,
    },
    {
        "label": "compact_dedupe_1200",
        "requested_top_k": 6,
        "allow_exact_top_k": False,
        "dedupe_urls": True,
        "evidence_char_limit": 1200,
    },
]


def _set_variant_environment(variant: Dict[str, Any]) -> None:
    os.environ["HANS_EXPERIMENT_MODE"] = "true"
    os.environ["HANS_EXPERIMENT_LABEL"] = str(variant["label"])
    os.environ["HANS_EXPERIMENT_ALLOW_EXACT_TOP_K"] = (
        "true" if variant["allow_exact_top_k"] else "false"
    )
    os.environ["HANS_EXPERIMENT_DEDUPE_URLS"] = (
        "true" if variant["dedupe_urls"] else "false"
    )
    os.environ["HANS_EXPERIMENT_EVIDENCE_CHAR_LIMIT"] = str(
        int(variant["evidence_char_limit"])
    )


def _result_row(
    *,
    phase: str,
    variant: Dict[str, Any],
    repeat_index: int,
    response: Dict[str, Any],
) -> Dict[str, Any]:
    generation = (
        response.get("observability", {})
        .get("generation", {})
        or {}
    )
    experiment = (
        response.get("observability", {})
        .get("experiment", {})
        or {}
    )
    validation = response.get("validation", {}) or {}
    quality = response.get("quality", {}) or {}
    timing = response.get("timing", {}) or {}

    row = {
        "phase": phase,
        "variant": variant["label"],
        "repeat": repeat_index,
        "requested_top_k": variant["requested_top_k"],
        "effective_top_k_by_topic": json.dumps(
            experiment.get("effective_top_k_by_topic", {}),
            sort_keys=True,
        ),
        "evidence_char_limit": experiment.get(
            "evidence_char_limit"
        ),
        "dedupe_urls": experiment.get("dedupe_urls"),
        "final_source_count": experiment.get(
            "final_source_count",
            len(response.get("sources", []) or []),
        ),
        "prompt_tokens": generation.get("prompt_tokens"),
        "completion_tokens": generation.get("completion_tokens"),
        "total_tokens": generation.get("total_tokens"),
        "retrieval_seconds": round(
            float(timing.get("retrieval", 0.0)),
            3,
        ),
        "generation_seconds": generation.get(
            "generation_total_seconds"
        ),
        "total_seconds": round(
            float(timing.get("total", 0.0)),
            3,
        ),
        "grounded": validation.get("is_grounded"),
        "citations_valid": validation.get("citations_valid"),
        "hallucinations_detected": validation.get(
            "has_hallucinations"
        ),
        "failure_type": validation.get("failure_type"),
        "quality_score": quality.get("quality_score"),
        "quality_label": quality.get("quality_label"),
        "review_reason": quality.get("review_reason"),
        "citation_count": quality.get("citation_count"),
        "topic_ids": json.dumps(
            [
                str(topic.get("topic_id") or "")
                for topic in response.get("detected_topics", [])
            ]
        ),
    }

    # Local-only review material. This is written to a separate JSON file
    # and is never added to Langfuse metadata/content.
    row["_review_detail"] = {
        "staff_draft": str(response.get("staff_draft") or ""),
        "sources": [
            {
                "title": str(source.get("title") or ""),
                "url": str(
                    source.get("source_url")
                    or source.get("url")
                    or ""
                ),
            }
            for source in (response.get("sources", []) or [])
        ],
    }

    return row


async def _run_variant(
    *,
    service: EmailAssistantService,
    phase: str,
    variant: Dict[str, Any],
    repeat_index: int,
) -> Dict[str, Any]:
    _set_variant_environment(variant)

    unique = uuid4().hex

    response = await service.process_email(
        email_text=DUAL_CITIZEN_EMAIL,
        student_email=f"dual.citizen.{unique}@example.invalid",
        subject=SUBJECT,
        thread_id=f"TOKEN-STUDY-{unique}",
        email_id=f"TOKEN-STUDY-{unique}",
        language="en",
        top_k=int(variant["requested_top_k"]),
    )

    return _result_row(
        phase=phase,
        variant=variant,
        repeat_index=repeat_index,
        response=response,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the isolated HANS dual-citizen token-efficiency study."
        )
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Repeated runs per variant; use 3+ for variance analysis.",
    )
    parser.add_argument(
        "--phase",
        choices=("all", "k-sweep", "prompt-variants"),
        default="all",
    )
    parser.add_argument(
        "--variant",
        choices=[
            variant["label"]
            for variant in (K_SWEEP + PROMPT_VARIANTS)
        ],
        default=None,
        help=(
            "Optional single variant label. Useful for a one-call "
            "human-review capture without running the whole phase."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="evaluation_outputs/token_efficiency",
    )
    args = parser.parse_args()

    repeats = max(1, int(args.repeats))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plan: List[tuple[str, Dict[str, Any]]] = []

    if args.phase in {"all", "k-sweep"}:
        plan.extend(("k_sweep", variant) for variant in K_SWEEP)

    if args.phase in {"all", "prompt-variants"}:
        plan.extend(
            ("prompt_variants", variant)
            for variant in PROMPT_VARIANTS
        )

    if args.variant:
        plan = [
            (phase, variant)
            for phase, variant in plan
            if variant["label"] == args.variant
        ]

        if not plan:
            raise SystemExit(
                f"Variant {args.variant!r} is not part of phase {args.phase!r}."
            )

    rows: List[Dict[str, Any]] = []

    with psycopg.connect(settings.database_url) as connection:
        service = EmailAssistantService(connection)

        for phase, variant in plan:
            for repeat_index in range(1, repeats + 1):
                print(
                    f"Running {phase}: {variant['label']} "
                    f"(repeat {repeat_index}/{repeats})"
                )

                try:
                    row = await _run_variant(
                        service=service,
                        phase=phase,
                        variant=variant,
                        repeat_index=repeat_index,
                    )
                except Exception as exc:
                    row = {
                        "phase": phase,
                        "variant": variant["label"],
                        "repeat": repeat_index,
                        "requested_top_k": variant[
                            "requested_top_k"
                        ],
                        "evidence_char_limit": variant[
                            "evidence_char_limit"
                        ],
                        "dedupe_urls": variant["dedupe_urls"],
                        "error": str(exc),
                    }

                rows.append(row)
                print(json.dumps(row, indent=2, ensure_ascii=False))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"dual_citizen_token_study_{stamp}.json"
    csv_path = output_dir / f"dual_citizen_token_study_{stamp}.csv"
    details_path = (
        output_dir
        / f"dual_citizen_token_study_{stamp}_review_details.json"
    )

    metrics_rows: List[Dict[str, Any]] = []
    review_details: List[Dict[str, Any]] = []

    for row in rows:
        metrics_row = {
            key: value
            for key, value in row.items()
            if key != "_review_detail"
        }
        metrics_rows.append(metrics_row)

        review_detail = row.get("_review_detail")
        if review_detail:
            review_details.append(
                {
                    "phase": row.get("phase"),
                    "variant": row.get("variant"),
                    "repeat": row.get("repeat"),
                    **dict(review_detail),
                }
            )

    json_path.write_text(
        json.dumps(metrics_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    details_path.write_text(
        json.dumps(review_details, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    fieldnames = sorted(
        {
            key
            for row in metrics_rows
            for key in row.keys()
        }
    )

    with csv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(metrics_rows)

    flush_langfuse()

    print()
    print(f"JSON:    {json_path}")
    print(f"CSV:     {csv_path}")
    print(f"DETAILS: {details_path}")


if __name__ == "__main__":
    asyncio.run(main())
