from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MailboxAttachment:
    filename: str
    content_type: str
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MailboxMessage:
    email_id: str
    thread_id: str
    sender_email: str
    subject: str
    email_text: str
    received_at: str
    attachments: tuple[MailboxAttachment, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "email_id": self.email_id,
            "thread_id": self.thread_id,
            "student_email": self.sender_email,
            "subject": self.subject,
            "email_text": self.email_text,
            "received_at": self.received_at,
            "attachment_count": len(self.attachments),
            "attachments": [
                attachment.to_dict()
                for attachment in self.attachments
            ],
        }
