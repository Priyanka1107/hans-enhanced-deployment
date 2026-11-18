from unittest.mock import Mock, patch

import pytest

from app.ui.mailbox_client import (
    MailboxUIError,
    save_mailbox_draft,
    send_mailbox_message,
)


@patch("app.ui.mailbox_client.requests.post")
def test_save_mailbox_draft_posts_expected_payload(post_mock) -> None:
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "status": "saved",
        "message_id": "<draft@example.com>",
        "automatic_send": False,
    }
    post_mock.return_value = response

    result = save_mailbox_draft(
        api_base="http://127.0.0.1:8009",
        headers={"X-HANS-API-Key": "test"},
        to_email="student@example.com",
        subject="Question",
        body="Draft body",
        in_reply_to="<source@example.com>",
    )

    assert result["status"] == "saved"
    kwargs = post_mock.call_args.kwargs
    assert kwargs["json"]["to_email"] == "student@example.com"
    assert kwargs["json"]["body"] == "Draft body"


@patch("app.ui.mailbox_client.requests.post")
def test_send_mailbox_message_surfaces_disabled_error(post_mock) -> None:
    response = Mock()
    response.ok = False
    response.status_code = 403
    response.json.return_value = {
        "detail": "Mailbox sending is disabled."
    }
    post_mock.return_value = response

    with pytest.raises(
        MailboxUIError,
        match="Mailbox sending is disabled",
    ):
        send_mailbox_message(
            api_base="http://127.0.0.1:8009",
            headers={"X-HANS-API-Key": "test"},
            to_email="student@example.com",
            subject="Question",
            body="Approved reply",
        )
