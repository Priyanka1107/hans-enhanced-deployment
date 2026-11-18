from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import quote

import requests


class MailboxUIError(RuntimeError):
    """Readable mailbox error for the staff-facing UI."""


def _error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text.strip()

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if detail:
            return str(detail)

    return str(payload)


def fetch_mailbox_status(
    *,
    api_base: str,
    headers: Dict[str, str],
    timeout: float = 30.0,
) -> Dict[str, Any]:
    try:
        response = requests.get(
            f"{api_base.rstrip('/')}/mailbox/status",
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MailboxUIError(
            "Could not reach the HANS mailbox endpoint."
        ) from exc

    if not response.ok:
        raise MailboxUIError(
            _error_detail(response)
            or f"Mailbox status request failed ({response.status_code})."
        )

    payload = response.json()

    if not isinstance(payload, dict):
        raise MailboxUIError(
            "Mailbox status response has an unexpected format."
        )

    return payload


def fetch_mailbox_messages(
    *,
    api_base: str,
    headers: Dict[str, str],
    limit: int = 20,
    unread_only: bool = True,
    timeout: float = 60.0,
) -> List[Dict[str, Any]]:
    try:
        response = requests.get(
            f"{api_base.rstrip('/')}/mailbox/messages",
            headers=headers,
            params={
                "limit": limit,
                "unread_only": str(
                    bool(unread_only)
                ).lower(),
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MailboxUIError(
            "Could not read messages from the configured mailbox."
        ) from exc

    if not response.ok:
        raise MailboxUIError(
            _error_detail(response)
            or f"Mailbox request failed ({response.status_code})."
        )

    payload = response.json()

    if not isinstance(payload, dict):
        raise MailboxUIError(
            "Mailbox response has an unexpected format."
        )

    messages = payload.get("messages", [])

    if not isinstance(messages, list):
        raise MailboxUIError(
            "Mailbox response does not contain a valid message list."
        )

    return [
        message
        for message in messages
        if isinstance(message, dict)
    ]


def fetch_mailbox_attachment(
    *,
    api_base: str,
    headers: Dict[str, str],
    email_id: str,
    attachment_index: int,
    timeout: float = 60.0,
) -> tuple[bytes, str, str]:
    try:
        response = requests.get(
            (
                f"{api_base.rstrip('/')}/mailbox/messages/"
                f"{quote(email_id, safe='')}/attachments/{attachment_index}"
            ),
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MailboxUIError(
            "Could not retrieve the requested attachment."
        ) from exc

    if not response.ok:
        raise MailboxUIError(
            _error_detail(response)
            or (
                "Mailbox attachment request failed "
                f"({response.status_code})."
            )
        )

    filename = (
        response.headers.get(
            "X-HANS-Attachment-Filename"
        )
        or "attachment"
    )
    content_type = (
        response.headers.get("Content-Type")
        or "application/octet-stream"
    ).split(";", 1)[0].strip()

    return response.content, filename, content_type


def attachment_summary(
    message: Dict[str, Any],
) -> str:
    attachments = message.get("attachments") or []

    if not attachments:
        return "No attachments"

    names = [
        str(item.get("filename") or "attachment")
        for item in attachments
        if isinstance(item, dict)
    ]

    if not names:
        count = int(
            message.get("attachment_count") or 0
        )
        return (
            f"{count} attachment(s)"
            if count
            else "No attachments"
        )

    return ", ".join(names)



def _post_mailbox_write(
    *,
    api_base: str,
    endpoint: str,
    headers: Dict[str, str],
    to_email: str,
    subject: str,
    body: str,
    in_reply_to: str | None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    try:
        response = requests.post(
            f"{api_base.rstrip('/')}{endpoint}",
            headers=headers,
            json={
                "to_email": to_email,
                "subject": subject,
                "body": body,
                "in_reply_to": in_reply_to,
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MailboxUIError(
            "Could not reach the HANS mailbox write endpoint."
        ) from exc

    if not response.ok:
        raise MailboxUIError(
            _error_detail(response)
            or f"Mailbox write request failed ({response.status_code})."
        )

    payload = response.json()
    if not isinstance(payload, dict):
        raise MailboxUIError(
            "Mailbox write response has an unexpected format."
        )

    return payload


def save_mailbox_draft(
    *,
    api_base: str,
    headers: Dict[str, str],
    to_email: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    return _post_mailbox_write(
        api_base=api_base,
        endpoint="/mailbox/drafts",
        headers=headers,
        to_email=to_email,
        subject=subject,
        body=body,
        in_reply_to=in_reply_to,
        timeout=timeout,
    )


def send_mailbox_message(
    *,
    api_base: str,
    headers: Dict[str, str],
    to_email: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    return _post_mailbox_write(
        api_base=api_base,
        endpoint="/mailbox/send",
        headers=headers,
        to_email=to_email,
        subject=subject,
        body=body,
        in_reply_to=in_reply_to,
        timeout=timeout,
    )
