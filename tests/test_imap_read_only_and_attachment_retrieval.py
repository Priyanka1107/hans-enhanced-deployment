from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.mailbox.imap_client import (
    IMAPMailboxClient,
    IMAPMailboxError,
)


def make_client() -> IMAPMailboxClient:
    return IMAPMailboxClient(
        host="imap.example.com",
        port=993,
        username="staff@example.com",
        password="secret",
        folder="HANS-Test",
        use_ssl=True,
    )


def raw_message_with_attachment() -> bytes:
    return (
        b"From: student@example.com\r\n"
        b"To: staff@example.com\r\n"
        b"Message-ID: <message-1@example.com>\r\n"
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
        b"JVBERi0xLjQ=\r\n"
        b"--abc--\r\n"
    )


def test_inbox_listing_opens_folder_read_only_and_uses_body_peek(monkeypatch):
    client = make_client()
    connection = Mock()

    connection.select.return_value = ("OK", [b"1"])
    connection.search.return_value = ("OK", [b"1"])
    connection.fetch.return_value = (
        "OK",
        [(b"1 (BODY[] {100}", raw_message_with_attachment())],
    )

    monkeypatch.setattr(
        client,
        "_connect",
        lambda: connection,
    )

    messages = client.list_messages(
        limit=20,
        unread_only=True,
    )

    connection.select.assert_called_once_with(
        "HANS-Test",
        readonly=True,
    )
    connection.search.assert_called_once_with(
        None,
        "UNSEEN",
    )
    connection.fetch.assert_called_once_with(
        b"1",
        "(BODY.PEEK[])",
    )

    assert len(messages) == 1
    assert messages[0].email_id == "<message-1@example.com>"
    assert messages[0].sender_email == "student@example.com"
    assert len(messages[0].attachments) == 1


def test_inbox_listing_can_request_all_messages(monkeypatch):
    client = make_client()
    connection = Mock()

    connection.select.return_value = ("OK", [b"1"])
    connection.search.return_value = ("OK", [b""])
    monkeypatch.setattr(
        client,
        "_connect",
        lambda: connection,
    )

    assert client.list_messages(
        limit=20,
        unread_only=False,
    ) == []

    connection.search.assert_called_once_with(
        None,
        "ALL",
    )


def test_inbox_listing_with_zero_limit_does_not_connect(monkeypatch):
    client = make_client()
    connect = Mock()
    monkeypatch.setattr(
        client,
        "_connect",
        connect,
    )

    assert client.list_messages(limit=0) == []
    connect.assert_not_called()


def test_attachment_fetch_searches_by_message_id_and_uses_body_peek(monkeypatch):
    client = make_client()
    connection = Mock()

    connection.select.return_value = ("OK", [b"1"])
    connection.search.return_value = ("OK", [b"7"])
    connection.fetch.return_value = (
        "OK",
        [(b"7 (BODY[] {100}", raw_message_with_attachment())],
    )

    monkeypatch.setattr(
        client,
        "_connect",
        lambda: connection,
    )

    content, filename, content_type = client.get_attachment(
        email_id="<message-1@example.com>",
        attachment_index=0,
    )

    connection.select.assert_called_once_with(
        "HANS-Test",
        readonly=True,
    )
    connection.search.assert_called_once_with(
        None,
        "HEADER",
        "Message-ID",
        "<message-1@example.com>",
    )
    connection.fetch.assert_called_once_with(
        b"7",
        "(BODY.PEEK[])",
    )

    assert content.startswith(b"%PDF")
    assert filename == "transcript.pdf"
    assert content_type == "application/pdf"


def test_attachment_fetch_rejects_missing_email_id():
    client = make_client()

    with pytest.raises(
        ValueError,
        match="email_id is required",
    ):
        client.get_attachment(
            email_id="",
            attachment_index=0,
        )


def test_attachment_fetch_rejects_negative_index():
    client = make_client()

    with pytest.raises(
        ValueError,
        match="zero or greater",
    ):
        client.get_attachment(
            email_id="<message-1@example.com>",
            attachment_index=-1,
        )


def test_attachment_fetch_reports_message_not_found(monkeypatch):
    client = make_client()
    connection = Mock()

    connection.select.return_value = ("OK", [b"1"])
    connection.search.return_value = ("OK", [b""])

    monkeypatch.setattr(
        client,
        "_connect",
        lambda: connection,
    )

    with pytest.raises(
        IMAPMailboxError,
        match="message was not found",
    ):
        client.get_attachment(
            email_id="<missing@example.com>",
            attachment_index=0,
        )


def test_attachment_fetch_reports_out_of_range_attachment(monkeypatch):
    client = make_client()
    connection = Mock()

    connection.select.return_value = ("OK", [b"1"])
    connection.search.return_value = ("OK", [b"7"])
    connection.fetch.return_value = (
        "OK",
        [(b"7 (BODY[] {100}", raw_message_with_attachment())],
    )

    monkeypatch.setattr(
        client,
        "_connect",
        lambda: connection,
    )

    with pytest.raises(
        IndexError,
        match="attachment does not exist",
    ):
        client.get_attachment(
            email_id="<message-1@example.com>",
            attachment_index=5,
        )
