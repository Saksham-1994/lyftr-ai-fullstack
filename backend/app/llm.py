
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import litellm
from litellm import completion

from .config import settings


# Initialize LiteLLM disk cache
try:
    Path(settings.cache_dir).mkdir(parents=True, exist_ok=True)
    litellm.cache = litellm.Cache(
        type="disk",
        disk_cache_dir=settings.cache_dir
    )
    CACHE_ENABLED = True
except Exception:
    litellm.cache = None
    CACHE_ENABLED = False


_RESPONSE_CACHE: dict[str, dict[str, Any]] = {}


def _fingerprint(model: str, messages: list[dict]) -> str:
    canonical = json.dumps(
        {"model": model, "messages": messages},
        sort_keys=True,
        ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _parse_simulation(header: str | None) -> dict[str, int]:
    parsed = {}
    if not header:
        return parsed

    for item in header.split(","):
        if "=" not in item:
            continue
        key, value = item.strip().split("=", 1)
        try:
            status = int(value)
        except ValueError:
            continue
        if status in {429, 500, 502, 503}:
            parsed[key.strip()] = status

    return parsed


def _usage(response, messages):
    usage = getattr(response, "usage", None)
    prompt = getattr(usage, "prompt_tokens", None) if usage else None
    output = getattr(usage, "completion_tokens", None) if usage else None

    if prompt is None:
        prompt = max(
            1,
            sum(len(m.get("content", "")) for m in messages) // 4
        )

    if output is None:
        text = response.choices[0].message.content or ""
        output = max(1, len(text) // 4)

    return int(prompt), int(output)


def generate_reply(
    messages: list[dict],
    simulate_failure: str | None = None
) -> tuple[str, dict]:

    providers = [
        (settings.llm_model, key, f"key_{i + 1}")
        for i, key in enumerate(settings.llm_api_keys)
    ]

    if settings.groq_api_key:
        providers.append(
            (settings.groq_model, settings.groq_api_key, "groq_1")
        )

    if not providers:
        raise RuntimeError("No LLM API keys configured")

    start = time.perf_counter()

    simulated = (
        _parse_simulation(simulate_failure)
        if settings.enable_failure_simulation
        else {}
    )

    last_error = None
    fallback_attempts = 0

    for model, api_key, key_id in providers:
        cache_key = _fingerprint(model, messages)

        if cache_key in _RESPONSE_CACHE:
            cached = _RESPONSE_CACHE[cache_key]
            return cached["reply"], {
                "resolution_source": "LLM_CACHE",
                "model": model,
                "latency_ms": max(
                    0,
                    int((time.perf_counter() - start) * 1000)
                ),
                "input_tokens": cached["input_tokens"],
                "output_tokens": cached["output_tokens"],
                "key_id": None,
                "fallback_attempts": fallback_attempts,
            }

        status = simulated.get(key_id, simulated.get("*"))
        if status:
            last_error = RuntimeError(
                f"Simulated provider failure: HTTP {status}"
            )
            fallback_attempts += 1
            continue

        try:
            response = completion(
                model=model,
                messages=messages,
                api_key=api_key,
                caching=CACHE_ENABLED,
                timeout=45,
                num_retries=0,
            )

            reply = response.choices[0].message.content

            if not reply or not reply.strip():
                raise RuntimeError("Provider returned an empty response")

            input_tokens, output_tokens = _usage(
                response, messages
            )

            latency = max(
                1,
                int((time.perf_counter() - start) * 1000)
            )

            metadata = {
                "resolution_source": "LIVE_INFERENCE",
                "model": model,
                "latency_ms": latency,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "key_id": key_id,
                "fallback_attempts": fallback_attempts,
            }

            _RESPONSE_CACHE[cache_key] = {
                "reply": reply,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

            return reply, metadata

        except Exception:
            fallback_attempts += 1
            last_error = RuntimeError(
                f"Provider {key_id} unavailable"
            )
            continue

    raise RuntimeError("all providers unavailable") from last_error
