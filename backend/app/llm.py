
import hashlib
import json
import time
from typing import Any

import litellm
from litellm import completion

from .config import settings


# --------------------------------------------------
# 1. Initialize LiteLLM in-memory cache
# --------------------------------------------------

try:
    litellm.enable_cache(type="local")
    CACHE_ENABLED = True
    print("LiteLLM local cache initialized successfully")

except Exception as exc:
    litellm.cache = None
    CACHE_ENABLED = False
    print(
        f"LiteLLM cache initialization failed: "
        f"{type(exc).__name__}: {exc}"
    )


# Additional response cache for accurate metadata
_RESPONSE_CACHE: dict[str, dict[str, Any]] = {}


# --------------------------------------------------
# 2. Generate a unique cache fingerprint
# --------------------------------------------------

def _fingerprint(model: str, messages: list[dict]) -> str:
    canonical = json.dumps(
        {
            "model": model,
            "messages": messages
        },
        sort_keys=True,
        ensure_ascii=False
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


# --------------------------------------------------
# 3. Parse failure simulation header
# --------------------------------------------------

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


# --------------------------------------------------
# 4. Extract token usage
# --------------------------------------------------

def _usage(response, messages):
    usage = getattr(response, "usage", None)

    prompt_tokens = (
        getattr(usage, "prompt_tokens", None)
        if usage else None
    )

    completion_tokens = (
        getattr(usage, "completion_tokens", None)
        if usage else None
    )

    if prompt_tokens is None:
        prompt_tokens = max(
            1,
            sum(
                len(str(message.get("content", "")))
                for message in messages
            ) // 4
        )

    if completion_tokens is None:
        response_text = (
            response.choices[0].message.content or ""
        )

        completion_tokens = max(
            1,
            len(response_text) // 4
        )

    return int(prompt_tokens), int(completion_tokens)


# --------------------------------------------------
# 5. Main LLM response generation with failover
# --------------------------------------------------

def generate_reply(
    messages: list[dict],
    simulate_failure: str | None = None
) -> tuple[str, dict]:

    # Gemini providers
    providers = [
        (settings.llm_model, key, f"key_{i + 1}")
        for i, key in enumerate(settings.llm_api_keys)
    ]

    # Groq fallback provider
    if settings.groq_api_key:
        providers.append(
            (
                settings.groq_model,
                settings.groq_api_key,
                "groq_1"
            )
        )

    if not providers:
        raise RuntimeError("No LLM API keys configured")

    start = time.perf_counter()

    # Failure simulation is enabled only when configured
    simulated = (
        _parse_simulation(simulate_failure)
        if settings.enable_failure_simulation
        else {}
    )

    last_error = None
    fallback_attempts = 0

    # Try each provider in sequence
    for model, api_key, key_id in providers:

        cache_key = _fingerprint(model, messages)

        # Check response cache first
        if cache_key in _RESPONSE_CACHE:

            cached = _RESPONSE_CACHE[cache_key]

            latency = max(
                0,
                int((time.perf_counter() - start) * 1000)
            )

            metadata = {
                "resolution_source": "LLM_CACHE",
                "model": model,
                "latency_ms": latency,
                "input_tokens": cached["input_tokens"],
                "output_tokens": cached["output_tokens"],
                "key_id": None,
                "fallback_attempts": fallback_attempts
            }

            return cached["reply"], metadata

        # Apply simulated provider failure
        status = simulated.get(
            key_id,
            simulated.get("*")
        )

        if status:

            last_error = RuntimeError(
                f"Simulated provider failure: HTTP {status}"
            )

            fallback_attempts += 1
            continue

        try:

            # Call the LLM provider
            response = completion(
                model=model,
                messages=messages,
                api_key=api_key,
                caching=CACHE_ENABLED,
                timeout=45,
                num_retries=0
            )

            reply = response.choices[0].message.content

            if not reply or not reply.strip():
                raise RuntimeError(
                    "Provider returned an empty response"
                )

            # Extract token usage
            input_tokens, output_tokens = _usage(
                response,
                messages
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
                "fallback_attempts": fallback_attempts
            }

            # Save response in the custom cache
            _RESPONSE_CACHE[cache_key] = {
                "reply": reply,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }

            return reply, metadata

        except Exception as exc:

            last_error = exc
            fallback_attempts += 1

            print(
                f"Provider {key_id} failed: "
                f"{type(exc).__name__}: {exc}"
            )

            continue

    # All providers failed
    raise RuntimeError(
        "all providers unavailable"
    ) from last_error
