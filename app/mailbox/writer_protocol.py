from __future__ import annotations

from typing import Protocol


class MailboxWriter(Protocol):
    """Write operations used by the staff-reviewed HANS workflow."""

    def save_draft(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> str:
        """Create a mailbox draft and return its Message-ID."""
        ...

    def send_message(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> str:
        """Send one staff-approved message and return its Message-ID."""
        ...
