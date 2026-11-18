from enhanced_email_ui import EnhancedHANSEmailUI


def test_supported_attachments_allow_common_staff_documents() -> None:
    message = {
        "attachments": [
            {"filename": "transcript.pdf"},
            {"filename": "photo.JPG"},
            {"filename": "results.xlsx"},
            {"filename": "notes.txt"},
        ]
    }

    supported = EnhancedHANSEmailUI._supported_attachments(
        message
    )

    assert [item[0] for item in supported] == [0, 1, 2, 3]


def test_supported_attachments_block_executable_and_macro_files() -> None:
    message = {
        "attachments": [
            {"filename": "installer.exe"},
            {"filename": "script.ps1"},
            {"filename": "macro.docm"},
            {"filename": "safe.pdf"},
        ]
    }

    supported = EnhancedHANSEmailUI._supported_attachments(
        message
    )

    assert len(supported) == 1
    assert supported[0][0] == 3
    assert supported[0][1]["filename"] == "safe.pdf"
