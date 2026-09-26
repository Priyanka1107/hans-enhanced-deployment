# HANS - System Overview and Project Results

## 1. Executive summary

HANS is a staff-facing student-support assistant developed for HTW Berlin. Its purpose is to help staff prepare responses to student enquiries while keeping the answer tied to official university information and keeping the final decision with staff.

A typical student email may ask several things at once: the application deadline, required documents, language proof, application route, study format, or whether a foreign qualification can be recognised. These questions are difficult for a simple chatbot because the most similar webpage is not always the correct page for the applicant's programme, degree level or application route.

HANS addresses this by placing programme recognition, topic detection, evidence selection and review safeguards around retrieval-augmented generation (RAG). The system retrieves HTW information first, then asks the language model to draft an answer from the supplied evidence.

The tested current tested setup demonstrated the full workflow from a controlled Gmail mailbox through Apache Hop and HANS to a Gmail Draft. The draft is never sent automatically.

**Current result:** HANS is a working staff-support implementation that retrieves relevant official HTW information, prepares reviewable email drafts, and was successfully demonstrated through the complete Gmail → Apache Hop → HANS → Gmail Draft workflow. Every generated reply remains subject to staff review and manual sending.

---

## 2. The problem being addressed

Student Services has to answer repeated questions, but the questions are not always simple FAQ questions. One email can contain several topics, and applicant details can change which information is relevant.

Examples include:

- different deadlines for different programmes or semesters;
- documents that are programme-specific rather than university-wide;
- different application routes for EU/EEA and non-EU/EEA applicants;
- language-proof rules that are not the same as the language of instruction;
- foreign qualification recognition questions that are separate from the application route;
- follow-up emails that refer to earlier context without repeating it.

A general-purpose language model can write fluent text but may still use the wrong source, combine unrelated rules, or make a conclusion that is stronger than the evidence supports. The project therefore treats answer quality as a **pipeline problem**, not only a model problem.

---

## 3. What HANS does

The current workflow follows these steps:

1. read or receive a student enquiry;
2. identify the response language and useful applicant context;
3. resolve the target programme and degree level when possible;
4. detect all relevant topics in the email;
5. create focused retrieval queries for the detected topics;
6. retrieve general HTW evidence and programme-specific official evidence;
7. filter and prioritise evidence by programme, degree, topic, route and administrative stage;
8. build a structured evidence pack;
9. generate one staff-ready email draft;
10. apply deterministic safeguards and validation checks;
11. expose model, token and timing information for review;
12. return the result to Apache Hop;
13. create a Gmail Draft when the workflow is eligible;
14. leave editing and sending to staff.

The system is therefore not an autonomous admissions service. It is an assistant for evidence retrieval and draft preparation.

---

## 4. System architecture

![HANS End-to-End Architecture](diagrams/HANS_End_to_End_Architecture.png)

The architecture has two main areas.

### 4.1 Knowledge preparation and indexing

Official HTW webpages and structured source material are cleaned, organised and indexed. The current retrieval setup uses:

- `BAAI/bge-base-en-v1.5` embeddings;
- 768-dimensional vectors;
- PostgreSQL with pgvector using the public schema-v1 store;
- MiniLM cross-encoder reranking enabled after the initial candidate search;
- a programme catalogue for programme identity;
- a separate official programme-evidence resource for programme/topic facts.

### 4.2 Runtime staff-support workflow

Apache Hop reads and routes email input. HANS resolves context, retrieves evidence and generates a reviewable draft. The active generation path in the demonstrated setup is Llama 3.1 8B through Ollama on a shared Mac test host reached over a private Tailscale network.

The output is a Gmail Draft. `automatic_send` remains false.

### 4.3 How the main components work together

Apache Hop moves the email through the workflow. It reads the controlled mailbox, normalises input fields, decides whether the email is in scope, builds the request, calls the HANS API, parses the structured response and creates a Gmail Draft when the result is eligible.

HANS handles interpretation and evidence. It resolves programme/degree context, detects topics, creates retrieval queries, selects evidence, builds the prompt, calls the model and applies review safeguards.

PostgreSQL/pgvector provides semantic retrieval while keeping metadata close to the retrieved text. The programme catalogue and official programme-evidence resource add control where general semantic retrieval is too broad.

