from __future__ import annotations

import html
import re
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import parseaddr
from typing import TypedDict


class EMLAttachment(TypedDict):
    filename: str
    content_type: str
    size_bytes: int


class ParsedEML(TypedDict):
    sender_email: str
    subject: str
    received_at: str
    body: str
    attachments: list[EMLAttachment]


def _html_to_text(value: str) -> str:
    text = re.sub(
        r"(?is)<(script|style).*?>.*?</\1>",
        "",
        value,
    )
    text = re.sub(
        r"(?i)<br\s*/?>",
        "\n",
        text,
    )
    text = re.sub(
        r"(?i)</p\s*>",
        "\n\n",
        text,
    )
    text = re.sub(
        r"(?s)<[^>]+>",
        "",
        text,
    )
    text = html.unescape(text)
    text = re.sub(
        r"\r\n?",
        "\n",
        text,
    )
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def _message_body(
    message: Message,
) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue

            if (
                part.get_content_disposition()
                == "attachment"
            ):
                continue

            content_type = (
                part.get_content_type()
            )

            if content_type not in {
                "text/plain",
                "text/html",
            }:
                continue

            try:
                content = part.get_content()
            except (
                LookupError,
                UnicodeDecodeError,
            ):
                payload = (
                    part.get_payload(
                        decode=True
                    )
                    or b""
                )

                charset = (
                    part.get_content_charset()
                    or "utf-8"
                )

                content = payload.decode(
                    charset,
                    errors="replace",
                )

            if not isinstance(
                content,
                str,
            ):
                continue

            if (
                content_type
                == "text/plain"
            ):
                plain_parts.append(
                    content.strip()
                )
            else:
                html_parts.append(
                    content
                )

    else:
        try:
            content = (
                message.get_content()
            )
        except (
            LookupError,
            UnicodeDecodeError,
        ):
            payload = (
                message.get_payload(
                    decode=True
                )
                or b""
            )

            charset = (
                message.get_content_charset()
                or "utf-8"
            )

            content = payload.decode(
                charset,
                errors="replace",
            )

        if isinstance(
            content,
            str,
        ):
            if (
                message.get_content_type()
                == "text/html"
            ):
                html_parts.append(
                    content
                )
            else:
                plain_parts.append(
                    content.strip()
                )

    plain_text = "\n\n".join(
        part
        for part in plain_parts
        if part
    ).strip()

    if plain_text:
        return plain_text

    html_text = "\n\n".join(
        part
        for part in html_parts
        if part
    )

    return _html_to_text(
        html_text
    )


def _attachment_parts(
    message: Message,
) -> list[Message]:
    parts: list[Message] = []

    for part in message.walk():
        if part.is_multipart():
            continue

        filename = str(
            part.get_filename()
            or ""
        ).strip()

        disposition = (
            part.get_content_disposition()
        )

        if (
            disposition != "attachment"
            and not filename
        ):
            continue

        parts.append(
            part
        )

    return parts


def _attachment_metadata(
    message: Message,
) -> list[EMLAttachment]:
    attachments: list[
        EMLAttachment
    ] = []

    for index, part in enumerate(
        _attachment_parts(
            message
        )
    ):
        filename = str(
            part.get_filename()
            or ""
        ).strip()

        if not filename:
            filename = (
                f"attachment-{index + 1}"
            )

        payload = (
            part.get_payload(
                decode=True
            )
            or b""
        )

        attachments.append(
            {
                "filename": filename,
                "content_type": (
                    part.get_content_type()
                ),
                "size_bytes": len(
                    payload
                ),
            }
        )

    return attachments


def parse_eml_bytes(
    data: bytes,
) -> ParsedEML:
    message = BytesParser(
        policy=policy.default
    ).parsebytes(
        data
    )

    reply_to = str(
        message.get(
            "Reply-To"
        )
        or ""
    ).strip()

    from_header = str(
        message.get(
            "From"
        )
        or ""
    ).strip()

    sender_email = parseaddr(
        reply_to
        or from_header
    )[1].strip()

    return {
        "sender_email": (
            sender_email
        ),
        "subject": str(
            message.get(
                "Subject"
            )
            or ""
        ).strip(),
        "received_at": str(
            message.get(
                "Date"
            )
            or ""
        ).strip(),
        "body": (
            _message_body(
                message
            )
        ),
        "attachments": (
            _attachment_metadata(
                message
            )
        ),
    }


def extract_eml_attachment(
    data: bytes,
    attachment_index: int,
) -> tuple[
    bytes,
    str,
    str,
]:
    message = BytesParser(
        policy=policy.default
    ).parsebytes(
        data
    )

    parts = _attachment_parts(
        message
    )

    if (
        attachment_index < 0
        or attachment_index
        >= len(parts)
    ):
        raise IndexError(
            "Attachment index is out of range."
        )

    part = parts[
        attachment_index
    ]

    filename = str(
        part.get_filename()
        or ""
    ).strip()

    if not filename:
        filename = (
            "attachment-"
            f"{attachment_index + 1}"
        )

    return (
        part.get_payload(
            decode=True
        )
        or b"",
        filename,
        part.get_content_type(),
    )


def build_reply_eml_bytes(
    *,
    recipient: str,
    subject: str,
    body: str,
) -> bytes:
    recipient = (
        recipient.strip()
    )
    subject = (
        subject.strip()
    )
    body = (
        body.strip()
    )

    if not body:
        raise ValueError(
            "There is no staff draft to export."
        )

    message = EmailMessage(
        policy=policy.default
    )

    if recipient:
        message["To"] = (
            recipient
        )

    if subject:
        reply_subject = (
            subject
        )

        if not re.match(
            r"(?i)^re\s*:",
            reply_subject,
        ):
            reply_subject = (
                f"Re: {reply_subject}"
            )

        message["Subject"] = (
            reply_subject
        )

    # Outlook-compatible indication that this
    # file represents an unsent message.
    # No From header is set. The staff member's
    # mail client chooses the sending account.
    message["X-Unsent"] = "1"

    message.set_content(
        body,
        charset="utf-8",
    )

    return message.as_bytes(
        policy=policy.default
    )
