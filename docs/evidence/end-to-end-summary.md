# End-to-End Gmail / Apache Hop Evidence

## Demonstrated path

`Gmail → Apache Hop → HANS :8013 → Apache Hop → Gmail Draft`

## Recorded values

| Field | Value |
|---|---|
| HTTP status | `200` |
| Provider | `htw_ollama` |
| Model | `llama3.1:8b` |
| Prompt tokens | `2934` |
| Completion tokens | `432` |
| Total tokens | `3366` |
| Model total seconds | `64.945` |
| Generation total seconds | `65.523` |
| `flagged_for_human` | `true` / `Y` |
| `review_required` | `true` / `Y` |
| `automatic_send` | `false` / `N` |
| Gmail helper action | `draft_created` |
| `sent` | `false` |
| Helper exit code | `0` |

The Gmail Draft was physically confirmed after the pipeline completed.

## Semantic note

The route/qualification draft correctly kept the VPD conclusion cautious, but it also contained an over-strong eligibility/application-route statement. The validator marked manual review for an unsupported eligibility/admission statement. This is a useful example of why the quality score is a review aid rather than a guarantee of semantic correctness.