The language model's role is to turn selected evidence into clear staff wording. It is not given authority to invent rules, decide admission or make a binding eligibility judgement.

---

## 5. Why programme identity and programme facts are separated

A key lesson from the project is that programme identity and programme facts should not be treated as the same problem.

The programme catalogue answers questions such as:

- What programme did the student name?
- Is the name or abbreviation recognised?
- What is the degree level?
- What is the official programme URL?

Programme-specific evidence answers a different set of questions:

- What is the deadline?
- Which documents are required?
- What language proof is accepted?
- What is the study format?
- Is professional experience required?

This separation reduces the risk of using a correct fact from the wrong programme or using an old hard-coded value when the official page has changed.

---

## 6. Prompt and evidence approach

HANS uses **structured, evidence-grounded RAG instruction prompting**. It does not ask the model to answer from general knowledge. The model receives a controlled prompt with:

- the student's original message;
- the requested response language;
- programme/applicant context;
- the detected topics;
- a mapping between topics and supporting evidence where available;
- numbered evidence documents such as `[Doc 1]`, `[Doc 2]`;
- instructions for a normal staff email.

Representative rules include:

- use only the evidence supplied in the prompt;
- answer all detected topics but do not add unrelated topics;
- use programme-specific evidence for programme-specific questions;
- preserve uncertainty when a fact cannot be confirmed;
- do not classify formal applicant eligibility;
- place citations after factual claims;
- preserve the student's language;
- do not expose internal technical terms such as retrieval or grounding in the student-facing draft.

Important administrative rules are also supported by deterministic code rather than prompt wording alone. Examples include unknown-programme handling, qualification-recognition safeguards and application-route rules.

### 6.1 Example: a multi-topic enquiry

A realistic email may ask for the next application deadline, required documents, teaching language and study format in one message. HANS separates these into several topics and retrieves evidence for each topic rather than relying on one broad search result.

This is important because the best source for the deadline can be different from the best source for documents or study format. The model receives the combined evidence only after topic-specific retrieval and source checks.

### 6.2 Example: an unknown programme

If a student asks about a programme name that cannot be confirmed in the HTW programme catalogue, HANS should not guess a similar programme. It uses a safe clarification path and asks for the exact official programme name or link. No programme-specific deadline or document list is invented.

This path can be deterministic, so token/timing fields can correctly be empty because no model call was needed.

### 6.3 Example: application route versus qualification recognition

A student can be an EU citizen while holding a foreign school qualification. These are two different questions: which application route applies, and how the foreign qualification is assessed. HANS keeps these topics separate so that citizenship does not automatically answer the qualification-recognition question.

---

## 7. Human review and safety design

Human review is part of the system design, not a temporary workaround.

Every generated email remains a draft. The operational sequence is:

`HANS draft → validation/review metadata → Gmail Draft → staff review/edit → manual send`

The validator checks selected patterns such as citation structure and some unsupported or source-mismatch claims. It does **not** prove that every sentence is semantically correct.

This distinction became important in testing: a draft could receive a high automated score and still contain wording that a staff reviewer should change. The system therefore never uses the quality score as permission to send an email automatically.

Manual review also checks whether the draft actually answers the question, whether the cited source supports the exact claim, whether the programme and degree are correct, and whether the wording is stronger than the evidence allows.

---

## 8. Development and system evolution

### 8.1 Baseline HANS foundation

The baseline created a curated, traceable HTW knowledge foundation. Historical source preparation started from a larger English HTW crawl and produced 170 structured HANS objects. The baseline retrieval direction used BGE embeddings and PostgreSQL/pgvector.

### 8.2 Enhanced proof of concept

The experimental PoC added programme recognition, programme states, multi-topic processing, follow-up context, programme-specific official evidence, validation metadata and email-drafting workflows. It also evaluated a different retrieval stack using Cohere multilingual embeddings, Qdrant and Cohere reranking, together with Claude/Mistral generation paths and Gmail/n8n workflow experiments.

### 8.3 Self-hosted transfer

Useful mechanisms from the PoC were moved back into a baseline-oriented, self-hosted architecture. This work included local/self-hosted model paths, the BGE/pgvector retrieval direction, application and qualification safeguards, Apache Hop integration, regression testing and observability.

### 8.4 Current tested setup

