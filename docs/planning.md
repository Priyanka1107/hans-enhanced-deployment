# HANS Planning and Roadmap

## 1. Current project state

The current tested implementation is technically frozen and end-to-end demonstrated. The remaining work is documentation, presentation, repository review, packaging and controlled follow-up experiments rather than unreviewed behavioural changes.

## 2. Completed milestones

- baseline source/retrieval architecture established;
- Enhanced PoC programme/topic/follow-up mechanisms implemented and evaluated;
- programme catalogue and programme-specific evidence controls added;
- provider-independent generation boundary established;
- local >3B generation path exercised;
- Llama 3.1 8B current runtime established;
- token/timing observability implemented;
- final curated UI demo cases added;
- frozen eight-case final acceptance executed;
- all runtime drafts manually reviewed semantically;
- Apache Hop → HANS → Gmail Draft E2E proven;
- final application tagged;
- `.env.local` removed from Git tracking in post-freeze hygiene work.

## 3. Documentation / academic close-out

Priority close-out items:

1. maintain authoritative Markdown documentation in `docs/`;
2. provide professor-facing Google Docs/Word documents;
3. include architecture and representative prompt examples;
4. include final acceptance and E2E evidence;
5. preserve version history and current-vs-historical boundaries;
6. run final code/repository review;
7. capture defence screenshots/evidence.

## 4. Future institutional-pilot roadmap

### Operational hardening
- permanent model host;
- managed Apache Hop runtime/scheduler;
- idempotent mailbox polling;
- retries and dead-letter handling;
- service monitoring and alerting;
- production secrets management.

### Knowledge governance
- assigned owners for programme/source freshness;
- scheduled source validation;
- evidence versioning;
- change approval for high-risk rules.

### Validation improvements
- broader semantic claim-support checks;
- stronger route/qualification reasoning safeguards;
- structured factual-claim extraction;
- review analytics based on staff edits.

### Evaluation improvements
- larger blinded staff evaluation;
- topic-level answer completeness scoring;
- retrieval recall/precision benchmarks against labelled evidence;
- German-language retrieval corpus experiments if German source coverage expands.

### Product integration
- institutional mailbox/service account;
- staff authentication/roles;
- production audit trail;
- feedback loop from accepted/edited drafts without training on raw student emails by default.

## 5. Explicitly optional / non-blocking items

A dashboard is useful future work but is not required to establish the completed end-to-end objective. Likewise, production observability platforms such as Langfuse can be evaluated later rather than retrofitted into the frozen demo candidate.


## Planned controlled experiments

1. Compare the current MiniLM reranker with a BGE/document-merging control and an alternative reranker using the same source snapshot and evaluation cases.
2. Measure prompt-token reduction by removing duplicate instructions and redundant evidence while checking topic coverage, citation behaviour and manual semantic quality.
3. Design a semi-automated source-refresh workflow with crawling, cleaning, object construction, candidate indexing, regression testing and a human promotion gate.
