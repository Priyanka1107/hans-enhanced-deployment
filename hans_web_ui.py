from __future__ import annotations

import base64
import hashlib
import html
import io
import mimetypes
import os
import zipfile
import re
import time
import uuid
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

from app.ui.eml_file import (
    build_reply_eml_bytes,
    extract_eml_attachment,
    parse_eml_bytes,
)

try:
    from evaluation.ui_eval_logger import save_ui_evaluation_run
except ImportError:
    save_ui_evaluation_run = None

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / '.env', override=False)

API_BASE = os.getenv(
    'HANS_UI_API_URL',
    os.getenv('HANS_API_BASE', 'http://127.0.0.1:8009'),
).rstrip('/')
HEALTH_URL = f'{API_BASE}/health'
EMAIL_URL = f'{API_BASE}/email'
INTERNAL_API_KEY = os.getenv('HANS_INTERNAL_API_KEY', '').strip()
TIMEOUT_SECONDS = float(os.getenv('HANS_UI_API_TIMEOUT', '720'))
CUSTOM_CASE_ID = 'CUSTOM-MANUAL'

VIEWABLE_IMAGE_TYPES = {
    'image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/webp'
}
TEXT_ATTACHMENT_TYPES = {'text/plain', 'text/csv'}



UI_TEXT: dict[str, dict[str, str]] = {
    "de": {
        "app_title": "HANS E-Mail-Assistent",
        "incoming_mailbox": "Eingehende E-Mails",
        "view_attachment": "Anhang anzeigen",
        "load_selected_email": "E-Mail laden",
        "remove_selected_eml": "E-Mail entfernen",
        "add_eml_files": "Hinzufügen",
        "select_eml_files": "Lokale .eml-Dateien auswählen",
        "refresh_inbox": "Aktualisieren",
        "sender": "Absender",
        "subject": "Betreff",
        "received": "Empfangen",
        "attachments": "Anhänge",
        "no_pending": "Derzeit sind keine lokalen .eml-Dateien ausstehend.",
        "incoming_metadata": "E-Mail-Metadaten",
        "student_email": "E-Mail-Adresse des Studierenden",
        "incoming_student_email": "Eingehende Studierenden-E-Mail",
        "generate_staff_draft": "Entwurf erstellen",
        "generating": "HANS erstellt den Antwortentwurf…",
        "clear": "Leeren",
        "copy_draft": "Kopieren",
        "open_full_draft": "Vollansicht",
        "export_reply": "Als .eml exportieren",
        "save_to_mailbox_drafts": "In Entwürfen speichern",
        "send_email": "E-Mail senden",
        "file_saved_remove": "✓ Datei gespeichert — verarbeitete E-Mail entfernen",
        "keep_pending": "Ausstehend lassen",
        "draft_ready": "✓ Entwurf bereit",
        "generation": "Generierung",
        "total": "Gesamt",
        "staff_draft": "Antwortentwurf",
        "validation_quality_sources": "Validierung, Qualität und Quellen",
        "reference_links": "Quellen zur Prüfung",
        "source": "Quelle",
        "attachment_dialog_title": "Anhang auswählen",
        "choose_attachment": "Anhang zum Anzeigen auswählen:",
        "preview": "Vorschau",
        "document_preview": "Dokumentvorschau",
        "download_attachment": "Anhang herunterladen",
        "attachment_unavailable": "Die ausgewählte E-Mail ist nicht mehr verfügbar.",
        "no_attachments": "Die ausgewählte E-Mail enthält keine Anhänge.",
        "open_attachment_error": "Anhang konnte nicht geöffnet werden",
        "inline_preview_unavailable": "Für diesen Anhangstyp ist keine Inline-Vorschau verfügbar.",
        "full_draft_title": "Vollständiger Antwortentwurf",
        "review_summary": "PRÜFÜBERSICHT FÜR MITARBEITENDE",
        "no_draft": "Es wurde noch kein Entwurf erstellt.",
        "programme": "Studiengang",
        "topics_detected": "Erkannte Themen",
        "none_detected": "Keine erkannt",
        "grounded": "Quellenbasiert",
        "citations_valid": "Quellenangaben gültig",
        "hallucinations": "Halluzinationen erkannt",
        "review_required": "Prüfung erforderlich",
        "confidence": "Konfidenz",
        "failure_type": "Fehlertyp",
        "review_reason": "Prüfgrund",
        "yes": "Ja",
        "no": "Nein",
        "not_available": "Nicht verfügbar",
        "selected": "Ausgewählt",
        "no_subject": "(kein Betreff)",
        "mailbox_disabled": (
            "Die Postfachintegration ist in dieser Testphase deaktiviert. "
            "Fügen Sie lokale .eml-Dateien hinzu oder fügen Sie eine Anfrage manuell ein."
        ),
        "attachment": "Anhang",
        "online": "Online",
        "offline": "Offline",
        "unavailable": "Nicht verfügbar",
    },
    "en": {
        "app_title": "HANS Email Assistant",
        "incoming_mailbox": "Incoming mailbox",
        "view_attachment": "View attachment",
        "load_selected_email": "Load email",
        "remove_selected_eml": "Remove email",
        "add_eml_files": "Add .eml",
        "select_eml_files": "Select local .eml files",
        "refresh_inbox": "Refresh",
        "sender": "Sender",
        "subject": "Subject",
        "received": "Received",
        "attachments": "Attachments",
        "no_pending": "No local .eml files are currently pending.",
        "incoming_metadata": "Incoming email metadata",
        "student_email": "Student email",
        "incoming_student_email": "Incoming student email",
        "generate_staff_draft": "Generate draft",
        "generating": "HANS is generating the staff draft…",
        "clear": "Clear",
        "copy_draft": "Copy",
        "open_full_draft": "Full view",
        "export_reply": "Export .eml",
        "save_to_mailbox_drafts": "Save draft",
        "send_email": "Send email",
        "file_saved_remove": "✓ File saved — remove processed email",
        "keep_pending": "Keep pending",
        "draft_ready": "✓ Draft ready",
        "generation": "Generation",
        "total": "Total",
        "staff_draft": "Staff draft",
        "validation_quality_sources": "Validation, quality and sources",
        "reference_links": "Sources for staff verification",
        "source": "Source",
        "attachment_dialog_title": "Select attachment",
        "choose_attachment": "Choose the attachment to view:",
        "preview": "Preview",
        "document_preview": "Document preview",
        "download_attachment": "Download attachment",
        "attachment_unavailable": "The selected email is no longer available.",
        "no_attachments": "The selected email has no attachments.",
        "open_attachment_error": "Could not open attachment",
        "inline_preview_unavailable": "Inline preview is not available for this attachment type.",
        "full_draft_title": "Full staff draft",
        "review_summary": "STAFF REVIEW SUMMARY",
        "no_draft": "No draft has been generated yet.",
        "programme": "Programme",
        "topics_detected": "Topics detected",
        "none_detected": "None detected",
        "grounded": "Grounded",
        "citations_valid": "Citations valid",
        "hallucinations": "Hallucinations detected",
        "review_required": "Review required",
        "confidence": "Confidence",
        "failure_type": "Failure type",
        "review_reason": "Review reason",
        "yes": "Yes",
        "no": "No",
        "not_available": "Not available",
        "selected": "Selected",
        "no_subject": "(no subject)",
        "mailbox_disabled": (
            "Mailbox integration is disabled for this testing phase. "
            "Add local .eml files or paste an inquiry manually."
        ),
        "attachment": "attachment",
        "online": "Online",
        "offline": "Offline",
        "unavailable": "Unavailable",
    },
}


