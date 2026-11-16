from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.ui.mailbox_client import (
    MailboxUIError,
    attachment_summary,
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
