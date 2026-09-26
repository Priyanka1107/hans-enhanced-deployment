# HANS Prompt Architecture

The current approach is **structured, evidence-grounded retrieval-augmented generation (RAG) instruction prompting**. It is mainly zero-shot: task rules and official evidence are supplied directly rather than relying on many example answers.

## 1. Purpose

This document describes the prompt design used by the current HANS email-drafting workflow and records the main prompt approaches evaluated during development.

The current prompt path is assembled mainly from:

- `app/runtime/local_llm.py` — shared system prompt and user/evidence prompt;
- `app/email/service.py` — strengthened email-format and source-to-claim rules;
- `app/email/multitopic.py` — topic-specific retrieval/generation instructions and evidence handling.

The current service calls the generation client with a strengthened system prompt plus a structured user prompt/evidence pack.

## 2. Prompt design objective

The goal is not to make the model answer from general knowledge. The prompt is designed to make the model transform a controlled evidence pack into one professional staff draft while preserving uncertainty when evidence is insufficient.

The central principle is:

> Retrieve first, constrain the evidence, then generate from the supplied evidence only.

## 3. Current shared system prompt — representative excerpt

The current shared prompt states, in substance:

```text
You are HANS, the HTW Berlin AI-assisted email drafting system.
Prepare one staff-ready email draft in response to a student's enquiry.

Mandatory rules include:
- the draft is for staff review and is not a binding admission decision;
- use only the evidence documents supplied in the prompt;
- answer every detected topic but do not introduce unrelated topics;
- if evidence does not support a conclusion, say it could not be confirmed;
- use programme-specific evidence for programme-specific questions;
- do not classify formal applicant eligibility;
- place [Doc N] citations after supported factual claims;
- preserve the incoming language;
- do not expose internal retrieval/model processes;
- keep the draft easy for staff to verify and edit.
```

Implementation reference: `app/runtime/local_llm.py::build_email_system_prompt()`.

## 4. Strengthened service prompt

The current email service extends the shared prompt with email-format and source-to-claim rules. Representative rules are:

```text
EMAIL FORMAT RULES
- Reply directly to the student/applicant.
- Do not write a Subject line in the email body.
- Use exactly one greeting and one closing.
- Do not add route advice unless route/process is a detected topic.

SOURCE-TO-CLAIM RULES
- Cite the specific document that directly supports a factual claim.
- Do not use an application page for study-format claims unless it explicitly states the format.
- Do not infer teaching language from an English-language-proof requirement.
- Do not state on-campus/online/hybrid/full-time/part-time unless cited evidence supports it.
- Cautious wording is acceptable when evidence is incomplete.
```

Implementation reference: `app/email/service.py::_build_strengthened_system_prompt()`.

## 5. Structured user prompt / evidence pack

The current user prompt is structured rather than free-form. It contains sections for:

- reply language;
- interpreted applicant/programme context;
- detected topics;
- topic-to-evidence ownership where available;
- official evidence blocks;
- final generation instructions.

A simplified representation is:

```text
REPLY LANGUAGE
English (en)
Write the entire staff email draft in English.

INTERPRETED CONTEXT
- target programme / degree / applicant context ...

TOPICS TO ANSWER
- Application deadline: ...
- Required documents: ...

TOPIC-SPECIFIC EVIDENCE
- Application deadline -> [Doc 1]
- Required documents -> [Doc 2]

OFFICIAL EVIDENCE
[Doc 1] ...
[Doc 2] ...

Create one complete staff-ready email draft.
- Cover every listed topic.
- Use programme-specific evidence first.
- Use [Doc N] citations after factual claims.
- Do not make unsupported assumptions.
```

Implementation reference: `app/runtime/local_llm.py::build_email_user_prompt()`.

## 6. Language handling

For German requests, the prompt explicitly instructs the model to write the entire staff draft in German while allowing official programme names, URLs, source titles and `[Doc N]` citations to remain unchanged where necessary.

This is more reliable than asking the model to infer output language implicitly.

## 7. Topic ownership and evidence ownership

A key improvement was to make topic/evidence ownership explicit. The user prompt can map a requested topic to the final public document numbers that support it.

This reduces a common RAG failure mode: a document can be relevant to the email overall while still being the wrong source for one specific claim.

Tests covering this include `tests/test_topic_evidence_mapping.py` and `tests/test_topic_evidence_prompt.py`.

## 8. Unknown-programme safety path

Unknown-programme handling is intentionally not dependent on a free-generation prompt. The system can produce a deterministic clarification response without an LLM generation call.

Consequences:

- no invented programme-specific deadline/document information;
- generation observability can legitimately be absent (`n/a`);
- staff review still remains required.

