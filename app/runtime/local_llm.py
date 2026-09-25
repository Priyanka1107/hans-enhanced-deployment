from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

from app.settings import settings


logger = logging.getLogger(__name__)


class LocalLLMError(RuntimeError):
    pass


_GENERATION_LOCKS: Dict[int, asyncio.Lock] = {}


def _get_generation_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    loop_key = id(loop)

    lock = _GENERATION_LOCKS.get(loop_key)

    if lock is None:
        lock = asyncio.Lock()
        _GENERATION_LOCKS[loop_key] = lock

    return lock


def _remove_thinking_block(text: str) -> str:
    cleaned = re.sub(
        r"<think>.*?</think>",
        "",
        text or "",
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned.strip()


def _environment_bool(
    name: str,
    default: bool,
) -> bool:
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


class HTWOllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv(
            "OLLAMA_BASE_URL",
            settings.ollama_base_url,
        ).rstrip("/")

        self.model = os.getenv(
            "OLLAMA_MODEL",
            settings.ollama_model,
        )

        self.timeout = _environment_float(
            "OLLAMA_TIMEOUT",
            float(settings.ollama_timeout),
        )

        self.verify_ssl = _environment_bool(
            "OLLAMA_VERIFY_SSL",
            bool(settings.verify_ssl),
        )

        self.max_attempts = max(
            1,
            _environment_int(
                "OLLAMA_MAX_ATTEMPTS",
                6,
            ),
        )

        self.backoff_seconds = (
            5.0,
            10.0,
            20.0,
            30.0,
            45.0,
        )

        # Observability only. This must not affect generation behaviour.
        self.last_generation_metrics: Dict[str, Any] = {}

    async def _post_with_503_retry(
        self,
        *,
        client: httpx.AsyncClient,
        url: str,
        payload: Dict[str, Any],
    ) -> httpx.Response:
        for attempt in range(
            1,
            self.max_attempts + 1,
        ):
            started = time.perf_counter()

            try:
                response = await client.post(
                    url,
                    json=payload,
                )
            except httpx.TimeoutException as exc:
                elapsed = time.perf_counter() - started
                raise LocalLLMError(
                    "HTW model request timed out after "
                    f"{elapsed:.1f} seconds. A first request may "
                    "take longer while the model is loaded."
                ) from exc
            except httpx.RequestError as exc:
                raise LocalLLMError(
                    f"HTW model request failed: {exc}"
                ) from exc

            elapsed = time.perf_counter() - started

            if response.status_code != 503:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise LocalLLMError(
                        "HTW model request failed with "
                        f"HTTP {response.status_code}: "
                        f"{_response_error_text(response)}"
                    ) from exc

                logger.info(
                    "HTW Ollama request completed with HTTP %s "
                    "on attempt %s in %.1f seconds.",
                    response.status_code,
                    attempt,
                    elapsed,
                )
                return response

            logger.warning(
                "HTW Ollama queue full on attempt %s/%s "
                "after %.1f seconds: %s",
                attempt,
                self.max_attempts,
                elapsed,
                _response_error_text(response),
            )

            if attempt >= self.max_attempts:
                raise LocalLLMError(
                    "The shared HTW Ollama request queue "
                    "remained full after "
                    f"{self.max_attempts} sequential attempts."
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
                "Retrying HTW Ollama request in %.1f seconds.",
                delay,
            )
            await asyncio.sleep(delay)

        raise LocalLLMError(
            "Unexpected HTW Ollama retry-loop termination."
        )

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        # Prevent metrics from a previous request being reused.
        self.last_generation_metrics = {}

        if not self.base_url:
            raise LocalLLMError(
                "Ollama base URL is not configured."
            )

        payload: Dict[str, Any] = {
            "model": self.model,
            "stream": False,
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
            "options": {
                "temperature": temperature,
            },
        }

        url = f"{self.base_url}/api/chat"

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
                "Sending sequential Ollama request to %s "
                "using model %s.",
                self.base_url,
                self.model,
            )

            async with httpx.AsyncClient(
                timeout=timeout,
                verify=self.verify_ssl,
                follow_redirects=True,
            ) as client:
                response = await self._post_with_503_retry(
                    client=client,
                    url=url,
                    payload=payload,
                )

        try:
            data: Dict[str, Any] = response.json()
        except ValueError as exc:
            raise LocalLLMError(
                "HTW model returned invalid JSON."
            ) from exc

        message = data.get("message") or {}
        content = str(
            message.get("content") or ""
        )

        if not content:
            raise LocalLLMError(
                "HTW model returned an empty response."
            )

        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")

        total_tokens = None

        if (
            isinstance(prompt_tokens, int)
            and isinstance(completion_tokens, int)
        ):
            total_tokens = (
                prompt_tokens
                + completion_tokens
            )

        def ns_to_seconds(value):
            if isinstance(value, (int, float)):
                return round(
                    float(value) / 1_000_000_000.0,
                    3,
                )
            return None

        self.last_generation_metrics = {
            "provider": "htw_ollama",
            "model": str(
                data.get("model")
                or self.model
            ),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model_total_seconds": ns_to_seconds(
                data.get("total_duration")
            ),
            "load_seconds": ns_to_seconds(
                data.get("load_duration")
            ),
            "prompt_eval_seconds": ns_to_seconds(
                data.get("prompt_eval_duration")
            ),
            "completion_eval_seconds": ns_to_seconds(
                data.get("eval_duration")
            ),
        }

        return _remove_thinking_block(content)


