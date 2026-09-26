# HANS - Architecture

## 1. Purpose

This document describes the authoritative architecture of the current tested HANS implementation.

HANS - Highly Automated Natural Language Support System is an AI-assisted staff-support system for HTW Berlin. It processes student enquiries, retrieves applicable information from HTW knowledge sources, generates a reviewable staff email draft, attaches source and validation information, and integrates with Apache Hop for mailbox orchestration.

The system is deliberately designed as a **human-in-the-loop assistant**:

- HANS generates drafts only.
- Staff review remains mandatory.
- `automatic_send = false`.
- HANS does not make binding admission decisions.
- HANS does not train model weights on incoming student emails.

The final tested application checkpoint is:

`6dafee6`

Final implementation tags:

- `checkpoint-2026-09-25-final-e2e`
- `checkpoint-2026-09-25-final-ui-observability`

The later commit `251fddf` contains repository/environment-security hygiene only and does not change the tested HANS application behaviour.

---

## 2. End-to-End Architecture

![HANS End-to-End Architecture](diagrams/HANS_End_to_End_Architecture.png)

The diagram above is the primary architecture figure for the current tested implementation. The Gmail mailbox and manually executed Apache Hop flow were demonstrated. Outlook/shared-mailbox input, scheduled triggering, persistent operational logging and a feedback loop are target or supporting concepts in the figure, not claims of completed production integration.

The architecture separates two major areas:

1. **Knowledge preparation and indexing**
2. **Runtime staff-support email processing**

Supporting resources such as the programme catalogue, programme-specific official evidence, temporary thread context, observability, and candidate prioritisation connect these two areas.

---

## 3. Current Validated Runtime Configuration

