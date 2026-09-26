# HANS Evaluation and Acceptance Evidence

## 1. Evaluation philosophy

The evaluation treats HANS quality as a pipeline property rather than a model-only property. The analysis therefore combines automated signals with manual semantic review.

No universal “best model” conclusion is claimed. Different model runs were used as controlled diagnostic/comparison paths.

## 2. Evaluation dimensions

The evaluation considered:

- programme resolution;
- topic coverage;
- evidence applicability;
- citation presence/structure;
- selected grounding/claim-support checks;
- unknown-programme safety;
- follow-up context;
- German/English response language;
- route/qualification separation;
- provider/model observability;
- token counts;
- timing;
- staff-review requirement;
- end-to-end Gmail Draft creation.

## 3. Model paths evaluated

The project exercised multiple generation paths during development, including:

- local Mistral;
- Mistral API comparison models;
- HTW-hosted Qwen3 path when available;
- final Llama 3.1 8B local/Ollama path.

The four-model evaluation was diagnostic. The protected acceptance run used `llama3.1:8b`.

## 4. Final frozen acceptance artefact

Acceptance evidence is recorded in:

`evaluation/results/llama31-8b-final-rc1-0e4219c-2026-09-25.json`

and checkpointed by commit `9fee966`.

Backend quality RC1: `0e4219c`.

## 5. Eight-case final acceptance summary

| Case | Purpose | Automated outcome | Manual semantic interpretation |
|---|---|---|---|
| MM-001 MPMD multi-topic EN | Deadline, documents, teaching language, study format | HTTP 200; review required; score 70; topic coverage warning | Useful staff draft; deadline/language strong; document list not exhaustive; study-format wording requires care |
| MM-002 unknown programme | Safe handling of unconfirmed programme | Deterministic no-generation path; programme_not_confirmed; score 75 | Strong safety behaviour: no invented programme-specific facts |
| MM-003 MPMD German | German deadline/documents | HTTP 200; automated score 100 | Functional German draft, but wording/document-language nuances still require staff review |
| MM-004 follow-up first | Follow-up/regression behaviour | HTTP 200; score 60/review; grounded=false; citations_valid=false; hallucination flag true | Correct deadline, but unsupported and unasked additions were detected; substantive staff editing required |
| MM-005 follow-up second | Follow-up continuation / English requirements | HTTP 200; review path | Clean/usable controlled result in final manual review |
| MM-006 out-of-scope | Hop relevance/skip path | Hop skip; no HANS generation | Correct by design |
| MM-007 IB pending graduation | Pending degree, English/fee context | HTTP 200; automated score 100 | Important semantic-validator limitation: staff review identified fee/route phrasing issues not captured by the score |
| MM-008 dual-citizen route | Route + foreign qualification/VPD | Controlled route/recognition handling | Final corpus result useful; later final E2E run also showed why staff review remains necessary |

The table intentionally separates automated output from manual judgment.

### Manual disposition of the final recorded run

| Disposition | Cases | Interpretation |
|---|---|---|
| Clean passes in the controlled test | MM-002, MM-005, MM-006, MM-008 | MM-002 is a deterministic safety response and MM-006 is a Hop skip. MM-008 was acceptable for staff review, with a caution that Hochschulstart steps may be too categorical while the exact programme is unresolved. “Clean pass” never authorises automatic sending. |
| Acceptable staff drafts with limitations | MM-001, MM-003 | MM-001 did not give a fully exhaustive document list and the study-format validator remained conservative. MM-003 was functional German but needed wording and document-language review. |
| Substantive staff editing required | MM-004, MM-007 | MM-004 added unsupported/unasked DAAD, language and study-format content; the validator caught a claim/source mismatch and scored it 60. MM-007 mixed English-language exemption with uni-assist fee wording and included unasked FIBAA material despite an automated score of 100. |

This classification is the manual review of the **25 September RC1 artefact committed at `9fee966`**, not a pass rate produced by the validator. See [`model-comparison-and-token-measurement.md`](model-comparison-and-token-measurement.md) for the earlier Mistral runs and the measurement protocol.

## 6. Why quality_score is not semantic correctness

A central finding is that an automated score can be high while the draft still contains a claim that staff should edit. The final system therefore treats quality/validation metadata as a review aid, not a send-authorisation signal.

The validator is strongest at selected patterns such as citation structure, some source-to-claim mismatches and explicitly encoded high-risk claims. It is not a universal fact checker.

## 7. Final end-to-end evidence

The Gmail/Apache Hop end-to-end run used the frozen final application and returned:

| Metric | Recorded E2E value |
|---|---|
| Endpoint | `http://127.0.0.1:8013/v1/drafts` |
| HTTP status | 200 |
| Provider | `htw_ollama` |
| Model | `llama3.1:8b` |
| Prompt tokens | 2934 |
| Completion tokens | 432 |
| Total tokens | 3366 |
| Model total seconds | 64.945 |
| Generation total seconds | 65.523 |
| automatic_send | false / N |
| review_required | true / Y |
| Gmail action | `draft_created` |
| sent | false |

The draft was physically visible in Gmail after the Hop pipeline completed.

## 8. End-to-end semantic observation

The final E2E draft correctly kept the VPD conclusion cautious, but it also contained an over-strong eligibility/application-route statement. The validator flagged a manual-review condition for an unsupported eligibility/admission statement while still reporting a high quality score.

This is useful system evidence: automated safeguards can reduce risk, but they do not remove the need for staff review.

## 9. Observability

For LLM generation paths, the final response can expose:

- provider;
- model;
- prompt tokens;
- completion tokens;
- total tokens;
- model timing;
- generation timing.

The Tkinter UI surfaces these metrics. Deterministic safety paths that do not call an LLM legitimately show no generation metrics.

## 10. Generation stochasticity

Repeated runs of the same semantic case produced different completion lengths and timing. This is expected model stochasticity and should be acknowledged in interpretation. Reproducibility therefore depends on frozen code/evidence/test cases, not on byte-identical generated prose.

## 11. Acceptance conclusion

The current system met the integration objective:

- HANS could process representative application questions;
- the local >3B model path was operational;
- tokens/timing were measurable;
- unsafe/unknown paths remained review-oriented;
- Apache Hop could call HANS and create a Gmail Draft;
- automatic sending remained disabled.

The tested state is appropriate to describe as a working, human-supervised proof of concept — not as an autonomous production admissions system.


## Retrieval comparison planned

The current tested setup uses MiniLM cross-encoder reranking. Earlier baseline work did not retain that reranker as the default, while the Enhanced PoC evaluated Cohere reranking in a different retrieval stack. A future matched comparison should therefore hold the source snapshot, query set, BGE embeddings, candidate count and generation path constant while comparing: (A) current MiniLM reranking, (B) BGE/document merging without cross-encoder reranking, and (C) an alternative reranker if available.

## Tabular acceptance summaries

The authoritative acceptance artefact remains the recorded JSON result. The documentation package also provides derived CSV and XLSX summaries for easier human review. These files are generated from the JSON and do not represent a separate run.
