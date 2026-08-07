from __future__ import annotations

import os
from typing import Protocol

from app.runtime.local_llm import HTWOllamaClient
from app.runtime.mistral_api import MistralAPIClient
from app.settings import settings


class GenerationClient(Protocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        ...


def selected_generation_provider() -> str:
    return os.getenv(
        "GENERATION_PROVIDER",
        "htw_ollama",
    ).strip().lower()


def selected_generation_model() -> str:
    provider = selected_generation_provider()

    if provider in {"mistral", "mistral_api", "cloud_mistral"}:
        return os.getenv("MISTRAL_MODEL", "").strip()

    return os.getenv(
        "OLLAMA_MODEL",
        settings.ollama_model,
    ).strip()


def build_generation_client() -> GenerationClient:
    provider = selected_generation_provider()

    if provider in {"mistral", "mistral_api", "cloud_mistral"}:
        return MistralAPIClient()

    if provider in {"htw_ollama", "ollama", "local"}:
        return HTWOllamaClient()

    raise RuntimeError(
        "Unsupported GENERATION_PROVIDER: "
        f"{provider}. Use htw_ollama or mistral_api."
    )
