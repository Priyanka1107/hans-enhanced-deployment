from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CORPUS_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "multimodel_corpus.json"
)


def main() -> None:
    data = json.loads(
        CORPUS_PATH.read_text(encoding="utf-8")
    )

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
        route = case["expected_route"]
        generation = case["expected_generation"]

        if route == "SKIP":
            action = "HOP_SKIP"
            hop_skip_cases += 1

        elif route == "HANS" and generation is False:
            action = "HANS_SAFETY_NO_GENERATION"
            hans_safety_cases += 1

        elif route == "HANS" and generation is True:
            action = "HANS_MODEL_EVALUATION"
            model_cases += 1

        else:
            raise RuntimeError(
                f"Unsupported case configuration: "
                f"{case['case_id']}"
            )

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


if __name__ == "__main__":
    main()
