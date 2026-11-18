from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import enhanced_api_server as api


def run(coro):
    return asyncio.run(coro)


def test_api_key_rejects_request_when_server_key_is_not_configured(monkeypatch):
    monkeypatch.setattr(
        api,
        "settings",
        SimpleNamespace(api_key=""),
    )

    with pytest.raises(HTTPException) as exc:
        run(api.verify_internal_api_key("anything"))

    assert exc.value.status_code == 503


def test_api_key_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(
        api,
        "settings",
        SimpleNamespace(api_key="correct-key"),
    )

    with pytest.raises(HTTPException) as exc:
        run(api.verify_internal_api_key("wrong-key"))

    assert exc.value.status_code == 401


def test_api_key_accepts_matching_key(monkeypatch):
    monkeypatch.setattr(
        api,
        "settings",
        SimpleNamespace(api_key="correct-key"),
    )

    assert run(api.verify_internal_api_key("correct-key")) is None


def test_email_request_rejects_empty_email():
    with pytest.raises(ValidationError):
        api.EmailRequest(email_text="")


def test_email_request_rejects_top_k_below_minimum():
    with pytest.raises(ValidationError):
        api.EmailRequest(
            email_text="Hello",
            top_k=2,
        )


def test_email_request_rejects_top_k_above_maximum():
    with pytest.raises(ValidationError):
        api.EmailRequest(
            email_text="Hello",
            top_k=11,
        )


def test_mailbox_write_request_rejects_empty_body():
    with pytest.raises(ValidationError):
        api.MailboxWriteRequest(
            to_email="student@example.com",
            body="",
        )


def test_mailbox_status_always_reports_automatic_send_false():
    with (
        patch.object(api, "mailbox_enabled", return_value=True),
        patch.object(api, "mailbox_write_enabled", return_value=True),
        patch.object(api, "mailbox_send_enabled", return_value=True),
    ):
        result = run(api.mailbox_status())

    assert result["automatic_send"] is False
    assert result["enabled"] is True
    assert result["write_enabled"] is True
    assert result["send_enabled"] is True


def test_mailbox_messages_refuses_when_mailbox_is_disabled():
    with patch.object(api, "mailbox_enabled", return_value=False):
        with pytest.raises(HTTPException) as exc:
            run(api.mailbox_messages())

    assert exc.value.status_code == 503


@pytest.mark.parametrize("limit", [0, 101])
def test_mailbox_messages_rejects_invalid_message_limit(limit):
    with patch.object(api, "mailbox_enabled", return_value=True):
        with pytest.raises(HTTPException) as exc:
            run(
                api.mailbox_messages(
                    limit=limit,
                    unread_only=True,
                )
            )

    assert exc.value.status_code == 400


def test_mailbox_messages_returns_normalized_read_only_response():
    message = Mock()
    message.to_dict.return_value = {
        "email_id": "m1",
        "student_email": "student@example.com",
    }

    client = Mock()
    client.list_messages.return_value = [message]

    with (
        patch.object(api, "mailbox_enabled", return_value=True),
        patch.object(api, "build_mailbox_client", return_value=client),
    ):
        result = run(
            api.mailbox_messages(
                limit=20,
                unread_only=True,
            )
        )

    assert result["count"] == 1
    assert result["read_only"] is True
    assert result["automatic_send"] is False


def test_mailbox_message_provider_failure_becomes_502():
    client = Mock()
    client.list_messages.side_effect = RuntimeError("provider unavailable")

    with (
        patch.object(api, "mailbox_enabled", return_value=True),
        patch.object(api, "build_mailbox_client", return_value=client),
    ):
        with pytest.raises(HTTPException) as exc:
            run(api.mailbox_messages())

    assert exc.value.status_code == 502


def test_attachment_viewing_refuses_when_mailbox_is_disabled():
    with patch.object(api, "mailbox_enabled", return_value=False):
        with pytest.raises(HTTPException) as exc:
            run(
                api.mailbox_attachment(
                    email_id="<m1@example.com>",
                    attachment_index=0,
                )
            )

    assert exc.value.status_code == 503


def test_attachment_viewing_rejects_negative_index():
    with patch.object(api, "mailbox_enabled", return_value=True):
        with pytest.raises(HTTPException) as exc:
            run(
                api.mailbox_attachment(
                    email_id="<m1@example.com>",
                    attachment_index=-1,
                )
            )

    assert exc.value.status_code == 400


