from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import requests
import tkinter as tk
from dotenv import load_dotenv
from tkinter import messagebox, scrolledtext, ttk


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
            "HANS Enhanced Email Assistant"
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

        title = ttk.Label(
            main,
            text=(
                "HANS Enhanced Email Assistant "
                "(Draft Only)"
            ),
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(
            anchor=tk.W,
            pady=(0, 8),
        )

        status_row = ttk.Frame(main)
        status_row.pack(
            fill=tk.X,
            pady=(0, 8),
        )

        ttk.Label(
            status_row,
            text="API status:",
        ).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(
            value="Checking..."
        )

        self.status_label = ttk.Label(
            status_row,
            textvariable=self.status_var,
        )
        self.status_label.pack(
            side=tk.LEFT,
            padx=(8, 16),
        )

        ttk.Button(
            status_row,
            text="Test API",
            command=self._check_api_async,
        ).pack(side=tk.LEFT)

        ttk.Label(
            status_row,
            text=f"Backend: {API_BASE}",
        ).pack(
            side=tk.RIGHT,
        )

        test_frame = ttk.LabelFrame(
            main,
            text="Evaluation test case",
            padding=8,
        )
        test_frame.pack(
            fill=tk.X,
            pady=(0, 8),
        )

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
            main,
            text="Incoming email metadata",
            padding=8,
        )
        metadata_frame.pack(
            fill=tk.X,
            pady=(0, 8),
        )

        for column in range(4):
            metadata_frame.columnconfigure(
                column,
                weight=1,
            )

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

        self._add_entry(
            metadata_frame,
            row=1,
            label="Thread ID",
            variable=self.thread_id_var,
            label_column=0,
            entry_column=1,
        )

        self._add_entry(
            metadata_frame,
            row=1,
            label="Email ID",
            variable=self.email_id_var,
            label_column=2,
            entry_column=3,
        )

        ttk.Label(
            metadata_frame,
            text="Language",
        ).grid(
            row=2,
            column=0,
            sticky=tk.W,
            pady=(8, 0),
        )

        ttk.Combobox(
            metadata_frame,
            textvariable=self.language_var,
            values=("en", "de"),
            state="readonly",
            width=8,
        ).grid(
            row=2,
            column=1,
            sticky=tk.W,
            pady=(8, 0),
        )

        ttk.Label(
            metadata_frame,
            text="Top K",
        ).grid(
            row=2,
            column=2,
            sticky=tk.W,
            pady=(8, 0),
        )

        ttk.Spinbox(
            metadata_frame,
            from_=3,
            to=10,
            textvariable=self.top_k_var,
            width=8,
        ).grid(
            row=2,
            column=3,
            sticky=tk.W,
            pady=(8, 0),
        )

        # -----------------------------------------------------------------
        # Main resizable work area
        #
        # The upper pane contains the incoming email and action buttons.
        # The lower pane contains the generated draft and technical details.
        # Drag the horizontal divider to give more space to either section.
        # -----------------------------------------------------------------
        work_pane = ttk.Panedwindow(
            main,
            orient=tk.VERTICAL,
        )
        work_pane.pack(
            fill=tk.BOTH,
            expand=True,
            pady=(0, 8),
        )

        input_section = ttk.Frame(work_pane)
        result_section = ttk.Frame(work_pane)

        work_pane.add(
            input_section,
            weight=2,
        )
        work_pane.add(
            result_section,
            weight=3,
        )

        email_frame = ttk.LabelFrame(
            input_section,
            text="Incoming student email",
            padding=8,
        )
        email_frame.pack(
            fill=tk.BOTH,
            expand=True,
            pady=(0, 8),
        )

        self.email_text = scrolledtext.ScrolledText(
            email_frame,
            height=8,
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
        )

        details_frame = ttk.LabelFrame(
            output_pane,
            text="Validation, quality and sources",
            padding=8,
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
            height=18,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
        )
        self.draft_text.pack(
            fill=tk.BOTH,
            expand=True,
        )

        self.details_text = scrolledtext.ScrolledText(
            details_frame,
            height=18,
            wrap=tk.WORD,
            font=("Consolas", 9),
        )
        self.details_text.pack(
            fill=tk.BOTH,
            expand=True,
        )

        self.footer_var = tk.StringVar(
            value=(
                "Draft-only workflow: "
                "automatic sending is disabled."
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
                "Online"
                f" | database={data.get('database')}"
                f" | provider={data.get('generation_provider')}"
                f" | model={data.get('generation_model')}"
                f" | automatic_send={data.get('automatic_send')}"
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
        self.draft_text.insert(
            "1.0",
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
            "timing": result.get("timing"),
            "ui_client": result.get("_ui_client"),
        }

        self.details_text.delete(
            "1.0",
            tk.END,
        )
        self.details_text.insert(
            "1.0",
            json.dumps(
                summary,
                ensure_ascii=False,
                indent=2,
            ),
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
        full_draft_text.insert(
            "1.0",
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
