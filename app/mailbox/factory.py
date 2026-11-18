from __future__ import annotations

import os

from app.mailbox.imap_client import IMAPMailboxClient
from app.mailbox.imap_smtp_writer import IMAPSMTPMailboxWriter
from app.mailbox.protocol import MailboxClient
from app.mailbox.writer_protocol import MailboxWriter


def _env_bool(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def mailbox_enabled() -> bool:
    return _env_bool(
        "HANS_MAILBOX_ENABLED",
        False,
    )


def mailbox_write_enabled() -> bool:
    return _env_bool(
        "HANS_MAILBOX_WRITE_ENABLED",
        False,
    )


def mailbox_send_enabled() -> bool:
    return _env_bool(
        "HANS_MAILBOX_SEND_ENABLED",
        False,
    )


def build_mailbox_client() -> MailboxClient:
    provider = os.getenv(
        "HANS_MAILBOX_PROVIDER",
        "imap",
    ).strip().lower()

    if provider != "imap":
        raise RuntimeError(
            f"Unsupported HANS mailbox provider: {provider}"
        )

    return IMAPMailboxClient(
        host=os.getenv(
            "HANS_IMAP_HOST",
            "",
        ),
        port=int(
            os.getenv(
                "HANS_IMAP_PORT",
                "993",
            )
        ),
        username=os.getenv(
            "HANS_IMAP_USERNAME",
            "",
        ),
        password=os.getenv(
            "HANS_IMAP_PASSWORD",
            "",
        ),
        folder=os.getenv(
            "HANS_IMAP_FOLDER",
            "INBOX",
        ),
        use_ssl=_env_bool(
            "HANS_IMAP_USE_SSL",
            True,
        ),
    )


def build_mailbox_writer() -> MailboxWriter:
    provider = os.getenv(
        "HANS_MAILBOX_PROVIDER",
        "imap",
    ).strip().lower()

    if provider != "imap":
        raise RuntimeError(
            f"Unsupported HANS mailbox writer provider: {provider}"
        )

    imap_username = os.getenv(
        "HANS_IMAP_USERNAME",
        "",
    )
    imap_password = os.getenv(
        "HANS_IMAP_PASSWORD",
        "",
    )

    return IMAPSMTPMailboxWriter(
        imap_host=os.getenv(
            "HANS_IMAP_HOST",
            "",
        ),
        imap_port=int(
            os.getenv(
                "HANS_IMAP_PORT",
                "993",
            )
        ),
        imap_username=imap_username,
        imap_password=imap_password,
        drafts_folder=os.getenv(
            "HANS_IMAP_DRAFTS_FOLDER",
            "Drafts",
        ),
        imap_use_ssl=_env_bool(
            "HANS_IMAP_USE_SSL",
            True,
        ),
        smtp_host=os.getenv(
            "HANS_SMTP_HOST",
            "",
        ),
        smtp_port=int(
            os.getenv(
                "HANS_SMTP_PORT",
                "465",
            )
        ),
        smtp_username=(
            os.getenv("HANS_SMTP_USERNAME", "")
            or imap_username
        ),
        smtp_password=(
            os.getenv("HANS_SMTP_PASSWORD", "")
            or imap_password
        ),
        smtp_use_ssl=_env_bool(
            "HANS_SMTP_USE_SSL",
            True,
        ),
        smtp_starttls=_env_bool(
            "HANS_SMTP_STARTTLS",
            False,
        ),
    )
