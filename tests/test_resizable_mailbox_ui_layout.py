from pathlib import Path


def _patcher_text() -> str:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "apply_resizable_mailbox_ui_layout.py"
    )
    return path.read_text(
        encoding="utf-8",
    )


def test_resizable_layout_patcher_has_required_safety_markers() -> None:
    text = _patcher_text()

    assert "pre_resizable_layout_backup" in text
    assert "HANS_RESIZABLE_LAYOUT_V1" in text
    assert "HANS_MAILBOX_UI_INTEGRATION_V1" in text


def test_resizable_layout_patcher_preserves_evaluation_tools() -> None:
    text = _patcher_text()

    assert "Show evaluation tools" in text
    assert "Hide evaluation tools" in text
    assert "_toggle_evaluation_tools" in text


def test_resizable_layout_patcher_uses_main_vertical_pane() -> None:
    text = _patcher_text()

    assert "self.main_pane = ttk.Panedwindow" in text
    assert "orient=tk.VERTICAL" in text
    assert "self.main_pane.add" in text