| Layer | Current tested configuration |
|---|---|
| Primary use case | Staff-facing student-support email drafting |
| Workflow orchestration | Apache Hop |
| HANS API | `POST /v1/drafts` |
| Runtime backend used for final E2E | `http://127.0.0.1:8013` |
| Embedding model | `BAAI/bge-base-en-v1.5` |
| Embedding dimensions | 768 |
| Embedding-language orientation | English |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` (enabled) |
| DB candidates before reranking | 30 |
| Vector store | PostgreSQL + pgvector, public schema-v1 |
| Active generation provider | `htw_ollama` |
| Active generation model | `llama3.1:8b` |
| Model host used for final demo | Shared Mac test host running Ollama |
| Private model access | Tailscale |
| Staff/demo UI | Tkinter desktop UI |
| Final email output | Gmail Draft |
| Automatic sending | Disabled |

The provider identifier `htw_ollama` is an application configuration name. It must not be interpreted as proof that the final Llama process is hosted on a permanent HTW production server.

---

## 4. Architectural Principles

### 4.1 Human-in-the-loop

HANS does not send student replies automatically.

The workflow ends with a Gmail draft that must be reviewed and, where necessary, edited by staff before manual sending.

This is an intentional safety boundary rather than an unfinished automation feature.

### 4.2 Official evidence first

Programme-specific and institutional factual statements should be supported by attributable HTW evidence whenever such evidence is available.

The system therefore separates:

- programme identity;
- programme-specific official evidence;
- general semantic retrieval.

### 4.3 Programme identity before programme-specific facts

A named programme should be resolved before HANS presents programme-specific deadlines, requirements, documents, study format, or similar facts.

An unknown programme must not silently map to a different programme.

### 4.4 Semantic relevance is not administrative applicability

A retrieved source may be semantically similar but still be inappropriate because it concerns:

- another programme;
- another degree level;
- another application route;
- another administrative stage;
- a special applicant category;
- an unrelated topic.

HANS therefore applies programme, degree, topic, route, and source-applicability controls after candidate retrieval.

### 4.5 Model-independent workflow boundary

Apache Hop calls the HANS API rather than calling a specific LLM directly.

This keeps mailbox orchestration, retrieval, prompt construction, model hosting, and validation as separate architectural responsibilities.

---

# Part A – Knowledge Preparation and Indexing

## 5. Source Foundation

The project evolved from a curated HANS source foundation based on official HTW Berlin information.

Historical source preparation produced a canonical set of structured HANS knowledge objects rather than using arbitrary raw webpages directly.

The source-preparation principle is:

`HTW source pages → extraction → cleaning / normalisation → scope and source classification → structured HANS knowledge objects → embedding / indexing`

The object layer preserves source identity and supports traceability, filtering, citation generation, and later programme/topic-aware retrieval.

---

## 6. Embedding Model

The **current tested runtime** uses:

- `BAAI/bge-base-en-v1.5`
- 768 dimensions
- English embedding model

This is consistent with the primarily English knowledge corpus used by the final runtime.

The project previously evaluated a different retrieval stack during the Enhanced PoC:

- Cohere multilingual embeddings
- 1,024 dimensions
- Qdrant

That Cohere/Qdrant configuration belongs to the earlier experimental Enhanced PoC and is **not the current runtime architecture**.

A future multilingual source corpus would require a new retrieval experiment rather than assuming that the current BGE embeddings are automatically appropriate. Such a change would require re-embedding, score recalibration, matched retrieval evaluation, and final-answer regression testing.

---

## 7. Vector Store and Retrieval Index

The current tested runtime uses:

`PostgreSQL + pgvector` with the public schema-v1 tables `documents`, `web_chunks` and `qa_pairs`.

The retrieval layer combines vector search with structured metadata and later applicability controls.

Conceptually:

`topic-specific query → BGE query embedding → pgvector candidate retrieval → programme / degree / topic applicability checks → programme-specific evidence merge → deduplication / prioritisation → generation evidence pack`

The current tested configuration has MiniLM cross-encoder reranking enabled after the initial BGE/pgvector candidate search. Earlier baseline testing did not consistently benefit from this reranker, so a matched comparison against BGE/document-merging and an alternative reranker is planned before a longer-running pilot fixes the retrieval configuration.

---

## 8. Chunking and Index-Version Boundary

Different project stages used different indexing settings.

Examples from project history include:

- baseline object/chunk preparation;
- Enhanced PoC passage preparation;
- later V2 source-refresh experiments.

Therefore the chunking values visible in historical diagrams must not be interpreted as one universal final-runtime constant.

The important final architectural requirements are that:

- chunks remain traceable to their parent source;
- structure and metadata are retained;
- the same embedding family is used for indexed content and runtime queries;
- source/index changes are regression-tested before becoming active.

---

## 9. Programme Catalogue

The programme catalogue provides programme identity and control information.

Primary resource:

`programme_catalog.json`

Its role includes:

- official programme names;
- trusted aliases;
- degree-level information;
- official programme URLs.

The catalogue should not become a permanent store for frequently changing facts such as application deadlines or language-test thresholds.

---

## 10. Official Programme Evidence

Programme-specific official evidence is maintained separately from programme identity.

Primary resource:

`programme_official_pages.json`

This layer may contain evidence for topics such as:

- application deadlines;
- required documents;
- language requirements;
- language of instruction;
- study format;
- professional-experience requirements;
- programme-specific application information.

Evidence is selected by **programme + topic**, not merely by URL.

Multiple snippets from one official page may therefore legitimately be retained when they support different requested topics.

---

# Part B – Runtime Staff-Support Workflow

## 11. Input Sources

The demonstrated email workflow uses a controlled Gmail test mailbox.

The target institutional architecture can later use an HTW shared mailbox without changing the internal HANS RAG architecture.

The runtime input contains fields such as subject, sender, email body, email ID, thread ID, and language/context metadata.

The Tkinter UI provides a second manual/demo interaction path for testing HANS without the mailbox workflow.

---

## 12. Apache Hop Responsibility

Apache Hop is the orchestration layer.

It owns:

- mailbox input;
- field normalisation;
- email metadata creation;
- initial HANS relevance routing;
- HANS configuration loading;
- request construction;
- authenticated HTTP call;
- response parsing;
- test/audit result persistence;
- draft eligibility routing;
- Gmail draft payload preparation;
- Gmail draft creation.

Apache Hop should **not** duplicate HANS retrieval or generation logic.

---

## 13. HANS Responsibility

HANS owns:

- language and context interpretation;
- programme and degree resolution;
- follow-up classification;
- multi-topic detection;
- retrieval-query construction;
- semantic retrieval;
- official programme evidence retrieval;
- source applicability filtering;
- prompt/evidence construction;
- generation;
- deterministic safeguards;
- citation/grounding/claim validation;
- quality and review metadata;
- generation observability.

Keeping these responsibilities inside HANS means that changing the generation provider does not require redesigning the Apache Hop workflow.

---

## 14. HANS Application Endpoint

The current email-drafting endpoint is:

`POST /v1/drafts`

Authentication uses:

`X-HANS-API-Key`

The workflow also exposes health information through:

`GET /health`

The final validated health configuration identified:

- `generation_provider = htw_ollama`
- `generation_model = llama3.1:8b`
- `embedding_model = BAAI/bge-base-en-v1.5`
- `database = operational`
- `automatic_send = false`

---

## 15. Programme and Degree Resolution

Programme resolution follows a conservative order.

Key rules include:

1. An explicit programme in the current email body is authoritative.
2. The subject is supporting context, not stronger evidence than the body.
3. Explicit Bachelor/Master wording should not be overwritten by an incompatible match.
4. Subject/body disagreement is treated as a conflict instead of being silently resolved.
5. An unknown programme must not be mapped automatically to the nearest known programme.

If a programme cannot be confirmed safely, HANS should produce a clarification/review-oriented response rather than fabricate programme-specific information.

---

## 16. Follow-Up and Thread Context

Thread context is intentionally temporary and limited.

It is intended for follow-up wording such as:

- “Is that also required?”
- “What about the deadline?”
- “Does the same apply to me?”

when the current message omits context that was clearly established earlier in the same thread.

Thread memory must not become permanent truth.

A new programme name, explicit context change, or ambiguous follow-up requires fresh interpretation.

---

## 17. Multi-Topic Detection

HANS processes a set of topics rather than only one dominant intent.

Examples include:

- `application_deadline`
- `required_documents`
- `application_route`
- `admission_requirements`
- `language_proof`
- `language_of_instruction`
- `english_language_requirements`
- `fees`
- `study_format`
- `work_experience`
- `application_before_graduation`
- qualification/recognition context

A focused evidence query is generated for each detected topic.

This is important because a multi-question student email should not be compressed into one blended retrieval query.

---

## 18. Evidence Retrieval

The final retrieval process combines:

- topic-specific semantic retrieval;
- programme catalogue context;
- direct programme-specific official evidence;
- source applicability controls;
- candidate merging and deduplication.

Conceptually:

`email → programme/applicant context → topic detection → one evidence query per topic → BGE embedding → pgvector retrieval → direct programme evidence → applicability filtering → source prioritisation → final evidence pack`

---

## 19. Evidence Applicability

Candidate evidence is not accepted solely because it has high vector similarity.

Evidence may be rejected or deprioritised when it applies to:

- another programme;
- another degree level;
- another application route;
- a special applicant category;
- enrolment rather than application;
- a topic not requested;
- a different administrative stage.

This source-applicability layer is one of the main architectural differences between ordinary semantic search and HANS's staff-support workflow.

---

## 20. Generation Layer

The active demonstrated generation path is:

- provider: `htw_ollama`
- model: `llama3.1:8b`
- runtime: Ollama
- host: shared Mac test host
- network: private Tailscale access

The generation prompt receives:

- original student email;
- requested response language;
- programme context;
- detected topics;
- selected evidence;
- source/citation identifiers;
- staff-review instructions.

The expected output is one coherent staff-ready email draft.

---

## 21. Evaluated Generation Alternative

Mistral API models were used as a controlled comparison option during project evaluation.

They are not the active final runtime.

The comparison was used to evaluate generation behaviour, local versus API-based generation paths, and token/timing behaviour under controlled cases.

The project does not claim a universal model winner.

---

## 22. Prompt and Evidence Boundary

Generation quality depends on more than the LLM.

A failure can originate from:

`programme resolution → topic detection → source availability → retrieval → evidence filtering → prompt construction → generation → validation`

A stronger generator cannot recover information that was never detected, retrieved, or passed into the prompt.

Prompt design is therefore documented separately in `docs/prompts.md`.

---

## 23. Deterministic Safeguards

The final implementation contains deterministic safeguards in addition to model prompting.

Examples include:

- unknown-programme handling;
- programme/degree conflict handling;
- application-route invariants;
- unsupported qualification-recognition safeguards;
- scope and unasked-topic controls;
- citation and claim-support checks;
- mandatory review behaviour.

These safeguards complement the LLM; they do not replace semantic staff review.

---

## 24. Validation and Review Metadata

The validator records structured signals such as:

- citations;
- grounding indicators;
- claim-support issues;
- quality diagnostics;
- review reasons;
- failure type;
- review-required state.

The validation layer is a **rule-based safeguard**, not universal semantic fact checking.

In particular:

- a high quality score is not proof that every claim is correct;
- selected unsupported/source-mismatch patterns can be detected;
- other semantic problems can still require human review.

This limitation is explicitly documented in the project evaluation.

---

## 25. Human Review

Every generated student-response draft remains a staff draft.

The required operational sequence is:

`HANS draft → review metadata → Gmail Draft → staff review/edit → manual send`

Automatic final sending is outside the scope of the current tested implementation.

---

# Part C – Observability

## 26. Generation Observability

The final implementation records generation information including:

- provider;
- model;
- prompt tokens;
- completion tokens;
- total tokens;
- generation time;
- request/response timing.

These metrics are exposed through the structured HANS response and displayed in the final Tkinter UI when an LLM generation call occurs.

---

## 27. Safety-Path Observability

Some deterministic safety paths do not call the generation model.

For example, an unknown-programme path may produce a deterministic clarification without an LLM call.

In such a case generation observability can legitimately be absent or shown as `n/a`.

This should not be interpreted as an observability failure.

---

# Part D – Apache Hop Integration

## 28. Apache Hop Pipeline

The demonstrated final pipeline contains the following logical steps:

- `01 - Read Gmail Test Emails`
- `01B - Normalize Gmail Fields`
- `01C - Add HANS Email Metadata`
- `02 - Determine HANS Relevance`
- `03 - Relevant for HANS?`
- `04A - Skipped Email`
- `05A - Save Skipped Emails`
- `04B - Load HANS Configuration`
- `05 - Build HANS Request`
- `06 - Call HANS Draft API`
- `06A - Remove Secret`
- `07 - Raw HANS Response`
- `08 - Parse HANS Response`
- `08A - Calculate Response Seconds`
- `09 - Save HANS Results`
- `10 - Draft Eligible?`
- `10A - No Gmail Draft`
- `10B - Draft Ready`
- `11 - Prepare Gmail Draft Payload`
- `12 - Create Gmail Draft`

The pipeline intentionally separates workflow orchestration from HANS retrieval/generation intelligence.

---

## 29. End-to-End Evidence

The final Apache Hop → HANS → Gmail Draft demonstration successfully completed against the frozen final application.

Verified characteristics included:

- HANS endpoint: `http://127.0.0.1:8013/v1/drafts`
- HTTP status: `200`
- provider: `htw_ollama`
- model: `llama3.1:8b`
- prompt tokens: `2934`
- completion tokens: `432`
- total tokens: `3366`
- generation total seconds: `65.523`
- automatic send: `N`
- flagged for human: `Y`
- review required: `Y`
- Gmail action: `draft_created`
- sent: `false`

