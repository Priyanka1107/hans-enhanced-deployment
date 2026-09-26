# HANS - Highly Automated Natural Language Support System

HANS is an AI-assisted staff-support system for HTW Berlin. It combines a curated HTW knowledge base, programme-aware and multi-topic retrieval, local language-model generation, review safeguards and Apache Hop workflow orchestration to prepare reviewable email drafts.

The demonstrated workflow is:

`Gmail -> Apache Hop -> HANS -> Gmail Draft -> staff review`

Replies are **not sent automatically**. Staff remain responsible for checking, editing where necessary, and manually sending each draft.

## Current tested configuration

- Behavioural reference: `6dafee6`
- Acceptance artefact checkpoint: `9fee966`
- Backend quality checkpoint: `0e4219c`
- End-to-end tag: `checkpoint-2026-09-25-final-e2e`
- UI/observability tag: `checkpoint-2026-09-25-final-ui-observability`
- Repository hygiene after the tested behavioural state: `251fddf`
- Embeddings: `BAAI/bge-base-en-v1.5` (768 dimensions)
- Retrieval store: PostgreSQL + pgvector, public schema-v1 (`documents`, `web_chunks`, `qa_pairs`)
- Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2` (enabled in the tested configuration)
- Active generator: `llama3.1:8b` via Ollama on the shared Mac test host
- Orchestration: Apache Hop
- Output: Gmail Draft only (`automatic_send = false`)

The separate `hans_v2` source-refresh store is a controlled experiment and is **not active** in the tested runtime.

## Where to start

- [`docs/index.md`](docs/index.md) - documentation map.
- [`docs/HANS_Project_Overview.md`](docs/HANS_Project_Overview.md) - clear system overview for professor/stakeholder review.
- [`docs/HANS_Technical_Handover.md`](docs/HANS_Technical_Handover.md) - detailed technical architecture, implementation, evaluation and handover.
- [`docs/architecture.md`](docs/architecture.md) - architecture source of truth.
- [`docs/prompts.md`](docs/prompts.md) - prompt method, rules and examples.
- [`docs/evaluation.md`](docs/evaluation.md) - acceptance, manual semantic review and planned retrieval comparison.
- [`docs/model-comparison-and-token-measurement.md`](docs/model-comparison-and-token-measurement.md) - Mistral/Llama runs and the token measurement protocol.
- [`docs/operations.md`](docs/operations.md) - operational handover and source-maintenance guidance.
- [`docs/repository-placement.md`](docs/repository-placement.md) - exact copy map and repository review sequence.

## Primary deliverables

The `deliverables/` folder contains two professionally formatted Word documents:

1. `HANS_Project_Overview_and_Results.docx` - 11-page system overview for a professor or stakeholder.
2. `HANS_Technical_Architecture_Implementation_and_Evaluation.docx` - 42-page technical architecture, implementation, evaluation and handover document.

Both documents include page numbers and contents pages. The architecture and Apache Hop figures are embedded directly so the Word files can be shared independently of the repository.

## Evaluation evidence

The authoritative acceptance artefact is the recorded JSON evaluation result committed at `9fee966`. This package includes that JSON, the four initial model-run artefacts, and derived CSV/XLSX summaries. The summaries are tabular views of the final recorded run, not a new evaluation. The final manual disposition is four clean passes (MM-002, MM-005, MM-006, MM-008, with an MM-008 wording caution), two acceptable staff drafts with limitations (MM-001, MM-003), and two requiring substantive editing (MM-004, MM-007).

## Current follow-up work

The tested configuration is retained as the reference while the following controlled work is planned:

- compare the current MiniLM reranker with a BGE/document-merging control and an alternative reranker on the same source snapshot and test cases;
- evaluate prompt/evidence token reduction without weakening topic coverage or answer quality;
- develop a one-click or few-click source-refresh workflow that automates crawling, cleaning, object construction, candidate indexing and tests while keeping a human approval gate before activation;
- add duplicate-processing protection, managed scheduling and production monitoring before regular mailbox operation.

## Historical reference

The detailed 4 September handover is preserved under `docs/archive/` for traceability. Historical baseline and Enhanced PoC material remains useful background, but the current documents clearly separate those experiments from the tested system configuration.
