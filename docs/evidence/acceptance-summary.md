# Acceptance Summary

## Recorded run

- Backend quality checkpoint: `0e4219c`
- Run label: `llama31-8b-final-rc1-0e4219c-2026-09-25`
- Provider: `htw_ollama`
- Model: `llama3.1:8b`
- Cases recorded: 8
- Evaluation process exit: 0
- Artefact: `evaluation/results/llama31-8b-final-rc1-0e4219c-2026-09-25.json`
- Artefact commit: `9fee966`

## Case-level runtime metrics

| Case | Purpose | Total tokens | Generation time |
|---|---|---:|---:|
| MM-001 | MPMD multi-topic EN | 3981 | 64.092 s |
| MM-002 | Unknown programme safety | n/a | no LLM call |
| MM-003 | MPMD German | 2820 | 58.193 s |
| MM-004 | Follow-up first | 1677 | 28.018 s |
| MM-005 | Follow-up second | 1639 | 30.262 s |
| MM-006 | Out-of-scope | n/a | Hop skip |
| MM-007 | IB pending graduation | 3862 | 69.632 s |
| MM-008 | Dual-citizen route | 3384 | 55.257 s |

## Manual review conclusion

Manual semantic review was required for every generated draft. The protected corpus demonstrated useful safety behaviour, but it also showed that automated quality fields do not replace staff judgment. MM-002 was a strong deterministic safety case; MM-007 showed a semantic fee/route issue that automated scoring did not identify; MM-008 showed careful VPD uncertainty while still benefiting from staff review.

## Final manual disposition

- Four clean controlled-case passes: MM-002, MM-005, MM-006 and MM-008 (MM-008 retained a Hochschulstart wording caution).
- Two acceptable staff drafts with limitations: MM-001 and MM-003.
- Two requiring substantive staff editing: MM-004 and MM-007.

These categories were assigned by manual review, not by automated `quality_score`; every generated email still requires staff approval before sending. MM-004 was scored 60/review and flagged by validation. MM-007 was scored 100/good despite a fee/route problem found manually.
