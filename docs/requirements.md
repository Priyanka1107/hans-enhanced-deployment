# HANS Requirements

## 1. Scope

This document states the tested system requirements and distinguishes implemented requirements from future operational requirements.

## 2. Functional requirements

| ID | Requirement | Final status |
|---|---|---|
| FR-01 | Accept a student enquiry with subject/body/sender metadata | Implemented |
| FR-02 | Detect reply language and preserve English/German response language | Implemented |
| FR-03 | Resolve known programme and degree context conservatively | Implemented |
| FR-04 | Represent programme state as confirmed / unknown / not provided where relevant | Implemented |
| FR-05 | Detect multiple requested topics in one enquiry | Implemented |
| FR-06 | Create topic-specific retrieval queries | Implemented |
| FR-07 | Retrieve semantically relevant evidence from PostgreSQL/pgvector | Implemented |
| FR-08 | Merge programme-specific official evidence with general retrieval | Implemented |
| FR-09 | Apply programme/degree/topic/route/source applicability controls | Implemented |
| FR-10 | Generate one staff-ready draft using only supplied evidence | Implemented |
| FR-11 | Add `[Doc N]` citations and staff-verification source links | Implemented |
| FR-12 | Preserve limited thread context for genuine follow-ups | Implemented |
| FR-13 | Fail safely for unconfirmed/unknown programmes | Implemented |
| FR-14 | Expose review/validation metadata | Implemented |
| FR-15 | Expose provider/model/token/timing observability | Implemented |
| FR-16 | Accept authenticated draft-generation requests at `/v1/drafts` | Implemented |
| FR-17 | Let Apache Hop route relevant emails to HANS | Implemented |
| FR-18 | Let Apache Hop create a Gmail draft from eligible HANS output | Implemented and E2E demonstrated |
| FR-19 | Prevent automatic final sending | Implemented |
| FR-20 | Allow staff to review/edit before manual sending | Implemented by workflow design |

## 3. Safety and quality requirements

| ID | Requirement | Final status |
|---|---|---|
| QR-01 | Do not make binding admission decisions | Implemented in prompt/safeguards; staff review required |
| QR-02 | Do not fabricate missing programme-specific facts | Implemented as prompt/safety rule; not guaranteed universally |
| QR-03 | Prefer programme-specific official evidence | Implemented |
| QR-04 | Separate application route from qualification recognition | Implemented in context/routing rules |
| QR-05 | Do not claim VPD requirement without supporting evidence | Implemented guard |
| QR-06 | Do not infer teaching language from English-proof requirements | Implemented prompt/source-to-claim rule |
| QR-07 | Do not infer online/hybrid/presence delivery without explicit evidence | Implemented prompt/source-to-claim rule |
| QR-08 | Flag all generated drafts for staff review | Implemented |
| QR-09 | Treat validator output as diagnostic, not a correctness guarantee | Documented operational requirement |

## 4. Non-functional requirements

### Traceability
Outputs should expose sources/citations and enough metadata to understand the retrieval/generation path.

### Reproducibility
The tested application is checkpointed at `6dafee6`; final acceptance evidence is committed at `9fee966`.

### Security
Secrets must be supplied through environment/session configuration and must not be committed. `.env.local` was removed from tracking in post-freeze hygiene commit `251fddf`.

### Provider independence
Apache Hop must call HANS rather than a provider-specific LLM endpoint. Provider/model changes should remain internal to HANS.

### Observability
Generated responses should expose provider/model, token counts and timing when an LLM call occurs.

### Human oversight
The workflow must terminate at a reviewable draft, not an automatically sent student reply.

## 5. Future operational requirements

The following are outside the final current implementation and belong to a production pilot:

- managed Apache Hop scheduling and retry policy;
- duplicate-processing protection (idempotency)/duplicate-prevention for scheduled mailbox polling;
- production secrets management;
- permanent model-host SLA and monitoring;
- source freshness ownership and change approval;
- incident handling and audit retention policy;
- privacy/security review for institutional deployment;
- mailbox permissions and service-account governance;
- formal performance/SLO targets.
