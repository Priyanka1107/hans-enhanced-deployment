# HANS Version History and Architecture Evolution

## 1. Purpose

This is a concise evolution record for academic and technical review. It is not a full Git log.

## 2. Baseline HANS

The baseline established the source/retrieval foundation:

- structured HTW knowledge objects;
- local BGE embeddings;
- PostgreSQL + pgvector;
- database-backed RAG/reference QA behaviour;
- institutional source traceability.

This baseline is conceptually distinct from later development experiments.

## 3. Enhanced PoC

The Enhanced PoC introduced or evaluated:

- programme recognition and explicit programme states;
- multi-topic detection;
- one query per topic;
- programme-specific official evidence;
- temporary follow-up context;
- Cohere multilingual embeddings and Qdrant;
- Cohere reranking;
- Claude/Mistral generation experiments;
- Gmail/n8n draft integration;
- citation/review metadata.

These components were experimental and should not all be described as part of the current runtime.

## 4. Production-readiness transfer

Useful PoC mechanisms were transferred into a more baseline-oriented self-hosted architecture:

- programme catalogue and programme official evidence;
- source applicability and conflict controls;
- provider-independent generation client;
- local model-host paths;
- stronger prompts and deterministic guards;
- Apache Hop integration work;
- token/timing measurement framework.

## 5. Current tested state

The demonstrated state combines:

- BAAI/bge-base-en-v1.5 (768-d);
- PostgreSQL + pgvector;
- Llama 3.1 8B via Ollama;
- topic-specific retrieval/evidence ownership;
- validation/review metadata;
- Tkinter observability UI;
- Apache Hop orchestration;
- Gmail Draft creation with no automatic sending.

## 6. Important final checkpoints

| Reference | Meaning |
|---|---|
| `0e4219c` | Final backend quality RC1 — qualification-recognition guard and final backend quality state |
| `9fee966` | Final Llama 3.1 8B acceptance artefact committed |
| `6dafee6` | Tested application; UI observability and curated demo cases |
| `checkpoint-2026-09-25-final-ui-observability` | Tag marking final UI/observability application state |
| `checkpoint-2026-09-25-final-e2e` | Tag marking successful final E2E demonstration on the final application state |
| `251fddf` | Post-freeze repository hygiene: stop tracking local environment configuration |

## 7. Interpretation rule

For behavioural claims, `6dafee6` is the frozen final tested reference. `251fddf` is newer in Git history but does not represent a newer application behaviour version.


## Configuration clarification recorded 26 September 2026

A read-only repository audit confirmed that the current tested retrieval path uses the public schema-v1 tables (`documents`, `web_chunks`, `qa_pairs`) and not the separate `hans_v2` candidate store. The same audit confirmed that `cross-encoder/ms-marco-MiniLM-L-6-v2` is enabled in `config.yaml` and passed into the normal topic retrieval path. These findings update the handover wording but do not change application behaviour.