def test_attachment_viewing_returns_inline_bytes():
    client = Mock()
    client.get_attachment.return_value = (
        b"%PDF-test",
        "transcript.pdf",
        "application/pdf",
    )

    with (
        patch.object(api, "mailbox_enabled", return_value=True),
        patch.object(api, "build_mailbox_client", return_value=client),
    ):
        response = run(
            api.mailbox_attachment(
                email_id="<m1@example.com>",
                attachment_index=0,
            )
        )

    assert response.body == b"%PDF-test"
    assert response.media_type == "application/pdf"
    assert response.headers["x-hans-attachment-filename"] == "transcript.pdf"


def test_attachment_viewing_rejects_files_over_25_mb():
    client = Mock()
    client.get_attachment.return_value = (
        b"x" * (25 * 1024 * 1024 + 1),
        "large.pdf",
        "application/pdf",
    )

    with (
        patch.object(api, "mailbox_enabled", return_value=True),
        patch.object(api, "build_mailbox_client", return_value=client),
    ):
        with pytest.raises(HTTPException) as exc:
            run(
                api.mailbox_attachment(
                    email_id="<m1@example.com>",
                    attachment_index=0,
                )
            )

    assert exc.value.status_code == 413


def test_attachment_not_found_becomes_404():
    client = Mock()
    client.get_attachment.side_effect = IndexError(
        "The requested attachment does not exist."
    )

    with (
        patch.object(api, "mailbox_enabled", return_value=True),
        patch.object(api, "build_mailbox_client", return_value=client),
    ):
        with pytest.raises(HTTPException) as exc:
            run(
                api.mailbox_attachment(
                    email_id="<m1@example.com>",
                    attachment_index=5,
                )
            )

    assert exc.value.status_code == 404


def test_saving_draft_is_blocked_when_write_is_disabled():
    request = api.MailboxWriteRequest(
        to_email="student@example.com",
        subject="Question",
        body="Draft reply",
    )

    with patch.object(api, "mailbox_write_enabled", return_value=False):
        with pytest.raises(HTTPException) as exc:
            run(api.mailbox_save_draft(request))

    assert exc.value.status_code == 403


def test_saving_draft_calls_writer_only_after_explicit_request():
    request = api.MailboxWriteRequest(
        to_email="student@example.com",
        subject="Question",
        body="Draft reply",
        in_reply_to="<m1@example.com>",
    )
    writer = Mock()
    writer.save_draft.return_value = "<draft@example.com>"

    with (
        patch.object(api, "mailbox_write_enabled", return_value=True),
        patch.object(api, "build_mailbox_writer", return_value=writer),
    ):
        result = run(api.mailbox_save_draft(request))

    assert result["status"] == "saved"
    assert result["automatic_send"] is False
    writer.save_draft.assert_called_once()


def test_sending_is_blocked_when_send_is_disabled():
    request = api.MailboxWriteRequest(
        to_email="student@example.com",
        subject="Question",
        body="Approved reply",
    )

    with patch.object(api, "mailbox_send_enabled", return_value=False):
        with pytest.raises(HTTPException) as exc:
            run(api.mailbox_send(request))

    assert exc.value.status_code == 403


def test_send_endpoint_calls_writer_only_after_explicit_request():
    request = api.MailboxWriteRequest(
        to_email="student@example.com",
        subject="Question",
        body="Approved reply",
        in_reply_to="<m1@example.com>",
    )
    writer = Mock()
    writer.send_message.return_value = "<sent@example.com>"

    with (
        patch.object(api, "mailbox_send_enabled", return_value=True),
        patch.object(api, "build_mailbox_writer", return_value=writer),
    ):
        result = run(api.mailbox_send(request))

    assert result["status"] == "sent"
    assert result["automatic_send"] is False
    writer.send_message.assert_called_once()


def test_email_generation_returns_503_when_service_is_not_initialized(monkeypatch):
    monkeypatch.setattr(api, "email_service", None)

    request = api.EmailRequest(
        email_text="What is the application deadline?"
    )

    with pytest.raises(HTTPException) as exc:
        run(api.process_email(request))

    assert exc.value.status_code == 503


def test_email_generation_converts_service_value_error_to_400(monkeypatch):
    service = Mock()
    service.process_email.side_effect = ValueError("invalid request")
    monkeypatch.setattr(api, "email_service", service)

    request = api.EmailRequest(
        email_text="What is the application deadline?"
    )

    with pytest.raises(HTTPException) as exc:
        run(api.process_email(request))

    assert exc.value.status_code == 400


def test_email_generation_converts_unexpected_failure_to_manual_review_error(monkeypatch):
    service = Mock()
    service.process_email.side_effect = RuntimeError("model down")
    monkeypatch.setattr(api, "email_service", service)

    request = api.EmailRequest(
        email_text="What is the application deadline?"
    )

    with pytest.raises(HTTPException) as exc:
        run(api.process_email(request))

    assert exc.value.status_code == 500
    assert "reviewed manually" in exc.value.detail
