# HANS Model Comparison and Token Measurement

## Scope and evidence

This records the September model test paths and the measurement convention for the **self-hosted transfer/current implementation**. It does not retroactively assign token instrumentation to the separate baseline copy or Enhanced PoC. The eight-case corpus version was `2026-09-21`, and the recorded endpoint was `http://127.0.0.1:8013`. The result files below are the primary evidence; automated scores are diagnostic and manual review determines whether a staff draft is usable.

| Recorded path | Provider and model reported by HANS | Run artefact | Generation result |
|---|---|---|---|
| Local Llama, initial | `htw_ollama`, `llama3.1:8b` | `evaluation/results/llama31-8b-baseline-2026-09-22.json` | Five LLM generations; MM-002 and MM-008 took deterministic clarification paths; MM-006 was skipped by Hop |
| Local Mistral | `htw_ollama`, `mistral:latest` | `evaluation/results/mistral-local-baseline-2026-09-23.json` | Same five generation cases; MM-008 still took a deterministic clarification path |
| Mistral Small API | `mistral_api`, `mistral-small-latest` | `evaluation/results/mistral-small-api-baseline-2026-09-23.json` | Same five generation cases; MM-008 still took a deterministic clarification path |
| Mistral Large API | `mistral_api`, `mistral-large-latest` | `evaluation/results/mistral-large-api-baseline-2026-09-23.json` | Same five generation cases; MM-008 still took a deterministic clarification path |
| Local Llama, final RC1 | `htw_ollama`, `llama3.1:8b` | `evaluation/results/llama31-8b-final-rc1-0e4219c-2026-09-25.json` | Six LLM generations including MM-008 after backend quality hardening; MM-002 deterministic; MM-006 Hop skip |

The final RC1 artefact was committed at `9fee966` on `fix/2026-09-23-final-quality-hardening`; backend quality checkpoint `0e4219c` was used for that run. The tested application/UI reference is `6dafee6`; the later `251fddf` commit was repository hygiene, not a new behaviour test. The model labels identify the configured endpoint/model alias at run time; `mistral:latest` and `*-latest` are not pinned immutable model revisions in these artefacts.

## What the comparison supports

For the five cases with generation metrics in all four initial runs (MM-001, MM-003, MM-004, MM-005, MM-007), the recorded mean generation times were 42.79 s for initial local Llama, 41.19 s for local Mistral, 1.94 s for Mistral Small API, and 4.89 s for Mistral Large API. These are descriptive timings from single runs, not a latency benchmark or a quality ranking. Provider token counts, prompt serialization, service load, generation variability and later code changes can affect comparisons. MM-008 is especially unsuitable for a model-only comparison because the earlier runs stopped at unknown-programme clarification, whereas the final RC1 path generated a route/recognition draft. The final acceptance classification belongs only to the final RC1 run.

The Mistral paths show an implemented local alternative and two external API comparison options. The demonstrated final Gmail Draft workflow used local Llama 3.1 8B, not Mistral. Earlier Enhanced PoC Claude/Mistral tests used Cohere/Qdrant and must also remain separate from this BGE/pgvector test series.

## Token measurement protocol for the current system

1. Record one row per corpus case with run label, corpus version, case ID, execution action, provider, model, `prompt_tokens`, `completion_tokens`, `total_tokens`, `model_total_seconds`, `generation_total_seconds`, and request elapsed time where returned.
2. Use the token/timing values exposed by the configured HANS generation response and preserved in the evaluation JSON. In each recorded LLM case, `total_tokens = prompt_tokens + completion_tokens`. These are model/provider-reported usage fields as surfaced by HANS; the provided run files do not independently verify the tokenizer or provider accounting implementation.
3. Leave generation fields null for deterministic no-generation and Hop-skip cases. A null value is **not zero tokens** and must not be included in averages over generated cases.
4. Keep `model_total_seconds`, `generation_total_seconds`, and API/request elapsed time distinct. They measure different spans and must be labelled separately.
5. Compare only identified cases and state the number of generated cases. Do not infer semantic quality, cost, or provider-wide efficiency from token totals. Review the actual draft, citations and source applicability alongside measurements.
6. Retain the immutable recorded JSON and commit/run reference for every reported number. For repeated stochastic runs, report run-level values or a stated aggregation rather than implying byte-identical output.

For the final RC1 E2E demonstration, the separately recorded Hop→HANS→Gmail Draft call reported **2,934 prompt + 432 completion = 3,366 total tokens**, model total 64.945 s, and generation total 65.523 s. This E2E call is not one of the eight corpus rows and must not be added to the corpus totals.

## Separate manual UI demonstration on 26 September 2026

The Tkinter UI screenshot at `docs/diagrams/HANS_UI.png` shows a separate `CUSTOM-MANUAL` request using the active `llama3.1:8b` endpoint. Its displayed usage is **3,642 prompt + 262 completion = 3,904 total tokens**, with **57.324 seconds reported generation time**. Prompt tokens are 93.3% of this one request and completion tokens 6.7%. This is not a frozen MM-001 row, the eight-case acceptance aggregate, or the separately recorded Gmail E2E call above. Its draft remains subject to staff review.

This observation does not isolate the tokens used by system instructions, email text, or retrieved evidence, and it does not establish an average request size, cost, or an optimized prompt. A future controlled token study should record those prompt components, hold the corpus/model/source snapshot and retrieval settings fixed, repeat cases, and compare token use and latency alongside citation coverage, topic completeness, source applicability, and manual edit severity. No prompt-reduction quality result is claimed here.

## Professor milestone mapping

- **Larger than 3B local LLM:** the final `llama3.1:8b` run exercised all eight routes, with six model-generated cases and two no-generation/skip cases. This verifies the local >3B scenario in the controlled PoC, not production capacity.
- **Mistral approach:** local `mistral:latest`, Mistral Small API and Mistral Large API runs are recorded above as alternative paths, not the active E2E generator.
- **Token measurement:** per-case fields, null handling, timing boundaries and comparison limitations are specified here; UI and API observability expose the active run values.
- **Architecture and prompts:** `architecture.md`, `prompts.md`, the technical handover and Word deliverables document the implementation and representative prompt examples. Native Google Docs sharing is a separate submission action.
