# HANS Full Functional Test Plan

## Purpose

This plan verifies the current HANS Email Assistant staging candidate before server testing.

It combines:
1. automated regression tests; and
2. manual end-to-end tests that require the real mailbox, database, model endpoint, Windows UI, or SMTP.

No test should send a real student email. Use only controlled test addresses.

---

## A. Startup and health

### HANS-001 — Backend starts successfully
**Action:** Start `enhanced_api_server.py`.

**Expected:** API starts on the configured port without traceback.

### HANS-002 — UI starts successfully
**Action:** Start `enhanced_email_ui.py`.

**Expected:** HANS Email Assistant opens and remains responsive.

### HANS-003 — Health indicator becomes Online
**Expected:** The top-right UI shows `Online` and the configured HTTP backend URL.

### HANS-004 — Database unavailable
**Action:** Stop PostgreSQL and start the backend.

**Expected:** Startup or health check clearly reports the database problem. HANS must not silently pretend retrieval is operational.

### HANS-005 — Model endpoint unavailable
**Action:** Use an invalid/unreachable model endpoint in a controlled test configuration.

**Expected:** Draft generation fails clearly and the email remains for manual staff review.

---

## B. API authentication and validation

### HANS-010 — Correct internal API key
**Expected:** Authenticated mailbox and draft endpoints work.

### HANS-011 — Wrong internal API key
**Expected:** Request is rejected with 401.

### HANS-012 — Missing server API key
**Expected:** Protected endpoint reports authentication is not configured.

### HANS-013 — Empty email body
**Expected:** Generation request is rejected.

### HANS-014 — Invalid Top K below minimum
**Expected:** Request is rejected.

### HANS-015 — Invalid Top K above maximum
**Expected:** Request is rejected.

### HANS-016 — Empty draft body
**Expected:** Save/send request is rejected.

---

## C. Inbox and mailbox reading

### HANS-020 — Refresh inbox
**Action:** Click **Refresh inbox**.

**Expected:** Unread test messages appear without triggering Qwen generation.

### HANS-021 — No unread messages
**Expected:** UI displays a clear no-unread-messages status.

### HANS-022 — Mailbox unavailable
**Action:** Use an invalid IMAP configuration in a controlled test.

**Expected:** UI shows a readable mailbox error and stays responsive.

### HANS-023 — Select mailbox message
**Expected:** Selected row is highlighted and relevant mailbox controls become available.

### HANS-024 — Load selected email
**Expected:** Student email, subject and incoming email body populate correctly.

### HANS-025 — Loading email does not generate a draft
**Expected:** Staff draft remains empty until **Generate staff draft** is clicked.

### HANS-026 — Read-only inbox behavior
**Expected:** Reading/loading through HANS does not intentionally mark the message read, move it, or delete it.

---

## D. Attachments

### HANS-030 — Attachment count
**Expected:** Attachment count matches the real email and is centered in the table.

### HANS-031 — View one supported attachment
**Expected:** Supported file opens in the default local viewer.

### HANS-032 — View multiple supported attachments
**Expected:** Mouse-selectable list appears. Clicking a filename and **Open** opens the selected file.

### HANS-033 — Double-click attachment choice
**Expected:** Double-click opens the selected supported file.

### HANS-034 — Cancel attachment choice
**Expected:** Dialog closes and no attachment is opened.

### HANS-035 — PDF attachment
**Expected:** PDF can be opened.

### HANS-036 — Image attachment
**Expected:** PNG/JPG/JPEG/GIF/BMP/WEBP can be opened.

### HANS-037 — Office attachment
**Expected:** DOC/DOCX/XLS/XLSX/PPT/PPTX can be opened if the OS has an associated application.

### HANS-038 — Text/data attachment
**Expected:** TXT/CSV can be opened.

### HANS-039 — Unsafe attachment type
**Examples:** EXE, MSI, BAT, CMD, PS1, VBS, JS, JAR, DOCM, XLSM, PPTM.

**Expected:** HANS does not offer the file as viewable.

### HANS-040 — Attachment larger than 25 MB
**Expected:** Viewing is rejected with a clear size-limit message.

### HANS-041 — Attachment review safeguard
**Expected:** Attachment content is never passed into RAG/LLM automatically. The generated response remains flagged for manual verification when the enquiry depends on an attachment.

---

## E. Scope routing

### HANS-050 — Supported admissions question
**Expected:** Routes to HANS generation.

### HANS-051 — English language requirement question
**Expected:** Routes to HANS generation.

### HANS-052 — Required documents question
**Expected:** Routes to HANS generation.

### HANS-053 — Clearly out-of-scope Mensa question
**Expected:** Routes to SKIP and does not call Qwen.

### HANS-054 — Unclear/general request
**Expected:** Routes to REVIEW and does not call Qwen.

### HANS-055 — Mixed supported + unrelated wording
**Expected:** Supported admissions signal is not incorrectly lost because of an unrelated word.

---

## F. Draft generation

### HANS-060 — Generate staff draft from loaded mailbox email
**Expected:** Draft is generated only after staff clicks **Generate staff draft**.

### HANS-061 — Generate from manual email input
**Expected:** Manual input still works without mailbox selection.

### HANS-062 — English reply structure
**Expected:** Canonical applicant greeting and HTW Student Services closing are present once.

### HANS-063 — German reply structure
**Expected:** Canonical German greeting/closing are present once.

### HANS-064 — Applicant/staff role protection
**Expected:** Draft must not speak as if HTW staff are the applicant.

