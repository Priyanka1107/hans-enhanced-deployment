from email.message import EmailMessage
from unittest.mock import Mock, patch

import pytest

from app.mailbox.imap_smtp_writer import (
    IMAPSMTPMailboxWriter,
    _reply_subject,
)


def _writer() -> IMAPSMTPMailboxWriter:
    return IMAPSMTPMailboxWriter(
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="staff@example.com",
        imap_password="secret",
        drafts_folder="Drafts",
        imap_use_ssl=True,
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_username="staff@example.com",
        smtp_password="secret",
        smtp_use_ssl=True,
        smtp_starttls=False,
    )


def test_reply_subject_is_added_once() -> None:
    assert _reply_subject("Application") == "Re: Application"
    assert _reply_subject("Re: Application") == "Re: Application"


def test_build_message_sets_reply_headers() -> None:
    message = _writer()._build_message(
        to_email="student@example.com",
        subject="Application",
        body="Hello",
        in_reply_to="<original@example.com>",
    )

    assert isinstance(message, EmailMessage)
    assert message["To"] == "student@example.com"
    assert message["Subject"] == "Re: Application"
    assert message["In-Reply-To"] == "<original@example.com>"
    assert message["References"] == "<original@example.com>"


@patch("app.mailbox.imap_smtp_writer.imaplib.IMAP4_SSL")
def test_save_draft_appends_with_draft_flag(imap_mock) -> None:
    connection = Mock()
    connection.append.return_value = ("OK", [b"saved"])
    imap_mock.return_value = connection

    message_id = _writer().save_draft(
        to_email="student@example.com",
        subject="Application",
        body="Hello",
        in_reply_to="<original@example.com>",
    )

    assert message_id
    connection.login.assert_called_once()
    args = connection.append.call_args.args
    assert args[0] == "Drafts"
    assert args[1] == "\\Draft"
    assert b"student@example.com" in args[3]


@patch("app.mailbox.imap_smtp_writer.smtplib.SMTP_SSL")
def test_send_message_uses_smtp_only_after_explicit_call(smtp_mock) -> None:
    connection = Mock()
    smtp_mock.return_value = connection

    message_id = _writer().send_message(
        to_email="student@example.com",
        subject="Application",
        body="Hello",
    )

    assert message_id
    connection.login.assert_called_once_with(
        "staff@example.com",
        "secret",
    )
    connection.send_message.assert_called_once()


def test_empty_body_is_rejected() -> None:
    with pytest.raises(ValueError, match="Draft body is empty"):
        _writer().save_draft(
            to_email="student@example.com",
            subject="Application",
            body="",
        )
