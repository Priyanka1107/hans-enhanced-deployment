# HANS test package and mailbox write roadmap

## 1. Python runtime status

The active HANS email workflow is Python-based:

- Tkinter staff UI
- FastAPI backend
- Python mailbox adapter
- Python scope router
- Python retrieval/generation/validation pipeline
- PostgreSQL/pgvector database access

The repository still contains legacy and infrastructure artifacts such as Apache Hop, n8n, shell/batch launchers, Docker/Singularity files and historical utilities. They are not required by the new email-to-UI runtime.

## 2. Environment configuration

The project should use a project-local `.env` for local testing or server-injected environment variables in deployment.

Do not package or commit the real `.env`.

Include only `.env.example` in distributable ZIP files.

A Python virtual environment may live outside the project folder. Testers should normally create their own venv from `requirements.txt`.

## 3. Test ZIP

Use:

`python scripts/build_email_ui_test_package.py`

Output:

`dist/HANS_email_ui_test_package.zip`

The package intentionally excludes:

- .env and secrets
- .git
- virtual environments
- runtime logs/data
- Apache Hop
- n8n
- old demos and experiments
- unrelated deliverables

The PostgreSQL/pgvector database is not embedded in the ZIP and must be provided/configured separately.

## 4. Mail write implementation

The mailbox write capability is implemented on the development branch
`feature/2026-11-mailbox-drafts`.

Current staff workflow:

1. Staff loads an incoming email.
2. HANS generates a proposed response.
3. Staff edits the response in the UI.
4. Staff may choose **Save to mailbox drafts**.
5. Staff may choose **Send email** only when sending is explicitly enabled.
6. Direct sending always displays a confirmation dialog before the API call.

Configuration gates:

- `HANS_MAILBOX_WRITE_ENABLED=false` by default
- `HANS_MAILBOX_SEND_ENABLED=false` by default
- `automatic_send` remains false

The current controlled Gmail test implementation uses:

- IMAP for reading
- IMAP APPEND with the Draft flag for saving drafts
- SMTP for explicit sending

The provider-facing design separates read and write responsibilities so a
Microsoft Graph implementation can replace IMAP/SMTP for production without
changing the HANS RAG/generation pipeline.

Before production deployment, add/verify:

- duplicate-send/idempotency protection
- persistent audit logging of staff send actions
- organization-approved identity and permissions
- Microsoft Graph implementation for HTW Microsoft 365 if selected

## 5. Microsoft Outlook / production

Yes, HANS can support Outlook/Microsoft 365.

Preferred production integration:

Microsoft Graph + OAuth / organization-approved identity.

Typical permissions depend on HTW policy and deployment identity:

- Mail.Read for inbox reading
- Mail.ReadWrite for creating/updating drafts
- Mail.Send only if direct sending is approved

Exact authentication and permissions must be confirmed with HTW IT before production implementation.

The current provider-independent mailbox abstraction allows a Graph implementation to be added without changing the HANS RAG/generation pipeline.

## 6. Recommended production interaction

Safest initial production workflow:

Incoming mail -> HANS UI -> generate draft -> staff edits -> Save to Outlook Drafts -> staff sends from Outlook.

This keeps the actual send action inside the institution's normal mail client while HANS remains a drafting assistant.

Later, if approved:

Incoming mail -> HANS UI -> generate -> staff edits -> explicit Send button -> Microsoft Graph.
