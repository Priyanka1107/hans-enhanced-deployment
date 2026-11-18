from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
import webbrowser
from pathlib import Path
from typing import Any, Dict

import requests
import tkinter as tk
from dotenv import load_dotenv
from tkinter import messagebox, scrolledtext, ttk

from app.ui.mailbox_client import (
    MailboxUIError,
    attachment_summary,
    fetch_mailbox_messages,
    fetch_mailbox_status,
    save_mailbox_draft,
    send_mailbox_message,
)
# HANS_MAILBOX_UI_INTEGRATION_V1


PROJECT_ROOT = Path(__file__).resolve().parent

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

API_BASE = os.getenv(
    "HANS_UI_API_URL",
    os.getenv(
        "HANS_API_BASE",
        "http://127.0.0.1:8009",
    ),
).rstrip("/")

HEALTH_URL = f"{API_BASE}/health"
EMAIL_URL = f"{API_BASE}/email"

INTERNAL_API_KEY = os.getenv(
    "HANS_INTERNAL_API_KEY",
    "",
).strip()

TIMEOUT_SECONDS = float(
    os.getenv(
        "HANS_UI_API_TIMEOUT",
        "720",
    )
)

TEST_CASES_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "ui_test_cases.json"
)

CUSTOM_CASE_ID = "CUSTOM-MANUAL"

try:
    from evaluation.ui_eval_logger import (
        save_ui_evaluation_run,
    )
except ImportError:
    save_ui_evaluation_run = None


def _request_headers() -> Dict[str, str]:
    if not INTERNAL_API_KEY:
        raise RuntimeError(
            "HANS_INTERNAL_API_KEY is not configured in .env."
        )

    return {
        "X-HANS-API-Key": INTERNAL_API_KEY,
    }


def _load_test_cases() -> Dict[str, Dict[str, Any]]:
    if not TEST_CASES_PATH.exists():
        return {}

    payload = json.loads(
        TEST_CASES_PATH.read_text(
            encoding="utf-8",
        )
    )

    return {
        str(case["test_case_id"]): case
        for case in payload.get("cases", [])
        if case.get("test_case_id")
    }


class EnhancedHANSEmailUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(
            "HANS Email Assistant"
        )
        self.root.geometry("1450x900")
        self.root.minsize(1000, 720)

        # Start maximized on Windows when supported. The UI still works
        # normally on platforms where the "zoomed" state is unavailable.
        try:
            self.root.state("zoomed")
        except tk.TclError:
            pass

        self.processing = False
        self.last_result: Dict[str, Any] | None = None
        self.test_cases = _load_test_cases()
        self.mailbox_messages: list[Dict[str, Any]] = []

        self._build_ui()
        self._load_default_case()
        self._check_api_async()

    def _build_ui(self) -> None:
        main = ttk.Frame(
            self.root,
            padding=12,
        )
        main.pack(
            fill=tk.BOTH,
            expand=True,
        )

        # Restrained visual hierarchy for the staff-facing UI.
        ui_style = ttk.Style()
        ui_style.configure(
            "Section.TLabelframe.Label",
            font=("Segoe UI", 11, "bold"),
            foreground="#315F7D",
        )
        ui_style.configure(
            "Backend.TLabel",
            font=("Segoe UI", 9),
            foreground="#5B6570",
        )

        title = ttk.Label(
            main,
            text="HANS Email Assistant",
            font=("Segoe UI", 16, "bold"),
            foreground="#24495F",
        )
        title.pack(
            anchor=tk.W,
            pady=(0, 8),
        )

        # Compact operational status: useful for staff without exposing
        # development controls such as Test API or evaluation toggles.
        status_row = ttk.Frame(main)
        status_row.pack(
            fill=tk.X,
            pady=(0, 8),
        )

        ttk.Label(
            status_row,
            text=f"Backend: {API_BASE}",
            style="Backend.TLabel",
        ).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(
            value="Checking..."
        )
        self.status_label = ttk.Label(
            status_row,
            textvariable=self.status_var,
            style="Backend.TLabel",
        )
        self.status_label.pack(
            side=tk.LEFT,
            padx=(14, 0),
        )

        # Main vertical workspace. Each child pane can be resized by
        # dragging the separator between sections.
        self.main_pane = ttk.Panedwindow(
            main,
            orient=tk.VERTICAL,
        )
        self.main_pane.pack(
            fill=tk.BOTH,
            expand=True,
            pady=(0, 8),
        )

        # HANS_RESIZABLE_LAYOUT_V1

        mailbox_frame = ttk.LabelFrame(
            self.main_pane,
            text="Incoming mailbox",
            padding=8,
            style="Section.TLabelframe",
        )
        self.main_pane.add(
            mailbox_frame,
            weight=2,
        )

        mailbox_toolbar = ttk.Frame(
            mailbox_frame
        )
        mailbox_toolbar.pack(
            fill=tk.X,
            pady=(0, 6),
        )

        self.mailbox_info_var = tk.StringVar(
            value=(
                "Mailbox not loaded. Refreshing the inbox "
                "does not call Qwen."
            )
        )

        ttk.Label(
            mailbox_toolbar,
            textvariable=self.mailbox_info_var,
        ).pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

        self.mailbox_refresh_button = ttk.Button(
            mailbox_toolbar,
            text="Refresh inbox",
            command=self._refresh_mailbox_async,
        )
        self.mailbox_refresh_button.pack(
            side=tk.RIGHT,
        )

        self.mailbox_load_button = ttk.Button(
            mailbox_toolbar,
            text="Load selected email",
            command=self._load_selected_mailbox_email,
            state="disabled",
        )
        self.mailbox_load_button.pack(
            side=tk.RIGHT,
            padx=(0, 8),
        )

        mailbox_list_frame = ttk.Frame(
            mailbox_frame
        )
        mailbox_list_frame.pack(
            fill=tk.X,
        )

        columns = (
            "sender",
            "subject",
            "received",
            "attachments",
        )

        self.mailbox_tree = ttk.Treeview(
            mailbox_list_frame,
            columns=columns,
            show="headings",
            height=5,
            selectmode="browse",
        )

        self.mailbox_tree.heading(
            "sender",
            text="Sender",
        )
        self.mailbox_tree.heading(
            "subject",
            text="Subject",
        )
        self.mailbox_tree.heading(
            "received",
            text="Received",
        )
        self.mailbox_tree.heading(
            "attachments",
            text="Attachments",
            anchor=tk.CENTER,
        )

        self.mailbox_tree.column(
            "sender",
            width=220,
            anchor=tk.W,
        )
        self.mailbox_tree.column(
            "subject",
            width=520,
            anchor=tk.W,
        )
        self.mailbox_tree.column(
            "received",
            width=190,
            anchor=tk.W,
        )
        self.mailbox_tree.column(
            "attachments",
            width=180,
            anchor=tk.CENTER,
        )

        mailbox_scrollbar = ttk.Scrollbar(
            mailbox_list_frame,
            orient=tk.VERTICAL,
            command=self.mailbox_tree.yview,
        )
        self.mailbox_tree.configure(
            yscrollcommand=mailbox_scrollbar.set
        )

        self.mailbox_tree.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )
        mailbox_scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y,
        )

        self.mailbox_tree.bind(
            "<<TreeviewSelect>>",
            self._on_mailbox_selection,
        )
        self.mailbox_tree.bind(
            "<Double-1>",
            lambda _event: (
                self._load_selected_mailbox_email()
            ),
        )

        self.test_frame = ttk.LabelFrame(
            main,
            text="Evaluation test case",
            padding=8,
        )
        test_frame = self.test_frame

        test_frame.columnconfigure(
            1,
            weight=1,
        )

        ttk.Label(
            test_frame,
            text="Test case ID",
        ).grid(
            row=0,
            column=0,
            sticky=tk.W,
            padx=(0, 8),
        )

        self.test_case_var = tk.StringVar()

        self.test_case_combo = ttk.Combobox(
            test_frame,
            textvariable=self.test_case_var,
            values=[CUSTOM_CASE_ID] + list(self.test_cases.keys()),
            state="readonly",
        )
        self.test_case_combo.grid(
            row=0,
            column=1,
            sticky=(tk.W, tk.E),
        )

        ttk.Button(
            test_frame,
            text="Load test case",
            command=self._load_selected_case,
        ).grid(
            row=0,
            column=2,
            padx=(8, 0),
        )

        metadata_frame = ttk.LabelFrame(
            self.main_pane,
            text="Incoming email metadata",
            padding=8,
            style="Section.TLabelframe",
        )
        self.main_pane.add(
            metadata_frame,
            weight=0,
        )

        metadata_frame.columnconfigure(
            1,
            weight=1,
        )
        metadata_frame.columnconfigure(
            3,
            weight=2,
        )

        # Keep all metadata values internally because the backend, thread
        # handling, reply headers and evaluation logic still use them.
        # Only Student email and Subject are staff-facing fields.
        self.student_email_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.thread_id_var = tk.StringVar()
        self.email_id_var = tk.StringVar()
        self.language_var = tk.StringVar(
            value="en"
        )
        self.top_k_var = tk.IntVar(
            value=6
        )

        self._add_entry(
            metadata_frame,
            row=0,
            label="Student email",
            variable=self.student_email_var,
            label_column=0,
            entry_column=1,
        )

        self._add_entry(
            metadata_frame,
            row=0,
            label="Subject",
            variable=self.subject_var,
            label_column=2,
            entry_column=3,
        )

        # -----------------------------------------------------------------
        # Incoming email and generated results are independent adjustable
        # panes inside the main vertical workspace.
        # -----------------------------------------------------------------
        input_section = ttk.Frame(
            self.main_pane
        )
        result_section = ttk.Frame(
            self.main_pane
        )

        self.main_pane.add(
            input_section,
            weight=3,
        )
        self.main_pane.add(
            result_section,
            weight=4,
        )

        email_frame = ttk.LabelFrame(
            input_section,
            text="Incoming student email",
            padding=8,
            style="Section.TLabelframe",
        )
        email_frame.pack(
            fill=tk.BOTH,
            expand=True,
            pady=(0, 8),
        )

        self.email_text = scrolledtext.ScrolledText(
            email_frame,
            height=5,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
        )
        self.email_text.pack(
            fill=tk.BOTH,
            expand=True,
        )

        button_row = ttk.Frame(input_section)
        button_row.pack(
            fill=tk.X,
        )

        self.generate_button = ttk.Button(
            button_row,
            text="Generate staff draft",
            command=self._generate_async,
        )
        self.generate_button.pack(
            side=tk.LEFT,
        )

        ttk.Button(
            button_row,
            text="Clear",
            command=self._clear,
        ).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        ttk.Button(
            button_row,
            text="Copy draft",
            command=self._copy_draft,
        ).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        ttk.Button(
            button_row,
            text="Open full draft",
            command=self._open_full_draft,
        ).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        self.save_draft_button = ttk.Button(
            button_row,
            text="Save to mailbox drafts",
            command=self._save_mailbox_draft_async,
            state="disabled",
        )
        self.save_draft_button.pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        self.send_button = ttk.Button(
            button_row,
            text="Send email",
            command=self._confirm_and_send_mailbox_message,
            state="disabled",
        )
        self.send_button.pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        self.progress = ttk.Progressbar(
            button_row,
            mode="indeterminate",
        )
        self.progress.pack(
            side=tk.RIGHT,
            fill=tk.X,
            expand=True,
            padx=(20, 0),
        )

        # -----------------------------------------------------------------
        # Resizable result area
        #
        # Drag the vertical divider between the draft and validation panel.
        # This makes it easy to enlarge the draft for demos/screenshots.
        # -----------------------------------------------------------------
        output_pane = ttk.Panedwindow(
            result_section,
            orient=tk.HORIZONTAL,
        )
        output_pane.pack(
            fill=tk.BOTH,
            expand=True,
        )

        draft_frame = ttk.LabelFrame(
            output_pane,
            text="Staff draft",
            padding=8,
            style="Section.TLabelframe",
        )

        details_frame = ttk.LabelFrame(
            output_pane,
            text="Validation, quality and sources",
            padding=8,
            style="Section.TLabelframe",
        )

        output_pane.add(
            draft_frame,
            weight=4,
        )
        output_pane.add(
            details_frame,
            weight=2,
        )

        self.draft_text = scrolledtext.ScrolledText(
            draft_frame,
            height=8,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
        )
        self.draft_text.pack(
            fill=tk.BOTH,
            expand=True,
        )

        self.details_text = scrolledtext.ScrolledText(
            details_frame,
            height=8,
            wrap=tk.WORD,
            font=("Consolas", 9),
        )
        self.details_text.pack(
            fill=tk.BOTH,
            expand=True,
        )

        self.footer_var = tk.StringVar(
            value=(
                "Staff review required before sending. "
                "Automatic sending is disabled."
            )
        )

        ttk.Label(
            main,
            textvariable=self.footer_var,
        ).pack(
            anchor=tk.W,
            pady=(8, 0),
        )

    @staticmethod
    def _add_entry(
        frame: ttk.LabelFrame,
        *,
        row: int,
        label: str,
        variable: tk.StringVar,
        label_column: int,
        entry_column: int,
    ) -> None:
        ttk.Label(
            frame,
            text=label,
        ).grid(
            row=row,
            column=label_column,
            sticky=tk.W,
            padx=(0, 8),
            pady=(0, 6),
        )

        ttk.Entry(
            frame,
            textvariable=variable,
        ).grid(
            row=row,
            column=entry_column,
            sticky=(tk.W, tk.E),
            padx=(0, 12),
            pady=(0, 6),
        )

    def _load_default_case(self) -> None:
        # Start with a clean manual input instead of silently loading the
        # first evaluation preset. This avoids stale test-case metadata.
        self._load_custom_case()

    def _load_custom_case(self) -> None:
        self.test_case_var.set(CUSTOM_CASE_ID)
        self.student_email_var.set("")
        self.subject_var.set("")
        self.thread_id_var.set(
            f"ui-thread-{uuid.uuid4().hex[:8]}"
        )
        self.email_id_var.set(
            f"ui-email-{uuid.uuid4().hex[:8]}"
        )
        self.language_var.set("en")
        self.top_k_var.set(6)

        self.email_text.delete(
            "1.0",
            tk.END,
        )
        self.draft_text.delete(
            "1.0",
            tk.END,
        )
        self.details_text.delete(
            "1.0",
            tk.END,
        )

    def _load_selected_case(self) -> None:
        case_id = (
            self.test_case_var.get().strip()
        )

        if case_id == CUSTOM_CASE_ID:
            self._load_custom_case()
            return

        case = self.test_cases.get(
            case_id
        )

        if case is None:
            messagebox.showwarning(
                "Unknown test case",
                (
                    "The selected test case was not found "
                    "in evaluation/ui_test_cases.json."
                ),
            )
            return

        self._apply_case(case)

    def _apply_case(
        self,
        case: Dict[str, Any],
    ) -> None:
        self.test_case_var.set(
            str(case.get("test_case_id") or "")
        )
        self.student_email_var.set(
            str(case.get("student_email") or "")
        )
        self.subject_var.set(
            str(case.get("subject") or "")
        )
        if case.get("fresh_ids"):
            fresh_suffix = uuid.uuid4().hex[:8]

            self.thread_id_var.set(
                f"ui-demo-thread-{fresh_suffix}"
            )
            self.email_id_var.set(
                f"ui-demo-email-{fresh_suffix}"
            )
        else:
            self.thread_id_var.set(
                str(case.get("thread_id") or "")
            )
            self.email_id_var.set(
                str(case.get("email_id") or "")
            )
        self.language_var.set(
            str(case.get("language") or "en")
        )
        self.top_k_var.set(
            int(case.get("top_k") or 6)
        )

        self.email_text.delete(
            "1.0",
            tk.END,
        )
        self.email_text.insert(
            "1.0",
            str(case.get("email_text") or ""),
        )

        self.draft_text.delete(
            "1.0",
            tk.END,
        )
        self.details_text.delete(
            "1.0",
            tk.END,
        )

    def _check_api_async(self) -> None:
        self.status_var.set(
            "Checking..."
        )

        threading.Thread(
            target=self._check_api,
            daemon=True,
        ).start()

    def _check_api(self) -> None:
        try:
            response = requests.get(
                HEALTH_URL,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            message = (
                "Status: Online"
                f" | DB: {data.get('database')}"
                f" | Model: {data.get('generation_model')}"
            )

            self.root.after(
                0,
                self._set_status,
                True,
                message,
            )
        except Exception as exc:
            self.root.after(
                0,
                self._set_status,
                False,
                str(exc),
            )

    def _set_status(
        self,
        ok: bool,
        message: str,
    ) -> None:
        self.status_var.set(message)
        self.status_label.configure(
            foreground=(
                "green" if ok else "red"
            )
        )

    def _toggle_evaluation_tools(self) -> None:
        """Show or hide development-only evaluation controls."""
        if self.test_frame.winfo_manager():
            self.test_frame.pack_forget()
            if hasattr(self, "evaluation_toggle_button"):
                self.evaluation_toggle_button.configure(
                    text="Show evaluation tools",
                )
            return

        self.test_frame.pack(
            fill=tk.X,
            pady=(0, 8),
            before=self.main_pane,
        )
        if hasattr(self, "evaluation_toggle_button"):
            self.evaluation_toggle_button.configure(
                text="Hide evaluation tools",
            )

    def _refresh_mailbox_async(self) -> None:
        if self.processing:
            messagebox.showinfo(
                "HANS is busy",
                "Wait for the current draft request to finish.",
            )
            return

        try:
            headers = _request_headers()
        except Exception as exc:
            messagebox.showerror(
                "Mailbox configuration error",
                str(exc),
            )
            return

        self.mailbox_refresh_button.configure(
            state="disabled",
            text="Refreshing...",
        )
        self.mailbox_info_var.set(
            "Reading mailbox... No Qwen generation is running."
        )

        threading.Thread(
            target=self._refresh_mailbox,
            args=(headers,),
            daemon=True,
        ).start()

    def _refresh_mailbox(
        self,
        headers: Dict[str, str],
    ) -> None:
        try:
            status = fetch_mailbox_status(
                api_base=API_BASE,
                headers=headers,
                timeout=30,
            )

            if not status.get("enabled"):
                raise MailboxUIError(
                    "Mailbox integration is disabled in the backend. "
                    "Set HANS_MAILBOX_ENABLED=true in .env and restart "
                    "the backend."
                )

            messages = fetch_mailbox_messages(
                api_base=API_BASE,
                headers=headers,
                limit=20,
                unread_only=True,
                timeout=60,
            )

            self.root.after(
                0,
                self._apply_mailbox_capabilities,
                status,
            )
            self.root.after(
                0,
                self._display_mailbox_messages,
                messages,
            )
        except Exception as exc:
            self.root.after(
                0,
                self._display_mailbox_error,
                str(exc),
            )

    def _apply_mailbox_capabilities(
        self,
        status: Dict[str, Any],
    ) -> None:
        write_enabled = bool(
            status.get("write_enabled")
        )
        send_enabled = bool(
            status.get("send_enabled")
        )

        self.save_draft_button.configure(
            state=(
                "normal"
                if write_enabled
                else "disabled"
            )
        )
        self.send_button.configure(
            state=(
                "normal"
                if send_enabled
                else "disabled"
            )
        )

    def _display_mailbox_messages(
        self,
        messages: list[Dict[str, Any]],
    ) -> None:
        self.mailbox_messages = messages

        for item in self.mailbox_tree.get_children():
            self.mailbox_tree.delete(item)

        for index, message in enumerate(messages):
            self.mailbox_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    str(
                        message.get("student_email")
                        or ""
                    ),
                    str(
                        message.get("subject")
                        or ""
                    ),
                    str(
                        message.get("received_at")
                        or ""
                    ),
                    str(
                        message.get("attachment_count")
                        or 0
                    ),
                ),
            )

        self.mailbox_refresh_button.configure(
            state="normal",
            text="Refresh inbox",
        )
        self.mailbox_load_button.configure(
            state="disabled",
        )

        if messages:
            self.mailbox_info_var.set(
                f"{len(messages)} unread message(s) loaded. "
                "Select an email to inspect it."
            )
        else:
            self.mailbox_info_var.set(
                "No unread messages found."
            )

    def _display_mailbox_error(
        self,
        error: str,
    ) -> None:
        self.mailbox_refresh_button.configure(
            state="normal",
            text="Refresh inbox",
        )
        self.mailbox_load_button.configure(
            state="disabled",
        )
        self.mailbox_info_var.set(
            f"Mailbox unavailable: {error}"
        )

        messagebox.showwarning(
            "Mailbox unavailable",
            error,
        )

    def _on_mailbox_selection(
        self,
        _event=None,
    ) -> None:
        selection = self.mailbox_tree.selection()

        self.mailbox_load_button.configure(
            state=(
                "normal"
                if selection
                else "disabled"
            )
        )

        if not selection:
            return

        try:
            index = int(selection[0])
            message = self.mailbox_messages[index]
        except (ValueError, IndexError):
            return

        self.mailbox_info_var.set(
            "Selected: "
            f"{message.get('subject') or '(no subject)'}"
            " | "
            + attachment_summary(message)
        )

    def _load_selected_mailbox_email(self) -> None:
        selection = self.mailbox_tree.selection()

        if not selection:
            messagebox.showinfo(
                "No email selected",
                "Select an inbox message first.",
            )
            return

        try:
            index = int(selection[0])
            message = self.mailbox_messages[index]
        except (ValueError, IndexError):
            messagebox.showerror(
                "Mailbox selection error",
                "The selected inbox message is no longer available. "
                "Refresh the inbox and try again.",
            )
            return

        self.test_case_var.set(
            CUSTOM_CASE_ID
        )
        self.student_email_var.set(
            str(
                message.get("student_email")
                or ""
            )
        )
        self.subject_var.set(
            str(
                message.get("subject")
                or ""
            )
        )
        self.thread_id_var.set(
            str(
                message.get("thread_id")
                or ""
            )
        )
        self.email_id_var.set(
            str(
                message.get("email_id")
                or ""
            )
        )

        self.email_text.delete(
            "1.0",
            tk.END,
        )
        self.email_text.insert(
            "1.0",
            str(
                message.get("email_text")
                or ""
            ),
        )

        self.draft_text.delete(
            "1.0",
            tk.END,
        )
        self.details_text.delete(
            "1.0",
            tk.END,
        )

        attachments = (
            message.get("attachments")
            or []
        )

        details = [
            "MAILBOX MESSAGE",
            f"Received: {message.get('received_at') or 'n/a'}",
            f"Attachments: {attachment_summary(message)}",
            "",
            "Loading an email does not generate a HANS draft.",
            "Press 'Generate staff draft' when you want to process it.",
        ]

        if attachments:
            details.extend(
                [
                    "",
                    "ATTACHMENT METADATA",
                ]
            )

            for attachment in attachments:
                if not isinstance(
                    attachment,
                    dict,
                ):
                    continue

                details.append(
                    "- "
                    f"{attachment.get('filename') or 'attachment'}"
                    " | "
                    f"{attachment.get('content_type') or 'unknown type'}"
                    " | "
                    f"{attachment.get('size_bytes') or 'size unknown'} bytes"
                )

        self.details_text.insert(
            "1.0",
            "\n".join(details),
        )

        self.last_result = None
        self.footer_var.set(
            "Mailbox email loaded. "
            "No draft has been generated yet."
        )

    def _payload(self) -> Dict[str, Any]:
        email_text = self.email_text.get(
            "1.0",
            tk.END,
        ).strip()

        if not email_text:
            raise ValueError(
                "Incoming email text is required."
            )

        student_email = (
            self.student_email_var.get().strip()
            or None
        )
        subject = (
            self.subject_var.get().strip()
            or None
        )
        language = (
            self.language_var.get().strip()
            or "en"
        )
        top_k = int(self.top_k_var.get())

        thread_id = (
            self.thread_id_var.get().strip()
            or f"ui-thread-{uuid.uuid4().hex[:8]}"
        )

        email_id = (
            self.email_id_var.get().strip()
            or f"ui-email-{uuid.uuid4().hex[:8]}"
        )

        self.thread_id_var.set(thread_id)
        self.email_id_var.set(email_id)

        # If a preset was loaded and then edited, it is no longer that
        # evaluation case. Mark it as CUSTOM so logs cannot claim that the
        # official test case produced a result from modified input.
        selected_case_id = self.test_case_var.get().strip()
        selected_case = self.test_cases.get(selected_case_id)

        if selected_case is not None:
            preset_values = {
                "email_text": str(
                    selected_case.get("email_text") or ""
                ).strip(),
                "student_email": (
                    str(
                        selected_case.get("student_email") or ""
                    ).strip()
                    or None
                ),
                "subject": (
                    str(
                        selected_case.get("subject") or ""
                    ).strip()
                    or None
                ),
                "thread_id": str(
                    selected_case.get("thread_id") or ""
                ).strip(),
                "email_id": str(
                    selected_case.get("email_id") or ""
                ).strip(),
                "language": str(
                    selected_case.get("language") or "en"
                ).strip(),
                "top_k": int(
                    selected_case.get("top_k") or 6
                ),
            }

            current_values = {
                "email_text": email_text,
                "student_email": student_email,
                "subject": subject,
                "thread_id": thread_id,
                "email_id": email_id,
                "language": language,
                "top_k": top_k,
            }

            if current_values != preset_values:
                self.test_case_var.set(CUSTOM_CASE_ID)

        return {
            "email_text": email_text,
            "student_email": student_email,
            "subject": subject,
            "thread_id": thread_id,
            "email_id": email_id,
            "language": language,
            "top_k": top_k,
        }

    def _generate_async(self) -> None:
        if self.processing:
            return

        try:
            payload = self._payload()
            _request_headers()
        except Exception as exc:
            messagebox.showerror(
                "Configuration or input error",
                str(exc),
            )
            return

        self.processing = True
        self.generate_button.configure(
            state="disabled",
            text="Processing...",
        )
        self.progress.start()
        self.footer_var.set(
            "Waiting for the HANS backend..."
        )

        threading.Thread(
            target=self._generate,
            args=(payload,),
            daemon=True,
        ).start()

    def _generate(
        self,
        payload: Dict[str, Any],
    ) -> None:
        test_case_id = (
            self.test_case_var.get().strip()
            or payload["thread_id"]
        )

        started = time.perf_counter()

        try:
            response = requests.post(
                EMAIL_URL,
                json=payload,
                headers=_request_headers(),
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
                    test_case_id=test_case_id,
                    request_payload=payload,
                    response_payload=result,
                )

            self.root.after(
                0,
                self._display_result,
                result,
                saved_path,
            )
        except Exception as exc:
            saved_path = None

            if save_ui_evaluation_run is not None:
                saved_path = save_ui_evaluation_run(
                    test_case_id=test_case_id,
                    request_payload=payload,
                    response_payload=None,
                    error=str(exc),
                )

            self.root.after(
                0,
                self._display_error,
                str(exc),
                saved_path,
            )
        finally:
            self.root.after(
                0,
                self._finish_processing,
            )

    def _display_result(
        self,
        result: Dict[str, Any],
        saved_path: Path | None,
    ) -> None:
        self.last_result = result

        draft = str(
            result.get("staff_draft") or ""
        )

        self.draft_text.delete(
            "1.0",
            tk.END,
        )
        self._insert_clickable_text(
            self.draft_text,
            draft,
        )

        summary = {
            "is_followup": result.get("is_followup"),
            "followup_type": result.get("followup_type"),
            "flagged_for_human": result.get(
                "flagged_for_human"
            ),
            "automatic_send": result.get(
                "automatic_send"
            ),
            "email_context": result.get(
                "email_context"
            ),
            "detected_topics": result.get(
                "detected_topics"
            ),
            "validation": result.get(
                "validation"
            ),
            "quality": result.get("quality"),
            "sources": result.get("sources"),
            "observability": result.get("observability"),
            "timing": result.get("timing"),
            "ui_client": result.get("_ui_client"),
        }

        self.details_text.delete(
            "1.0",
            tk.END,
        )

        # Staff-facing summary: keep the most important review signals visible
        # without requiring staff to search through the raw JSON.
        email_context = result.get("email_context") or {}
        validation = result.get("validation") or {}
        quality = result.get("quality") or {}
        topics = result.get("detected_topics") or []
        sources = result.get("sources") or []
        observability = result.get("observability") or {}
        generation = observability.get("generation") or {}

        programme = (
            email_context.get("matched_programme")
            or email_context.get("target_program")
            or email_context.get("target_programme")
            or "n/a"
        )

        topic_labels = [
            str(topic.get("label") or topic.get("topic_id"))
            for topic in topics
            if isinstance(topic, dict)
            and (topic.get("label") or topic.get("topic_id"))
        ]

        def yes_no(value: Any) -> str:
            if value is True:
                return "Yes"
            if value is False:
                return "No"
            return "n/a"

        def display_value(value: Any) -> str:
            if value is None:
                return "n/a"
            return str(value)

        generation_seconds = generation.get(
            "generation_total_seconds"
        )

        if isinstance(generation_seconds, (int, float)):
            generation_time_text = (
                f"{generation_seconds:.3f} s"
            )
        elif generation_seconds is None:
            generation_time_text = "n/a"
        else:
            generation_time_text = str(
                generation_seconds
            )

        self.details_text.tag_configure(
            "section",
            font=("Segoe UI", 10, "bold"),
        )
        self.details_text.tag_configure(
            "label",
            font=("Segoe UI", 9, "bold"),
        )
        self.details_text.tag_configure(
            "ok",
            foreground="darkgreen",
            font=("Segoe UI", 9, "bold"),
        )
        self.details_text.tag_configure(
            "warn",
            foreground="darkorange",
            font=("Segoe UI", 9, "bold"),
        )
        self.details_text.tag_configure(
            "technical",
            font=("Consolas", 8),
        )
        self.details_text.tag_configure(
            "link",
            foreground="blue",
            underline=True,
        )

        self.details_text.insert(
            tk.END,
            "STAFF REVIEW SUMMARY\n",
            "section",
        )

        def add_summary_line(
            label: str,
            value: Any,
            value_tag: str | None = None,
        ) -> None:
            self.details_text.insert(
                tk.END,
                f"{label}: ",
                "label",
            )
            self.details_text.insert(
                tk.END,
                f"{display_value(value)}\n",
                value_tag or (),
            )

        add_summary_line("Programme", programme)
        add_summary_line(
            "Topics detected",
            ", ".join(topic_labels) if topic_labels else "n/a",
        )
        add_summary_line(
            "Grounded",
            yes_no(validation.get("is_grounded")),
            "ok" if validation.get("is_grounded") is True else "warn",
        )
        add_summary_line(
            "Citations valid",
            yes_no(validation.get("citations_valid")),
            "ok" if validation.get("citations_valid") is True else "warn",
        )
        add_summary_line(
            "Hallucinations detected",
            yes_no(validation.get("has_hallucinations")),
            "ok" if validation.get("has_hallucinations") is False else "warn",
        )

        review_required = quality.get("review_required")
        add_summary_line(
            "Review required",
            yes_no(review_required),
            "warn" if review_required is True else "ok",
        )
        add_summary_line(
            "Review reason",
            quality.get("review_reason") or "n/a",
            "warn" if review_required is True else None,
        )
        add_summary_line(
            "Automatic sending",
            "Disabled" if result.get("automatic_send") is False else display_value(
                result.get("automatic_send")
            ),
            "ok" if result.get("automatic_send") is False else "warn",
        )
        add_summary_line("Sources used", len(sources))
        add_summary_line(
            "Model",
            generation.get("model"),
        )
        add_summary_line(
            "Generation time",
            generation_time_text,
        )

        self.details_text.insert(
            tk.END,
            "\nOFFICIAL SOURCES\n",
            "section",
        )

        seen_urls = set()
        source_index = 0
        for source in sources:
            if not isinstance(source, dict):
                continue
            url = str(source.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            source_index += 1
            title = str(source.get("title") or f"Source {source_index}")

            self.details_text.insert(
                tk.END,
                f"{source_index}. {title}\n",
                "label",
            )
            tag_name = f"source_link_{source_index}"
            self.details_text.insert(
                tk.END,
                f"   {url}\n",
                (tag_name, "link"),
            )
            self.details_text.tag_bind(
                tag_name,
                "<Button-1>",
                lambda _event, target=url: webbrowser.open_new_tab(target),
            )
            self.details_text.tag_bind(
                tag_name,
                "<Enter>",
                lambda _event: self.details_text.configure(cursor="hand2"),
            )
            self.details_text.tag_bind(
                tag_name,
                "<Leave>",
                lambda _event: self.details_text.configure(cursor=""),
            )

        if source_index == 0:
            self.details_text.insert(
                tk.END,
                "No source links returned.\n",
            )

        self.details_text.insert(
            tk.END,
            "\nGENERATION OBSERVABILITY\n",
            "section",
        )
        add_summary_line(
            "Provider",
            generation.get("provider"),
        )
        add_summary_line(
            "Prompt tokens",
            generation.get("prompt_tokens"),
        )
        add_summary_line(
            "Completion tokens",
            generation.get("completion_tokens"),
        )
        add_summary_line(
            "Total tokens",
            generation.get("total_tokens"),
        )

        self.details_text.insert(
            tk.END,
            "\nTECHNICAL DETAILS (raw JSON)\n",
            "section",
        )
        self.details_text.insert(
            tk.END,
            json.dumps(
                summary,
                ensure_ascii=False,
                indent=2,
            ),
            "technical",
        )

        if saved_path is not None:
            self.footer_var.set(
                "Evaluation result saved to: "
                f"{saved_path}"
            )
        else:
            self.footer_var.set(
                "Response received. "
                "Evaluation logging is disabled."
            )

    @staticmethod
    def _insert_clickable_text(
        widget: tk.Text,
        text: str,
    ) -> None:
        """Insert text and make http/https URLs open in the default browser."""
        widget.delete("1.0", tk.END)
        widget.tag_configure(
            "url_link",
            foreground="blue",
            underline=True,
        )

        last_end = 0
        link_index = 0

        for match in re.finditer(
            r"https?://[^\s<>\"']+",
            text,
        ):
            start, end = match.span()
            url = match.group(0).rstrip(".,;:)")

            widget.insert(
                tk.END,
                text[last_end:start],
            )

            tag_name = f"url_link_{link_index}"
            widget.insert(
                tk.END,
                url,
                (tag_name, "url_link"),
            )
            widget.tag_bind(
                tag_name,
                "<Button-1>",
                lambda _event, target=url: webbrowser.open_new_tab(target),
            )
            widget.tag_bind(
                tag_name,
                "<Enter>",
                lambda _event, target_widget=widget: target_widget.configure(
                    cursor="hand2"
                ),
            )
            widget.tag_bind(
                tag_name,
                "<Leave>",
                lambda _event, target_widget=widget: target_widget.configure(
                    cursor=""
                ),
            )

            # Preserve any punctuation stripped from the clickable URL.
            widget.insert(
                tk.END,
                match.group(0)[len(url):],
            )

            last_end = end
            link_index += 1

        widget.insert(
            tk.END,
            text[last_end:],
        )

    def _display_error(
        self,
        error: str,
        saved_path: Path | None,
    ) -> None:
        message = (
            f"Backend request failed:\n{error}"
        )

        if saved_path is not None:
            message += (
                "\n\nError record saved to:\n"
                f"{saved_path}"
            )

        messagebox.showerror(
            "HANS request failed",
            message,
        )

        self.footer_var.set(
            "The request failed. "
            "Check the backend terminal."
        )

    def _finish_processing(self) -> None:
        self.processing = False
        self.progress.stop()
        self.generate_button.configure(
            state="normal",
            text="Generate staff draft",
        )

    def _mailbox_write_payload(self) -> Dict[str, Any]:
        recipient = self.student_email_var.get().strip()
        subject = self.subject_var.get().strip()
        body = self.draft_text.get(
            "1.0",
            tk.END,
        ).strip()
        in_reply_to = self.email_id_var.get().strip() or None

        if not recipient:
            raise ValueError(
                "Student email address is required."
            )
        if not body:
            raise ValueError(
                "There is no staff draft to save or send."
            )

        return {
            "to_email": recipient,
            "subject": subject,
            "body": body,
            "in_reply_to": in_reply_to,
        }

    def _save_mailbox_draft_async(self) -> None:
        try:
            payload = self._mailbox_write_payload()
            headers = _request_headers()
        except Exception as exc:
            messagebox.showerror(
                "Cannot save draft",
                str(exc),
            )
            return

        self.save_draft_button.configure(
            state="disabled",
            text="Saving...",
        )
        self.footer_var.set(
            "Saving staff-edited reply to mailbox Drafts..."
        )

        threading.Thread(
            target=self._save_mailbox_draft,
            args=(headers, payload),
            daemon=True,
        ).start()

    def _save_mailbox_draft(
        self,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> None:
        try:
            result = save_mailbox_draft(
                api_base=API_BASE,
                headers=headers,
                **payload,
            )
            self.root.after(
                0,
                self._mailbox_write_success,
                "Draft saved",
                (
                    "The edited response was saved to the configured "
                    "mailbox Drafts folder."
                ),
                result,
            )
        except Exception as exc:
            self.root.after(
                0,
                self._mailbox_write_error,
                "Draft save failed",
                str(exc),
            )
        finally:
            self.root.after(
                0,
                self.save_draft_button.configure,
                {
                    "state": "normal",
                    "text": "Save to mailbox drafts",
                },
            )

    def _confirm_and_send_mailbox_message(self) -> None:
        try:
            payload = self._mailbox_write_payload()
            headers = _request_headers()
        except Exception as exc:
            messagebox.showerror(
                "Cannot send email",
                str(exc),
            )
            return

        preview = payload["body"]
        if len(preview) > 700:
            preview = preview[:700] + "\n..."

        confirmed = messagebox.askyesno(
            "Confirm email send",
            (
                "This will send an email from the configured mailbox.\n\n"
                f"To: {payload['to_email']}\n"
                f"Subject: {payload['subject'] or '(no subject)'}\n\n"
                f"{preview}\n\n"
                "Send this email now?"
            ),
            icon="warning",
        )

        if not confirmed:
            return

        self.send_button.configure(
            state="disabled",
            text="Sending...",
        )
        self.footer_var.set(
            "Sending staff-approved email..."
        )

        threading.Thread(
            target=self._send_mailbox_message,
            args=(headers, payload),
            daemon=True,
        ).start()

    def _send_mailbox_message(
        self,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> None:
        try:
            result = send_mailbox_message(
                api_base=API_BASE,
                headers=headers,
                **payload,
            )
            self.root.after(
                0,
                self._mailbox_write_success,
                "Email sent",
                "The staff-approved email was sent successfully.",
                result,
            )
        except Exception as exc:
            self.root.after(
                0,
                self._mailbox_write_error,
                "Email send failed",
                str(exc),
            )
        finally:
            self.root.after(
                0,
                self.send_button.configure,
                {
                    "state": "normal",
                    "text": "Send email",
                },
            )

    def _mailbox_write_success(
        self,
        title: str,
        message: str,
        result: Dict[str, Any],
    ) -> None:
        message_id = str(
            result.get("message_id") or ""
        ).strip()

        detail = message
        if message_id:
            detail += f"\n\nMessage ID: {message_id}"

        messagebox.showinfo(
            title,
            detail,
        )
        self.footer_var.set(message)

    def _mailbox_write_error(
        self,
        title: str,
        error: str,
    ) -> None:
        messagebox.showerror(
            title,
            error,
        )
        self.footer_var.set(error)

    def _open_full_draft(self) -> None:
        """Open the current staff draft in a larger scrollable window."""
        draft = self.draft_text.get(
            "1.0",
            tk.END,
        ).strip()

        if not draft:
            messagebox.showinfo(
                "No draft available",
                "Generate a staff draft first.",
            )
            return

        popup = tk.Toplevel(self.root)
        popup.title("HANS - Full Staff Draft")
        popup.geometry("1000x780")
        popup.minsize(700, 500)

        container = ttk.Frame(
            popup,
            padding=12,
        )
        container.pack(
            fill=tk.BOTH,
            expand=True,
        )

        ttk.Label(
            container,
            text="Full staff draft",
            font=("Segoe UI", 13, "bold"),
        ).pack(
            anchor=tk.W,
            pady=(0, 8),
        )

        full_draft_text = scrolledtext.ScrolledText(
            container,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
        )
        full_draft_text.pack(
            fill=tk.BOTH,
            expand=True,
        )
        self._insert_clickable_text(
            full_draft_text,
            draft,
        )

        button_row = ttk.Frame(container)
        button_row.pack(
            fill=tk.X,
            pady=(8, 0),
        )

        def copy_full_draft() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(draft)

        ttk.Button(
            button_row,
            text="Copy draft",
            command=copy_full_draft,
        ).pack(side=tk.LEFT)

        ttk.Button(
            button_row,
            text="Close",
            command=popup.destroy,
        ).pack(
            side=tk.RIGHT,
        )

    def _clear(self) -> None:
        # Clear the entire request, not only the message body. Leaving the
        # old subject/test-case metadata behind can create a false mixed case.
        self._load_custom_case()
        self.last_result = None
        self.footer_var.set(
            "Draft-only workflow: "
            "automatic sending is disabled."
        )

    def _copy_draft(self) -> None:
        draft = self.draft_text.get(
            "1.0",
            tk.END,
        ).strip()

        if not draft:
            messagebox.showinfo(
                "Nothing to copy",
                "No staff draft is available.",
            )
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(draft)

        self.footer_var.set(
            "Staff draft copied to clipboard."
        )


def main() -> None:
    root = tk.Tk()
    EnhancedHANSEmailUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
