# HANS Code Review Guide

## 1. Purpose

This guide prepares a reviewer to distinguish the final active HANS path from historical experiments and legacy deployment material.

## 2. Review baseline

Use `6dafee6` as the tested application-behaviour reference.

`251fddf` is a later repository-security hygiene commit and should not be interpreted as a change to HANS behaviour.

## 3. Active areas to inspect first

### API and orchestration
- `enhanced_api_server.py`
- `app/email/service.py`
- `app/email/multitopic.py`
- `app/intent_router.py`

### Knowledge and retrieval
- `app/knowledge/programme_catalog.py`
- `app/knowledge/programme_context.py`
- `app/knowledge/programme_official_evidence.py`
- `app/retrieval/baseline_adapter.py`
- `app/retrieval/conflict.py`
- `app/retrieval/document_identity.py`

### Generation
- `app/runtime/generation.py`
- `app/runtime/local_llm.py`
- `app/runtime/mistral_api.py`

### Validation
- `app/validation/email_validator.py`

### UI
- `enhanced_email_ui.py`

### Apache Hop integration
- `apache-hop/hans_gmail_draft_demo.hpl`
- `apache-hop/create_gmail_draft_imap.py`

### Evaluation/tests
- `evaluation/multimodel_corpus.json`
- `evaluation/results/llama31-8b-final-rc1-0e4219c-2026-09-25.json`
- `tests/test_topic_evidence_mapping.py`
- `tests/test_topic_evidence_prompt.py`
- selected `tests/integration/*_manual.py` files used for guarded/manual verification.

## 4. Key design questions for review

1. Is programme identity resolved before programme-specific facts are emitted?
2. Are topic-specific queries and evidence mappings preserved end-to-end?
3. Can semantically relevant but administratively inapplicable evidence leak into the final pack?
4. Are prompt rules duplicated unnecessarily in code and prompt text?
5. Are high-risk administrative claims protected deterministically where prompt-only protection is insufficient?
6. Is provider-specific logic isolated behind the generation abstraction?
7. Does validation clearly distinguish heuristic diagnostics from correctness guarantees?
8. Can any path set or imply automatic sending?
9. Are secrets/log outputs safely handled?
10. Do legacy docs/scripts risk confusing current deployment behaviour?

## 5. Known technical-debt / review hotspots

### Validator scope
The validator contains selected rule-based checks. It is not a universal semantic verifier. Reviewers should not treat `quality_score=100` or `is_grounded=true` as proof of correctness.

### Prompt/rule growth
The final system contains both shared prompt rules, strengthened service rules and deterministic post-generation guards. A future refactor could centralise rule ownership and reduce duplication while preserving behaviour.

### Historical paths
The repository contains baseline, migration, Docker/Singularity, GUI/SSH and experimental documentation. Some files are still useful evidence but may describe old assumptions or ports. The final `docs/` layer should be treated as authoritative.

### Database URLs in examples/logging
Review example connection strings and scripts that print `DATABASE_URL`. Even when values are examples, production use should avoid logging credentials embedded in URLs.

### Historic `.env.local`
The file is no longer tracked after `251fddf`, but historical repository exposure means any real historical credential should be rotated before broad sharing.

### Manual integration tests
Several integration tests are intentionally manual. A future engineering pass could classify them explicitly as smoke/manual suites and separate them from deterministic CI tests.

## 6. Safety review checklist

- [ ] `automatic_send` is false on all final paths.
- [ ] Gmail helper creates drafts only.
- [ ] Unknown-programme path does not fabricate facts.
- [ ] Route and qualification recognition remain separate.
- [ ] VPD is not asserted without evidence.
- [ ] No API keys/passwords are committed.
- [ ] UI/logs do not print secrets.
- [ ] Staff-review disclaimer/review state is preserved.

## 7. Documentation consistency checklist

- [ ] Final generator described as Llama 3.1 8B / Ollama.
- [ ] Final embeddings described as BAAI/bge-base-en-v1.5, 768-d.
- [ ] Final vector store described as PostgreSQL + pgvector.
- [ ] Cohere/Qdrant described only as Enhanced PoC history.
- [ ] n8n described as earlier integration work, not the demonstrated orchestration path.
- [ ] Apache Hop described as demonstrated orchestration path.
- [ ] `6dafee6` described as tested application.
- [ ] `251fddf` described as post-freeze hygiene only.

## 8. Suggested review order

1. `docs/index.md`
2. `docs/architecture.md`
3. `enhanced_api_server.py`
4. `app/email/service.py`
5. `app/email/multitopic.py`
6. knowledge/retrieval modules
7. generation modules
8. validator
9. Apache Hop assets
10. final evaluation artefact/tests
11. legacy/historical files only after the active path is understood.


## Retrieval configuration to verify

During review, confirm that `config.yaml`, `app/settings.py`, `app/retrieval/baseline_adapter.py` and `hansdb/retrieval.py` agree on the active embedding model, candidate count, reranker and public schema-v1 table usage. Treat `scapy_migration/` and `hans_v2` as separate migration/experiment utilities unless a future change explicitly promotes that store.
