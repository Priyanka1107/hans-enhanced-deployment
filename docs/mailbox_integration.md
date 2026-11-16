# HANS mailbox integration architecture

## Goal

Read incoming student emails directly into the HANS staff UI without Apache Hop.

## Runtime flow

1. A provider-specific mailbox adapter reads incoming messages.
2. The adapter normalizes provider data into a common HANS mailbox message.
3. FastAPI exposes the normalized inbox to the staff UI.
4. Staff selects an email in the UI.
5. The selected normalized email is sent to the existing HANS /email endpoint.
6. The existing HANS scope router decides HANS / REVIEW / SKIP.
7. Only HANS-routed messages reach retrieval and Qwen generation.
8. Staff reviews the draft. Automatic sending remains disabled.

## Why Apache Hop is not required

Hop previously performed three main responsibilities:

- read email from the mailbox;
- normalize fields;
- call the HANS REST API.

Those responsibilities can be implemented directly in Python:

- app/mailbox/* reads and normalizes email;
- FastAPI exposes inbox messages;
- the UI calls the same HANS backend API.

The HANS RAG/generation pipeline is unchanged.

## Current implementation

Provider-independent mailbox protocol:
app/mailbox/protocol.py

Normalized message and attachment models:
app/mailbox/models.py

First read-only provider:
app/mailbox/imap_client.py

Mailbox provider factory/configuration:
app/mailbox/factory.py

FastAPI endpoints:

- GET /mailbox/status
- GET /mailbox/messages?limit=20&unread_only=true

Mailbox integration is disabled by default.

## Configuration

HANS_MAILBOX_ENABLED=false
HANS_MAILBOX_PROVIDER=imap
HANS_IMAP_HOST=
HANS_IMAP_PORT=993
HANS_IMAP_USERNAME=
HANS_IMAP_PASSWORD=
HANS_IMAP_FOLDER=INBOX
HANS_IMAP_USE_SSL=true

Credentials must remain in environment/server secrets and must never be
committed.

## Safety properties

- read-only mailbox access;
- BODY.PEEK is used for IMAP message fetches;
- no delete/move/reply/send operation;
- automatic_send remains false;
- mailbox listing does not call Qwen;
- attachment metadata is exposed, but attachment contents are not processed;
- UI/API contract is provider-independent so Microsoft Graph can be added later
  without changing HANS generation logic.

## Next step

Wire the existing Tkinter UI to /mailbox/messages with:

- Refresh inbox button;
- inbox list;
- Load selected email button;
- sender, subject, body, IDs and attachment metadata populated into the existing
  input fields;
- existing Generate staff draft button remains the only action that calls HANS
  generation.