## 9. Prompt scope controls

The current prompt/service path includes rules intended to prevent evidence leakage into unrelated sections of the draft. Examples include:

- answer only detected topics;
- do not add language requirements, deadlines or fees simply because they appear in retrieved evidence;
- add application-route advice only when route/process is requested;
- for missing evidence, write a normal student-facing uncertainty sentence rather than an internal staff note;
- avoid technical words such as “retrieval”, “grounding” or “evidence documents” in the student-facing draft.

## 10. High-risk claim controls

Prompting is reinforced with deterministic code for selected high-risk areas, including:

- unsupported VPD claims;
- qualification-recognition claims;
- application-route invariants;
- programme/degree conflicts;
- selected source-to-claim mismatches.

This reflects an important design lesson: critical administrative constraints should not rely on prompt wording alone.

## 11. Example — multi-topic programme enquiry

### Input intent
A student asks about an MPMD application deadline, required documents, teaching language and study format.

### Prompt strategy
1. Resolve MPMD and Master context.
2. Detect four topics.
3. Retrieve one or more evidence sources per topic.
4. Prefer official programme evidence and degree-index evidence.
5. Map topics to final `[Doc N]` identifiers.
6. Generate one email covering all four topics without adding unrelated information.
7. Validate citations/claims and require staff review.

### Expected behaviour
The draft should answer all four questions, use cautious wording for study-format details when needed, and cite the exact source supporting each factual claim.

## 12. Example — unknown programme

### Input
A student asks for the deadline and documents for a programme name that HTW does not list.

### Expected behaviour
HANS should state that the exact programme could not be confirmed, ask for the official programme name/link, and avoid inventing deadlines or documents.

The protected acceptance case `MM-002-UNKNOWN-PROGRAMME-EN` exercised this safety path.

## 13. Example — application route vs qualification recognition

A dual-citizen enquiry can contain two separate questions:

- Which application route applies?
- How is the foreign school qualification recognised / is a VPD required?

The current design keeps these topics separate. It should not recommend uni-assist as the main route solely because the applicant resides abroad or has a foreign certificate when EU/EEA citizenship changes the route. At the same time, the qualification-recognition question may still require separate official evidence.

## 14. Prompt evolution across development

### Earlier Enhanced PoC
The Enhanced PoC used a more direct evidence-to-answer prompt with Cohere/Qdrant retrieval and Claude/Mistral generation experiments.

### Production-readiness transfer
Prompting was moved into a provider-independent generation boundary and strengthened with programme/topic rules, source-to-claim constraints and deterministic safeguards.

### Current tested state
The current tested state uses the shared prompt + strengthened service prompt + structured topic/evidence user prompt. Llama 3.1 8B is the active generator in the demonstrated setup; Mistral remains an evaluated comparison path.

## 15. Limitations of prompt engineering

Prompting cannot repair an upstream information failure. Errors may originate from:

`programme resolution → topic detection → source availability → retrieval → evidence filtering → prompt construction → generation → validation`

A larger or better model cannot recover a fact that was not retrieved or passed into the prompt. This is why HANS quality is treated as a pipeline property rather than a model-only property.

## 16. Review guidance

When modifying prompts:

1. change one behaviour at a time;
2. run deterministic/unit tests for affected prompt structure;
3. run protected regression cases;
4. inspect the actual generated drafts manually;
5. verify that a fix does not add unrelated content elsewhere;
6. record token/timing effects where material;
7. checkpoint only after semantic review.


## 17. Implementation audit summary

The prompt implementation audit on the tested branch confirmed the active construction path in:

- `app/runtime/local_llm.py` for shared system/user prompt builders;
- `app/email/service.py` for strengthened rules and topic-evidence mapping;
- `app/email/multitopic.py` for topic/evidence retrieval instructions;
- `app/validation/email_validator.py` for rule-based review signals;
- `tests/test_topic_evidence_prompt.py` and `tests/test_topic_evidence_mapping.py` for prompt structure regressions.

The audit also confirmed rules covering evidence-only generation, topic scope, route advice, language-of-instruction vs language-proof separation, study-format caution and missing-evidence uncertainty.


## Prompt-token optimisation as a future experiment

Prompt tokens are expected to dominate completion tokens because the request contains system rules, applicant/programme context, detected topics, topic-to-evidence ownership and official evidence excerpts. Token reduction should therefore be tested as a controlled experiment rather than by removing evidence ad hoc. Safe candidates include removing duplicated instructions, shortening repeated metadata and deduplicating evidence from the same source. Any change must be checked against the same acceptance cases and manual semantic review.
