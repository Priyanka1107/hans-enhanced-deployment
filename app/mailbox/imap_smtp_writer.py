from __future__ import annotations

from email.message import EmailMessage
from email.utils import make_msgid
import imaplib
import smtplib
import ssl


class MailboxWriteError(RuntimeError):
    pass


def _reply_subject(subject: str) -> str:
    value = (subject or "").strip()

    if not value:
        return "Re: HANS enquiry"

    if value.lower().startswith("re:"):
        return value

    return f"Re: {value}"


class IMAPSMTPMailboxWriter:
    """
    Test/provider implementation for mailbox draft creation and sending.

    Drafts are stored with IMAP APPEND. Sending uses SMTP. This is suitable
    for the current controlled Gmail test mailbox. A Microsoft Graph writer
    can implement the same MailboxWriter protocol later for production.
    """

    def __init__(
        self,
        *,
        imap_host: str,
        imap_port: int,
        imap_username: str,
        imap_password: str,
        drafts_folder: str,
        imap_use_ssl: bool,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        smtp_use_ssl: bool,
        smtp_starttls: bool,
    ) -> None:
        self.imap_host = imap_host.strip()
        self.imap_port = imap_port
        self.imap_username = imap_username.strip()
        self.imap_password = imap_password
        self.drafts_folder = drafts_folder.strip() or "Drafts"
        self.imap_use_ssl = imap_use_ssl

        self.smtp_host = smtp_host.strip()
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username.strip()
        self.smtp_password = smtp_password
        self.smtp_use_ssl = smtp_use_ssl
        self.smtp_starttls = smtp_starttls

        if not self.imap_host:
            raise ValueError("IMAP host is required for draft creation")
        if not self.imap_username:
            raise ValueError("IMAP username is required for draft creation")
        if not self.imap_password:
            raise ValueError("IMAP password is required for draft creation")

    def _build_message(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        in_reply_to: str | None,
    ) -> EmailMessage:
        recipient = (to_email or "").strip()
        message_body = (body or "").strip()

        if not recipient:
            raise ValueError("Recipient email address is required")
        if not message_body:
            raise ValueError("Draft body is empty")

        message = EmailMessage()
        message["Message-ID"] = make_msgid()
        message["From"] = (
            self.smtp_username
            or self.imap_username
        )
        message["To"] = recipient
        message["Subject"] = _reply_subject(subject)

        reply_id = (in_reply_to or "").strip()
        if reply_id:
            message["In-Reply-To"] = reply_id
            message["References"] = reply_id

        message.set_content(message_body)
        return message

    def _connect_imap(self):
        try:
            if self.imap_use_ssl:
                connection = imaplib.IMAP4_SSL(
                    self.imap_host,
                    self.imap_port,
                )
            else:
                connection = imaplib.IMAP4(
                    self.imap_host,
                    self.imap_port,
                )

            connection.login(
                self.imap_username,
                self.imap_password,
            )
            return connection
        except Exception as exc:
            raise MailboxWriteError(
                "Unable to connect to the mailbox for draft creation."
            ) from exc

    def save_draft(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> str:
        message = self._build_message(
            to_email=to_email,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
        )
        connection = self._connect_imap()

        try:
            status, _ = connection.append(
                self.drafts_folder,
                "\\Draft",
                None,
                message.as_bytes(),
            )

            if status != "OK":
                raise MailboxWriteError(
                    "The mailbox rejected the draft creation request. "
                    "Check HANS_IMAP_DRAFTS_FOLDER."
                )

            return str(message["Message-ID"])
        finally:
            try:
                connection.logout()
            except Exception:
                pass

    def send_message(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> str:
        if not self.smtp_host:
            raise ValueError(
                "SMTP host is required for sending"
            )
        if not self.smtp_username:
            raise ValueError(
                "SMTP username is required for sending"
            )
        if not self.smtp_password:
            raise ValueError(
                "SMTP password is required for sending"
            )

        message = self._build_message(
            to_email=to_email,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
        )

        try:
            if self.smtp_use_ssl:
                connection = smtplib.SMTP_SSL(
                    self.smtp_host,
                    self.smtp_port,
                    context=ssl.create_default_context(),
                    timeout=60,
                )
            else:
                connection = smtplib.SMTP(
                    self.smtp_host,
                    self.smtp_port,
                    timeout=60,
                )

                if self.smtp_starttls:
                    connection.starttls(
                        context=ssl.create_default_context()
                    )

            try:
                connection.login(
                    self.smtp_username,
                    self.smtp_password,
                )
                connection.send_message(message)
            finally:
                try:
                    connection.quit()
                except Exception:
                    pass
        except Exception as exc:
            raise MailboxWriteError(
                "The configured mailbox could not send the message."
            ) from exc

        return str(message["Message-ID"])
