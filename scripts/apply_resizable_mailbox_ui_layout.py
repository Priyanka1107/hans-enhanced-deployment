from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
UI_PATH = ROOT / "enhanced_email_ui.py"
BACKUP_PATH = ROOT / "enhanced_email_ui.py.pre_resizable_layout_backup"

PATCH_MARKER = "# HANS_RESIZABLE_LAYOUT_V1"


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

    return text.replace(old, new, 1)


def main() -> None:
    if not UI_PATH.exists():
        raise RuntimeError(
            f"UI file not found: {UI_PATH}"
        )

    original = UI_PATH.read_text(
        encoding="utf-8",
    )

    if "# HANS_MAILBOX_UI_INTEGRATION_V1" not in original:
        raise RuntimeError(
            "Mailbox UI integration is not present. "
            "Apply the mailbox UI patch first."
        )

    if PATCH_MARKER in original:
        print(
            "Resizable layout integration is already present. "
            "No changes made."
        )
        return

    if not BACKUP_PATH.exists():
        shutil.copy2(
            UI_PATH,
            BACKUP_PATH,
        )
        print(
            f"Layout backup created: {BACKUP_PATH.name}"
        )

    patched = original

    old_status_button = '''        ttk.Button(
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
'''

    new_status_button = '''        ttk.Button(
            status_row,
            text="Test API",
            command=self._check_api_async,
        ).pack(side=tk.LEFT)

        self.evaluation_toggle_button = ttk.Button(
            status_row,
            text="Show evaluation tools",
            command=self._toggle_evaluation_tools,
        )
        self.evaluation_toggle_button.pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        ttk.Label(
            status_row,
            text=f"Backend: {API_BASE}",
        ).pack(
            side=tk.RIGHT,
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
'''

    patched = _replace_once(
        patched,
        old_status_button,
        new_status_button,
        label="main resizable workspace",
    )

    patched = _replace_once(
        patched,
        '''        mailbox_frame = ttk.LabelFrame(
            main,
            text="Incoming mailbox (read-only)",
            padding=8,
        )
        mailbox_frame.pack(
            fill=tk.X,
            pady=(0, 8),
        )
''',
        '''        mailbox_frame = ttk.LabelFrame(
            self.main_pane,
            text="Incoming mailbox (read-only)",
            padding=8,
        )
        self.main_pane.add(
            mailbox_frame,
            weight=2,
        )
''',
        label="mailbox pane",
    )

    patched = _replace_once(
        patched,
        '''        test_frame = ttk.LabelFrame(
            main,
            text="Evaluation test case",
            padding=8,
        )
        test_frame.pack(
            fill=tk.X,
            pady=(0, 8),
        )
''',
        '''        self.test_frame = ttk.LabelFrame(
            main,
            text="Evaluation test case",
            padding=8,
        )
        test_frame = self.test_frame
''',
        label="hidden evaluation tools",
    )

    patched = _replace_once(
        patched,
        '''        metadata_frame = ttk.LabelFrame(
            main,
            text="Incoming email metadata",
            padding=8,
        )
        metadata_frame.pack(
            fill=tk.X,
            pady=(0, 8),
        )
''',
        '''        metadata_frame = ttk.LabelFrame(
            self.main_pane,
            text="Incoming email metadata",
            padding=8,
        )
        self.main_pane.add(
            metadata_frame,
            weight=1,
        )
''',
        label="metadata pane",
    )

    old_work_pane = '''        # -----------------------------------------------------------------
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
'''

    new_work_pane = '''        # -----------------------------------------------------------------
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
'''

    patched = _replace_once(
        patched,
        old_work_pane,
        new_work_pane,
        label="incoming email and result panes",
    )

    patched = patched.replace(
        '''            height=8,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
''',
        '''            height=5,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
''',
        1,
    )

    patched = patched.replace(
        '''            height=18,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
''',
        '''            height=8,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
''',
        1,
    )

    patched = patched.replace(
        '''            height=18,
            wrap=tk.WORD,
            font=("Consolas", 9),
''',
        '''            height=8,
            wrap=tk.WORD,
            font=("Consolas", 9),
''',
        1,
    )

    toggle_method = '''    def _toggle_evaluation_tools(self) -> None:
        """Show or hide development-only evaluation controls."""
        if self.test_frame.winfo_manager():
            self.test_frame.pack_forget()
            self.evaluation_toggle_button.configure(
                text="Show evaluation tools",
            )
            return

        self.test_frame.pack(
            fill=tk.X,
            pady=(0, 8),
            before=self.main_pane,
        )
        self.evaluation_toggle_button.configure(
            text="Hide evaluation tools",
        )

'''

    patched = _replace_once(
        patched,
        '    def _refresh_mailbox_async(self) -> None:\n',
        (
            toggle_method
            + '    def _refresh_mailbox_async(self) -> None:\n'
        ),
        label="evaluation toggle method",
    )

    UI_PATH.write_text(
        patched,
        encoding="utf-8",
        newline="\n",
    )

    print(
        "Resizable mailbox UI layout applied successfully."
    )
    print(
        f"Layout backup: {BACKUP_PATH.name}"
    )
    print(
        "Evaluation tools are hidden by default and remain available "
        "from the top status row."
    )
    print(
        "Main sections are now separated by draggable vertical dividers."
    )


if __name__ == "__main__":
    main()
