from __future__ import annotations

from unittest.mock import patch

import pytest

from app.mailbox import factory


def test_mailbox_is_disabled_by_default_when_environment_flag_is_missing(monkeypatch):
    monkeypatch.delenv("HANS_MAILBOX_ENABLED", raising=False)

    assert factory.mailbox_enabled() is False


def test_mailbox_write_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("HANS_MAILBOX_WRITE_ENABLED", raising=False)

    assert factory.mailbox_write_enabled() is False


def test_mailbox_send_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("HANS_MAILBOX_SEND_ENABLED", raising=False)

    assert factory.mailbox_send_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_boolean_environment_flags_accept_common_true_values(monkeypatch, value):
    monkeypatch.setenv("HANS_MAILBOX_ENABLED", value)

    assert factory.mailbox_enabled() is True


def test_unsupported_mailbox_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("HANS_MAILBOX_PROVIDER", "unknown")

    with pytest.raises(RuntimeError, match="Unsupported HANS mailbox provider"):
        factory.build_mailbox_client()


def test_unsupported_mailbox_writer_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("HANS_MAILBOX_PROVIDER", "unknown")

    with pytest.raises(
        RuntimeError,
        match="Unsupported HANS mailbox writer provider",
    ):
        factory.build_mailbox_writer()


def test_mailbox_reader_uses_expected_imap_configuration(monkeypatch):
    monkeypatch.setenv("HANS_MAILBOX_PROVIDER", "imap")
    monkeypatch.setenv("HANS_IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("HANS_IMAP_PORT", "993")
    monkeypatch.setenv("HANS_IMAP_USERNAME", "staff@example.com")
    monkeypatch.setenv("HANS_IMAP_PASSWORD", "secret")
    monkeypatch.setenv("HANS_IMAP_FOLDER", "HANS-Test")
    monkeypatch.setenv("HANS_IMAP_USE_SSL", "true")

    client = factory.build_mailbox_client()

    assert client.host == "imap.example.com"
    assert client.port == 993
    assert client.username == "staff@example.com"
    assert client.folder == "HANS-Test"
    assert client.use_ssl is True


def test_mailbox_writer_reuses_imap_credentials_when_smtp_credentials_are_blank(
    monkeypatch,
):
    monkeypatch.setenv("HANS_MAILBOX_PROVIDER", "imap")
    monkeypatch.setenv("HANS_IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("HANS_IMAP_USERNAME", "staff@example.com")
    monkeypatch.setenv("HANS_IMAP_PASSWORD", "imap-app-password")
    monkeypatch.setenv("HANS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("HANS_SMTP_USERNAME", "")
    monkeypatch.setenv("HANS_SMTP_PASSWORD", "")

    writer = factory.build_mailbox_writer()

    assert writer.smtp_username == "staff@example.com"
    assert writer.smtp_password == "imap-app-password"


def test_mailbox_writer_uses_explicit_smtp_credentials_when_provided(monkeypatch):
    monkeypatch.setenv("HANS_MAILBOX_PROVIDER", "imap")
    monkeypatch.setenv("HANS_IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("HANS_IMAP_USERNAME", "imap@example.com")
    monkeypatch.setenv("HANS_IMAP_PASSWORD", "imap-secret")
    monkeypatch.setenv("HANS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("HANS_SMTP_USERNAME", "smtp@example.com")
    monkeypatch.setenv("HANS_SMTP_PASSWORD", "smtp-secret")

    writer = factory.build_mailbox_writer()

    assert writer.smtp_username == "smtp@example.com"
    assert writer.smtp_password == "smtp-secret"
