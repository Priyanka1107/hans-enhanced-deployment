from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.ui.mailbox_client import (
    MailboxUIError,
    attachment_summary,
    fetch_mailbox_attachment,
    fetch_mailbox_messages,
)


def test_attachment_summary_lists_names() -> None:
    message = {
        "attachment_count": 2,
        "attachments": [
            {"filename": "transcript.pdf"},
            {"filename": "certificate.pdf"},
        ],
    }

    assert attachment_summary(message) == (
        "transcript.pdf, certificate.pdf"
    )


def test_attachment_summary_handles_no_attachments() -> None:
    assert attachment_summary({}) == "No attachments"


@patch("app.ui.mailbox_client.requests.get")
def test_fetch_mailbox_messages_returns_normalized_list(
    get_mock,
) -> None:
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "messages": [
            {
                "email_id": "m1",
                "thread_id": "t1",
                "student_email": "student@example.com",
                "subject": "Application",
                "email_text": "Hello",
            }
        ]
    }
    get_mock.return_value = response

    messages = fetch_mailbox_messages(
        api_base="http://127.0.0.1:8009",
        headers={
            "X-HANS-API-Key": "test",
        },
    )

    assert len(messages) == 1
    assert messages[0]["email_id"] == "m1"


@patch("app.ui.mailbox_client.requests.get")
def test_fetch_mailbox_messages_surfaces_backend_detail(
    get_mock,
) -> None:
    response = Mock()
    response.ok = False
    response.status_code = 503
    response.json.return_value = {
        "detail": "Mailbox integration is disabled."
    }
    get_mock.return_value = response

    with pytest.raises(
        MailboxUIError,
        match="Mailbox integration is disabled",
    ):
        fetch_mailbox_messages(
            api_base="http://127.0.0.1:8009",
            headers={
                "X-HANS-API-Key": "test",
            },
        )


@patch("app.ui.mailbox_client.requests.get")
def test_fetch_mailbox_attachment_returns_bytes_and_metadata(
    get_mock,
) -> None:
    response = Mock()
    response.ok = True
    response.content = b"%PDF-test"
    response.headers = {
        "Content-Type": "application/pdf",
        "X-HANS-Attachment-Filename": "transcript.pdf",
    }
    get_mock.return_value = response

    content, filename, content_type = fetch_mailbox_attachment(
        api_base="http://127.0.0.1:8009",
        headers={
            "X-HANS-API-Key": "test",
        },
        email_id="<message-1@example.com>",
        attachment_index=0,
    )

    assert content == b"%PDF-test"
    assert filename == "transcript.pdf"
    assert content_type == "application/pdf"

    requested_url = get_mock.call_args.args[0]
    assert "%3Cmessage-1%40example.com%3E" in requested_url


@patch("app.ui.mailbox_client.requests.get")
def test_fetch_mailbox_attachment_surfaces_backend_error(
    get_mock,
) -> None:
    response = Mock()
    response.ok = False
    response.status_code = 413
    response.json.return_value = {
        "detail": "Attachment is larger than the 25 MB viewing limit."
    }
    get_mock.return_value = response

    with pytest.raises(
        MailboxUIError,
        match="25 MB viewing limit",
    ):
        fetch_mailbox_attachment(
            api_base="http://127.0.0.1:8009",
            headers={
                "X-HANS-API-Key": "test",
            },
            email_id="<message-1@example.com>",
            attachment_index=0,
        )
