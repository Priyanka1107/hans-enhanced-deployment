from __future__ import annotations

import asyncio
import re

from app.runtime.local_llm import HTWOllamaClient


EXPECTED_URL = (
    "https://f2ki-h100-1.f2.htw-berlin.de:11435"
)
EXPECTED_MODEL = "qwen3:32b"


def _normalise_exact_text(text: str) -> str:
    cleaned = str(text or "").strip()

    cleaned = re.sub(
        r"^```(?:plaintext|text|txt)?\s*",
        "",
        cleaned,
        count=1,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
        count=1,
        flags=re.IGNORECASE,
    )

    return cleaned.strip()


async def main() -> None:
    client = HTWOllamaClient()

    print("=" * 88)
    print("APPLICATION OLLAMA CLIENT TEST")
    print("=" * 88)
    print(f"Endpoint: {client.base_url}")
    print(f"Model: {client.model}")
    print(f"SSL verification: {client.verify_ssl}")
    print(f"Timeout: {client.timeout}")
    print(f"Maximum attempts: {client.max_attempts}")
    print("Concurrency: sequential")
    print("num_ctx override: not sent")

    if client.base_url != EXPECTED_URL:
        raise AssertionError(
            "HTWOllamaClient is not using the expected "
            f"HTW endpoint. Got: {client.base_url}"
        )

    if client.model != EXPECTED_MODEL:
        raise AssertionError(
            "HTWOllamaClient is not using qwen3:32b. "
            f"Got: {client.model}"
        )

    if client.verify_ssl is not True:
        raise AssertionError(
            "SSL verification must be enabled for HTW."
        )

    print("\nSending one request through HTWOllamaClient...")
    print("-" * 88)

    response = await client.generate(
        system_prompt=(
            "Return only the exact plain-text token "
            "requested by the user. Do not use Markdown "
            "or code fences."
        ),
        user_prompt="Reply with exactly: HTW_QWEN_OK",
        temperature=0.0,
    )

    normalised_response = (
        _normalise_exact_text(response)
    )

    print("\nRAW MODEL RESPONSE")
    print("-" * 88)
    print(response)

    print("\nNORMALISED VERIFICATION RESPONSE")
    print("-" * 88)
    print(normalised_response)

    if normalised_response != "HTW_QWEN_OK":
        raise AssertionError(
            "The application client reached a model, but "
            "the normalised verification response was not "
            f"HTW_QWEN_OK. Got: {normalised_response!r}"
        )

    print("\nTEST RESULT")
    print("-" * 88)
    print(
        "PASS: HTWOllamaClient used the HTW-hosted "
        "qwen3:32b model."
    )


if __name__ == "__main__":
    asyncio.run(main())
