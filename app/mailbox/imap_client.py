from __future__ import annotations

from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
import html
import imaplib
import re
from typing import Iterable

from app.mailbox.models import (
    MailboxAttachment,
    MailboxMessage,
)


class IMAPMailboxError(RuntimeError):
    pass


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""

    try:
        return str(
            make_header(
                decode_header(value)
            )
        ).strip()
    except Exception:
        return str(value).strip()


def _html_to_text(value: str) -> str:
    text = re.sub(
        r"(?is)<(script|style).*?>.*?</\\1>",
        " ",
        value or "",
    )
    text = re.sub(
        r"(?i)<br\\s*/?>",
        "\n",
        text,
    )
    text = re.sub(
        r"(?i)</p\\s*>",
        "\n\n",
        text,
    )
    text = re.sub(
        r"(?s)<[^>]+>",
        " ",
        text,
    )
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _message_body(message: Message) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    parts: Iterable[Message]

    if message.is_multipart():
        parts = message.walk()
    else:
        parts = (message,)

    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue

        content_type = part.get_content_type()

        if content_type not in {
            "text/plain",
            "text/html",
        }:
            continue

        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(
                charset,
                errors="replace",
            )

        if not isinstance(content, str):
            continue

        if content_type == "text/plain":
            plain_parts.append(content.strip())
        else:
            html_parts.append(
                _html_to_text(content)
            )

    if plain_parts:
        return "\n\n".join(
            part
            for part in plain_parts
            if part
        ).strip()

    return "\n\n".join(
        part
        for part in html_parts
        if part
    ).strip()


def _attachments(
    message: Message,
) -> tuple[MailboxAttachment, ...]:
    attachments: list[MailboxAttachment] = []

    for part in message.walk():
        if part.get_content_disposition() != "attachment":
            continue

        filename = _decode_header_value(
            part.get_filename()
        )
        payload = part.get_payload(
            decode=True
        )

        attachments.append(
            MailboxAttachment(
                filename=filename or "attachment",
                content_type=part.get_content_type(),
                size_bytes=(
                    len(payload)
                    if payload is not None
                    else None
                ),
            )
        )

    return tuple(attachments)


def _received_at(message: Message) -> str:
    raw_date = message.get("Date")

    if not raw_date:
        return ""

    try:
        return parsedate_to_datetime(
            raw_date
        ).isoformat()
    except Exception:
        return _decode_header_value(raw_date)