The generated draft was also physically confirmed in Gmail.

This establishes the demonstrated integration path:

`Gmail → Apache Hop → authenticated HANS API → retrieval/generation/validation → Apache Hop → Gmail Draft → staff review`

---

# Part E – Architecture Evolution

## 30. Baseline Reference System

The baseline HANS work established the canonical source/retrieval foundation.

Key characteristics included:

- structured HANS knowledge objects;
- BGE embeddings;
- PostgreSQL + pgvector;
- institutional source traceability;
- reference QA behaviour.

The baseline is kept conceptually separate from later experiments.

---

## 31. Enhanced PoC

The Enhanced PoC introduced and evaluated mechanisms such as:

- programme recognition;
- explicit programme states;
- multi-topic processing;
- one retrieval query per topic;
- programme-specific official evidence;
- follow-up context;
- Cohere multilingual embeddings;
- Qdrant;
- Cohere reranking;
- Claude/Mistral generation experiments;
- Gmail/n8n draft integration;
- validation and review metadata.

These experiments were important during development, but they must not be confused with the current runtime stack.

---

## 32. Current Tested Architecture

Useful mechanisms from the Enhanced PoC were transferred into a baseline-oriented self-hosted architecture.

The demonstrated architecture combines:

- programme controls;
- multi-topic processing;
- official programme evidence;
- BGE/PostgreSQL/pgvector retrieval;
- Llama 3.1 8B local generation;
- validation and review safeguards;
- generation observability;
- Apache Hop orchestration;
- Gmail Draft output.

