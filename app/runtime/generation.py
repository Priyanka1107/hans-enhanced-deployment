from __future__ import annotations

import os
from typing import Protocol

from app.runtime.litellm_api import HTWLiteLLMClient
from app.runtime.local_llm import HTWOllamaClient
from app.runtime.mistral_api import MistralAPIClient
from app.settings import settings


HTW_LITELLM_PROVIDERS = {
    "htw_litellm",
    "litellm",
}

MISTRAL_API_PROVIDERS = {
    "mistral",
    "mistral_api",
    "cloud_mistral",
}

OLLAMA_PROVIDERS = {
    "htw_ollama",
    "ollama",
    "local",
}


class GenerationClient(Protocol):
    """Common async interface implemented by all HANS generation providers."""

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        ...


def selected_generation_provider() -> str:
    """Return the configured generation provider using a normalized name."""
    return os.getenv(
        "GENERATION_PROVIDER",
        "htw_ollama",
    ).strip().lower()


def selected_generation_model() -> str:
    """Return the configured model name for the active generation provider."""
    provider = selected_generation_provider()

    if provider in HTW_LITELLM_PROVIDERS:
        return os.getenv(
            "LITELLM_MODEL",
            "",
        ).strip()

    if provider in MISTRAL_API_PROVIDERS:
        return os.getenv(
            "MISTRAL_MODEL",
            "",
        ).strip()

    if provider in OLLAMA_PROVIDERS:
        return os.getenv(
            "OLLAMA_MODEL",
            settings.ollama_model,
        ).strip()

    return ""


def build_generation_client() -> GenerationClient:
    """
    Build the generation client selected through environment configuration.

    Provider-specific HTTP details stay inside their own client modules so the
    email service can use one stable generate() interface.
    """
    provider = selected_generation_provider()

    if provider in HTW_LITELLM_PROVIDERS:
        return HTWLiteLLMClient()

    if provider in MISTRAL_API_PROVIDERS:
        return MistralAPIClient()

    if provider in OLLAMA_PROVIDERS:
        return HTWOllamaClient()

    supported_providers = (
        "htw_litellm, htw_ollama, or mistral_api"
    )

    raise RuntimeError(
        "Unsupported GENERATION_PROVIDER "
        f"{provider!r}. Use {supported_providers}."
    )