def build_email_system_prompt() -> str:
    return """
You are HANS, the HTW Berlin AI-assisted email drafting system.

Your task is to prepare one staff-ready email draft in response to a prospective or current student's enquiry.

Mandatory rules:

1. The draft is for HTW Berlin staff review. It must never claim to be a final or binding admission decision.

2. Use only the evidence documents provided in the prompt. Do not use general knowledge and do not invent missing facts.

3. Answer every detected topic from the student's message, but do not introduce unrelated topics.

4. When the evidence does not support a conclusion, state clearly that the information could not be confirmed from the available official sources.

5. Programme-specific questions must be answered using programme-specific evidence whenever available.

6. Do not classify an applicant's formal eligibility. Explain the documented requirements and state that the official application review determines eligibility.

7. Include citations in the form [Doc 1], [Doc 2] immediately after the factual claim they support.

8. Use simple, polite and professional language.

9. Preserve the language of the incoming email. Use English for English emails and German for German emails.

10. Start with an appropriate greeting. Use the student's first name only when it was clearly identified.

11. End with:
Kind regards,
HTW Berlin Student Services

For a German draft, end with:
Mit freundlichen Grüßen
Studierendenservice der HTW Berlin

12. Do not include a separate reference-link section. The application adds that after generation.

13. Do not include the system disclaimer. The application adds it after generation.

14. Do not mention internal processes such as vector search, retrieval, model confidence or topic detection.

15. Keep the draft easy for a staff member to verify and edit.
""".strip()



def _neutralize_applicant_anchor(text: str) -> str:
    """
    Convert common English first-person applicant wording into a neutral
    third-person description for generation. Retrieval keeps the original
    applicant wording.
    """
    value = str(text or "").strip()

    replacements = [
        (r"\bI am\b", "the applicant is"),
        (r"\bI'm\b", "the applicant is"),
        (r"\bI have\b", "the applicant has"),
        (r"\bI hold\b", "the applicant holds"),
        (r"\bI want\b", "the applicant wants"),
        (r"\bI need\b", "the applicant needs"),
        (r"\bI would\b", "the applicant would"),
        (r"\bI should\b", "the applicant should"),
        (r"\bI can\b", "the applicant can"),
        (r"\bmy\b", "the applicant's"),
        (r"\bme\b", "the applicant"),
        (r"\bI\b", "the applicant"),
    ]

    for pattern, replacement in replacements:
        value = re.sub(
            pattern,
            replacement,
            value,
            flags=re.IGNORECASE,
        )

    return value

