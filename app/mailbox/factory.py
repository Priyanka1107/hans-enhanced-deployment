from __future__ import annotations

import os

from app.mailbox.imap_client import IMAPMailboxClient
from app.mailbox.protocol import MailboxClient


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
