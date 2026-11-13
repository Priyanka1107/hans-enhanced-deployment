from unittest.mock import patch

from app.runtime.generation import (
    build_generation_client,
    selected_generation_model,
    selected_generation_provider,
)
from app.runtime.litellm_api import HTWLiteLLMClient
from app.runtime.local_llm import HTWOllamaClient
from app.runtime.mistral_api import MistralAPIClient


def test_selects_htw_litellm_provider_and_model() -> None:
    with patch.dict(
        "os.environ",
        {
            "GENERATION_PROVIDER": "htw_litellm",
            "LITELLM_MODEL": "qwen3.8-27b",
        },
        clear=False,
    ):
        assert selected_generation_provider() == "htw_litellm"
        assert selected_generation_model() == "qwen3.8-27b"
        assert isinstance(
            build_generation_client(),
            HTWLiteLLMClient,
        )


def test_existing_ollama_provider_remains_available() -> None:
    with patch.dict(
        "os.environ",
        {
            "GENERATION_PROVIDER": "htw_ollama",
            "OLLAMA_MODEL": "mistral-small:24b",
        },
        clear=False,
    ):
        assert selected_generation_model() == "mistral-small:24b"
        assert isinstance(
            build_generation_client(),
            HTWOllamaClient,
        )


def test_existing_mistral_provider_remains_available() -> None:
    with patch.dict(
        "os.environ",
        {
            "GENERATION_PROVIDER": "mistral_api",
            "MISTRAL_MODEL": "mistral-test-model",
        },
        clear=False,
    ):
        assert selected_generation_model() == "mistral-test-model"
        assert isinstance(
            build_generation_client(),
            MistralAPIClient,
        )


def test_unsupported_provider_fails_explicitly() -> None:
    with patch.dict(
        "os.environ",
        {
            "GENERATION_PROVIDER": "unsupported-provider",
        },
        clear=False,
    ):
        assert selected_generation_model() == ""

        try:
            build_generation_client()
        except RuntimeError as exc:
            assert "Unsupported GENERATION_PROVIDER" in str(exc)
        else:
            raise AssertionError(
                "Unsupported provider did not raise RuntimeError."
            )
