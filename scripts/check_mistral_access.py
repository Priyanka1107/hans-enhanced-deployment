from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

BASE_URL = os.getenv(
    "MISTRAL_BASE_URL",
    "https://api.mistral.ai/v1",
).rstrip("/")
API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
SELECTED_MODEL = os.getenv("MISTRAL_MODEL", "").strip()


def _fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def _model_value(model: Any, field: str, default: Any = None) -> Any:
    if isinstance(model, dict):
        return model.get(field, default)
    return getattr(model, field, default)


def main() -> None:
    if not API_KEY:
        _fail("MISTRAL_API_KEY is missing from .env")

    headers = {"Authorization": f"Bearer {API_KEY}"}

    with httpx.Client(timeout=60.0) as client:
        response = client.get(
            f"{BASE_URL}/models",
            headers=headers,
        )

        if response.status_code >= 400:
            _fail(
                "Model-list request failed with HTTP "
                f"{response.status_code}: {response.text[:400]}"
            )

        payload = response.json()
        models = payload.get("data", payload)

        if not isinstance(models, list):
            _fail("Unexpected model-list response format")

        chat_models = []
        for model in models:
            capabilities = _model_value(model, "capabilities", {}) or {}
            if not isinstance(capabilities, dict):
                capabilities = getattr(capabilities, "model_dump", lambda: {})()

            if capabilities.get("completion_chat", True):
                model_id = str(_model_value(model, "id", "")).strip()
                if model_id:
                    chat_models.append(model_id)

        chat_models = sorted(set(chat_models))

        print("Accessible chat-capable models:")
        for model_id in chat_models:
            marker = "  <selected>" if model_id == SELECTED_MODEL else ""
            print(f"- {model_id}{marker}")

        large_candidates = [
            model_id
            for model_id in chat_models
            if "large" in model_id.lower() or "medium" in model_id.lower()
        ]

        print("\nLarge/strong candidate IDs returned for this key:")
        if large_candidates:
            for model_id in large_candidates:
                print(f"- {model_id}")
        else:
            print("- None identified by name. Review the full list above.")

        if not SELECTED_MODEL:
            print(
                "\nSet MISTRAL_MODEL in .env to one exact model ID "
                "from the list, then run this script again."
            )
            return

        if SELECTED_MODEL not in chat_models:
            _fail(
                f"Selected model {SELECTED_MODEL!r} was not returned for this key."
            )

        test_response = client.post(
            f"{BASE_URL}/chat/completions",
            headers={
                **headers,
                "Content-Type": "application/json",
            },
            json={
                "model": SELECTED_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Reply with exactly: Mistral access test successful."
                        ),
                    }
                ],
                "temperature": 0,
                "max_tokens": 30,
            },
        )

        if test_response.status_code >= 400:
            _fail(
                "Completion test failed with HTTP "
                f"{test_response.status_code}: {test_response.text[:400]}"
            )

        test_payload = test_response.json()
        content = (
            test_payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        usage = test_payload.get("usage", {})

        print("\nCompletion test response:")
        print(content)
        print("Usage:", usage)


if __name__ == "__main__":
    try:
        main()
    except httpx.RequestError as exc:
        _fail(f"Network request failed: {exc}")
