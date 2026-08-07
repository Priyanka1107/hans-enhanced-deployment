from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)


BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "https://f2ki-h100-1.f2.htw-berlin.de:11435",
).rstrip("/")

MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:32b",
)

VERIFY_SSL = os.getenv(
    "OLLAMA_VERIFY_SSL",
    "true",
).strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}

REQUEST_TIMEOUT = float(
    os.getenv(
        "OLLAMA_TIMEOUT",
        "420",
    )
)

MAX_ATTEMPTS = max(
    1,
    int(
        os.getenv(
            "OLLAMA_MAX_ATTEMPTS",
            "6",
        )
    ),
)

BACKOFF_SECONDS = (
    5.0,
    10.0,
    20.0,
    30.0,
    45.0,
)


def _normalise_exact_text(text: str) -> str:
    """
    Remove a single outer Markdown code fence.

    Qwen may correctly return the requested token while wrapping it in
    ```plaintext ... ```. For a connectivity smoke test, that should
    still count as the requested answer.
    """
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


def _response_error_text(
    response: httpx.Response,
) -> str:
    try:
        payload = response.json()

        if isinstance(payload, dict):
            return str(
                payload.get("error")
                or payload
            )

        return str(payload)
    except Exception:
        return response.text[:500]


async def _request_with_503_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """
    Send one request at a time and retry only HTTP 503.

    No num_ctx override is sent.
    """
    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):
        started = time.perf_counter()

        try:
            response = await client.request(
                method,
                url,
                **kwargs,
            )
        except httpx.TimeoutException as exc:
            elapsed = time.perf_counter() - started
            raise RuntimeError(
                "The HTW server request timed out after "
                f"{elapsed:.1f} seconds. A first model load "
                "may take approximately one minute."
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Could not reach the HTW Ollama server: {exc}"
            ) from exc

        elapsed = time.perf_counter() - started

        if response.status_code != 503:
            print(
                f"Attempt {attempt}: HTTP "
                f"{response.status_code} in {elapsed:.1f}s"
            )
            response.raise_for_status()
            return response

        print(
            f"Attempt {attempt}: HTTP 503 in "
            f"{elapsed:.1f}s — "
            f"{_response_error_text(response)}"
        )

        if attempt >= MAX_ATTEMPTS:
            raise RuntimeError(
                "The shared HTW Ollama queue remained full "
                f"after {MAX_ATTEMPTS} sequential attempts."
            )

        retry_after = response.headers.get(
            "Retry-After"
        )

        if retry_after:
            try:
                delay = max(
                    1.0,
                    float(retry_after),
                )
            except ValueError:
                delay = BACKOFF_SECONDS[
                    min(
                        attempt - 1,
                        len(BACKOFF_SECONDS) - 1,
                    )
                ]
        else:
            delay = BACKOFF_SECONDS[
                min(
                    attempt - 1,
                    len(BACKOFF_SECONDS) - 1,
                )
            ]

        print(
            f"Waiting {delay:.0f}s before the "
            "next sequential attempt..."
        )
        await asyncio.sleep(delay)

    raise RuntimeError(
        "Unexpected retry-loop termination."
    )


async def main() -> None:
    print("=" * 88)
    print("HTW OLLAMA SEQUENTIAL SERVER TEST")
    print("=" * 88)
    print(f"Base URL: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"SSL verification: {VERIFY_SSL}")
    print(f"Read timeout: {REQUEST_TIMEOUT}")
    print("Concurrency: 1 request at a time")
    print("num_ctx override: NOT SENT")
    print("503 handling: retry with short backoff")

    expected_url = (
        "https://f2ki-h100-1.f2.htw-berlin.de:11435"
    )

    if BASE_URL != expected_url:
        raise AssertionError(
            "The smoke test is not using the expected HTW "
            f"endpoint. Got: {BASE_URL}"
        )

    if VERIFY_SSL is not True:
        raise AssertionError(
            "SSL verification must be enabled for HTW."
        )

    timeout = httpx.Timeout(
        connect=30.0,
        read=max(
            REQUEST_TIMEOUT,
            420.0,
        ),
        write=60.0,
        pool=30.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        verify=VERIFY_SSL,
        follow_redirects=True,
    ) as client:
        print("\n1. Checking available models")
        print("-" * 88)

        tags_response = await _request_with_503_retry(
            client,
            "GET",
            f"{BASE_URL}/api/tags",
        )

        tags_payload = tags_response.json()
        available_models = [
            str(model.get("name") or "")
            for model in tags_payload.get(
                "models",
                [],
            )
        ]

        print(
            "Available models:",
            ", ".join(available_models)
            or "(none returned)",
        )

        if MODEL not in available_models:
            raise AssertionError(
                f"Required model {MODEL!r} was not returned "
                "by the HTW Ollama server."
            )

        print("\n2. Sending one minimal chat request")
        print("-" * 88)

        request_payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only the exact plain-text token "
                        "requested by the user. Do not use Markdown "
                        "or code fences."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Reply with exactly: SERVER_OK"
                    ),
                },
            ],
            "stream": False,
        }

        chat_response = await _request_with_503_retry(
            client,
            "POST",
            f"{BASE_URL}/api/chat",
            json=request_payload,
        )

        payload = chat_response.json()
        message = payload.get("message") or {}

        raw_content = str(
            message.get("content") or ""
        ).strip()

        normalised_content = (
            _normalise_exact_text(raw_content)
        )

        thinking = str(
            message.get("thinking") or ""
        ).strip()

        print("\nRaw server response")
        print("-" * 88)
        print(raw_content or "(empty content)")

        print("\nNormalised verification response")
        print("-" * 88)
        print(normalised_content or "(empty content)")

        if thinking:
            print(
                "\nThe model also returned a separate "
                "thinking field. It is intentionally ignored."
            )

        print("\nTiming metadata")
        print("-" * 88)

        for field in (
            "total_duration",
            "load_duration",
            "prompt_eval_duration",
            "eval_duration",
            "prompt_eval_count",
            "eval_count",
            "done_reason",
        ):
            if field in payload:
                print(
                    f"{field}: {payload[field]}"
                )

        print("\nRequest payload used")
        print("-" * 88)
        print(
            json.dumps(
                request_payload,
                indent=2,
                ensure_ascii=False,
            )
        )

        if "num_ctx" in json.dumps(
            request_payload
        ):
            raise AssertionError(
                "num_ctx must not be sent."
            )

        print("\nTEST RESULT")
        print("-" * 88)

        if normalised_content != "SERVER_OK":
            raise AssertionError(
                "The HTW model responded, but the "
                "normalised verification response was not "
                f"SERVER_OK. Got: {normalised_content!r}"
            )

        print(
	    "PASS: The raw HTW Ollama endpoint accepted a "
    	    f"sequential {MODEL} request."
	)


if __name__ == "__main__":
    asyncio.run(main())