### HANS-065 — Programme ambiguity
**Expected:** Ambiguous programme/degree cases are flagged for staff confirmation instead of fabricated resolution.

### HANS-066 — Model/provider error
**Expected:** UI shows a controlled error and manual review remains possible.

---

## G. Retrieval, grounding and review quality

### HANS-070 — Official source links
**Expected:** Returned source URLs are visible and clickable.

### HANS-071 — Programme-specific evidence
**Expected:** Programme-specific questions use direct programme evidence when available.

### HANS-072 — Generic evidence only
**Expected:** Review panel flags source applicability when no sufficiently direct official programme evidence is available.

### HANS-073 — Question not directly answered
**Expected:** Review flags a missing sub-answer, such as a late language-certificate submission question that the draft does not address.

### HANS-074 — Citations valid
**Expected:** Review panel correctly reports citation validation status.

### HANS-075 — Grounding
**Expected:** Unsupported claims are not treated as grounded.

### HANS-076 — Attachment-dependent question
**Expected:** Manual verification reason remains visible because HANS did not inspect the attachment.

### HANS-077 — No hallucination false-positive for applicability warning
**Expected:** Weak source applicability may require review without automatically being labelled a hallucination.

---

## H. Staff draft editing

### HANS-080 — Edit generated draft
**Expected:** Staff can edit the draft text directly.

### HANS-081 — Copy draft
**Expected:** Current edited draft is copied, not an older generated version.

### HANS-082 — Open full draft
**Expected:** Full draft view shows the current draft content.

### HANS-083 — Clear
**Expected:** Clear resets the intended editable/display fields without corrupting application state.

---

## I. Save to mailbox Drafts

### HANS-090 — Write disabled
**Expected:** Save button remains disabled when `HANS_MAILBOX_WRITE_ENABLED=false`.

### HANS-091 — Save enabled
**Expected:** Save button becomes active when write capability is enabled.

### HANS-092 — Save edited draft
**Expected:** The exact staff-edited text is saved to the mailbox Drafts folder.

### HANS-093 — Recipient
**Expected:** Draft recipient equals the selected/student email.

### HANS-094 — Reply subject
**Expected:** Subject has `Re:` only once.

### HANS-095 — Reply threading headers
**Expected:** In-Reply-To/References use the original message ID when available.

### HANS-096 — Draft save failure
**Expected:** UI reports the failure and does not claim the draft was saved.

---

## J. Send controls

### HANS-100 — Send disabled by default
**Expected:** Send is disabled unless explicitly enabled.

### HANS-101 — Send enabled
**Expected:** Send button activates only when backend send capability is enabled.

### HANS-102 — Generate does not send
**Expected:** Generating a draft never sends an email.

### HANS-103 — Save to Drafts does not send
**Expected:** Saving a draft never sends an email.

### HANS-104 — Explicit send confirmation
**Expected:** Clicking **Send email** shows recipient, subject and body preview and asks for confirmation.

### HANS-105 — Cancel send
**Expected:** Choosing No/Cancel sends nothing.

### HANS-106 — Confirm controlled test send
**Expected:** Choosing Yes sends exactly one email to a controlled test address.

### HANS-107 — SMTP failure
**Expected:** UI reports a send failure and does not claim success.

### HANS-108 — Automatic send invariant
**Expected:** `automatic_send=false` remains true throughout the system design.

---

## K. UI behavior

### HANS-110 — Main title
**Expected:** `HANS Email Assistant` is centered.

### HANS-111 — Backend status
**Expected:** Only `Online` and the HTTP backend address appear at the top-right.

### HANS-112 — Metadata fields
**Expected:** Only Student email and Subject are visible. Thread ID, Email ID, language and Top K remain internal.

### HANS-113 — Section hierarchy
**Expected:** Section headings are readable, slightly emphasized, and do not crowd the layout.

### HANS-114 — Resizable panes
**Expected:** Staff can resize the main sections/panes without breaking the layout.

### HANS-115 — Small supported window size
**Expected:** UI remains usable at the configured minimum size.

### HANS-116 — Long email
**Expected:** Long content remains scrollable and does not break the window.

### HANS-117 — Long draft
**Expected:** Long generated response remains scrollable/editable.

### HANS-118 — Long source/review output
**Expected:** Validation/source panel remains scrollable.

---

## L. Database and retrieval store

### HANS-120 — PostgreSQL connection
**Expected:** Backend connects to the configured HANS database.

### HANS-121 — Schema version
**Expected:** Backend refuses an incompatible/missing schema instead of running against unknown structures.

### HANS-122 — pgvector retrieval
**Expected:** Semantic retrieval returns stored web chunks.

### HANS-123 — Embedding model compatibility
**Expected:** Query and stored embedding dimensions/models are compatible.

### HANS-124 — Database failure during request
**Expected:** Request fails clearly rather than returning fabricated content.

---

## M. Regression and packaging gate

The server package must not be created as final until:

- automated pytest suite passes;
- manual controlled-mailbox tests pass;
- Save to Drafts is verified;
- controlled Send test is verified if server testing includes SMTP;
- no real secrets are committed;
- `.env` is excluded from the package;
- package contains only required runtime/test/setup files;
- dependency/setup instructions are included.

---

## Automated test command

From the project root:

```powershell
& $py -m pytest .\tests -q
```

For readable test names during troubleshooting:

```powershell
& $py -m pytest .\tests -v
```

The verbose form is recommended for the final prerequisite test record because each test name explains what behavior was checked.