def _t(key: str) -> str:
    language = st.session_state.get("ui_language", "en")
    return UI_TEXT.get(language, UI_TEXT["en"]).get(key, key)


def _request_headers() -> dict[str, str]:
    if not INTERNAL_API_KEY:
        raise RuntimeError('HANS_INTERNAL_API_KEY is not configured in .env.')
    return {'X-HANS-API-Key': INTERNAL_API_KEY}


def _safe_download_name(subject: str) -> str:
    value = subject.strip() or 'HANS_Draft'
    value = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', value)
    value = ' '.join(value.split()).strip(' .') or 'HANS_Draft'
    value = value[:100].rstrip(' .') or 'HANS_Draft'
    return f"Draft_{value}_{time.strftime('%Y%m%d_%H%M%S')}.eml"


def _staff_draft_without_reference_list(draft: str) -> str:
    """Remove only HANS's staff-reference list from the editable/exported draft.

    English and German HANS reference headings are supported. Structured
    sources remain available separately in result["sources"]. If a known
    heading or the section boundary cannot be found, the draft is returned
    unchanged.
    """
    headings = (
        "Reference links for staff verification:",
        "Referenzlinks zur Prüfung durch Mitarbeitende:",
    )

    heading_index = -1
    heading = ""
    for candidate in headings:
        candidate_index = draft.find(candidate)
        if candidate_index != -1 and (
            heading_index == -1 or candidate_index < heading_index
        ):
            heading_index = candidate_index
            heading = candidate

    if heading_index == -1:
        return draft

    separator_match = re.search(
        r"(?m)^\\?---\s*$",
        draft[heading_index + len(heading):],
    )
    if separator_match is None:
        return draft

    separator_index = (
        heading_index
        + len(heading)
        + separator_match.start()
    )

    before = draft[:heading_index].rstrip()
    after = draft[separator_index:].lstrip("\n")
    return f"{before}\n\n{after}".strip()


