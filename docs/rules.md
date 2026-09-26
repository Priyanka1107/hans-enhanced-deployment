# HANS Rules and Invariants

## 1. Purpose

These rules describe the behaviour HANS should preserve across model/provider changes. Some are implemented in prompts, some in deterministic code, and some in workflow policy.

## 2. Workflow invariants

1. **Draft only.** `automatic_send` remains false.
2. **Mandatory staff review.** A draft is never equivalent to a final institutional decision.
3. **HANS owns intelligence; Apache Hop owns orchestration.** Hop should not duplicate retrieval or prompt logic.
4. **Secrets stay outside version control.** API keys and local credentials must be environment/session configuration.

## 3. Programme and context rules

1. The current email body is stronger evidence than a stale subject line when they conflict.
2. Explicit Bachelor/Master context must not be silently overwritten by an incompatible programme match.
3. Unknown programmes must not be mapped to a similar known programme merely to produce an answer.
4. Programme-specific facts require a confirmed programme or clearly applicable general evidence.
5. Follow-up context is temporary. Explicit new information overrides historical thread context.

## 4. Retrieval and evidence rules

1. Retrieve per detected topic rather than blending all topics into one query.
2. Prefer programme-specific official evidence when available.
3. Semantic similarity alone is not enough; check programme, degree, route, stage and topic applicability.
4. Keep topic-scoped evidence identities when one page legitimately supports different topics.
5. Deduplicate evidence without collapsing distinct topic-specific snippets.
6. Route/recognition evidence may be general HTW evidence when a specific programme is not the relevant scope.

## 5. Generation rules

The shared current system prompt establishes the following mandatory behaviour:

- produce one staff-ready email draft;
- use only evidence supplied in the prompt;
- do not use general knowledge to fill gaps;
- answer every detected topic and avoid unrelated topics;
- state clearly when a requested conclusion cannot be confirmed from available official sources;
- use programme-specific evidence for programme-specific questions;
- do not classify formal applicant eligibility;
- place `[Doc N]` citations after supported factual claims;
- use simple, polite, professional language;
- preserve the incoming email language;
- do not include a separate reference-link section or system disclaimer because the application appends them;
- do not mention internal retrieval/model processes in the student-facing draft;
- keep the draft easy for staff to verify and edit.

## 6. Strengthened source-to-claim rules

The final service extends the shared prompt with additional constraints:

- write directly to the student/applicant;
- do not add a Subject line inside the body;
- use one greeting and one closing;
- do not add route advice unless route/process is among the detected topics;
- cite the document that directly supports each factual claim;
- do not use a generic application page as study-format evidence unless it explicitly states study format;
- do not infer language of instruction from an English-language-proof requirement;
- do not describe a programme as on-campus, online, hybrid, full-time or part-time unless cited evidence explicitly supports it;
- cautious wording is acceptable when a detail is not explicitly confirmed.

## 7. Route and qualification rules

1. Application route and qualification recognition are separate questions.
2. EU/EEA citizenship should not be overridden merely because the applicant resides outside Germany or holds a foreign qualification.
3. A VPD requirement must not be asserted if the retrieved evidence does not support it.
4. The system may describe the documented process without declaring the applicant formally eligible.

## 8. Validation interpretation rules

1. `quality_score` is diagnostic and heuristic; it is not semantic correctness.
2. `has_hallucinations` is a selected rule-based indicator, not universal hallucination detection.
3. `citations_valid` primarily confirms citation structure/range and selected claim-support rules; it does not prove every claim is supported.
4. A human semantic review remains mandatory for final acceptance and for real staff use.
