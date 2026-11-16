from email import policy
from email.parser import BytesParser

from app.mailbox.imap_client import (
    _attachments,
    _message_body,
)
from app.mailbox.models import (
    MailboxAttachment,
    MailboxMessage,
)


def test_plain_text_body_is_preserved() -> None:
    raw = (
        b"From: student@example.com\r\n"
        b"To: hans@example.com\r\n"
        b"Subject: Application question\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Hello HANS,\r\n\r\n"
        b"What is the application deadline?\r\n"
    )

    message = BytesParser(
        policy=policy.default,
    ).parsebytes(raw)

    body = _message_body(message)

    assert "Hello HANS" in body
    assert "application deadline" in body


def test_html_body_is_converted_to_readable_text() -> None:
    raw = (
        b"From: student@example.com\r\n"
        b"To: hans@example.com\r\n"
        b"Subject: Application question\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"\r\n"
        b"<p>Hello HANS</p><p>Which documents are required?</p>"
    )

    message = BytesParser(
        policy=policy.default,
    ).parsebytes(raw)

    body = _message_body(message)

    assert "Hello HANS" in body
    assert "Which documents are required?" in body
    assert "<p>" not in body


def test_attachment_metadata_is_exposed_without_processing_file() -> None:
    raw = (
        b"From: student@example.com\r\n"
        b"To: hans@example.com\r\n"
        b"Subject: Transcript\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=abc\r\n"
        b"\r\n"
        b"--abc\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Please see attached.\r\n"
        b"--abc\r\n"
        b"Content-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename=transcript.pdf\r\n"
        b"Content-Transfer-Encoding: base64\r\n"
        b"\r\n"
        b"JVBERg==\r\n"
        b"--abc--\r\n"
    )

    message = BytesParser(
        policy=policy.default,
    ).parsebytes(raw)

    attachments = _attachments(message)

    assert len(attachments) == 1
    assert attachments[0].filename == "transcript.pdf"
    assert attachments[0].content_type == "application/pdf"
    assert attachments[0].size_bytes is not None


def test_mailbox_message_serializes_for_ui_contract() -> None:
    message = MailboxMessage(
        email_id="<message-1@example.com>",
        thread_id="<thread-1@example.com>",
        sender_email="student@example.com",
        subject="Application question",
        email_text="What is the deadline?",
        received_at="2026-11-16T12:00:00+01:00",
        attachments=(
            MailboxAttachment(
                filename="transcript.pdf",
                content_type="application/pdf",
                size_bytes=1234,
            ),
        ),
    )

    payload = message.to_dict()

    assert payload["student_email"] == "student@example.com"
    assert payload["attachment_count"] == 1
    assert payload["attachments"][0]["filename"] == "transcript.pdf"
