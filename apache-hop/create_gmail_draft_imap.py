import argparse
import imaplib
import json
import os
import re
import sys
import time

from email.message import EmailMessage
from email import policy


def find_drafts_folder(imap):
    status, mailboxes = imap.list()

    if status != "OK":
        raise RuntimeError("Could not list Gmail IMAP folders")

    for mailbox in mailboxes or []:
        text = mailbox.decode("utf-8", errors="replace")

        if "\\Drafts" not in text:
            continue

        match = re.search(r'"([^"]+)"\s*$', text)

        if match:
            return match.group(1)

    # English Gmail fallback.
    return "[Gmail]/Drafts"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-file", required=True)
    args = parser.parse_args()

    username = os.getenv("GMAIL_TEST_USERNAME", "").strip()
    password = os.getenv("GMAIL_TEST_APP_PASSWORD", "")

    if not username:
        raise RuntimeError("GMAIL_TEST_USERNAME is not set")

    if not password:
        raise RuntimeError("GMAIL_TEST_APP_PASSWORD is not set")

    with open(
        args.payload_file,
        "r",
        encoding="utf-8-sig",
    ) as handle:
        payload = json.load(handle)

    recipient = str(payload.get("to") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    body = str(payload.get("body") or "").strip()
    source_email_id = str(
        payload.get("source_email_id") or ""
    ).strip()

    if not recipient:
        raise RuntimeError("Draft recipient is missing")

    if not subject:
        raise RuntimeError("Draft subject is missing")

    if not body:
        raise RuntimeError("Draft body is missing")

    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject

    message = EmailMessage(policy=policy.SMTP)
    message["From"] = username
    message["To"] = recipient
    message["Subject"] = subject

    if source_email_id:
        message["X-HANS-Source-Email-ID"] = source_email_id

    message["X-HANS-Draft-Only"] = "true"
    message.set_content(body)

    imap = None

    try:
        imap = imaplib.IMAP4_SSL(
            "imap.gmail.com",
            993,
        )

        imap.login(username, password)

        drafts_folder = find_drafts_folder(imap)

        result = imap.append(
            drafts_folder,
            "(\\Draft)",
            imaplib.Time2Internaldate(time.time()),
            message.as_bytes(),
        )

        if result[0] != "OK":
            raise RuntimeError(
                f"Gmail rejected draft append: {result[0]}"
            )

        print(
            json.dumps(
                {
                    "ok": True,
                    "folder": drafts_folder,
                    "action": "draft_created",
                    "sent": False,
                }
            )
        )

    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "sent": False,
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)
