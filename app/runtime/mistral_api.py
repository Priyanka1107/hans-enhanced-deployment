from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict

import httpx


logger = logging.getLogger(__name__)


class MistralAPIError(RuntimeError):
    """Raised when the configured Mistral API request cannot be completed."""


class MistralAPIClient:
    """Small async client matching the generate() interface used by HANS."""

    def __init__(self) -> None:
        self.api_key = os.getenv("MISTRAL_API_KEY", "").strip()
        self.base_url = os.getenv(
            "MISTRAL_BASE_URL",
            "https://api.mistral.ai/v1",
        ).rstrip("/")
        self.model = os.getenv("MISTRAL_MODEL", "").strip()
        self.timeout = float(os.getenv("MISTRAL_TIMEOUT", "180"))
        self.max_tokens = int(os.getenv("MISTRAL_MAX_TOKENS", "1200"))
        self.max_attempts = max(
            1,
            int(os.getenv("MISTRAL_MAX_ATTEMPTS", "3")),
        )

    @staticmethod
    def _error_text(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return str(payload.get("message") or payload.get("detail") or payload)
            return str(payload)
        except Exception:
            return response.text[:500]

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        if not self.api_key:
            raise MistralAPIError("MISTRAL_API_KEY is not configured.")

        if not self.model:
            raise MistralAPIError(
                "MISTRAL_MODEL is not configured. Run the model-access check first."
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }

        timeout = httpx.Timeout(
            connect=30.0,
            read=self.timeout,
            write=60.0,
            pool=30.0,
        )

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            response: httpx.Response | None = None

            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = await client.post(
                        url,
                        headers=headers,
                        json=payload,
                    )
                except httpx.TimeoutException as exc:
                    raise MistralAPIError(
                        "Mistral API request timed out."
                    ) from exc
                except httpx.RequestError as exc:
                    raise MistralAPIError(
                        f"Mistral API request failed: {exc}"
                    ) from exc

                if response.status_code not in {429, 500, 502, 503, 504}:
                    break

                if attempt >= self.max_attempts:
                    break

                await asyncio.sleep(float(2 ** (attempt - 1)))

        if response is None:
            raise MistralAPIError("Mistral API returned no response.")

        if response.status_code >= 400:
            raise MistralAPIError(
                "Mistral API request failed with HTTP "
                f"{response.status_code}: {self._error_text(response)}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise MistralAPIError(
                "Mistral API returned invalid JSON."
            ) from exc

        choices = data.get("choices") or []
        if not choices:
            raise MistralAPIError(
                "Mistral API returned no completion choices."
            )

        message = choices[0].get("message") or {}
        content = message.get("content") or ""

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    text_parts.append(str(item["text"]))
            content = "\n".join(text_parts)

        result = str(content).strip()
        if not result:
            raise MistralAPIError(
                "Mistral API returned an empty completion."
            )

        usage = data.get("usage") or {}
        logger.info(
            "Mistral API generation completed using %s "
            "(prompt_tokens=%s, completion_tokens=%s, total_tokens=%s).",
            self.model,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )

        return result
