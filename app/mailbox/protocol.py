from __future__ import annotations

from typing import Protocol

from app.mailbox.models import MailboxMessage


class MailboxClient(Protocol):
    """Read-only mailbox interface used by the HANS staff UI."""

    def list_messages(
        self,
        *,
        limit: int = 20,
        unread_only: bool = True,
    ) -> list[MailboxMessage]:
        ...
