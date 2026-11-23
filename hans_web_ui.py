from __future__ import annotations

import hashlib
import mimetypes
import os
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
load_dotenv(PROJECT_ROOT / ".env", override=False)

API_BASE = os.getenv(
    "HANS_UI_API_URL",
    os.getenv("HANS_API_BASE", "http://127.0.0.1:8009"),
).rstrip("/")
EMAIL_URL = f"{API_BASE}/email"
HEALTH_URL = f"{API_BASE}/health"
INTERNAL_API_KEY = os.getenv("HANS_INTERNAL_API_KEY", "").strip()
TIMEOUT_SECONDS = float(os.getenv("HANS_UI_API_TIMEOUT", "720"))
CUSTOM_CASE_ID = "CUSTOM-MANUAL"

VIEWABLE_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/bmp",
    "image/webp",
}
TEXT_ATTACHMENT_TYPES = {
    "text/plain",
    "text/csv",
}


def _request_headers() -> dict[str, str]:
    if not INTERNAL_API_KEY:
        raise RuntimeError(
            "HANS_INTERNAL_API_KEY is not configured in .env."
        )
    return {"X-HANS-API-Key": INTERNAL_API_KEY}


def _safe_download_name(subject: str) -> str:
    value = subject.strip() or "HANS_Draft"
    value = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", value)
    value = " ".join(value.split()).strip(" .") or "HANS_Draft"
    value = value[:100].rstrip(" .") or "HANS_Draft"
    return f"{value}_{time.strftime('%Y%m%d_%H%M%S')}.eml"


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "pending_emails": [],
        "seen_upload_hashes": set(),
        "selected_pending_id": None,
        "loaded_email_id": None,
        "student_email": "",
        "subject": "",
        "incoming_text": "",
        "language": "en",
        "top_k": 6,
        "thread_id": "",
        "email_id": "",
        "last_result": None,
        "draft_text": "",
        "last_log_path": None,
        "status_message": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _add_uploaded_emails(uploaded_files: list[Any]) -> None:
    added = 0
    errors: list[str] = []

    for uploaded in uploaded_files:
        data = uploaded.getvalue()
        digest = hashlib.sha256(data).hexdigest()

        if digest in st.session_state.seen_upload_hashes:
            continue

        try:
            parsed = parse_eml_bytes(data)
        except Exception as exc:
            errors.append(f"{uploaded.name}: {exc}")
            st.session_state.seen_upload_hashes.add(digest)
            continue

        item_id = uuid.uuid4().hex

        st.session_state.pending_emails.append(
            {
                "id": item_id,
                "name": uploaded.name,
                "sha256": digest,
                "bytes": data,
                "parsed": parsed,
            }
        )
        st.session_state.seen_upload_hashes.add(digest)
        st.session_state.selected_pending_id = item_id
        added += 1

    if added:
        st.session_state.status_message = (
            f"Added {added} local .eml file(s) to the pending list."
        )

    if errors:
        st.warning(
            "Some .eml files could not be loaded:\n\n"
            + "\n".join(errors)
        )


def _pending_by_id(
    item_id: str | None,
) -> dict[str, Any] | None:
    if not item_id:
        return None

    for item in st.session_state.pending_emails:
        if item["id"] == item_id:
            return item

    return None


def _remove_pending(item_id: str | None) -> bool:
    if not item_id:
        return False

    before = len(st.session_state.pending_emails)

    st.session_state.pending_emails = [
        item
        for item in st.session_state.pending_emails
        if item["id"] != item_id
    ]

    removed = (
        len(st.session_state.pending_emails)
        < before
    )

    if (
        removed
        and st.session_state.selected_pending_id
        == item_id
    ):
        st.session_state.selected_pending_id = (
            st.session_state.pending_emails[0]["id"]
            if st.session_state.pending_emails
            else None
        )

    return removed


def _clear_editor() -> None:
    st.session_state.loaded_email_id = None
    st.session_state.student_email = ""
    st.session_state.subject = ""
    st.session_state.incoming_text = ""
    st.session_state.thread_id = ""
    st.session_state.email_id = ""
    st.session_state.last_result = None
    st.session_state.draft_text = ""
    st.session_state.last_log_path = None


