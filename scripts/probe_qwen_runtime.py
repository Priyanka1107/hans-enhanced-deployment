from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

BASE_URL = os.getenv("LITELLM_BASE_URL", "").rstrip("/")
CHAT_URL = (
    os.getenv("LITELLM_CHAT_URL", "").strip()
    or (f"{BASE_URL}/chat/completions" if BASE_URL else "")
)
API_KEY = os.getenv("LITELLM_API_KEY", "").strip()
MODEL = os.getenv("LITELLM_MODEL", "").strip()
VERIFY_TLS = os.getenv("LITELLM_VERIFY_TLS", "true").strip().lower() not in {
    "0", "false", "no", "off",
}


def _run_probe(label: str, enable_thinking):
    payload = {
        "model": MODEL,
        "stream": False,
        "temperature": 0.0,
        "messages": [
            {
                "role": "system",
                "content": "You are a concise diagnostic assistant.",
            },
            {
                "role": "user",
                "content": "Reply with exactly: OK",
            },
        ],
    }
    if enable_thinking is not None:
        payload["enable_thinking"] = enable_thinking

    started = time.perf_counter()
    with httpx.Client(
        timeout=httpx.Timeout(420.0, connect=30.0),
        verify=VERIFY_TLS,
        follow_redirects=True,
    ) as client:
        response = client.post(
            CHAT_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    elapsed = round(time.perf_counter() - started, 3)
    response.raise_for_status()
    data = response.json()

    usage = data.get("usage") or {}
    message = ((data.get("choices") or [{}])[0].get("message") or {})
    details = usage.get("completion_tokens_details") or {}

    result = {
        "label": label,
        "enable_thinking_sent": enable_thinking,
        "elapsed_seconds": elapsed,
        "model": data.get("model") or MODEL,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": details.get("reasoning_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "content": message.get("content"),
        "reasoning_content_chars": len(
            str(
                message.get("reasoning_content")
                or message.get("reasoning")
                or ""
            )
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    if not CHAT_URL or not API_KEY or not MODEL:
        raise RuntimeError(
            "LITELLM_CHAT_URL/LITELLM_BASE_URL, LITELLM_API_KEY and "
            "LITELLM_MODEL must be configured."
        )

    mode = os.getenv("HANS_QWEN_PROBE_MODE", "both").strip().lower()
    probes = []
    if mode in {"default", "both"}:
        probes.append(("provider-default", None))
    if mode in {"thinking-off", "both"}:
        probes.append(("thinking-off", False))

    for label, enable_thinking in probes:
        print(f"\n=== Qwen tiny probe: {label} ===")
        _run_probe(label, enable_thinking)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
