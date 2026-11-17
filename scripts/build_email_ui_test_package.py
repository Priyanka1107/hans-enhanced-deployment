from __future__ import annotations

from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "dist"
PACKAGE_NAME = "HANS_email_ui_test_package"

INCLUDE_PATHS = (
    ".env.example",
    "config.yaml",
    "requirements.txt",
    "enhanced_api_server.py",
    "enhanced_email_ui.py",
    "app",
    "hansdb",
    "config",
    "evaluation/ui_eval_logger.py",
    "evaluation/ui_test_cases.json",
    "tests/test_generation_provider.py",
    "tests/test_scope_router.py",
    "tests/test_review_flags.py",
    "tests/test_credit_recognition_topic.py",
    "tests/test_mailbox_integration.py",
    "tests/test_mailbox_ui_client.py",
    "docs/mailbox_integration.md",
    "docs/checkpoints/2026-11-16-pre-email-ui-integration.md",
    "docs/checkpoints/2026-11-17-email-ui-working.md",
    "docs/TEST_PACKAGE_AND_MAILBOX_ROADMAP.md",
)

EXCLUDED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    ".venv",
    "venv",
    "runtime_data",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
}

SECRET_FILENAMES = {
    ".env",
}


def _should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)

    if any(part in EXCLUDED_NAMES for part in relative.parts):
        return False

    if path.name in SECRET_FILENAMES:
        return False

    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False

    return True


def _copy_path(source: Path, destination_root: Path) -> None:
    if source.is_file():
        if _should_include(source):
            target = destination_root / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return

    if not source.is_dir():
        raise FileNotFoundError(f"Required package path is missing: {source}")

    for item in source.rglob("*"):
        if not item.is_file() or not _should_include(item):
            continue

        target = destination_root / item.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def build_package() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    staging_dir = OUTPUT_DIR / PACKAGE_NAME
    archive_path = OUTPUT_DIR / f"{PACKAGE_NAME}.zip"

    if staging_dir.exists():
        shutil.rmtree(staging_dir)

    if archive_path.exists():
        archive_path.unlink()

    staging_dir.mkdir(parents=True)

    for relative_path in INCLUDE_PATHS:
        _copy_path(
            ROOT / relative_path,
            staging_dir,
        )

    readme = staging_dir / "TEST_PACKAGE_README.txt"
    readme.write_text(
        "HANS email UI test package\n"
        "==========================\n\n"
        "1. Create a Python virtual environment.\n"
        "2. Install requirements.txt.\n"
        "3. Copy .env.example to .env.\n"
        "4. Fill required secrets/configuration locally.\n"
        "5. Configure PostgreSQL/pgvector and the HANS database.\n"
        "6. Start enhanced_api_server.py.\n"
        "7. Start enhanced_email_ui.py.\n\n"
        "IMPORTANT:\n"
        "- No real .env or mailbox credentials are included.\n"
        "- Automatic sending remains disabled.\n"
        "- Apache Hop and n8n are not required for this test package.\n"
        "- The database itself is not embedded in this ZIP.\n",
        encoding="utf-8",
    )

    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for file_path in staging_dir.rglob("*"):
            if file_path.is_file():
                archive.write(
                    file_path,
                    arcname=file_path.relative_to(staging_dir),
                )

    print(f"Created: {archive_path}")
    return archive_path


if __name__ == "__main__":
    build_package()
