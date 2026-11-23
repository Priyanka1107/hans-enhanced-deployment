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


def _init_state() -> None:
    defaults: dict[str, Any] = {
        'pending_emails': [],
        'seen_upload_hashes': set(),
        'selected_pending_id': None,
        'loaded_email_id': None,
        'student_email': '',
        'subject': '',
        'incoming_text': '',
        'language': 'en',
        'top_k': 6,
        'thread_id': '',
        'email_id': '',
        'last_result': None,
        'draft_text': '',
        'last_log_path': None,
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
            max-width: 1700px !important;
            padding: 0.35rem 0.75rem 0.45rem !important;
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
        st.session_state.selected_pending_id = item_id
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
    before = len(st.session_state.pending_emails)
    st.session_state.pending_emails = [
        item for item in st.session_state.pending_emails if item['id'] != item_id
    ]
    removed = len(st.session_state.pending_emails) < before
    if removed and st.session_state.selected_pending_id == item_id:
        st.session_state.selected_pending_id = (
            st.session_state.pending_emails[0]['id']
            if st.session_state.pending_emails else None
        )
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
        st.session_state.draft_text = str(result.get('staff_draft') or '')
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


def _mark_exported() -> None:
    loaded_id = st.session_state.loaded_email_id
    if loaded_id and _remove_pending(loaded_id):
        _clear_editor()
        st.session_state.status_message = (
            'Reply exported successfully. The processed incoming .eml '
            'was removed from the pending list.'
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
        return (
            'Mailbox integration is disabled for this testing phase. '
            'Add local .eml files or paste an inquiry manually.'
        )
    parsed = item['parsed']
    attachment_names = [
        str(value.get('filename') or 'attachment')
        for value in parsed['attachments']
    ]
    label = f"Selected: {parsed['subject'] or '(no subject)'}"
    if attachment_names:
        label += ' | ' + ', '.join(attachment_names)
    return label


def _review_value(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    if value is None:
        return "Not available"
    return str(value)


def _staff_review_summary_html(
    result: dict[str, Any] | None,
) -> str:
    if not result:
        return (
            '<div class="review-summary">'
            '<div class="review-summary-title">STAFF REVIEW SUMMARY</div>'
            '<div>No draft has been generated yet.</div>'
            '</div>'
        )

    validation = result.get("validation") or {}
    quality = result.get("quality") or {}
    email_context = result.get("email_context") or {}
    topics = result.get("detected_topics") or []
    sources = result.get("sources") or []

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

    parts = [
        '<div class="review-summary">',
        '<div class="review-summary-title">STAFF REVIEW SUMMARY</div>',
        '<div class="review-row"><span class="review-label">Programme:</span> '
        f'{html.escape(str(programme))}</div>',
        '<div class="review-row"><span class="review-label">Topics detected:</span> '
        f'{html.escape(", ".join(topic_labels) if topic_labels else "None detected")}</div>',
        '<div class="review-row"><span class="review-label">Grounded:</span> '
        f'<span class="{status_class(grounded)}">'
        f'{html.escape(_review_value(grounded))}</span></div>',
        '<div class="review-row"><span class="review-label">Citations valid:</span> '
        f'<span class="{status_class(citations_valid)}">'
        f'{html.escape(_review_value(citations_valid))}</span></div>',
        '<div class="review-row"><span class="review-label">Hallucinations detected:</span> '
        f'<span class="{status_class(hallucinations, positive_when_false=True)}">'
        f'{html.escape(_review_value(hallucinations))}</span></div>',
        '<div class="review-row"><span class="review-label">Review required:</span> '
        f'<span class="{status_class(review_required, positive_when_false=True)}">'
        f'{html.escape(_review_value(review_required))}</span></div>',
        '<div class="review-row"><span class="review-label">Confidence:</span> '
        f'{html.escape(_review_value(confidence))}</div>',
        '<div class="review-row"><span class="review-label">Failure type:</span> '
        f'{html.escape(_review_value(failure_type))}</div>',
        '<div class="review-reason"><span class="review-label">Review reason:</span> '
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
            "Preview",
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
            "Document preview",
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

    st.info(
        "Inline preview is not available for this attachment type."
    )


@st.dialog(
    "Select attachment",
    width="large",
)
def _attachment_dialog(
    item_id: str,
) -> None:
    item = _pending_by_id(
        item_id
    )

    if item is None:
        st.warning(
            "The selected email is no longer available."
        )
        return

    attachments = (
        item["parsed"]["attachments"]
    )

    if not attachments:
        st.info(
            "The selected email has no attachments."
        )
        return

    names = [
        attachment["filename"]
        for attachment in attachments
    ]

    selected_name = st.selectbox(
        "Choose the attachment to view:",
        names,
        key=f"attachment_choice_{item_id}",
    )

    index = names.index(
        selected_name
    )

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
            f"Could not open attachment: {exc}"
        )
        return

    if not actual_type:
        actual_type = (
            mimetypes.guess_type(
                actual_name
            )[0]
            or "application/octet-stream"
        )

    _render_attachment_preview(
        content=content,
        filename=actual_name,
        content_type=actual_type,
    )

    st.download_button(
        "Download attachment",
        data=content,
        file_name=actual_name,
        mime=actual_type,
        use_container_width=True,
    )


@st.dialog('Full staff draft', width='large')
def _full_draft_dialog() -> None:
    st.text_area(
        'Staff draft',
        value=st.session_state.draft_text,
        height=520,
        key='full_draft_preview',
    )


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
        'Reference links for staff verification'
        '</div>',
    ]

    for index, source in enumerate(
        sources,
        start=1,
    ):
        title = str(
            source.get("title")
            or f"Source {index}"
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
            '<div class="section-title">Incoming mailbox</div>',
            unsafe_allow_html=True,
        )
        pending = st.session_state.pending_emails
        selected_item = _pending_by_id(st.session_state.selected_pending_id)
        info_col, view_col, load_col, remove_col, add_col, refresh_col = st.columns(
            [5.5, 1.15, 1.25, 1.55, 1.1, 1.1],
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
                'View attachment',
                disabled=not attachments_available,
                use_container_width=True,
            ):
                _attachment_dialog(st.session_state.selected_pending_id)
        with load_col:
            if st.button(
                'Load selected email',
                disabled=selected_item is None,
                use_container_width=True,
            ):
                _load_selected()
                st.rerun()
        with remove_col:
            if st.button(
                'Remove selected .eml',
                disabled=selected_item is None,
                use_container_width=True,
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
            with st.popover('Add .eml files', use_container_width=True):
                uploaded = st.file_uploader(
                    'Select local .eml files',
                    type=['eml'],
                    accept_multiple_files=True,
                    label_visibility='collapsed',
                    key='mailbox_uploader',
                )
                if uploaded:
                    _add_uploaded_emails(uploaded)
        with refresh_col:
            st.button('Refresh inbox', disabled=True, use_container_width=True)

        if pending:
            st.markdown(
                (
                    '<div class="mailbox-header">'
                    '<div>Sender</div>'
                    '<div>Subject</div>'
                    '<div>Received</div>'
                    '<div>Attachments</div>'
                    '</div>'
                ),
                unsafe_allow_html=True,
            )

            for item in pending:
                parsed = item[
                    "parsed"
                ]

                selected = (
                    item["id"]
                    == st.session_state.selected_pending_id
                )

                row_class = (
                    "mailbox-row-wrap mailbox-row-selected"
                    if selected
                    else "mailbox-row-wrap"
                )

                st.markdown(
                    f'<div class="{row_class}">',
                    unsafe_allow_html=True,
                )

                sender_col, subject_col, received_col, attachment_col = (
                    st.columns(
                        [1.25, 2.2, 1.55, 0.55],
                        gap="small",
                    )
                )

                with sender_col:
                    if st.button(
                        parsed["sender_email"] or "",
                        key=f"mail_sender_{item['id']}",
                        type=("primary" if selected else "secondary"),
                        use_container_width=True,
                    ):
                        st.session_state.selected_pending_id = (
                            item["id"]
                        )
                        st.rerun()

                with subject_col:
                    if st.button(
                        parsed["subject"] or "",
                        key=f"mail_subject_{item['id']}",
                        type=("primary" if selected else "secondary"),
                        use_container_width=True,
                    ):
                        st.session_state.selected_pending_id = (
                            item["id"]
                        )
                        st.rerun()

                with received_col:
                    if st.button(
                        parsed["received_at"] or "",
                        key=f"mail_received_{item['id']}",
                        type=("primary" if selected else "secondary"),
                        use_container_width=True,
                    ):
                        st.session_state.selected_pending_id = (
                            item["id"]
                        )
                        st.rerun()

                with attachment_col:
                    if st.button(
                        str(
                            len(
                                parsed[
                                    "attachments"
                                ]
                            )
                        ),
                        key=f"mail_attach_{item['id']}",
                        type=("primary" if selected else "secondary"),
                        use_container_width=True,
                    ):
                        st.session_state.selected_pending_id = (
                            item["id"]
                        )
                        st.rerun()

                st.markdown(
                    "</div>",
                    unsafe_allow_html=True,
                )

        else:
            st.caption('No local .eml files are currently pending.')


def _render_metadata_and_input() -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="section-title">Incoming email metadata</div>',
            unsafe_allow_html=True,
        )
        left, right = st.columns([1, 2], gap='small')
        with left:
            st.text_input('Student email', key='student_email')
        with right:
            st.text_input('Subject', key='subject')

    with st.container(border=True):
        st.markdown(
            '<div class="section-title">Incoming student email</div>',
            unsafe_allow_html=True,
        )
        st.text_area(
            'Incoming student email',
            key='incoming_text',
            height=145,
            label_visibility='collapsed',
        )

    # Match the desktop staff UI: language and retrieval top-k remain
    # internal request values and are not exposed as staff controls.
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
        [1.35, 0.7, 0.95, 1.05, 1.45, 1.55, 0.95, 4.0],
        gap='small',
    )
    with columns[0]:
        if st.button('Generate staff draft', type='primary', use_container_width=True):
            with st.spinner('Generating staff draft...'):
                _generate()
            st.rerun()
    with columns[1]:
        if st.button('Clear', use_container_width=True):
            _clear_editor()
            st.session_state.status_message = 'Input and generated result cleared.'
            st.rerun()
    with columns[2]:
        if st.button('Copy draft', disabled=not draft, use_container_width=True):
            st.session_state.status_message = (
                'Draft is ready to copy from the Staff draft field.'
            )
    with columns[3]:
        if st.button('Open full draft', disabled=not draft, use_container_width=True):
            _full_draft_dialog()
    with columns[4]:
        st.download_button(
            'Export reply as .eml',
            data=eml_bytes or b'',
            file_name=export_name,
            mime='message/rfc822',
            disabled=eml_bytes is None,
            use_container_width=True,
            on_click=_mark_exported if eml_bytes else None,
        )
    with columns[5]:
        st.button('Save to mailbox drafts', disabled=True, use_container_width=True)
    with columns[6]:
        st.button('Send email', disabled=True, use_container_width=True)
    with columns[7]:
        if result:
            timing = result.get('timing') or {}
            generation = (
                (result.get('observability') or {}).get('generation') or {}
            )
            st.caption(
                f"Generation {generation.get('generation_total_seconds', '—')} s"
                f" · Total {timing.get('total', '—')} s"
            )


def _render_results() -> None:
    result = st.session_state.last_result
    left, right = st.columns([1, 1], gap='small')
    with left:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">Staff draft</div>',
                unsafe_allow_html=True,
            )
            st.text_area(
                'Staff draft',
                key='draft_text',
                height=285,
                label_visibility='collapsed',
            )

            draft_links = (
                _draft_source_links_html(
                    result
                )
            )

            if draft_links:
                st.markdown(
                    draft_links,
                    unsafe_allow_html=True,
                )
    with right:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">Validation, quality and sources</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                _staff_review_summary_html(
                    result
                ),
                unsafe_allow_html=True,
            )
    if result:
        generation = ((result.get('observability') or {}).get('generation') or {})
        if generation.get('reasoning_tokens') not in (None, 0):
            st.error(
                'Unexpected reasoning tokens detected. '
                'Do not use this run for validation.'
            )
        if st.session_state.last_log_path:
            st.caption(
                'Evaluation result saved: '
                f"{st.session_state.last_log_path}"
            )


def main() -> None:
    st.set_page_config(
        page_title='HANS Email Assistant',
        page_icon='📨',
        layout='wide',
        initial_sidebar_state='collapsed',
    )
    _init_state()
    _apply_desktop_style()
    st.markdown(
        '<div class="hans-title">HANS Email Assistant</div>',
        unsafe_allow_html=True,
    )
    online, status = _health_status()
    status_class = 'hans-online' if online else 'hans-offline'
    st.markdown(
        '<div class="hans-status">'
        f'<span class="{status_class}">{html.escape(status)}</span>'
        f'{html.escape(API_BASE)}'
        '</div>',
        unsafe_allow_html=True,
    )
    _render_mailbox()
    _render_metadata_and_input()
    _render_action_row()
    _render_results()
    st.markdown(
        '<div class="footer-line">'
        + html.escape(st.session_state.status_message)
        + '</div>',
        unsafe_allow_html=True,
    )


if __name__ == '__main__':
    main()
