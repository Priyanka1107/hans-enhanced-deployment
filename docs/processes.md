# HANS Processes

## 1. Purpose

This document describes the repeatable engineering and operational processes around the final HANS PoC.

## 2. Knowledge preparation process

`official HTW sources → extraction → cleaning/normalisation → structured source objects → embedding/indexing → programme-control resources`

Key controls:

- preserve URL/source identity;
- retain metadata required for applicability filtering;
- validate source scope before indexing;
- re-run retrieval regression after material index changes.

## 3. Runtime email process

1. Apache Hop reads the controlled mailbox.
2. Fields are normalised and HANS metadata is added.
3. A relevance step routes out-of-scope messages away from HANS.
4. Relevant messages are converted to the HANS request schema.
5. Hop calls `POST /v1/drafts` with authenticated configuration.
6. HANS interprets language, programme/degree, follow-up context and topics.
7. HANS retrieves evidence per topic and merges programme-specific evidence.
8. Applicability/source controls filter the candidate set.
9. The configured generator produces one staff draft.
10. Deterministic safeguards and the validator add review metadata.
11. HANS returns the structured response.
12. Hop records the result and applies the draft-eligibility gate.
13. Hop creates a Gmail Draft when eligible.
14. Staff review/edit the draft and send manually.

## 4. Follow-up process

Thread context is temporary and subordinate to new explicit information. A follow-up can reuse prior programme/topic context only when the current message clearly depends on it. A newly stated programme or incompatible degree context forces fresh interpretation.

## 5. Quality-change process

For behaviour-changing fixes:

1. reproduce the failing case;
2. locate the failure stage (routing, programme, topics, retrieval, filtering, prompt, generation, validation);
3. make the smallest fix at the correct stage;
4. run focused deterministic tests;
5. run protected regression cases;
6. run the affected runtime draft;
7. manually inspect semantics;
8. revert if behaviour regresses;
9. checkpoint only the proven change.

## 6. Model-comparison process

Model comparison is diagnostic rather than a competition for a universal winner.

Controlled runs should keep as much of the retrieval/evidence path fixed as possible and record:

- provider/model;
- prompt/completion/total tokens;
- generation time;
- HTTP/runtime success;
- validation flags;
- manual semantic observations.

## 7. Final acceptance process

The final Llama 3.1 8B acceptance used a frozen eight-case corpus covering:

- multi-topic MPMD;
- unknown programme;
- German response;
- follow-up behaviour;
- out-of-scope Hop skip;
- pending graduation;
- dual-citizen route/recognition handling.

Automated metrics were recorded, but every generated runtime draft was also reviewed manually.

## 8. End-to-end process validation

The final E2E process was validated against application checkpoint `6dafee6`:

`Gmail → Apache Hop → HANS :8013 → Apache Hop → Gmail Draft`

The helper reported `draft_created` and `sent=false`, and the draft was physically confirmed in Gmail.

## 9. Documentation process

The final documentation layer separates:

- current authoritative docs;
- historical experiment/migration docs;
- evidence assets;
- professor-facing consolidated documents;
- technical/code-review guidance.

Current docs should be updated when the architecture changes; historical files should be archived/labeled rather than silently rewritten.