def _load_selected() -> None:
    item = _pending_by_id(
        st.session_state.selected_pending_id
    )

    if item is None:
        st.warning(
            "Select a pending .eml file first."
        )
        return

    parsed = item["parsed"]
    token = item["id"][:8]

    st.session_state.loaded_email_id = item["id"]
    st.session_state.student_email = (
        parsed["sender_email"]
    )
    st.session_state.subject = parsed["subject"]
    st.session_state.incoming_text = parsed["body"]
    st.session_state.thread_id = (
        f"web-thread-{token}"
    )
    st.session_state.email_id = (
        f"web-email-{token}"
    )
    st.session_state.last_result = None
    st.session_state.draft_text = ""
    st.session_state.last_log_path = None
    st.session_state.status_message = (
        "Selected email loaded. "
        "No draft has been generated yet."
    )


def _generate() -> None:
    email_text = (
        st.session_state.incoming_text.strip()
    )

    if not email_text:
        st.error(
            "Incoming email text is required."
        )
        return

    try:
        headers = _request_headers()
    except Exception as exc:
        st.error(str(exc))
        return

    thread_id = (
        st.session_state.thread_id.strip()
        or f"web-thread-{uuid.uuid4().hex[:8]}"
    )
    email_id = (
        st.session_state.email_id.strip()
        or f"web-email-{uuid.uuid4().hex[:8]}"
    )

    st.session_state.thread_id = thread_id
    st.session_state.email_id = email_id

    payload = {
        "email_text": email_text,
        "student_email": (
            st.session_state.student_email.strip()
            or None
        ),
        "subject": (
            st.session_state.subject.strip()
            or None
        ),
        "thread_id": thread_id,
        "email_id": email_id,
        "language": (
            st.session_state.language.strip()
            or "en"
        ),
        "top_k": int(
            st.session_state.top_k
        ),
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

        client_latency = (
            time.perf_counter() - started
        )

        result["_ui_client"] = {
            "latency_seconds": round(
                client_latency,
                3,
            ),
            "api_base": API_BASE,
        }

        saved_path = None

        if save_ui_evaluation_run is not None:
            saved_path = save_ui_evaluation_run(
                test_case_id=CUSTOM_CASE_ID,
                request_payload=payload,
                response_payload=result,
            )

        st.session_state.last_result = result
        st.session_state.draft_text = str(
            result.get("staff_draft")
            or ""
        )
        st.session_state.last_log_path = (
            str(saved_path)
            if saved_path is not None
            else None
        )
        st.session_state.status_message = (
            "Draft generated. "
            "Staff review is required."
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

        st.error(
            f"HANS draft generation failed: {exc}"
        )


def _mark_exported() -> None:
    loaded_id = (
        st.session_state.loaded_email_id
    )

    if (
        loaded_id
        and _remove_pending(loaded_id)
    ):
        _clear_editor()
        st.session_state.status_message = (
            "Reply exported. The processed incoming "
            ".eml was removed from this browser "
            "session's pending list."
        )


def _render_health() -> None:
    try:
        response = requests.get(
            HEALTH_URL,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "healthy":
            st.success(
                "Backend online · "
                f"{data.get('generation_provider', 'provider n/a')} · "
                f"{data.get('generation_model', 'model n/a')}"
            )
        else:
            st.warning(
                "Backend status: "
                f"{data.get('status', 'unknown')}"
            )

    except Exception as exc:
        st.error(
            f"Backend unavailable at {API_BASE}: {exc}"
        )


def _render_pending_list() -> None:
    st.subheader("1. Incoming .eml files")

    uploaded = st.file_uploader(
        "Add one or more .eml files",
        type=["eml"],
        accept_multiple_files=True,
        help=(
            "Files are kept only in this browser "
            "session for the current testing workflow."
        ),
    )

    if uploaded:
        _add_uploaded_emails(uploaded)

    pending = (
        st.session_state.pending_emails
    )

    if not pending:
        st.info(
            "No pending .eml files in this "
            "browser session."
        )
        return

    rows: list[dict[str, Any]] = []

    for item in pending:
        parsed = item["parsed"]

        rows.append(
            {
                "File": item["name"],
                "Sender": parsed["sender_email"],
                "Subject": parsed["subject"],
                "Received": parsed["received_at"],
                "Attachments": len(
                    parsed["attachments"]
                ),
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )

    labels = {
        item["id"]: (
            f"{item['parsed']['subject'] or '(no subject)'}"
            " — "
            f"{item['parsed']['sender_email'] or item['name']}"
        )
        for item in pending
    }

    ids = [
        item["id"]
        for item in pending
    ]

    current = (
        st.session_state.selected_pending_id
    )

    index = (
        ids.index(current)
        if current in ids
        else 0
    )

    selected = st.selectbox(
        "Selected pending email",
        ids,
        index=index,
        format_func=lambda item_id: labels[
            item_id
        ],
    )

    st.session_state.selected_pending_id = (
        selected
    )

    col_load, col_remove = st.columns(2)

    with col_load:
        if st.button(
            "Load selected email",
            use_container_width=True,
        ):
            _load_selected()
            st.rerun()

    with col_remove:
        if st.button(
            "Remove selected .eml",
            use_container_width=True,
        ):
            was_loaded = (
                st.session_state.loaded_email_id
                == selected
            )

            if _remove_pending(selected):
                if was_loaded:
                    _clear_editor()

                st.session_state.status_message = (
                    "Selected .eml removed from the "
                    "pending list. The original uploaded "
                    "file was not deleted."
                )

            st.rerun()


def _render_attachments() -> None:
    item = _pending_by_id(
        st.session_state.loaded_email_id
    )

    if item is None:
        return

    attachments = (
        item["parsed"]["attachments"]
    )

    if not attachments:
        return

    with st.expander(
        "Attachments "
        f"({len(attachments)}) "
        "— staff viewing only"
    ):
        st.caption(
            "HANS does not analyse attachment "
            "contents in this testing version."
        )

        for index, metadata in enumerate(
            attachments
        ):
            name = metadata["filename"]

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
                    f"Could not open {name}: {exc}"
                )
                continue

            if not actual_type:
                actual_type = (
                    mimetypes.guess_type(
                        actual_name
                    )[0]
                    or "application/octet-stream"
                )

            st.markdown(
                f"**{actual_name}** · "
                f"{actual_type} · "
                f"{len(content)} bytes"
            )

            if (
                actual_type
                in VIEWABLE_IMAGE_TYPES
            ):
                st.image(
                    content,
                    caption=actual_name,
                )

            elif (
                actual_type
                in TEXT_ATTACHMENT_TYPES
            ):
                st.code(
                    content.decode(
                        "utf-8",
                        errors="replace",
                    ),
                    language=None,
                )

            st.download_button(
                f"Open/download {actual_name}",
                data=content,
                file_name=actual_name,
                mime=actual_type,
                key=(
                    "attachment-"
                    f"{item['id']}-"
                    f"{index}"
                ),
            )


def _render_editor() -> None:
    st.subheader(
        "2. Review incoming enquiry"
    )

    st.text_input(
        "Student email",
        key="student_email",
    )

    st.text_input(
        "Subject",
        key="subject",
    )

    st.text_area(
        "Incoming email",
        key="incoming_text",
        height=260,
    )

    col_lang, col_topk = st.columns(2)

    with col_lang:
        st.selectbox(
            "Response language",
            ["en", "de"],
            key="language",
        )

    with col_topk:
        st.slider(
            "Retrieval top-k",
            min_value=3,
            max_value=10,
            key="top_k",
        )

    _render_attachments()

    if st.button(
        "Generate staff draft",
        type="primary",
        use_container_width=True,
    ):
        with st.spinner(
            "HANS is generating a staff draft..."
        ):
            _generate()

        st.rerun()


def _render_result() -> None:
    result = (
        st.session_state.last_result
    )

    if not result:
        return

    st.subheader("3. Staff draft")

    st.warning(
        "Staff review is required before sending. "
        "Automatic sending is disabled."
    )

    st.text_area(
        "Editable reply",
        key="draft_text",
        height=380,
    )

    draft = (
        st.session_state.draft_text.strip()
    )

    if draft:
        try:
            eml_bytes = build_reply_eml_bytes(
                recipient=(
                    st.session_state.student_email
                ),
                subject=(
                    st.session_state.subject
                ),
                body=draft,
            )

            filename = _safe_download_name(
                st.session_state.subject
            )

            st.download_button(
                "Export reviewed reply as .eml",
                data=eml_bytes,
                file_name=filename,
                mime="message/rfc822",
                type="primary",
                use_container_width=True,
                on_click=_mark_exported,
            )

        except Exception as exc:
            st.error(
                "Cannot prepare .eml export: "
                f"{exc}"
            )

    validation = (
        result.get("validation")
        or {}
    )
    quality = (
        result.get("quality")
        or {}
    )
    timing = (
        result.get("timing")
        or {}
    )
    observability = (
        result.get("observability")
        or {}
    )
    generation = (
        observability.get("generation")
        or {}
    )
    email_context = (
        result.get("email_context")
        or {}
    )

    with st.expander(
        "Staff review summary",
        expanded=True,
    ):
        st.write(
            {
                "Programme": (
                    email_context.get(
                        "target_program"
                    )
                    or email_context.get(
                        "target_programme"
                    )
                    or "n/a"
                ),
                "Topics detected": [
                    (
                        topic.get("label")
                        or topic.get(
                            "topic_id"
                        )
                    )
                    for topic in (
                        result.get(
                            "detected_topics"
                        )
                        or []
                    )
                ],
                "Grounded": (
                    validation.get(
                        "is_grounded"
                    )
                ),
                "Citations valid": (
                    validation.get(
                        "citations_valid"
                    )
                ),
                "Hallucinations detected": (
                    validation.get(
                        "has_hallucinations"
                    )
                ),
                "Review required": (
                    quality.get(
                        "review_required"
                    )
                ),
                "Review reason": (
                    quality.get(
                        "review_reason"
                    )
                ),
                "Automatic sending": (
                    result.get(
                        "automatic_send",
                        False,
                    )
                ),
                "Model": generation.get(
                    "model",
                    "n/a",
                ),
                "Generation time (s)": (
                    generation.get(
                        "generation_total_seconds"
                    )
                ),
                "Total request time (s)": (
                    timing.get("total")
                ),
            }
        )

    sources = (
        result.get("sources")
        or []
    )

    with st.expander(
        f"Official sources ({len(sources)})",
        expanded=True,
    ):
        if not sources:
            st.info(
                "No source links returned."
            )

        for index, source in enumerate(
            sources,
            start=1,
        ):
            title = (
                source.get("title")
                or f"Source {index}"
            )
            url = (
                source.get("url")
                or ""
            )

            st.markdown(
                f"**{index}. {title}**"
            )

            if url:
                st.markdown(
                    f"[{url}]({url})"
                )

            excerpt = (
                source.get("excerpt")
            )

            if excerpt:
                st.caption(excerpt)

    with st.expander(
        "Technical details"
    ):
        st.json(result)

    if st.session_state.last_log_path:
        st.caption(
            "Evaluation result saved on server: "
            f"{st.session_state.last_log_path}"
        )


def main() -> None:
    st.set_page_config(
        page_title="HANS Email Assistant",
        page_icon="📨",
        layout="wide",
    )

    _init_state()

    st.title("HANS Email Assistant")
    st.caption(
        "HTW Berlin staff testing · "
        "local .eml workflow · "
        "manual review and send"
    )

    _render_health()

    if st.session_state.status_message:
        st.info(
            st.session_state.status_message
        )

    left, right = st.columns(
        [0.95, 1.35],
        gap="large",
    )

    with left:
        _render_pending_list()

    with right:
        _render_editor()
        _render_result()

    st.divider()

    st.caption(
        "Mailbox integration and automatic sending "
        "are disabled for this testing phase. "
        "Each browser session keeps its own pending "
        ".eml list."
    )


if __name__ == "__main__":
    main()