class IMAPMailboxClient:
    """
    Read-only IMAP mailbox client.

    It uses BODY.PEEK so fetching a message does not intentionally mark it
    as read. HANS never deletes, moves, replies to, or modifies mailbox mail.
    """

    def __init__(
        self,
        *,
        host: str,
        username: str,
        password: str,
        folder: str = "INBOX",
        port: int = 993,
        use_ssl: bool = True,
    ) -> None:
        self.host = host.strip()
        self.username = username.strip()
        self.password = password
        self.folder = folder.strip() or "INBOX"
        self.port = port
        self.use_ssl = use_ssl

        if not self.host:
            raise ValueError(
                "IMAP host is required"
            )

        if not self.username:
            raise ValueError(
                "IMAP username is required"
            )

        if not self.password:
            raise ValueError(
                "IMAP password is required"
            )

    def _connect(self):
        try:
            if self.use_ssl:
                connection = imaplib.IMAP4_SSL(
                    self.host,
                    self.port,
                )
            else:
                connection = imaplib.IMAP4(
                    self.host,
                    self.port,
                )

            connection.login(
                self.username,
                self.password,
            )
            return connection
        except Exception as exc:
            raise IMAPMailboxError(
                "Unable to connect or authenticate to the configured mailbox."
            ) from exc

    def get_attachment(
        self,
        *,
        email_id: str,
        attachment_index: int,
    ) -> tuple[bytes, str, str]:
        """
        Fetch one attachment by Message-ID and zero-based attachment index.

        The message is opened read-only and BODY.PEEK is used so viewing an
        attachment does not intentionally alter mailbox state.
        """
        if not email_id.strip():
            raise ValueError("email_id is required")

        if attachment_index < 0:
            raise ValueError("attachment_index must be zero or greater")

        connection = self._connect()

        try:
            status, _ = connection.select(
                self.folder,
                readonly=True,
            )
            if status != "OK":
                raise IMAPMailboxError(
                    "Unable to open the configured mailbox folder."
                )

            status, data = connection.search(
                None,
                "HEADER",
                "Message-ID",
                email_id.strip(),
            )
            if status != "OK":
                raise IMAPMailboxError(
                    "Unable to search for the requested mailbox message."
                )

            message_numbers = (
                data[0].split()
                if data and data[0]
                else []
            )
            if not message_numbers:
                raise IMAPMailboxError(
                    "The requested mailbox message was not found."
                )

            status, payload = connection.fetch(
                message_numbers[-1],
                "(BODY.PEEK[])",
            )
            if status != "OK" or not payload:
                raise IMAPMailboxError(
                    "Unable to read the requested mailbox message."
                )

            raw_message = next(
                (
                    item[1]
                    for item in payload
                    if (
                        isinstance(item, tuple)
                        and len(item) >= 2
                        and isinstance(item[1], bytes)
                    )
                ),
                None,
            )
            if raw_message is None:
                raise IMAPMailboxError(
                    "The requested mailbox message had no readable payload."
                )

            parsed = BytesParser(
                policy=policy.default,
            ).parsebytes(raw_message)

            parts = [
                part
                for part in parsed.walk()
                if part.get_content_disposition() == "attachment"
            ]
            if attachment_index >= len(parts):
                raise IndexError(
                    "The requested attachment does not exist."
                )

            part = parts[attachment_index]
            content = part.get_payload(decode=True)
            if content is None:
                content = b""

            filename = _decode_header_value(
                part.get_filename()
            ) or "attachment"
            content_type = (
                part.get_content_type()
                or "application/octet-stream"
            )

            return content, filename, content_type
        finally:
            try:
                connection.close()
            except Exception:
                pass
            try:
                connection.logout()
            except Exception:
                pass

    def list_messages(
        self,
        *,
        limit: int = 20,
        unread_only: bool = True,
    ) -> list[MailboxMessage]:
        if limit < 1:
            return []

        connection = self._connect()

        try:
            status, _ = connection.select(
                self.folder,
                readonly=True,
            )

            if status != "OK":
                raise IMAPMailboxError(
                    "Unable to open the configured mailbox folder."
                )

            criterion = "UNSEEN" if unread_only else "ALL"
            status, data = connection.search(
                None,
                criterion,
            )

            if status != "OK":
                raise IMAPMailboxError(
                    "Unable to search the configured mailbox folder."
                )

            message_numbers = (
                data[0].split()
                if data and data[0]
                else []
            )

            selected = list(
                reversed(
                    message_numbers[-limit:]
                )
            )

            messages: list[MailboxMessage] = []

            for sequence_number in selected:
                status, payload = connection.fetch(
                    sequence_number,
                    "(BODY.PEEK[])",
                )

                if status != "OK" or not payload:
                    continue

                raw_message = next(
                    (
                        item[1]
                        for item in payload
                        if (
                            isinstance(item, tuple)
                            and len(item) >= 2
                            and isinstance(
                                item[1],
                                bytes,
                            )
                        )
                    ),
                    None,
                )

                if raw_message is None:
                    continue

                parsed = BytesParser(
                    policy=policy.default,
                ).parsebytes(raw_message)

                message_id = _decode_header_value(
                    parsed.get("Message-ID")
                )

                if not message_id:
                    message_id = (
                        f"imap-{sequence_number.decode(errors='ignore')}"
                    )

                references = _decode_header_value(
                    parsed.get("References")
                )
                in_reply_to = _decode_header_value(
                    parsed.get("In-Reply-To")
                )

                thread_id = (
                    references.split()[0]
                    if references
                    else in_reply_to
                    or message_id
                )

                sender_email = parseaddr(
                    _decode_header_value(
                        parsed.get("From")
                    )
                )[1]

                messages.append(
                    MailboxMessage(
                        email_id=message_id,
                        thread_id=thread_id,
                        sender_email=sender_email,
                        subject=_decode_header_value(
                            parsed.get("Subject")
                        ),
                        email_text=_message_body(
                            parsed
                        ),
                        received_at=_received_at(
                            parsed
                        ),
                        attachments=_attachments(
                            parsed
                        ),
                    )
                )

            return messages
        finally:
            try:
                connection.close()
            except Exception:
                pass

            try:
                connection.logout()
            except Exception:
                pass