def build_email_user_prompt(
    *,
    original_email: str,
    email_context: Dict[str, Any],
    topics: List[Dict[str, Any]],
    documents: List[Dict[str, Any]],
    topic_evidence: List[Dict[str, Any]] | None = None,
) -> str:
    profile_lines: List[str] = []

    context_labels = {
        "student_name": "Student name",
        "previous_degree": "Previous/current degree",
        "target_degree": "Target degree",
        "target_program": "Target programme",
        "country": "Country/background",
        "citizenship_group": "Citizenship category",
        "residence_country": "Residence country",
        "target_program_url": "Programme URL",
        "target_program_application_url": (
            "Programme application URL"
        ),
    }

    for key, label in context_labels.items():
        value = email_context.get(key)

        if value:
            profile_lines.append(
                f"- {label}: {value}"
            )

    if str(email_context.get("programme_status") or "").strip() == "not_provided":
        profile_lines.append(
            "- Programme confirmation: No confirmed HTW programme has been identified."
        )
        profile_lines.append(
            "- Programme naming rule: Do not present descriptive wording from the student's email "
            "as an official or confirmed programme title."
        )

    topic_lines: List[str] = []

    for topic in topics:
        topic_text = (
            topic.get("query")
            or topic.get("user_anchor")
            or topic.get("base_query")
            or ""
        )

        topic_lines.append(
            f"- {topic.get('label')}: "
            f"{_neutralize_applicant_anchor(topic_text)}"
        )

    topic_evidence_lines: List[str] = []

    for mapping in topic_evidence or []:
        label = str(
            mapping.get("label")
            or mapping.get("topic_id")
            or "Topic"
        ).strip()

        doc_numbers = [
            number
            for number in mapping.get("doc_numbers", [])
            if isinstance(number, int) and number > 0
        ]

        if doc_numbers:
            citations = ", ".join(
                f"[Doc {number}]"
                for number in doc_numbers
            )

            topic_evidence_lines.append(
                f"- {label}: {citations}"
            )
        else:
            topic_evidence_lines.append(
                f"- {label}: no final evidence document assigned"
            )

    topic_evidence_section = ""

    if topic_evidence_lines:
        topic_evidence_section = "\n".join(
            [
                "TOPIC-SPECIFIC EVIDENCE",
                "-----------------------",
                *topic_evidence_lines,
                "",
                (
                    "Use the evidence assigned to each topic when "
                    "supporting that topic's factual claims."
                ),
                "",
            ]
        )

    evidence_blocks: List[str] = []

    for index, document in enumerate(
        documents,
        start=1,
    ):
        title = document.get("title", "")
        url = (
            document.get("source_url")
            or document.get("url")
            or ""
        )
        content = (
            document.get("content")
            or document.get("chunk_text")
            or ""
        )
        object_type = document.get(
            "object_type",
            "",
        )
        last_updated = document.get(
            "last_updated",
            "",
        )

        evidence_blocks.append(
            "\n".join(
                [
                    f"[Doc {index}]",
                    f"Title: {title}",
                    f"URL: {url}",
                    f"Type: {object_type}",
                    f"Last updated: {last_updated}",
                    "Content:",
                    str(content)[:1800],
                ]
            )
        )

    reply_language = str(
        email_context.get("reply_language")
        or email_context.get("input_language")
        or "en"
    ).lower()

    if reply_language.startswith("de"):
        language_label = "German (de)"
        language_instruction = (
            "Write the entire staff email draft in German. "
            "Do not switch to English except for official programme names, "
            "URLs, source titles, or [Doc N] citations."
        )
    else:
        language_label = "English (en)"
        language_instruction = (
            "Write the entire staff email draft in English."
        )

    return f"""
REPLY LANGUAGE
--------------
{language_label}
{language_instruction}

INTERPRETED CONTEXT
-------------------
{chr(10).join(profile_lines) if profile_lines else "- No reliable profile details detected."}

TOPICS THAT MUST BE ANSWERED
----------------------------
{chr(10).join(topic_lines)}

{topic_evidence_section}OFFICIAL EVIDENCE
-----------------
{chr(10).join(evidence_blocks)}

Create one complete staff-ready email draft.

Important:
- Cover every listed topic.
- Answer only the topics listed under TOPICS THAT MUST BE ANSWERED.
- Evidence documents may contain information about other topics.
- Do not add application deadlines or application periods unless application_deadline is a listed topic.
- Do not add separate programme-duration, curriculum, language-of-instruction, study-format, admission-requirements, scholarship, or application-route information unless that topic is listed.
- For required_documents, document requirements and their directly necessary qualifiers are allowed.
- Use programme-specific evidence first.
- Use [Doc N] citations after factual claims.
- Do not make unsupported assumptions.
- Do not write a reference-link list.
- Do not write a disclaimer.
""".strip()
