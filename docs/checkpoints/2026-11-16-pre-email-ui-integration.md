# HANS checkpoint — before mailbox/email UI integration

Date: 2026-11-16

## Frozen recovery point

Recovery branch:
checkpoint/2026-11-16-pre-email-ui-integration

Exact tested commit:
5ba10c5b1272a518870af52eb0a4883f710c44f2

The recovery branch must remain unchanged. It represents the last tested
state before mailbox/email-to-UI integration work started.

## Verified state at this checkpoint

- API port: 8009
- Generation provider: htw_litellm
- Model: qwen3.8-27b
- Embeddings: BAAI/bge-base-en-v1.5
- PostgreSQL + pgvector operational
- Automatic sending disabled
- Python scope router supports HANS / REVIEW / SKIP
- SKIP stops before retrieval/generation and consumes no Qwen tokens
- Attachment references produce an explicit manual-verification reason
- Ambiguous Bachelor/Master programme degree produces a review reason
- Credit-recognition topic detection fixed
- Credit-recognition answer completeness validation added
- Focused regression suite: 20 tests passed

## Important known limitations at checkpoint

- HANS does not inspect attachment contents.
- Programme/source applicability still requires staff review in difficult cases.
- Model usage reports unusually high completion-token counts; provider semantics
  still need verification before treating this as a token-accounting bug.
- Full Q&A workbook regression has not yet been completed.

## Recovery commands

Inspect checkpoint without changing another working branch:

git fetch origin
git switch --detach origin/checkpoint/2026-11-16-pre-email-ui-integration

Create a new recovery work branch from the checkpoint:

git fetch origin
git switch -c recovery/2026-11-16-hans origin/checkpoint/2026-11-16-pre-email-ui-integration

Do not use git reset --hard when local work is present. Stash or commit local
changes first.

## Email integration branch

New development branch:
feature/2026-11-email-ui-integration

It was created from the exact checkpoint commit above.

Target architecture without Apache Hop:

Mailbox provider -> Python mailbox adapter -> FastAPI -> staff UI -> HANS draft API

Mailbox reading and HANS generation remain separate. Fetching the inbox does not
invoke the LLM. A message reaches HANS generation only when staff requests a
draft (or a future explicitly controlled workflow invokes draft generation).
