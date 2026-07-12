from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

load_dotenv(ENV_PATH, override=True)


def _load_yaml() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Configuration file not found: {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


_yaml = _load_yaml()


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT

    environment: str = os.getenv("HANS_ENVIRONMENT", "development")
    api_host: str = os.getenv("HANS_API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("HANS_API_PORT", "8008"))

    api_key: str = os.getenv("HANS_INTERNAL_API_KEY", "")

    database_url: str = os.getenv(
        "DATABASE_URL",
        _yaml.get("database", {}).get(
            "url",
            "postgresql://postgres:postgres@127.0.0.1:5433/hans",
        ),
    )

    embedding_model: str = _yaml.get("model", {}).get(
        "embedding_model",
        "BAAI/bge-base-en-v1.5",
    )

    embedding_dimension: int = int(
        _yaml.get("model", {}).get("embedding_dim", 768)
    )

    reranker_enabled: bool = bool(
        _yaml.get("retrieval", {})
        .get("reranker", {})
        .get("enabled", True)
    )

    reranker_model: str = (
        _yaml.get("retrieval", {})
        .get("reranker", {})
        .get("model_name", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    )

    retrieval_top_k_db: int = int(
        _yaml.get("retrieval", {}).get("top_k_db", 30)
    )

    retrieval_top_k_per_topic: int = int(
        os.getenv("RETRIEVAL_TOP_K_PER_TOPIC", "6")
    )

    final_source_limit: int = int(
        os.getenv("FINAL_SOURCE_LIMIT", "8")
    )

    ollama_base_url: str = _yaml.get("runtime", {}).get(
        "ollama_base_url",
        "",
    )

    ollama_model: str = _yaml.get("runtime", {}).get(
        "ollama_model",
        "qwen3:32b",
    )

    ollama_timeout: int = int(
        _yaml.get("runtime", {}).get("ollama_timeout", 300)
    )

    verify_ssl: bool = bool(
        _yaml.get("runtime", {}).get("verify_ssl", True)
    )

    disclaimer_path: Path = Path(
        os.getenv(
            "DISCLAIMER_PATH",
            str(PROJECT_ROOT / "config" / "disclaimer.md"),
        )
    )

    thread_memory_enabled: bool = (
        os.getenv("THREAD_MEMORY_ENABLED", "true").lower() == "true"
    )

    max_email_characters: int = int(
        os.getenv("MAX_EMAIL_CHARACTERS", "20000")
    )

    staff_review_required_for_all: bool = (
        os.getenv(
            "STAFF_REVIEW_REQUIRED_FOR_ALL",
            "true",
        ).lower()
        == "true"
    )


settings = Settings()