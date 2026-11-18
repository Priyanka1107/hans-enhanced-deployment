from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)


logger = logging.getLogger(__name__)


class HTWLiteLLMError(RuntimeError):
    """Raised when communication with the HTW LiteLLM endpoint fails."""


_GENERATION_LOCKS: Dict[int, asyncio.Lock] = {}


def _get_generation_lock() -> asyncio.Lock:
    """
    Return one generation lock per asyncio event loop.

    HANS currently serializes generation requests. Preserving that behavior
    avoids introducing concurrency changes while the generation provider is
    being tested.
    """
    loop = asyncio.get_running_loop()
    loop_key = id(loop)

    lock = _GENERATION_LOCKS.get(loop_key)

    if lock is None:
        lock = asyncio.Lock()
        _GENERATION_LOCKS[loop_key] = lock

    return lock


def _environment_bool(
    name: str,
    default: bool,
) -> bool:
    """Read a Boolean environment variable using common true/false values."""
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    return raw_value.strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _environment_float(
    name: str,
    default: float,
) -> float:
    """Read a floating-point environment variable with a safe fallback."""
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError:
        logger.warning(
            "Invalid %s value %r. Using default %s.",
            name,
            raw_value,
            default,
        )
        return default


def _environment_int(
    name: str,
    default: int,
) -> int:
    """Read an integer environment variable with a safe fallback."""
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        logger.warning(
            "Invalid %s value %r. Using default %s.",
            name,
            raw_value,
            default,
        )
        return default


def _remove_thinking_block(text: str) -> str:
    """
    Remove visible model reasoning blocks from the staff-facing completion.

    The existing HTW Ollama client applies the same cleanup. Keeping this
    behavior consistent prevents transport changes from altering the UI output
    format.
    """
    cleaned = re.sub(
        r"<think>.*?</think>",
        "",
        text or "",
        flags=re.DOTALL | re.IGNORECASE,
    )

    return cleaned.strip()


def _response_error_text(
    response: httpx.Response,
) -> str:
    """Return a concise response error without exposing request credentials."""
    try:
        payload = response.json()

        if isinstance(payload, dict):
            error = payload.get("error")

            if isinstance(error, dict):
                return str(
                    error.get("message")
                    or error
                )

            return str(
                error
                or payload
            )

        return str(payload)

    except ValueError:
        return response.text[:500]


