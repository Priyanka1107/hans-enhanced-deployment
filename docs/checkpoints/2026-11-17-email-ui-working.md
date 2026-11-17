# HANS checkpoint — working email-to-UI integration

Date: 2026-11-17

## Frozen commit

Commit:

`dda2d9857c5f821e09b4be5c1aa39ab25198643c`

Recovery branch:

`checkpoint/2026-11-17-email-ui-working`

Staging / pre-main branch:

`staging/2026-11-email-ui-working`

## Verified state

- FastAPI backend runs on port 8009.
- Generation provider: HTW LiteLLM.
- Generation model: qwen3.8-27b.
- PostgreSQL + pgvector operational.
- Scope routing: HANS / REVIEW / SKIP.
- Automatic sending disabled.
- Read-only mailbox integration implemented in Python.
- IMAP test mailbox successfully read into the Tkinter UI.
- Staff can select and load a mailbox message into the existing HANS input fields.
- Mailbox refresh itself does not invoke Qwen.
- Attachment metadata is visible, but attachment contents are not processed.
- Evaluation controls remain available for regression testing.
- UI sections support the current resizable staff workflow.
- Focused regression suite passed before this checkpoint.

## Runtime architecture

Mailbox -> Python mailbox adapter -> FastAPI -> staff UI -> existing HANS /email endpoint -> scope router -> retrieval/Qwen when applicable.

Apache Hop is not required in this runtime path.

## Important limitations

- Current mailbox implementation is read-only.
- Current IMAP implementation uses username/password credentials and is intended for controlled testing.
- Draft creation and sending are not implemented yet.
- Production Microsoft 365/Outlook integration should use Microsoft Graph/OAuth rather than relying on basic IMAP credentials.
- Attachment contents are not yet inspected.
- Database contents are external to the code package.