The demonstrated setup uses BGE + PostgreSQL/pgvector retrieval, Llama 3.1 8B through Ollama, Apache Hop orchestration, a Tkinter staff/demo UI, token/timing observability and Gmail Draft creation.

---

## 9. Evaluation approach

The project does not treat one model score as the complete evaluation. HANS quality was checked across several layers:

- programme resolution;
- topic detection;
- retrieval/source applicability;
- citation behaviour;
- English/German drafting;
- unknown-programme safety;
- follow-up handling;
- route and qualification-recognition separation;
- token/timing observability;
- staff-review flags;
- complete Gmail Draft integration.

Several model paths were used during development for controlled comparison. The main engineering question was whether the same HANS retrieval and review boundary could support different generation providers. No universal “best model” claim is made. Cloud/API runs were substantially faster in several cases, but the earlier cloud PoC also used a different retrieval and reranking stack, so those results should not be treated as a model-only comparison.

Manual semantic review was part of the evaluation. Automated fields can show citation structure, selected risk patterns and technical metrics, but they cannot guarantee that every sentence is correct for the applicant's exact situation.

---

## 10. Eight-case acceptance run

A protected eight-case run was completed with `llama3.1:8b` against backend quality checkpoint `0e4219c`.

| Case | What it checks | Main lesson |
|---|---|---|
| MM-001 | Multi-topic MPMD enquiry | Several evidence topics can be combined, but topic coverage still needs review |
| MM-002 | Unknown programme | Safe clarification is better than guessing |
| MM-003 | German response | Output language can be controlled, but wording quality still matters |
| MM-004 | Follow-up behaviour | Context handling can work while generated wording still needs editing |
| MM-005 | English-requirements follow-up | A focused follow-up can reuse context without repeating the whole first email |
| MM-006 | Out-of-scope routing | Not every email should reach HANS |
| MM-007 | Pending graduation / fee context | High automated scores can miss a semantic issue |
| MM-008 | Dual citizenship / recognition | Application route and qualification recognition must remain separate |

The final manual disposition was **four clean passes** (MM-002, MM-005, MM-006, MM-008, with a wording caution on MM-008), **two acceptable staff drafts with limitations** (MM-001, MM-003), and **two requiring substantive staff editing** (MM-004, MM-007). The categories describe controlled test outcomes, not automatic send readiness. All cases were recorded, and every generated draft was manually reviewed. The unknown-programme path safely avoided invented programme-specific facts. At least one source/claim issue was successfully flagged by validation, while the International Business fee/route case showed that automated scoring can still miss a semantic problem.

Repeated generation runs also showed normal variation in wording, token counts and timing.

---

## 11. End-to-end Apache Hop result

The complete controlled workflow was demonstrated as:

`Gmail → Apache Hop → HANS :8013 → Apache Hop → Gmail Draft`

| Metric | Value |
|---|---|
| HTTP status | 200 |
| Generation provider | `htw_ollama` |
| Model | `llama3.1:8b` |
| Prompt tokens | 2,934 |
| Completion tokens | 432 |
| Total tokens | 3,366 |
| Generation time | 65.523 s |
| Human review required | Yes |
| Automatic send | No |
| Gmail action | `draft_created` |
| Sent | `false` |

The Gmail Draft was physically visible after the pipeline completed.

![Apache Hop email-drafting pipeline](evidence/Apache_Hop_Final_Pipeline.png)

The demonstration proves more than the backend API in isolation. The surrounding workflow successfully read Gmail input, built the HANS request, waited for generation, parsed the response, preserved review/observability fields, prepared the Gmail payload and created the draft without sending it.

---

## 12. Observability

The current response can expose:

- provider and model name;
- prompt tokens;
- completion tokens;
- total tokens;
- model timing;
- generation timing;
- request timing;
- review/failure metadata.

The Tkinter UI displays the main generation metrics. A deterministic safety response can legitimately show no generation metrics because no model call was made.

Token and timing measurements are engineering measurements, not quality scores. The current self-hosted transfer records per-case prompt/completion/total tokens and distinct model, generation and request timing where a model call occurs. No-generation and Hop-skip cases have null generation fields, not zero usage. The initial local Llama, local Mistral, Mistral Small API and Mistral Large API runs are diagnostic comparisons; the final RC1 acceptance is a later quality checkpoint. See [`model-comparison-and-token-measurement.md`](model-comparison-and-token-measurement.md) for the run identifiers, method and comparison limits.