class HTWLiteLLMClient:
    """
    Async generation client for the HTW OpenAI-compatible LiteLLM endpoint.

    This class is intentionally limited to model communication. Retrieval,
    evidence selection, prompt construction, validation, and staff-facing
    processing remain in their existing HANS modules.
    """

    def __init__(self) -> None:
        self.base_url = os.getenv(
            "LITELLM_BASE_URL",
            "",
        ).rstrip("/")

        configured_chat_url = os.getenv(
            "LITELLM_CHAT_URL",
            "",
        ).strip()

        self.chat_url = (
            configured_chat_url
            or (
                f"{self.base_url}/chat/completions"
                if self.base_url
                else ""
            )
        )

        self.api_key = os.getenv(
            "LITELLM_API_KEY",
            "",
        ).strip()

        self.model = os.getenv(
            "LITELLM_MODEL",
            "",
        ).strip()

        self.timeout = _environment_float(
            "LITELLM_TIMEOUT",
            420.0,
        )

        self.verify_tls = _environment_bool(
            "LITELLM_VERIFY_TLS",
            True,
        )

        self.trust_env = _environment_bool(
            "LITELLM_TRUST_ENV",
            True,
        )

        self.max_attempts = max(
            1,
            _environment_int(
                "LITELLM_MAX_ATTEMPTS",
                6,
            ),
        )

        thinking_raw = os.getenv(
            "LITELLM_ENABLE_THINKING",
            "",
        ).strip().lower()

        if thinking_raw in {"1", "true", "yes", "on"}:
            self.enable_thinking: bool | None = True
        elif thinking_raw in {"0", "false", "no", "off"}:
            self.enable_thinking = False
        else:
            self.enable_thinking = None

        self.backoff_seconds = (
            5.0,
            10.0,
            20.0,
            30.0,
            45.0,
        )

        # Observability only. These values must not influence generation.
        self.last_generation_metrics: Dict[str, Any] = {}

    def _validate_configuration(self) -> None:
        """Fail early with a clear message when required settings are missing."""
        missing_settings = []

        if not self.chat_url:
            missing_settings.append(
                "LITELLM_CHAT_URL or LITELLM_BASE_URL"
            )

        if not self.api_key:
            missing_settings.append("LITELLM_API_KEY")

        if not self.model:
            missing_settings.append("LITELLM_MODEL")

        if missing_settings:
            raise HTWLiteLLMError(
                "Missing required HTW LiteLLM configuration: "
                + ", ".join(missing_settings)
            )

    async def _post_with_retry(
        self,
        *,
        client: httpx.AsyncClient,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> httpx.Response:
        """
        Send one generation request with bounded retries for temporary failures.

        Authentication and validation errors are not retried because repeating
        those requests would not resolve the underlying configuration problem.
        """
        retryable_status_codes = {
            429,
            502,
            503,
            504,
        }

        for attempt in range(
            1,
            self.max_attempts + 1,
        ):
            started = time.perf_counter()

            try:
                response = await client.post(
                    self.chat_url,
                    json=payload,
                    headers=headers,
                )

            except httpx.TimeoutException as exc:
                elapsed = time.perf_counter() - started

                raise HTWLiteLLMError(
                    "HTW LiteLLM request timed out after "
                    f"{elapsed:.1f} seconds."
                ) from exc

            except httpx.RequestError as exc:
                raise HTWLiteLLMError(
                    f"HTW LiteLLM request failed: {exc}"
                ) from exc

            elapsed = time.perf_counter() - started

            if response.status_code not in retryable_status_codes:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise HTWLiteLLMError(
                        "HTW LiteLLM request failed with "
                        f"HTTP {response.status_code}: "
                        f"{_response_error_text(response)}"
                    ) from exc

                logger.info(
                    "HTW LiteLLM request completed with HTTP %s "
                    "on attempt %s in %.1f seconds using model %s.",
                    response.status_code,
                    attempt,
                    elapsed,
                    self.model,
                )

                return response

            logger.warning(
                "HTW LiteLLM returned retryable HTTP %s "
                "on attempt %s/%s after %.1f seconds.",
                response.status_code,
                attempt,
                self.max_attempts,
                elapsed,
            )

            if attempt >= self.max_attempts:
                raise HTWLiteLLMError(
                    "HTW LiteLLM remained unavailable after "
                    f"{self.max_attempts} attempts. "
                    f"Last HTTP status: {response.status_code}."
                )

            retry_after = response.headers.get(
                "Retry-After"
            )

            if retry_after:
                try:
                    base_delay = max(
                        1.0,
                        float(retry_after),
                    )
                except ValueError:
                    base_delay = self.backoff_seconds[
                        min(
                            attempt - 1,
                            len(self.backoff_seconds) - 1,
                        )
                    ]
            else:
                base_delay = self.backoff_seconds[
                    min(
                        attempt - 1,
                        len(self.backoff_seconds) - 1,
                    )
                ]

            delay = base_delay + random.uniform(
                0.0,
                2.0,
            )

            logger.info(
                "Retrying HTW LiteLLM request in %.1f seconds.",
                delay,
            )

            await asyncio.sleep(delay)

        raise HTWLiteLLMError(
            "Unexpected HTW LiteLLM retry-loop termination."
        )

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        """
        Generate one completion using the common HANS generation interface.

        The system and user prompts are supplied by the existing HANS prompt
        builder. This client does not modify retrieval evidence or prompt text.
        """
        self.last_generation_metrics = {}

        self._validate_configuration()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "temperature": temperature,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        if self.enable_thinking is not None:
            payload["enable_thinking"] = self.enable_thinking

        timeout = httpx.Timeout(
            connect=30.0,
            read=max(
                self.timeout,
                420.0,
            ),
            write=60.0,
            pool=30.0,
        )

        generation_lock = _get_generation_lock()

        async with generation_lock:
            logger.info(
                "Sending sequential HTW LiteLLM request "
                "using model %s.",
                self.model,
            )

            async with httpx.AsyncClient(
                timeout=timeout,
                verify=self.verify_tls,
                trust_env=self.trust_env,
                follow_redirects=True,
            ) as client:
                response = await self._post_with_retry(
                    client=client,
                    payload=payload,
                    headers=headers,
                )

        try:
            data: Dict[str, Any] = response.json()
        except ValueError as exc:
            raise HTWLiteLLMError(
                "HTW LiteLLM returned invalid JSON."
            ) from exc

        choices = data.get("choices") or []

        if not choices:
            raise HTWLiteLLMError(
                "HTW LiteLLM returned no completion choices."
            )

        message = choices[0].get("message") or {}
        content = message.get("content") or ""

        if isinstance(content, list):
            text_parts = []

            for item in content:
                if (
                    isinstance(item, dict)
                    and item.get("text")
                ):
                    text_parts.append(
                        str(item["text"])
                    )

            content = "\n".join(text_parts)

        generated_text = str(content).strip()

        if not generated_text:
            raise HTWLiteLLMError(
                "HTW LiteLLM returned an empty completion."
            )

        usage = data.get("usage") or {}

        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")

        if (
            not isinstance(total_tokens, int)
            and isinstance(prompt_tokens, int)
            and isinstance(completion_tokens, int)
        ):
            total_tokens = (
                prompt_tokens
                + completion_tokens
            )

        self.last_generation_metrics = {
            "provider": "htw_litellm",
            "model": str(
                data.get("model")
                or self.model
            ),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "enable_thinking": self.enable_thinking,

            # The OpenAI-compatible response does not expose Ollama-style
            # native model timing. HANS records end-to-end generation time
            # separately in the email service.
            "model_total_seconds": None,
            "load_seconds": None,
            "prompt_eval_seconds": None,
            "completion_eval_seconds": None,
        }

        return _remove_thinking_block(
            generated_text
        )
