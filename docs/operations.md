# HANS Operations and Reproducibility Guide

## 1. Scope

This guide describes the verified current runtime boundaries without exposing secrets. It intentionally avoids legacy commands that may no longer represent the final worktree.

## 2. Worktree and application checkpoints

Final worktree used for the last acceptance/E2E activity:

`C:\Working_Student\HTW\HANS_Project\hans-hop-e2e-finalization`

Tested application: `6dafee6`
Post-freeze repository hygiene: `251fddf`

## 3. Python environment boundary

The final worktree reused the existing shared environment rather than creating or upgrading a new environment during finalisation:

`C:\Working_Student\HTW\HANS_Project\hans-enhanced-deployment\.venv\Scripts\python.exe`

No secret values should be written into documentation or committed files.

## 4. Runtime configuration

Verified final health configuration:

- provider: `htw_ollama`
- model: `llama3.1:8b`
- embedding model: `BAAI/bge-base-en-v1.5`
- database: operational
- automatic send: false

Final local backend used for E2E validation:

`http://127.0.0.1:8013`

The historical port `8009` should not be presented as the final E2E runtime.

## 5. Required configuration categories

Typical runtime configuration includes:

- database connection configuration;
- generation-provider/model configuration;
- HANS internal API key;
- model-host/private-network configuration where applicable;
- Gmail test credentials for the Hop helper;
- optional UI API URL override.

Only variable names/placeholders belong in documentation. Real credentials must stay outside version control.

## 6. API verification

After starting the final backend, verify:

- `/health` returns healthy/operational state;
- provider/model match the intended run;
- `automatic_send` is false;
- authenticated `/v1/drafts` requests return structured HANS output.

## 7. Tkinter UI

`enhanced_email_ui.py` is a Tkinter desktop UI, not Streamlit.

The final UI can display:

- provider;
- model;
- prompt tokens;
- completion tokens;
- total tokens;
- generation time;
- raw technical response details.

Unknown-programme safety paths can show `n/a` generation metrics because no LLM call occurs.

## 8. Apache Hop

Final pipeline assets include:

- `apache-hop/hans_gmail_draft_demo.hpl`
- `apache-hop/create_gmail_draft_imap.py`

The final Hop path reads Gmail, normalises/routes the message, calls HANS, parses/saves the response, checks draft eligibility, prepares the Gmail payload and creates a draft.

The helper must create a draft only and return `sent=false`.

## 9. Secrets and repository hygiene

`.env` is ignored. `.env.local` was removed from Git tracking in commit `251fddf` while remaining usable locally.

Because an earlier baseline commit contained a tracked `.env.local`, any real credential that was historically committed should be considered exposed and rotated before broad repository access. Do not reproduce the historical value in documentation.

## 10. Recovery/checkpoints

Important final checkpoints:

- `0e4219c` — final backend quality RC1;
- `9fee966` — final Llama acceptance artefact;
- `6dafee6` — tested application;
- `checkpoint-2026-09-25-final-ui-observability` — final UI/observability tag;
- `checkpoint-2026-09-25-final-e2e` — successful final E2E tag;
- `251fddf` — post-freeze repository hygiene.

## 11. Operational limitations

A future production pilot still needs:

- managed scheduling;
- duplicate prevention/duplicate-processing protection (idempotency);
- production credential management;
- model-host monitoring/SLA;
- mailbox/service-account governance;
- formal logging/audit retention;
- source-refresh ownership;
- retry/incident procedures.


## Plain-language note: duplicate-processing protection

When Apache Hop is scheduled to poll the mailbox repeatedly, it may see the same message more than once. The operational workflow should remember that the email has already been processed so it does not create a second draft for the same message. This property is often called *idempotency* in software engineering.


## Knowledge-base refresh workflow

A new website scrape must not be inserted directly into the active vector store. The controlled maintenance path is: crawl -> change detection -> cleaning -> classification -> canonical-object update -> candidate chunking/embedding -> retrieval and draft regression -> human approval -> promotion. The V2 experiment demonstrated a separate candidate-index approach but was not promoted to the current runtime.

A future maintenance tool should automate this process into a one-click or few-click workflow while keeping an explicit human approval gate before activation.

## Scheduling status

Manual/local Apache Hop execution and the Gmail -> HANS -> Gmail Draft flow are tested. Windows Task Scheduler, cron, Hop Server, fixed-time polling and true event-driven Gmail triggers are future deployment options and are not claimed as tested.
