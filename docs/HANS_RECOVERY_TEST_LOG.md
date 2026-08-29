# HANS Recovery and Integration Test Log

## Current integration baseline

Date: 2026-08-29

Backend:
http://127.0.0.1:8011

Generation provider:
htw_ollama

Generation model:
llama3.1:8b

Automatic send:
False

Human review:
Required for all generated drafts.

## Recovery checkpoints

### baseline-2026-08-08-ef7eda1
Clean recovered August 8 baseline.

### checkpoint-2026-08-29-ui-disclaimer
Restored:
- custom/manual test case support
- resizable test UI
- draft-only title
- full-draft view
- staff-review disclaimer

### checkpoint-2026-08-29-programme-resolution
Verified body-first programme resolution.

Rule:
- current email body is authoritative
- subject is fallback/context only
- subject/body mismatch is recorded
- an explicitly named but unknown programme does not silently fall back to the subject

## Fix #2 - Degree-aware evidence filtering

### International Business - Master

Result:
PARTIAL PASS

Verified:
- International Business in the email body overrides MPMD in the subject.
- Target degree remains Master.
- Conflicting catalogue degree Bachelor is no longer injected into retrieval query terms.
- Generic Bachelor application-period evidence is excluded.
- Subject/body mismatch is recorded.

Remaining content issues:
- Bachelor-specific evidence embedded inside general pages can still survive filtering.
- Unsupported or insufficiently supported deadline claims can still be generated.
- Claim/source validation does not yet catch every weak claim.
- Draft may contain information not requested by the student.

Validation observed:
- grounded: false
- citations_valid: false
- hallucinations: true
- confidence: 0.6
- failure_type: claim_source_mismatch
- quality_score: 60

### Project Management and Data Science - Master regression

Result:
PASS

Verified:
- target programme: Project Management and Data Science
- target degree: Master
- programme resolution source: email_body
- grounded: true
- citations_valid: true
- hallucinations: false
- confidence: 1.0
- quality_score: 100

Conclusion:
Degree-aware filtering did not regress the strong MPMD path.

### International Business - Bachelor regression

Result:
DEGREE-FILTER PASS / CONTENT REVIEW

Verified:
- target programme: International Business
- target degree: Bachelor
- catalogue degree: Bachelor
- programme resolution source: email_body
- subject/body mismatch: false
- Bachelor evidence remains available when Bachelor is the requested degree.

Remaining content issues:
- draft stated an application period that was not clearly supported by the displayed evidence
- draft added unrequested information about pre-study internship
- draft added English-proof information not requested by the student
- draft added Hochschulstart / NC information not requested by the student
- application-route applicability still needs stronger profile-aware source control

Validation observed:
- grounded: false
- citations_valid: false
- hallucinations: true
- confidence: 0.6
- failure_type: claim_source_mismatch
- quality_score: 60

### Unknown programme regression

Input programme:
Quantum Business Analytics

Result:
PASS

Verified:
- programme_resolution_source: email_body_unconfirmed
- programme_status: unknown
- target degree: Master
- retrieved sources: 0
- final sources: 0
- no programme-specific LLM answer generated
- confidence: 0.0
- failure_type: programme_not_confirmed
- human review required

This confirms that an explicitly named but unconfirmed programme is not replaced by unrelated programme or general programme information.

## Known remaining content-quality work

1. Source applicability inside broad/general HTW pages.
2. Degree applicability inside page content, not only page identity/title/URL.
3. Deadline claim/source validation.
4. Language-of-instruction claim validation.
5. Preventing unsupported inference.
6. Preventing answers to topics the student did not ask.
7. Better programme-specific evidence for International Business.
8. Study-format evidence and validation.

These issues are intentionally deferred until after the end-to-end integration checkpoint.

## Next implementation phase

Apache Hop + Gmail draft integration.

Target flow:

Gmail test email
-> Apache Hop
-> relevance routing
-> HANS /email API
-> parse HANS response
-> save audit result
-> determine draft eligibility
-> create Gmail draft
-> staff review
-> manual send

Automatic sending must remain disabled.
