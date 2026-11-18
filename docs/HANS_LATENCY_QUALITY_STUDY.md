# HANS Latency / Quality Study

## Goal

Choose a HANS configuration that reduces generation latency and token usage without weakening:

- topic detection;
- direct answers to every student question;
- grounding and citation validity;
- programme-specific evidence;
- source-applicability warnings;
- missing-answer warnings;
- staff-ready draft quality.

The current approved staging configuration remains unchanged. This study runs only on the experiment branch.

## Why this study is needed

The 18 November 2026 E2E run showed that generation dominates latency.

Examples:

| Case | Retrieval | Generation | Prompt tokens | Completion tokens |
| --- | ---: | ---: | ---: | ---: |
| Simple deadline | ~5 s | ~38 s | 1,596 | 2,974 |
| Multi-topic MPMD | ~5 s | ~139 s | 3,929 | 10,690 |
| Qualification route | ~3 s | ~177 s | 2,102 | 13,515 |

The large completion-token counts indicate that model thinking/reasoning may be a major latency contributor. Retrieval and validation are comparatively small.

## Profiles

### A — Current baseline

Preserves the present behavior.

```text
LITELLM_ENABLE_THINKING=
HANS_E2E_TOP_K=6
HANS_RETRIEVAL_STANDARD_TOP_K=5
HANS_RETRIEVAL_HIGH_RISK_TOP_K=8
FINAL_SOURCE_LIMIT=8
HANS_EVIDENCE_CHARS_PER_DOC=1800
```

### B — Thinking off only

Isolates the effect of Qwen thinking while leaving retrieval/evidence unchanged.

```text
LITELLM_ENABLE_THINKING=false
HANS_E2E_TOP_K=6
HANS_RETRIEVAL_STANDARD_TOP_K=5
HANS_RETRIEVAL_HIGH_RISK_TOP_K=8
FINAL_SOURCE_LIMIT=8
HANS_EVIDENCE_CHARS_PER_DOC=1800
```

### C — Balanced

Moderately reduces retrieval and prompt evidence after thinking is disabled.

```text
LITELLM_ENABLE_THINKING=false
HANS_E2E_TOP_K=4
HANS_RETRIEVAL_STANDARD_TOP_K=4
HANS_RETRIEVAL_HIGH_RISK_TOP_K=6
FINAL_SOURCE_LIMIT=6
HANS_EVIDENCE_CHARS_PER_DOC=1200
```

### D — Lean

Stronger reduction used only to establish the lower latency boundary.

```text
LITELLM_ENABLE_THINKING=false
HANS_E2E_TOP_K=3
HANS_RETRIEVAL_STANDARD_TOP_K=3
HANS_RETRIEVAL_HIGH_RISK_TOP_K=5
FINAL_SOURCE_LIMIT=5
HANS_EVIDENCE_CHARS_PER_DOC=900
```

## Important

Restart the HANS backend after changing server-side environment variables. Settings are loaded when the backend starts.

The E2E runner itself also reads `HANS_E2E_TOP_K` and `HANS_E2E_PROFILE`, so run it from a new PowerShell window or set those values before running the script.

## What to record for each profile

For every E2E case record:

- detected topics;
- hard-check pass/fail;
- failure type;
- review reason;
- source count;
- prompt tokens;
- completion tokens;
- total tokens;
- retrieval seconds;
- generation seconds;
- total seconds;
- whether every question was actually answered;
- whether the indicators correctly matched any missing answer;
- whether cited sources directly support the claims;
- whether the draft is staff-ready.

## Selection rule

Do not automatically choose the fastest profile.

Preferred profile must:

1. preserve all expected topic detections;
2. preserve or improve missing-answer/source-applicability safeguards;
3. retain valid citations and relevant sources;
4. produce a staff-ready draft for all clean cases;
5. avoid a material drop in factual completeness;
6. then, among configurations meeting 1–5, choose the configuration with the best latency/token efficiency.

A moderate configuration is preferable to the absolute minimum if it gives more reliable answer quality.

## Expected interpretation

If Profile B gives most of the speed improvement with comparable draft quality, keep the current retrieval/source settings and disable thinking.

If B is still slow, compare C.

Use D only if C remains materially slower and D does not lose important evidence or answer quality.