This represents the current tested implementation state.

---

# Part F – Known Architectural Limitations

## 33. Current Limitations

The current implementation is a working integration setup rather than a fully operated institutional production service.

Known limitations include:

- shared Mac test host rather than permanent production model infrastructure;
- no permanent managed Apache Hop scheduler/runtime;
- operational idempotency and duplicate-prevention need further hardening before scheduled mailbox polling;
- mailbox authentication remains a test/development setup;
- source freshness still requires operational ownership;
- validation is selective/rule-based rather than universal semantic verification;
- model outputs are stochastic;
- some cases still require substantive staff editing;
- retrieval/index settings evolved during the project and must be versioned carefully;
- production monitoring, ownership, retry behaviour, and incident procedures remain future operational work.

These limitations do not invalidate the demonstrated workflow. They define the boundary between the current tested implementation and a future institutional pilot.

---

## 34. Architectural Safety Boundary

The final architecture should therefore be understood as:

> A retrieval-augmented, human-supervised staff assistant that automates evidence retrieval and draft preparation while deliberately retaining final administrative responsibility with HTW staff.

It should **not** be described as an autonomous admissions decision system or an automatically sending support bot.

---

# Part G – Reproducibility and Checkpoints

## 35. Important Git Checkpoints

| Checkpoint | Purpose |
|---|---|
| `0e4219c` | Final backend quality RC1 |
| `9fee966` | Final Llama 3.1 8B acceptance artefact |
| `6dafee6` | Final tested application / UI observability |
| `checkpoint-2026-09-25-final-ui-observability` | Tag on final tested application |
| `checkpoint-2026-09-25-final-e2e` | Tag on final tested application after successful E2E demonstration |
| `251fddf` | Post-freeze repository/environment-security hygiene |

The application-behaviour reference remains `6dafee6`.

---

## 36. Related Documentation

The architecture document should be read together with:

- `docs/prompts.md`
- `docs/evaluation.md`
- `docs/requirements.md`
- `docs/rules.md`
- `docs/processes.md`
- `docs/operations.md`
- `docs/code-review-guide.md`

These documents provide the detailed implementation, testing, prompt, operational, and review perspectives without overloading the architecture specification.

---

## 37. Status

**Architecture status:** Current tested architecture documented.

**Application state:** Frozen and end-to-end tested.

**Automatic sending:** Disabled.

**Operational responsibility:** Staff review and manual sending.
