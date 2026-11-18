# HANS Test Execution Record — 18 November 2026

## Baseline under test

Branch: `feature/2026-11-full-functional-tests`

The branch is based on the approved staging baseline `staging/2026-11-email-ui-working`.

## Automated regression execution

Command:

```powershell
& $py -m pytest .\tests -v
```

Result:

- Collected: 127 tests
- Passed: 127
- Failed: 0
- Duration: 8.97 seconds
- Platform: Windows / Python 3.11.9
- pytest: 9.1.1

Status: **PASS**

## What the automated suite verifies

The passing suite covers:

- API authentication and request validation
- mailbox configuration and capability flags
- inbox read-only behaviour
- IMAP BODY.PEEK usage
- mailbox message parsing
- attachment metadata and attachment retrieval
- safe attachment type filtering
- 25 MB attachment viewing limit
- mailbox draft creation
- SMTP send path only after explicit invocation
- reply headers and subject handling
- HANS / REVIEW / SKIP scope routing
- generation-provider selection
- canonical English/German email structure
- applicant/staff role-reversal protection
- credit-recognition topic coverage
- attachment manual-review safeguards
- unanswered-subquestion detection
- source-applicability review flagging
- topic-to-evidence ownership
- prompt topic boundaries
- resizable staff UI safety markers

## Remaining pre-server verification

The automated suite is necessary but not sufficient for server readiness.

The following live checks remain:

1. End-to-end generation against the real PostgreSQL/pgvector store and HTW model endpoint.
2. Manual comparison of each incoming question against the generated draft.
3. Verification that missing answers are reflected by the review indicators.
4. Verification that weak/non-applicable sources are reflected by the review indicators.
5. Source-link/citation inspection against the actual retrieved evidence.
6. Live timing measurement: retrieval, generation, validation and total latency.
7. Real Gmail IMAP read and attachment-view behaviour.
8. Controlled save-to-Drafts test.
9. Controlled SMTP send test only to an approved test address.
10. Failure/recovery checks for unavailable DB/model/mailbox where practical.

## Release gate

HANS should not be treated as server-ready until:

- automated tests remain 100% passing;
- the live E2E acceptance run is reviewed;
- critical E2E cases pass;
- latency is understood and acceptable or documented;
- setup/dependency documentation is complete;
- the final server TAR contains only required files and no secrets.
