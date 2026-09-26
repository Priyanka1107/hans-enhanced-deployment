# HANS Quality Regression Matrix

## Purpose

This document tracks whether each HANS implementation change improves
or degrades the actual staff-facing draft.

Technical success and draft-quality success are evaluated separately.

Automated validation scores alone are not treated as proof that a
draft is good.

## Evaluation dimensions

Each important regression case is reviewed on:

1. Programme resolution
2. Degree resolution
3. Topic detection
4. Source applicability
5. Claim/source support
6. Factual safety
7. Completeness
8. Conciseness and relevance
9. Citation quality
10. Staff usefulness
11. Input token usage
12. Output token usage
13. Total token usage
14. Generation latency
15. Output tokens per second

## Token metrics

For future model comparisons, record:

- input_tokens
- output_tokens
- total_tokens
- generation_seconds
- output_tokens_per_second

Provider-specific token values should be normalised by HANS.

Ollama:
- prompt_eval_count -> input_tokens
- eval_count -> output_tokens

Cloud model providers should be mapped to the same normalised fields.

Token metrics were not consistently captured for the recovery tests
below, so unavailable historical values are recorded as N/A rather
than estimated.

---

## Regression summary

| Case | Checkpoint | Model | Programme | Degree | Programme accuracy | Source applicability | Claim support | Conciseness | Overall usefulness | Quality score | Input tokens | Output tokens | Total tokens | Generation seconds | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| IB Master | Fix #1 | llama3.1:8b | International Business | Master | Good | Poor | Partial | Poor | Poor | 60 | N/A | N/A | N/A | N/A | Technical pass / content review |
| IB Master | Fix #2 | llama3.1:8b | International Business | Master | Good | Improved but incomplete | Poor | Partial | Poor | 60 | N/A | N/A | N/A | 92.27 | Mixed |
| MPMD Master | Fix #2 | llama3.1:8b | Project Management and Data Science | Master | Good | Good | Good | Acceptable | Good | 100 | N/A | N/A | N/A | 93.48 | Pass |
| IB Bachelor | Fix #2 | llama3.1:8b | International Business | Bachelor | Good | Partial | Poor | Poor | Poor | 60 | N/A | N/A | N/A | 117.69 | Technical pass / content review |
| Unknown programme | Fix #2 | deterministic guard | Quantum Business Analytics | Master | Good safety behaviour | N/A | N/A | Good | Good safety behaviour | 75 | 0 | 0 | 0 | 0 | Pass |

---

## International Business Master - Fix #1

### Technical result

PASS

### Positive

- Current email body correctly overrides stale MPMD subject.
- International Business is selected.
- Target degree is Master.
- Subject/body mismatch is recorded.

### Problems

- Catalogue Bachelor metadata influenced retrieval.
- Bachelor application-period evidence entered a Master enquiry.
- Draft used Bachelor deadlines after acknowledging that the Master's
  deadline was not explicitly confirmed.
- English-language evidence was not sufficiently applicable.
- Validation reported claim_source_mismatch.
- Quality score was 60.

### Manual assessment

POOR / REVIEW

---

## International Business Master - Fix #2

### Technical result

PASS

### Positive

- Body-first programme resolution remained correct.
- Target degree remained Master.
- Conflicting catalogue degree Bachelor was removed from retrieval
  query enrichment.
- Generic Bachelor application deadline evidence was removed.
- MPMD regression remained strong.
- Bachelor evidence remained available for actual Bachelor enquiries.

### Problems

- Bachelor-specific material embedded inside broad pages can still
  survive filtering.
- English-proficiency evidence still contained International Business
  Bachelor-specific information.
- The generated draft stated an unsupported Master's application
  period.
- Language-of-instruction support remained insufficient.
- Validation reported claim_source_mismatch.
- Quality score remained 60.

### Comparison with Fix #1

Technical mechanism:
IMPROVED

Source applicability:
IMPROVED

Claim support in the generated draft:
REGRESSED

Overall staff-facing usefulness:
NO CLEAR IMPROVEMENT

Conclusion:
Fix #2 is accepted as a technical improvement, but not classified as
an overall draft-quality improvement.

---

## Project Management and Data Science Master - Fix #2

### Result

PASS

- Programme resolution correct.
- Degree resolution correct.
- Programme-specific evidence retained.
- Grounded: true.
- Citations valid: true.
- Hallucinations: false.
- Confidence: 1.0.
- Quality score: 100.

### Manual assessment

GOOD

---

## International Business Bachelor - Fix #2

### Result

DEGREE-FILTER PASS / CONTENT REVIEW

### Positive

- Programme correct.
- Bachelor degree correct.
- Bachelor-specific evidence remains available when applicable.

### Problems

- Application deadline was not clearly supported by displayed evidence.
- Draft added unrequested pre-study internship information.
- Draft added unrequested English-proficiency information.
- Draft added unrequested Hochschulstart / NC information.
- Application-route applicability requires stronger applicant-context
  controls.
- Validation reported claim_source_mismatch.
- Quality score: 60.

### Manual assessment

POOR / REVIEW

---

## Unknown programme - Fix #2

### Result

PASS

- Unconfirmed programme remains unconfirmed.
- No unrelated programme fallback.
- Retrieval skipped.
- Model generation skipped.
- Sources: 0.
- Confidence: 0.0.
- Human review required.

### Manual assessment

GOOD SAFETY BEHAVIOUR

---

## Regression rule going forward

Before accepting any future HANS quality fix:

1. Run the frozen regression cases.
2. Compare the new draft against the previous checkpoint.
3. Record both technical behaviour and actual draft quality.
4. Record model, token usage and latency when available.
5. Do not classify a technical improvement as a quality improvement
   if the final staff draft becomes less safe or less useful.
6. Explicitly document any degraded case.
7. Preserve the previous Git checkpoint before continuing.