def _init_state() -> None:
    defaults: dict[str, Any] = {
        'pending_emails': [],
        'seen_upload_hashes': set(),
        'mailbox_uploader_version': 0,
        'selected_pending_id': None,
        'loaded_email_id': None,
        'student_email': '',
        'subject': '',
        'incoming_text': '',
        'ui_language': 'en',
        'language': 'en',
        'top_k': 6,
        'thread_id': '',
        'email_id': '',
        'last_result': None,
        'draft_text': '',
        'last_log_path': None,
        'export_confirmation_pending': False,
        'status_message': (
            'Staff review required before sending. '
            'Mailbox integration is disabled during testing.'
        ),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _apply_desktop_style() -> None:
    st.markdown(
        '''
        <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
            background: #f4f5f6 !important;
            color: #1f252b !important;
        }
        [data-testid="stHeader"], [data-testid="stToolbar"],
        [data-testid="stDecoration"], #MainMenu, footer {
            display: none !important;
        }
        .block-container {
            width: 100% !important;
            max-width: 1700px !important;
            padding: clamp(0.3rem, 0.7vw, 0.7rem)
                     clamp(0.45rem, 1vw, 0.95rem)
                     0.45rem !important;
            box-sizing: border-box !important;
        }

        /* Responsive sizing only; workflow and component structure stay unchanged. */
        .hans-title {
            font-size: clamp(1.05rem, 1.35vw, 1.35rem) !important;
        }

        [data-testid="stButton"] button,
        [data-testid="stDownloadButton"] button,
        [data-baseweb="select"] > div {
            font-size: clamp(0.68rem, 0.72vw, 0.78rem) !important;
        }

        textarea,
        input {
            font-size: clamp(0.78rem, 0.82vw, 0.9rem) !important;
        }

        @media (max-width: 1100px) {
            .block-container {
                padding-left: 0.4rem !important;
                padding-right: 0.4rem !important;
            }

            [data-testid="stButton"] button,
            [data-testid="stDownloadButton"] button {
                white-space: normal !important;
                line-height: 1.15 !important;
                min-height: 2rem !important;
            }

            .hans-status {
                font-size: 0.68rem !important;
            }
        }

        @media (max-width: 800px) {
            .section-title {
                font-size: 0.76rem !important;
            }

            .selected-line {
                font-size: 0.7rem !important;
            }

            .mailbox-header {
                font-size: 0.68rem !important;
            }

            .review-summary {
                font-size: 0.76rem !important;
            }
        }
        .hans-title {
            text-align: center;
            color: #24495f;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 1.35rem;
            font-weight: 700;
            margin: 0.05rem 0 0.1rem 0;
        }
        .hans-status {
            text-align: right;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 0.75rem;
            color: #5b6570;
            margin: -0.05rem 0 0.15rem 0;
        }
        .hans-online { color: #2f8f46; font-weight: 700; margin-right: 0.6rem; }
        .hans-offline { color: #b42318; font-weight: 700; margin-right: 0.6rem; }
        .section-title {
            color: #315f7d;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 0.82rem;
            font-weight: 700;
            margin: -0.05rem 0 0.25rem 0;
        }
        .selected-line {
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 0.76rem;
            color: #30373d;
            padding-top: 0.28rem;
            min-height: 1.6rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border: 1px solid #cfd5da !important;
            border-radius: 2px !important;
            box-shadow: none !important;
        }
        [data-testid="stTextInput"] label,
        [data-testid="stTextArea"] label,
        [data-testid="stSelectbox"] label,
        [data-testid="stNumberInput"] label {
            color: #30373d !important;
            font-family: "Segoe UI", Arial, sans-serif !important;
            font-size: 0.75rem !important;
        }
        input, textarea, [data-baseweb="select"] > div {
            background: #ffffff !important;
            color: #20262d !important;
            border-color: #bfc6cc !important;
        }
        textarea {
            font-family: "Segoe UI", Arial, sans-serif !important;
            font-size: 0.86rem !important;
        }
        [data-testid="stButton"] button,
        [data-testid="stDownloadButton"] button {
            min-height: 1.9rem !important;
            padding: 0.12rem 0.45rem !important;
            border-radius: 2px !important;
            font-family: "Segoe UI", Arial, sans-serif !important;
            font-size: 0.73rem !important;
            font-weight: 400 !important;
            background: #ffffff !important;
            color: #20262d !important;
            border: 1px solid #b9c0c6 !important;
            box-shadow: none !important;
        }
        [data-testid="stButton"] button:hover,
        [data-testid="stDownloadButton"] button:hover {
            border-color: #7b8b98 !important;
            color: #24495f !important;
        }
        [data-testid="stButton"] button[kind="primary"] {
            background: #176b9c !important;
            border-color: #125b86 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        [data-testid="stButton"] button[kind="primary"]:hover {
            background: #125b86 !important;
            border-color: #0f4f75 !important;
            color: #ffffff !important;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid #c7cdd2 !important;
            background: #ffffff !important;
        }
        div[data-testid="stFileUploader"] section {
            background: #ffffff !important;
            padding: 0.35rem !important;
            min-height: 3rem !important;
        }
        .review-summary {
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 0.82rem;
            line-height: 1.38;
            color: #20262d;
            height: 285px;
            overflow-y: auto;
            background: #ffffff;
            border: 1px solid #d4d9dd;
            padding: 0.65rem 0.75rem;
        }

        .review-summary-title {
            font-weight: 700;
            margin-bottom: 0.35rem;
            color: #20262d;
        }

        .review-row {
            margin-bottom: 0.16rem;
        }

        .review-label {
            font-weight: 700;
        }

        .review-reason {
            margin: 0.45rem 0 0.55rem 0;
            padding: 0.45rem 0.55rem;
            border-left: 4px solid #d97706;
            background: #fff7ed;
            color: #9a3412;
            font-weight: 600;
        }

        .review-ok {
            color: #2f7d32;
            font-weight: 700;
        }

        .review-warning {
            color: #b45309;
            font-weight: 700;
        }

        .review-sources-title {
            font-weight: 700;
            margin-top: 0.45rem;
            margin-bottom: 0.2rem;
        }

        .review-source {
            margin-bottom: 0.28rem;
            word-break: break-word;
        }

        .review-source a {
            color: #315f7d !important;
            text-decoration: underline;
        }

        .review-section-heading {
            font-weight: 700;
            color: #315f7d;
            margin-top: 0.45rem;
            margin-bottom: 0.18rem;
        }

        .mailbox-header {
            display: grid;
            grid-template-columns: 1.25fr 2.2fr 1.55fr 0.55fr;
            gap: 0;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 0.75rem;
            font-weight: 600;
            color: #505a62;
            border: 1px solid #cbd2d8;
            border-bottom: none;
            background: #f7f8f9;
        }

        .mailbox-header > div {
            padding: 0.32rem 0.55rem;
            border-right: 1px solid #d7dde1;
        }

        .mailbox-header > div:last-child {
            border-right: none;
            text-align: center;
        }

        .mailbox-row-wrap {
            margin: 0 !important;
            padding: 0 !important;
        }

        .mailbox-row-wrap [data-testid="column"] {
            padding: 0 !important;
        }

        .mailbox-row-wrap [data-testid="stButton"] {
            margin: 0 !important;
        }

        .mailbox-row-wrap [data-testid="stButton"] button {
            width: 100% !important;
            min-height: 2.15rem !important;
            border-radius: 0 !important;
            border-top: 1px solid #d7dde1 !important;
            border-left: 1px solid #d7dde1 !important;
            border-right: none !important;
            border-bottom: none !important;
            background: #ffffff !important;
            color: #20262d !important;
            justify-content: flex-start !important;
            padding: 0.24rem 0.5rem !important;
            font-size: 0.76rem !important;
        }

        .mailbox-row-wrap [data-testid="column"]:last-child
        [data-testid="stButton"] button {
            border-right: 1px solid #d7dde1 !important;
            justify-content: center !important;
        }

        /* Mailbox row interaction states.
           These rules intentionally come after the base white-cell rule. */
        .mailbox-row-wrap [data-testid="stButton"] button:hover {
            background: #d9eaf4 !important;
            border-color: #7ea7bf !important;
            color: #173e56 !important;
        }

        .mailbox-row-wrap [data-testid="stButton"] button[kind="primary"] {
            background: #176b9c !important;
            border-color: #125b86 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        .mailbox-row-wrap [data-testid="stButton"] button[kind="primary"]:hover {
            background: #125b86 !important;
            border-color: #0f4f75 !important;
            color: #ffffff !important;
        }

        /* Streamlit renders keyed widgets in wrappers such as st-key-mail_sender_*.
           Target those wrappers directly so the browser hover state is unmistakable. */
        div[class*="st-key-mail_sender_"] button:hover,
        div[class*="st-key-mail_subject_"] button:hover,
        div[class*="st-key-mail_received_"] button:hover,
        div[class*="st-key-mail_attach_"] button:hover {
            background: #cfe4f1 !important;
            border-color: #6f9db8 !important;
            color: #173e56 !important;
        }

        div[class*="st-key-mail_sender_"] button[kind="primary"],
        div[class*="st-key-mail_subject_"] button[kind="primary"],
        div[class*="st-key-mail_received_"] button[kind="primary"],
        div[class*="st-key-mail_attach_"] button[kind="primary"] {
            background: #176b9c !important;
            border-color: #125b86 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        div[class*="st-key-mail_sender_"] button[kind="primary"]:hover,
        div[class*="st-key-mail_subject_"] button[kind="primary"]:hover,
        div[class*="st-key-mail_received_"] button[kind="primary"]:hover,
        div[class*="st-key-mail_attach_"] button[kind="primary"]:hover {
            background: #0f5a86 !important;
            border-color: #0c496e !important;
            color: #ffffff !important;
        }

        .mailbox-row-selected [data-testid="stButton"] button {
            background: #176b9c !important;
            border-color: #125b86 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }


        /* v9: compact, scrollable mailbox with true full-row hover. */
        div[class*="st-key-mailbox_rows_scroll"] {
            max-height: 120px;
        }

        div[class*="st-key-mailbox_rows_scroll"] [data-testid="stVerticalBlock"] {
            gap: 0.12rem !important;
        }

        div[class*="st-key-mailbox_rows_scroll"] [data-testid="stHorizontalBlock"] {
            gap: 0 !important;
        }

        div[class*="st-key-mailbox_rows_scroll"]
        div[class*="st-key-mail_sender_"] button,
        div[class*="st-key-mailbox_rows_scroll"]
        div[class*="st-key-mail_subject_"] button,
        div[class*="st-key-mailbox_rows_scroll"]
        div[class*="st-key-mail_received_"] button,
        div[class*="st-key-mailbox_rows_scroll"]
        div[class*="st-key-mail_attach_"] button {
            min-height: 1.72rem !important;
            height: 1.72rem !important;
            padding: 0.05rem 0.38rem !important;
            margin: 0 !important;
            border-radius: 0 !important;
        }

        div[class*="st-key-mailbox_rows_scroll"]
        [data-testid="stHorizontalBlock"]:has(
            div[class*="st-key-mail_"] button:hover
        ) div[class*="st-key-mail_"] button {
            background: #cfe4f1 !important;
            border-color: #6f9db8 !important;
            color: #173e56 !important;
        }

        div[class*="st-key-mailbox_rows_scroll"]
        [data-testid="stHorizontalBlock"]:has(
            div[class*="st-key-mail_"] button[kind="primary"]
        ) div[class*="st-key-mail_"] button {
            background: #176b9c !important;
            border-color: #125b86 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        div[class*="st-key-mailbox_rows_scroll"]
        [data-testid="stHorizontalBlock"]:has(
            div[class*="st-key-mail_"] button[kind="primary"]:hover
        ) div[class*="st-key-mail_"] button {
            background: #0f5a86 !important;
            border-color: #0c496e !important;
            color: #ffffff !important;
        }


        /* v10: clear blue hover feedback for the staff action row. */
        div[class*="st-key-action_clear"] button:not(:disabled):hover,
        div[class*="st-key-action_copy"] button:not(:disabled):hover,
        div[class*="st-key-action_full"] button:not(:disabled):hover,
        div[class*="st-key-action_export"] button:not(:disabled):hover {
            background: #cfe4f1 !important;
            border-color: #6f9db8 !important;
            color: #173e56 !important;
        }

        div[class*="st-key-action_generate"] button:not(:disabled):hover {
            background: #0f5a86 !important;
            border-color: #0c496e !important;
            color: #ffffff !important;
        }

        /* Main workflow actions: Add, Load, Export. */
        div[class*="st-key-mailbox_primary_add"] [data-testid="stPopover"] > button,
        div[class*="st-key-mailbox_load_selected"] button:not(:disabled),
        div[class*="st-key-action_export"] button:not(:disabled) {
            background: #176b9c !important;
            border-color: #125b86 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        div[class*="st-key-mailbox_primary_add"] [data-testid="stPopover"] > button:hover,
        div[class*="st-key-mailbox_load_selected"] button:not(:disabled):hover,
        div[class*="st-key-action_export"] button:not(:disabled):hover {
            background: #0f5a86 !important;
            border-color: #0c496e !important;
            color: #ffffff !important;
        }

        div[class*="st-key-mailbox_primary_add"] [data-testid="stPopover"] > button {
            min-height: 1.9rem !important;
            height: 1.9rem !important;
            padding: 0.12rem 0.45rem !important;
            white-space: nowrap !important;
        }

        div[class*="st-key-mailbox_view_attachment"] button:not(:disabled):hover,
        div[class*="st-key-mailbox_remove_selected"] button:not(:disabled):hover,
        div[class*="st-key-action_clear"] button:not(:disabled):hover,
        div[class*="st-key-action_copy"] button:not(:disabled):hover,
        div[class*="st-key-action_full"] button:not(:disabled):hover {
            background: #cfe4f1 !important;
            border-color: #6f9db8 !important;
            color: #173e56 !important;
        }

        /* Keep disabled mailbox-draft/send controls visibly disabled. */
        div[class*="st-key-action_save_draft"] button:disabled,
        div[class*="st-key-action_send"] button:disabled {
            background: #f7f8f9 !important;
            color: #8a939a !important;
            border-color: #d2d7db !important;
            opacity: 1 !important;
        }

        .hans-generation-indicator {
            height: 1.9rem;
            display: flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0 0.65rem;
            border: 1px solid #93c5a1;
            border-radius: 3px;
            background: #eef9f0;
            color: #23783a;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 0.76rem;
            font-weight: 600;
            white-space: nowrap;
        }

        .hans-generation-dots {
            display: inline-flex;
            gap: 0.18rem;
            align-items: center;
        }

        .hans-generation-dots span {
            width: 0.42rem;
            height: 0.42rem;
            border-radius: 50%;
            background: #2f9e44;
            display: inline-block;
            animation: hansGenerationPulse 1.05s infinite ease-in-out;
        }

        .hans-generation-dots span:nth-child(2) { animation-delay: 0.15s; }
        .hans-generation-dots span:nth-child(3) { animation-delay: 0.30s; }

        @keyframes hansGenerationPulse {
            0%, 70%, 100% {
                transform: scale(0.72);
                opacity: 0.42;
            }
            35% {
                transform: scale(1.15);
                opacity: 1;
            }
        }

        .hans-generation-complete {
            height: 1.9rem;
            display: flex;
            align-items: center;
            padding: 0 0.65rem;
            border: 1px solid #93c5a1;
            border-radius: 3px;
            background: #eef9f0;
            color: #23783a;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 0.74rem;
            font-weight: 600;
            white-space: nowrap;
        }

        .draft-source-links {
            margin-top: 0.35rem;
            padding: 0.45rem 0.55rem;
            border: 1px solid #d7dde1;
            background: #ffffff;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 0.78rem;
            line-height: 1.35;
        }

        .draft-source-links-title {
            font-weight: 700;
            color: #315f7d;
            margin-bottom: 0.22rem;
        }

        .draft-source-link {
            margin-bottom: 0.18rem;
            word-break: break-word;
        }

        .draft-source-link a {
            color: #315f7d !important;
            text-decoration: underline !important;
        }

        .footer-line {
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 0.74rem;
            color: #40484f;
            margin-top: 0.25rem;
        }
        </style>
        ''',
        unsafe_allow_html=True,
    )


def _pending_by_id(item_id: str | None) -> dict[str, Any] | None:
    if not item_id:
        return None
    for item in st.session_state.pending_emails:
        if item['id'] == item_id:
            return item
    return None


def _add_uploaded_emails(uploaded_files: list[Any]) -> None:
    added = 0
    duplicate_count = 0
    errors: list[str] = []
    for uploaded in uploaded_files:
        data = uploaded.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        if digest in st.session_state.seen_upload_hashes:
            duplicate_count += 1
            continue
        try:
            parsed = parse_eml_bytes(data)
        except Exception as exc:
            errors.append(f'{uploaded.name}: {exc}')
            st.session_state.seen_upload_hashes.add(digest)
            continue
        item_id = uuid.uuid4().hex
        st.session_state.pending_emails.append({
            'id': item_id,
            'name': uploaded.name,
            'sha256': digest,
            'bytes': data,
            'parsed': parsed,
        })
        st.session_state.seen_upload_hashes.add(digest)
        added += 1
    parts: list[str] = []
    if added:
        parts.append(f'Added {added} local .eml file(s).')
    if duplicate_count:
        parts.append(f'Skipped {duplicate_count} duplicate file(s).')
    if parts:
        st.session_state.status_message = ' '.join(parts)
    if errors:
        st.error('Some .eml files could not be loaded:\n\n' + '\n'.join(errors))


def _remove_pending(item_id: str | None) -> bool:
    if not item_id:
        return False

    item = _pending_by_id(item_id)
    if item is None:
        return False

    before = len(st.session_state.pending_emails)
    st.session_state.pending_emails = [
        pending_item
        for pending_item in st.session_state.pending_emails
        if pending_item['id'] != item_id
    ]
    removed = len(st.session_state.pending_emails) < before

    if removed:
        digest = item.get('sha256')
        if digest:
            st.session_state.seen_upload_hashes.discard(digest)

        if st.session_state.selected_pending_id == item_id:
            st.session_state.selected_pending_id = None

    return removed


def _clear_editor() -> None:
    st.session_state.loaded_email_id = None
    st.session_state.student_email = ''
    st.session_state.subject = ''
    st.session_state.incoming_text = ''
    st.session_state.thread_id = f"web-thread-{uuid.uuid4().hex[:8]}"
    st.session_state.email_id = f"web-email-{uuid.uuid4().hex[:8]}"
    st.session_state.last_result = None
    st.session_state.draft_text = ''
    st.session_state.last_log_path = None
    st.session_state.export_confirmation_pending = False


def _load_selected() -> None:
    item = _pending_by_id(st.session_state.selected_pending_id)
    if item is None:
        st.warning('Select a pending .eml file first.')
        return
    parsed = item['parsed']
    token = item['id'][:8]
    st.session_state.loaded_email_id = item['id']
    st.session_state.student_email = parsed['sender_email']
    st.session_state.subject = parsed['subject']
    st.session_state.incoming_text = parsed['body']
    st.session_state.thread_id = f'web-thread-{token}'
    st.session_state.email_id = f'web-email-{token}'
    st.session_state.last_result = None
    st.session_state.draft_text = ''
    st.session_state.last_log_path = None
    st.session_state.export_confirmation_pending = False
    st.session_state.status_message = (
        'Selected email loaded. No draft has been generated yet.'
    )


def _generate() -> None:
    email_text = st.session_state.incoming_text.strip()
    if not email_text:
        st.error('Incoming email text is required.')
        return
    try:
        headers = _request_headers()
    except Exception as exc:
        st.error(str(exc))
        return
    thread_id = st.session_state.thread_id.strip() or f"web-thread-{uuid.uuid4().hex[:8]}"
    email_id = st.session_state.email_id.strip() or f"web-email-{uuid.uuid4().hex[:8]}"
    st.session_state.thread_id = thread_id
    st.session_state.email_id = email_id
    payload = {
        'email_text': email_text,
        'student_email': st.session_state.student_email.strip() or None,
        'subject': st.session_state.subject.strip() or None,
        'thread_id': thread_id,
        'email_id': email_id,
        'language': st.session_state.language.strip() or 'en',
        'top_k': int(st.session_state.top_k),
    }
    started = time.perf_counter()
    try:
        response = requests.post(
            EMAIL_URL,
            json=payload,
            headers=headers,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        result = response.json()
        client_latency = time.perf_counter() - started
        result['_ui_client'] = {
            'latency_seconds': round(client_latency, 3),
            'api_base': API_BASE,
        }
        saved_path = None
        if save_ui_evaluation_run is not None:
            saved_path = save_ui_evaluation_run(
                test_case_id=CUSTOM_CASE_ID,
                request_payload=payload,
                response_payload=result,
            )
        st.session_state.last_result = result
        st.session_state.draft_text = _staff_draft_without_reference_list(
            str(result.get('staff_draft') or '')
        )
        st.session_state.last_log_path = (
            str(saved_path) if saved_path is not None else None
        )
        st.session_state.status_message = (
            'Draft generated. Staff review is required.'
        )
    except Exception as exc:
        if save_ui_evaluation_run is not None:
            try:
                save_ui_evaluation_run(
                    test_case_id=CUSTOM_CASE_ID,
                    request_payload=payload,
                    error=str(exc),
                )
            except Exception:
                pass
        st.error(f'HANS draft generation failed: {exc}')


def _clear_editor_action() -> None:
    _clear_editor()
    st.session_state.status_message = (
        'Input and generated result cleared.'
    )


def _keep_export_pending() -> None:
    st.session_state.export_confirmation_pending = False
    st.session_state.status_message = (
        'Export was not confirmed. The incoming email '
        'remains in the pending list.'
    )


def _mark_export_requested() -> None:
    st.session_state.export_confirmation_pending = True
    st.session_state.status_message = (
        'Download started. After the browser finishes saving the .eml, '
        'click "File saved — remove processed email". '
        'If you cancelled the save dialog, click "Keep pending".'
    )


def _confirm_exported_action() -> None:
    loaded_id = st.session_state.loaded_email_id

    if not loaded_id:
        st.session_state.export_confirmation_pending = False
        st.session_state.status_message = (
            'Export could not be confirmed because no loaded incoming email '
            'is associated with this draft.'
        )
        return

    removed = _remove_pending(loaded_id)

    if not removed:
        st.session_state.export_confirmation_pending = False
        st.session_state.status_message = (
            'The exported email was not found in the pending list. '
            'No other email was removed.'
        )
        return

    _clear_editor()
    st.session_state.selected_pending_id = None
    st.session_state.export_confirmation_pending = False
    st.session_state.status_message = (
        'Reply export confirmed. The processed incoming .eml was removed '
        'from the pending list.'
    )


def _health_status() -> tuple[bool, str]:
    try:
        response = requests.get(HEALTH_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'healthy':
            return True, 'Online'
        return False, str(data.get('status') or 'Unavailable')
    except Exception:
        return False, 'Offline'


def _selected_label(item: dict[str, Any] | None) -> str:
    if item is None:
        return _t("mailbox_disabled")
    parsed = item['parsed']
    attachment_names = [
        str(value.get('filename') or _t("attachment"))
        for value in parsed['attachments']
    ]
    label = f"{_t('selected')}: {parsed['subject'] or _t('no_subject')}"
    if attachment_names:
        label += ' | ' + ', '.join(attachment_names)
    return label


def _review_value(value: Any) -> str:
    if value is True:
        return _t("yes")
    if value is False:
        return _t("no")
    if value is None:
        return _t("not_available")
    return str(value)


def _staff_review_summary_html(
    result: dict[str, Any] | None,
) -> str:
    if not result:
        return (
            '<div class="review-summary">'
            f'<div class="review-summary-title">{html.escape(_t("review_summary"))}</div>'
            f'<div>{html.escape(_t("no_draft"))}</div>'
            '</div>'
        )

    validation = result.get("validation") or {}
    quality = result.get("quality") or {}
    email_context = result.get("email_context") or {}
    topics = result.get("detected_topics") or []

    programme = (
        email_context.get("target_program")
        or email_context.get("target_programme")
        or email_context.get("matched_programme")
        or "n/a"
    )

    topic_labels = [
        str(topic.get("label") or topic.get("topic_id") or "")
        for topic in topics
        if topic.get("label") or topic.get("topic_id")
    ]

    grounded = validation.get("is_grounded")
    citations_valid = validation.get("citations_valid")
    hallucinations = validation.get("has_hallucinations")
    review_required = quality.get("review_required")
    review_reason = (
        quality.get("review_reason")
        or "No specific review reason was returned."
    )

    confidence = validation.get("confidence")
    failure_type = validation.get("failure_type")

    def status_class(
        value: Any,
        *,
        positive_when_false: bool = False,
    ) -> str:
        if value is None:
            return ""
        positive = (not value) if positive_when_false else bool(value)
        return "review-ok" if positive else "review-warning"

    topics_value = ", ".join(topic_labels) if topic_labels else _t("none_detected")

    parts = [
        '<div class="review-summary">',
        f'<div class="review-summary-title">{html.escape(_t("review_summary"))}</div>',
        '<div class="review-row"><span class="review-label">'
        f'{html.escape(_t("programme"))}:</span> '
        f'{html.escape(str(programme))}</div>',
        '<div class="review-row"><span class="review-label">'
        f'{html.escape(_t("topics_detected"))}:</span> '
        f'{html.escape(topics_value)}</div>',
        '<div class="review-row"><span class="review-label">'
        f'{html.escape(_t("grounded"))}:</span> '
        f'<span class="{status_class(grounded)}">'
        f'{html.escape(_review_value(grounded))}</span></div>',
        '<div class="review-row"><span class="review-label">'
        f'{html.escape(_t("citations_valid"))}:</span> '
        f'<span class="{status_class(citations_valid)}">'
        f'{html.escape(_review_value(citations_valid))}</span></div>',
        '<div class="review-row"><span class="review-label">'
        f'{html.escape(_t("hallucinations"))}:</span> '
        f'<span class="{status_class(hallucinations, positive_when_false=True)}">'
        f'{html.escape(_review_value(hallucinations))}</span></div>',
        '<div class="review-row"><span class="review-label">'
        f'{html.escape(_t("review_required"))}:</span> '
        f'<span class="{status_class(review_required, positive_when_false=True)}">'
        f'{html.escape(_review_value(review_required))}</span></div>',
        '<div class="review-row"><span class="review-label">'
        f'{html.escape(_t("confidence"))}:</span> '
        f'{html.escape(_review_value(confidence))}</div>',
        '<div class="review-row"><span class="review-label">'
        f'{html.escape(_t("failure_type"))}:</span> '
        f'{html.escape(_review_value(failure_type))}</div>',
        '<div class="review-reason"><span class="review-label">'
        f'{html.escape(_t("review_reason"))}:</span> '
        f'{html.escape(str(review_reason))}</div>',
    ]

    parts.append('</div>')
    return "".join(parts)



def _docx_text_preview(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            xml = archive.read("word/document.xml").decode(
                "utf-8",
                errors="replace",
            )

        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
        xml = re.sub(r"<[^>]+>", "", xml)

        return html.unescape(xml).strip()

    except Exception as exc:
        return f"Preview unavailable: {exc}"


def _xlsx_preview(content: bytes) -> dict[str, list[list[Any]]]:
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(
            io.BytesIO(content),
            read_only=True,
            data_only=True,
        )

        preview: dict[str, list[list[Any]]] = {}

        for sheet in workbook.worksheets[:5]:
            rows: list[list[Any]] = []

            for row in sheet.iter_rows(
                max_row=40,
                max_col=15,
                values_only=True,
            ):
                rows.append(list(row))

            preview[sheet.title] = rows

        return preview

    except Exception:
        return {}


def _render_attachment_preview(
    *,
    content: bytes,
    filename: str,
    content_type: str,
) -> None:
    suffix = Path(filename).suffix.lower()

    if (
        content_type in VIEWABLE_IMAGE_TYPES
        or suffix in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".webp",
        }
    ):
        st.image(
            content,
            caption=filename,
        )
        return

    if (
        content_type in TEXT_ATTACHMENT_TYPES
        or suffix in {
            ".txt",
            ".csv",
        }
    ):
        st.text_area(
            _t("preview"),
            value=content.decode(
                "utf-8",
                errors="replace",
            ),
            height=360,
            disabled=True,
        )
        return

    if (
        content_type == "application/pdf"
        or suffix == ".pdf"
    ):
        encoded = base64.b64encode(
            content
        ).decode("ascii")

        st.markdown(
            (
                '<iframe '
                'src="data:application/pdf;base64,'
                f'{encoded}" '
                'width="100%" height="520" '
                'style="border:1px solid #cfd5da;">'
                '</iframe>'
            ),
            unsafe_allow_html=True,
        )
        return

    if suffix == ".docx":
        st.text_area(
            _t("document_preview"),
            value=_docx_text_preview(
                content
            ),
            height=420,
            disabled=True,
        )
        return

    if suffix == ".xlsx":
        preview = _xlsx_preview(
            content
        )

        if preview:
            for sheet_name, rows in preview.items():
                st.markdown(
                    f"**{sheet_name}**"
                )
                st.dataframe(
                    rows,
                    hide_index=True,
                    use_container_width=True,
                )

            return

    st.info(_t("inline_preview_unavailable"))


def _attachment_dialog_body(item_id: str) -> None:
    item = _pending_by_id(item_id)

    if item is None:
        st.warning(_t("attachment_unavailable"))
        return

    attachments = item["parsed"]["attachments"]

    if not attachments:
        st.info(_t("no_attachments"))
        return

    names = [
        attachment["filename"]
        for attachment in attachments
    ]

    selected_name = st.selectbox(
        _t("choose_attachment"),
        names,
        key=f"attachment_choice_{item_id}",
    )

    index = names.index(selected_name)

    try:
        (
            content,
            actual_name,
            actual_type,
        ) = extract_eml_attachment(
            item["bytes"],
            index,
        )

    except Exception as exc:
        st.error(
            f'{_t("open_attachment_error")}: {exc}'
        )
        return

    if not actual_type:
        actual_type = (
            mimetypes.guess_type(actual_name)[0]
            or "application/octet-stream"
        )

    _render_attachment_preview(
        content=content,
        filename=actual_name,
        content_type=actual_type,
    )

    st.download_button(
        _t("download_attachment"),
        data=content,
        file_name=actual_name,
        mime=actual_type,
        use_container_width=True,
    )


@st.dialog("Anhang auswählen", width="large")
def _attachment_dialog_de(item_id: str) -> None:
    _attachment_dialog_body(item_id)


@st.dialog("Select attachment", width="large")
def _attachment_dialog_en(item_id: str) -> None:
    _attachment_dialog_body(item_id)


def _attachment_dialog(item_id: str) -> None:
    if st.session_state.get("ui_language", "en") == "de":
        _attachment_dialog_de(item_id)
    else:
        _attachment_dialog_en(item_id)


def _full_draft_dialog_body() -> None:
    st.text_area(
        _t("staff_draft"),
        value=st.session_state.draft_text,
        height=520,
        key='full_draft_preview',
    )


@st.dialog("Vollständiger Antwortentwurf", width="large")
def _full_draft_dialog_de() -> None:
    _full_draft_dialog_body()


@st.dialog("Full staff draft", width="large")
def _full_draft_dialog_en() -> None:
    _full_draft_dialog_body()


def _full_draft_dialog() -> None:
    if st.session_state.get("ui_language", "en") == "de":
        _full_draft_dialog_de()
    else:
        _full_draft_dialog_en()


def _draft_source_links_html(
    result: dict[str, Any] | None,
) -> str:
    if not result:
        return ""

    sources = (
        result.get("sources")
        or []
    )

    if not sources:
        return ""

    parts = [
        '<div class="draft-source-links">',
        '<div class="draft-source-links-title">'
        + html.escape(_t("reference_links"))
        + '</div>',
    ]

    for index, source in enumerate(
        sources,
        start=1,
    ):
        title = str(
            source.get("title")
            or f"{_t('source')} {index}"
        )

        url = str(
            source.get("url")
            or ""
        )

        if not url:
            continue

        safe_url = html.escape(
            url,
            quote=True,
        )

        parts.append(
            '<div class="draft-source-link">'
            f'[Doc {index}] {html.escape(title)}: '
            f'<a href="{safe_url}" target="_blank">'
            f'{html.escape(url)}'
            '</a>'
            '</div>'
        )

    parts.append(
        '</div>'
    )

    return "".join(
        parts
    )



def _render_mailbox() -> None:
    with st.container(border=True):
        st.markdown(
            f'<div class="section-title">{html.escape(_t("incoming_mailbox"))}</div>',
            unsafe_allow_html=True,
        )
        pending = st.session_state.pending_emails
        selected_item = _pending_by_id(st.session_state.selected_pending_id)

        info_col, view_col, load_col, remove_col, add_col = st.columns(
            [5.8, 1.2, 1.3, 1.4, 1.35],
            gap='small',
        )

        with info_col:
            st.markdown(
                '<div class="selected-line">'
                + html.escape(_selected_label(selected_item))
                + '</div>',
                unsafe_allow_html=True,
            )

        attachments_available = bool(
            selected_item and selected_item['parsed']['attachments']
        )

        with view_col:
            if st.button(
                _t("view_attachment"),
                disabled=not attachments_available,
                use_container_width=True,
                key="mailbox_view_attachment",
            ):
                _attachment_dialog(st.session_state.selected_pending_id)

        with load_col:
            if st.button(
                _t("load_selected_email"),
                disabled=selected_item is None,
                use_container_width=True,
                key="mailbox_load_selected",
            ):
                _load_selected()
                st.rerun()

        with remove_col:
            if st.button(
                _t("remove_selected_eml"),
                disabled=selected_item is None,
                use_container_width=True,
                key="mailbox_remove_selected",
            ):
                selected_id = st.session_state.selected_pending_id
                was_loaded = st.session_state.loaded_email_id == selected_id
                if _remove_pending(selected_id):
                    if was_loaded:
                        _clear_editor()
                    st.session_state.status_message = (
                        'Selected local .eml removed from the pending list. '
                        'The original file was not deleted.'
                    )
                st.rerun()

        with add_col:
            with st.container(key="mailbox_primary_add"):
                with st.popover(_t("add_eml_files"), use_container_width=True):
                    uploaded = st.file_uploader(
                        _t("select_eml_files"),
                        type=['eml'],
                        accept_multiple_files=True,
                        label_visibility='collapsed',
                        key=f"mailbox_uploader_{st.session_state.mailbox_uploader_version}",
                    )
                    if uploaded:
                        _add_uploaded_emails(uploaded)
                        st.session_state.mailbox_uploader_version += 1
                        st.rerun()

        if pending:
            st.markdown(
                (
                    '<div class="mailbox-header">'
                    f'<div>{html.escape(_t("sender"))}</div>'
                    f'<div>{html.escape(_t("subject"))}</div>'
                    f'<div>{html.escape(_t("received"))}</div>'
                    f'<div>{html.escape(_t("attachments"))}</div>'
                    '</div>'
                ),
                unsafe_allow_html=True,
            )

            with st.container(
                height=120,
                border=False,
                key='mailbox_rows_scroll',
            ):
                for item in pending:
                    parsed = item['parsed']
                    selected = (
                        item['id']
                        == st.session_state.selected_pending_id
                    )

                    sender_col, subject_col, received_col, attachment_col = st.columns(
                        [1.25, 2.2, 1.55, 0.55],
                        gap='small',
                    )

                    def select_row() -> None:
                        st.session_state.selected_pending_id = item['id']
                        st.rerun()

                    with sender_col:
                        if st.button(
                            parsed['sender_email'] or '',
                            key=f"mail_sender_{item['id']}",
                            type=('primary' if selected else 'secondary'),
                            use_container_width=True,
                        ):
                            select_row()

                    with subject_col:
                        if st.button(
                            parsed['subject'] or '',
                            key=f"mail_subject_{item['id']}",
                            type=('primary' if selected else 'secondary'),
                            use_container_width=True,
                        ):
                            select_row()

                    with received_col:
                        if st.button(
                            parsed['received_at'] or '',
                            key=f"mail_received_{item['id']}",
                            type=('primary' if selected else 'secondary'),
                            use_container_width=True,
                        ):
                            select_row()

                    with attachment_col:
                        if st.button(
                            str(len(parsed['attachments'])),
                            key=f"mail_attach_{item['id']}",
                            type=('primary' if selected else 'secondary'),
                            use_container_width=True,
                        ):
                            select_row()

        else:
            st.caption(_t("no_pending"))


def _render_metadata_and_input() -> None:
    with st.container(border=True):
        st.markdown(
            f'<div class="section-title">{html.escape(_t("incoming_metadata"))}</div>',
            unsafe_allow_html=True,
        )
        left, right = st.columns([1, 2], gap='small')
        with left:
            st.text_input(_t("student_email"), key='student_email')
        with right:
            st.text_input(_t("subject"), key='subject')

    with st.container(border=True):
        st.markdown(
            f'<div class="section-title">{html.escape(_t("incoming_student_email"))}</div>',
            unsafe_allow_html=True,
        )
        st.text_area(
            _t("incoming_student_email"),
            key='incoming_text',
            height=145,
            label_visibility='collapsed',
        )

    # UI language is independent from the backend request language.
    st.session_state.language = 'en'
    st.session_state.top_k = 6


def _render_action_row() -> None:
    result = st.session_state.last_result
    draft = st.session_state.draft_text.strip()
    eml_bytes: bytes | None = None
    export_name = 'HANS_Draft.eml'

    if draft:
        try:
            eml_bytes = build_reply_eml_bytes(
                recipient=st.session_state.student_email,
                subject=st.session_state.subject,
                body=draft,
            )
            export_name = _safe_download_name(st.session_state.subject)
        except Exception:
            eml_bytes = None

    columns = st.columns(
        [1.35, 0.7, 0.95, 1.05, 1.45, 4.0],
        gap='small',
    )
    generation_slot = columns[5].empty()

    with columns[0]:
        if st.button(
            _t("generate_staff_draft"),
            type='primary',
            use_container_width=True,
            key='action_generate',
        ):
            generation_slot.markdown(
                (
                    '<div class="hans-generation-indicator">'
                    '<span class="hans-generation-dots">'
                    '<span></span><span></span><span></span>'
                    '</span>'
                    f'<span>{html.escape(_t("generating"))}</span>'
                    '</div>'
                ),
                unsafe_allow_html=True,
            )
            _generate()
            st.rerun()

    with columns[1]:
        st.button(
            _t("clear"),
            use_container_width=True,
            key='action_clear',
            on_click=_clear_editor_action,
        )

    with columns[2]:
        if st.button(
            _t("copy_draft"),
            disabled=not draft,
            use_container_width=True,
            key='action_copy',
        ):
            st.session_state.status_message = (
                'Draft is ready to copy from the Staff draft field.'
            )

    with columns[3]:
        if st.button(
            _t("open_full_draft"),
            disabled=not draft,
            use_container_width=True,
            key='action_full',
        ):
            _full_draft_dialog()

    with columns[4]:
        st.download_button(
            _t("export_reply"),
            data=eml_bytes or b'',
            file_name=export_name,
            mime='message/rfc822',
            disabled=eml_bytes is None,
            use_container_width=True,
            on_click=_mark_export_requested if eml_bytes else None,
            key='action_export',
        )

    if st.session_state.export_confirmation_pending and eml_bytes is not None:
        with columns[5]:
            confirm_col, cancel_col = st.columns([1.8, 0.9], gap='small')

            with confirm_col:
                st.button(
                    _t("file_saved_remove"),
                    type='primary',
                    use_container_width=True,
                    key='action_confirm_export',
                    on_click=_confirm_exported_action,
                )

            with cancel_col:
                st.button(
                    _t("keep_pending"),
                    use_container_width=True,
                    key='action_keep_pending',
                    on_click=_keep_export_pending,
                )

    elif result:
        timing = result.get('timing') or {}
        generation = (
            (result.get('observability') or {}).get('generation')
            or {}
        )
        generation_slot.markdown(
            (
                '<div class="hans-generation-complete">'
                f'{html.escape(_t("draft_ready"))}'
                f' · {html.escape(_t("generation"))} '
                f'{html.escape(str(generation.get("generation_total_seconds", "—")))} s'
                f' · {html.escape(_t("total"))} '
                f'{html.escape(str(timing.get("total", "—")))} s'
                '</div>'
            ),
            unsafe_allow_html=True,
        )


def _render_results() -> None:
    result = st.session_state.last_result
    left, right = st.columns([1, 1], gap='small')
    with left:
        with st.container(border=True):
            st.markdown(
                f'<div class="section-title">{html.escape(_t("staff_draft"))}</div>',
                unsafe_allow_html=True,
            )
            st.text_area(
                _t("staff_draft"),
                key='draft_text',
                height=285,
                label_visibility='collapsed',
            )

            source_links = _draft_source_links_html(result)
            if source_links:
                st.markdown(
                    source_links,
                    unsafe_allow_html=True,
                )
    with right:
        with st.container(border=True):
            st.markdown(
                f'<div class="section-title">{html.escape(_t("validation_quality_sources"))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                _staff_review_summary_html(result),
                unsafe_allow_html=True,
            )
    if result:
        generation = ((result.get('observability') or {}).get('generation') or {})
        if generation.get('reasoning_tokens') not in (None, 0):
            st.error(
                'Unexpected reasoning tokens detected. '
                'Do not use this run for validation.'
            )
        # Evaluation logging remains enabled but its filesystem path is hidden from staff.


def main() -> None:
    st.set_page_config(
        page_title='HANS Email Assistant',
        page_icon='📨',
        layout='wide',
        initial_sidebar_state='collapsed',
    )
    _init_state()
    _apply_desktop_style()

    title_col, language_col = st.columns([8.5, 1.5], gap='small')
    with title_col:
        st.markdown(
            f'<div class="hans-title">{html.escape(_t("app_title"))}</div>',
            unsafe_allow_html=True,
        )
    with language_col:
        st.selectbox(
            'Sprache / Language',
            options=['en', 'de'],
            format_func=lambda value: 'Deutsch' if value == 'de' else 'English',
            key='ui_language',
            label_visibility='collapsed',
        )

    online, status = _health_status()
    status_class = 'hans-online' if online else 'hans-offline'
    if online:
        display_status = _t("online")
    elif status == 'Offline':
        display_status = _t("offline")
    elif status == 'Unavailable':
        display_status = _t("unavailable")
    else:
        display_status = status

    st.markdown(
        '<div class="hans-status">'
        f'<span class="{status_class}">{html.escape(display_status)}</span>'
        f'{html.escape(API_BASE)}'
        '</div>',
        unsafe_allow_html=True,
    )
    _render_mailbox()
    _render_metadata_and_input()
    _render_action_row()
    _render_results()
    # Persistent footer/status text is intentionally hidden in the staff UI.


if __name__ == '__main__':
    main()