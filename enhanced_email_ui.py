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
        self.root.geometry("1180x850")
        self.root.minsize(1000, 720)

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
                "(HTW Qwen / Draft Only)"
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
            values=list(self.test_cases.keys()),
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
            from_=1,
            to=20,
            textvariable=self.top_k_var,
            width=8,
        ).grid(
            row=2,
            column=3,
            sticky=tk.W,
            pady=(8, 0),
        )

        email_frame = ttk.LabelFrame(
            main,
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
            height=11,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
        )
        self.email_text.pack(
            fill=tk.BOTH,
            expand=True,
        )

        button_row = ttk.Frame(main)
        button_row.pack(
            fill=tk.X,
            pady=(0, 8),
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

        output_pane = ttk.Panedwindow(
            main,
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
            weight=3,
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
        if self.test_cases:
            first_id = next(
                iter(self.test_cases)
            )
            self.test_case_var.set(first_id)
            self._apply_case(
                self.test_cases[first_id]
            )
        else:
            self.test_case_var.set(
                "UI-MANUAL-TEST"
            )
            self.thread_id_var.set(
                f"ui-thread-{uuid.uuid4().hex[:8]}"
            )
            self.email_id_var.set(
                f"ui-email-{uuid.uuid4().hex[:8]}"
            )

    def _load_selected_case(self) -> None:
        case_id = (
            self.test_case_var.get().strip()
        )

        case = self.test_cases.get(
            case_id
        )

        if case is None:
            messagebox.showwarning(
                "Unknown test case",
                (
                    "The entered test case ID was not found "
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
                f" | database={data.get('database_ok')}"
                f" | automatic_send="
                f"{data.get('automatic_send')}"
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

        return {
            "email_text": email_text,
            "student_email": (
                self.student_email_var.get().strip()
                or None
            ),
            "subject": (
                self.subject_var.get().strip()
                or None
            ),
            "thread_id": thread_id,
            "email_id": email_id,
            "language": (
                self.language_var.get().strip()
                or "en"
            ),
            "top_k": int(
                self.top_k_var.get()
            ),
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
            "Waiting for the HANS backend and HTW Qwen..."
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

    def _clear(self) -> None:
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