---

## 13. Main strengths demonstrated

The project demonstrated:

- programme-aware and degree-aware handling;
- multi-topic retrieval instead of one broad query;
- direct programme-specific official evidence;
- controlled follow-up context;
- safe unknown-programme behaviour;
- English and German drafts;
- separation of application route and qualification recognition;
- citations and staff-verification links;
- deterministic safeguards for selected high-risk claims;
- provider/model/token/timing observability;
- working Apache Hop mailbox-to-Gmail-Draft integration;
- preserved human review throughout the workflow.

---

## 14. Known limitations and future operational work

The system is a working proof of concept, not a fully operated university production service.

Important limitations include:

- the Llama model runs on a shared test host rather than managed production infrastructure;
- validation is selective and rule-based, not universal fact checking;
- model wording is stochastic;
- some drafts still need meaningful staff editing;
- regular scheduled mailbox processing still needs duplicate-processing protection, retry rules and managed runtime ownership;
- mailbox authentication is a test/development arrangement;
- source freshness needs an agreed maintenance process;
- monitoring and incident ownership would be required for an operational pilot.

**Duplicate-processing protection** means that repeated mailbox polling should not create multiple drafts for the same email. Software engineers often call this property *idempotency*.

A managed pilot would also need stable institutional mailbox authentication, managed Apache Hop scheduling, defined retry/error routing, stable model hosting, source-freshness ownership, monitoring, and a privacy/security review for regular real-student-email processing.

---

## 15. Security, source maintenance and handover

The workflow is designed so Apache Hop only receives what it needs to call HANS. It does not need direct access to database internals, prompt implementation or model configuration.

Local configuration and credentials should not be committed to Git. The repository hygiene change `251fddf` stopped tracking `.env.local`; the local file can still exist on a developer machine while remaining outside version control. Before wider repository sharing, any historical credential that may have appeared in Git history should be treated as a credential-rotation issue.

Incoming student emails are used for retrieval/inference and are not used to train model weights in this proof of concept.

For a future pilot, responsibilities should be separated between a workflow owner (Apache Hop, mailbox, scheduling), a HANS backend owner (sources, retrieval, prompts, validation) and an infrastructure/model owner (model host, network access, monitoring and security updates).

---

## 16. Version and checkpoint summary

| Reference | Meaning |
|---|---|
| `0e4219c` | Backend quality checkpoint used for the protected acceptance run |
| `9fee966` | Commit recording the Llama acceptance artefact |
| `6dafee6` | Tested application state with UI observability and curated demos |
| `checkpoint-2026-09-25-final-ui-observability` | Tag on the tested application |
| `checkpoint-2026-09-25-final-e2e` | Tag confirming successful end-to-end demonstration |
| `251fddf` | Repository/environment-security hygiene after the behavioural freeze |

The behavioural reference remains `6dafee6`; `251fddf` does not change HANS runtime behaviour.

---

## 17. Short glossary

| Term | Meaning in this project |
|---|---|
| RAG | Retrieval-Augmented Generation: retrieve evidence first, then generate from it |
| Embedding | Numeric representation used to compare semantic similarity |
| pgvector | PostgreSQL extension used for vector similarity search |
| Programme catalogue | Controlled resource for programme names, aliases, degree level and official URLs |
| Official programme evidence | Selected HTW evidence for programme-specific topics |
| Topic detection | Identifying the separate questions contained in one email |
| Grounding | Checking whether claims are tied to supplied evidence |
| Human-in-the-loop | Staff remain part of the process and approve the draft before sending |
| Apache Hop | Workflow/orchestration tool used to connect mailbox input, HANS and Gmail Draft creation |
| Observability | Technical information such as model, token counts, timing and review status |

---

## 18. Current system status and next steps

HANS is a working staff-support implementation that can retrieve relevant official HTW information, prepare a reviewable email draft and complete the demonstrated Gmail -> Apache Hop -> HANS -> Gmail Draft workflow. Staff remain responsible for checking and sending every reply.

The next engineering priorities are controlled source-refresh automation, duplicate-processing protection for scheduled mailbox runs, stable monitoring and ownership, and measured retrieval/performance improvements. The accepted setup remains the reference configuration while alternative reranking and token-reduction ideas are tested against the same evaluation cases.
