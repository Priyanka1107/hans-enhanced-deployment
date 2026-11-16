from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
UI_PATH = ROOT / "enhanced_email_ui.py"
BACKUP_PATH = ROOT / "enhanced_email_ui.py.pre_mailbox_backup"

PATCH_MARKER = "# HANS_MAILBOX_UI_INTEGRATION_V1"


def _replace_once(
    text: str,
    old: str,
    new: str,
    *,
    label: str,
) -> str:
    count = text.count(old)

    if count != 1:
        raise RuntimeError(
            f"Could not safely patch {label}: "
            f"expected one insertion point, found {count}."
        )

    return text.replace(
        old,
        new,
        1,
    )


def main() -> None:
    if not UI_PATH.exists():
        raise RuntimeError(
            f"UI file not found: {UI_PATH}"
        )

    original = UI_PATH.read_text(
        encoding="utf-8",
    )

    if PATCH_MARKER in original:
        print(
            "Mailbox UI integration is already present. "
            "No changes made."
        )
        return

    if not BACKUP_PATH.exists():
        shutil.copy2(
            UI_PATH,
            BACKUP_PATH,
        )
        print(
            f"Backup created: {BACKUP_PATH.name}"
        )

    patched = original

    patched = _replace_once(
        patched,
        "from tkinter import messagebox, scrolledtext, ttk\n",
        (
            "from tkinter import messagebox, scrolledtext, ttk\n\n"
            "from app.ui.mailbox_client import (\n"
            "    MailboxUIError,\n"
            "    attachment_summary,\n"
            "    fetch_mailbox_messages,\n"
            "    fetch_mailbox_status,\n"
            ")\n"
            f"{PATCH_MARKER}\n"
        ),
        label="mailbox UI imports",
    )

    patched = _replace_once(
        patched,
        "        self.test_cases = _load_test_cases()\n\n"
        "        self._build_ui()\n",
        (
            "        self.test_cases = _load_test_cases()\n"
            "        self.mailbox_messages: list[Dict[str, Any]] = []\n\n"
            "        self._build_ui()\n"
        ),
        label="mailbox state",
    )

    mailbox_frame = '''        mailbox_frame = ttk.LabelFrame(
            main,
            text="Incoming mailbox (read-only)",
            padding=8,
        )
        mailbox_frame.pack(
            fill=tk.X,
            pady=(0, 8),
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
            anchor=tk.W,
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

'''

    patched = _replace_once(
        patched,
        "        test_frame = ttk.LabelFrame(\n"
        "            main,\n"
        "            text=\"Evaluation test case\",\n",
        (
            mailbox_frame
            + "        test_frame = ttk.LabelFrame(\n"
            "            main,\n"
            "            text=\"Evaluation test case\",\n"
        ),
        label="mailbox panel",
    )

    mailbox_methods = '''    def _refresh_mailbox_async(self) -> None:
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
                self._display_mailbox_messages,
                messages,
            )
        except Exception as exc:
            self.root.after(
                0,
                self._display_mailbox_error,
                str(exc),
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

'''

    patched = _replace_once(
        patched,
        "    def _payload(self) -> Dict[str, Any]:\n",
        (
            mailbox_methods
            + "    def _payload(self) -> Dict[str, Any]:\n"
        ),
        label="mailbox methods",
    )

    UI_PATH.write_text(
        patched,
        encoding="utf-8",
        newline="\n",
    )

    print(
        "Mailbox UI integration applied successfully."
    )
    print(
        f"Backup: {BACKUP_PATH.name}"
    )
    print(
        "Next: run Python compile/tests before starting the UI."
    )


if __name__ == "__main__":
    main()
