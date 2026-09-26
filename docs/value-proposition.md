# HANS Value Proposition

## 1. Problem

Student-support teams repeatedly answer questions about applications, deadlines, programme requirements, documents, language requirements, study format and applicant-specific routes. The underlying information is distributed across programme pages, central HTW pages, regulations and administrative guidance. A simple chatbot can retrieve semantically similar material, but that is insufficient when the evidence applies to another programme, degree level, route or administrative stage.

## 2. Target users

The primary users are HTW staff who prepare replies to prospective and current students. The system is not designed to replace staff judgment or to make admissions decisions.

## 3. Core value

HANS reduces the effort needed to turn an incoming enquiry into a source-aware first draft. It combines:

- programme and degree recognition;
- multi-topic question detection;
- evidence retrieval from official HTW sources;
- programme-specific evidence prioritisation;
- staff-ready draft generation;
- citations and source links;
- validation/review metadata;
- model/token/timing observability;
- Apache Hop mailbox orchestration;
- human review before sending.

## 4. Why the human-in-the-loop design matters

The current system deliberately stops at a reviewable draft. University admissions and student-service communication can depend on exceptions, applicant-specific evidence and changing regulations. Retaining staff review reduces the operational risk of treating a probabilistic model output as an authoritative administrative decision.

## 5. Differentiators from a generic RAG chatbot

HANS adds administrative applicability controls on top of semantic retrieval. It distinguishes:

- programme identity from programme facts;
- route guidance from qualification recognition;
- language-proof requirements from language of instruction;
- semantic relevance from administrative applicability;
- automated diagnostics from human semantic review.

## 6. Demonstrated outcome

The current tested state demonstrated a complete controlled workflow:

`Gmail → Apache Hop → HANS → retrieval/generation/validation → Apache Hop → Gmail Draft → staff review`

The draft was physically created in Gmail and was not automatically sent.

## 7. Non-goals

HANS is not positioned as:

- an autonomous admissions decision system;
- a replacement for official HTW regulations or staff authority;
- a system that automatically sends replies;
- a model-training pipeline over student emails;
- a universal semantic fact-checker.

## 8. Institutional value if developed further

With production ownership, monitoring, stable model hosting, mailbox governance, source-refresh processes and formal privacy/security approval, the PoC architecture could support a future institutional pilot for faster, more consistent and more traceable student-support drafting.


## Current system outcome in plain language

HANS was implemented as a working staff-support prototype that retrieves relevant official HTW information, generates a reviewable email draft, and was demonstrated through the complete Gmail → Apache Hop → HANS → Gmail Draft workflow. Staff remain responsible for checking and manually sending the reply.
