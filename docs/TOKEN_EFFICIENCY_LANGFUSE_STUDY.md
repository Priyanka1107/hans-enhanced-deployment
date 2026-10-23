# HANS token-efficiency study (post-thesis / experimental)

This study is intentionally isolated from the frozen thesis backend.

Branch:
`observability/2026-10-23-langfuse-opt-in`

## Safety boundary

- Do not run these experiments against the protected stable copy/port.
- Use a separate checkout/folder and a separate API/runtime port if exposing an API.
- The experiment controls are inactive unless `HANS_EXPERIMENT_MODE=true`.
- Langfuse tracing is inactive unless `LANGFUSE_ENABLED=true` and credentials are provided.
- Prompt/email content is redacted from Langfuse by default. Keep
  `LANGFUSE_CAPTURE_CONTENT=false` unless content capture is institutionally approved.
- The runner uses a fresh thread ID for every request, preventing thread-memory carry-over.

## Important correction to the earlier K=6/5/4/3 manual runs

For the dual-citizen topics (`application_route` and
`qualification_recognition`), the frozen backend applies:

`retrieval_top_k = max(requested_top_k, 8)`

Therefore earlier requests with K=6, K=5, K=4 and K=3 all used an effective
retrieval K of 8 for these two topics. Their identical prompt-token counts
cannot be interpreted as a true K=6/5/4/3 retrieval experiment.

The experimental K sweep explicitly enables exact K only on this isolated
branch and logs both requested and effective K.

## Study phases

### 1. Exact-K sweep

- K=6
- K=5
- K=4
- K=3

Everything else remains at the current experimental baseline.

### 2. Final-prompt variants

These keep the current retrieval safeguards/floors in place and change only
the evidence packaging passed to generation:

| Variant | Final prompt change |
| --- | --- |
| Control | Current behaviour — max 1,800 chars/source |
| A — Deduplicate | Merge duplicate URLs before generation |
| B — Compact | 1,800 → 1,200 chars/source |
| C — Compact + dedupe | Deduplicate + 1,200 chars/source |

## Metrics captured

- requested and effective Top K
- final source count
- prompt/input tokens
- completion/output tokens
- total tokens
- retrieval latency
- generation latency
- total latency
- grounded
- citations valid
- hallucinations detected
- quality score
- failure/review reason
- detected topics

When Langfuse is enabled, the same experiment labels and metrics are attached
to Langfuse observations for filtering and dashboard comparisons.

## Langfuse setup

Install dependencies in the experiment environment and add the following only
to the local `.env` (never commit real keys):

```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_CAPTURE_CONTENT=false
```

## Run

From the repository root:

```bash
python scripts/run_token_efficiency_study.py --phase k-sweep --repeats 1
python scripts/run_token_efficiency_study.py --phase prompt-variants --repeats 1
```

For a more defensible variance study:

```bash
python scripts/run_token_efficiency_study.py --phase all --repeats 3
```

Results are written to:

`evaluation_outputs/token_efficiency/`

Both JSON and CSV are produced even if Langfuse is unavailable.
