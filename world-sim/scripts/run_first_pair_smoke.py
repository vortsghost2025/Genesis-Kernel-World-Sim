"""First-pair cognition transport smoke test.

Resolves the model provider from the environment via the existing
``resolve_provider()`` contract (fail-closed: OLLAMA_HOST, NVIDIA_API_KEY,
OPENROUTER_API_KEY, or GENESIS_FIRST_PAIR_BASE_URL), then makes exactly one
bounded raw chat completion and reports a sanitized result.

No canonical persistence, no state, no heartbeat, no ledger. This proves the
cognition transport is alive before any living-loop run.

Usage (from world-sim/):
    $env:OLLAMA_HOST = "http://localhost:11434"
    $env:GENESIS_FIRST_PAIR_MODEL = "qwen3.5:4b"
    python scripts/run_first_pair_smoke.py

NVIDIA switch (same script, zero code changes):
    $env:NVIDIA_API_KEY = "<key>"
    $env:GENESIS_FIRST_PAIR_MODEL = "<model id from the endpoint>"
    python scripts/run_first_pair_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

from openai import OpenAI

from backend.world.first_pair_cognition_model import (
    _client_api_key,
    resolve_provider,
    sanitize_provider_error,
)


def _safe_head(text: str, maximum: int = 120) -> str:
    cleaned = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in text)
    return cleaned[:maximum]


def main() -> int:
    try:
        config = resolve_provider()
    except Exception as exc:
        print(f"SMOKE=FAIL resolve_provider: {sanitize_provider_error(exc)}")
        return 1

    print(f"SMOKE_PROVIDER={config.provider_type}")
    print(f"SMOKE_BASE_URL={config.base_url}")
    print(f"SMOKE_MODEL={config.model}")
    print(f"SMOKE_API_KEY_SET={config.api_key is not None}")

    try:
        client = OpenAI(
            base_url=config.base_url,
            api_key=_client_api_key(config),
            timeout=60.0,
        )
        response = client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": "Reply with exactly one word: alive."}],
            max_tokens=1024,
            temperature=0.0,
        )
        content = response.choices[0].message.content
    except Exception as exc:
        print(f"SMOKE=FAIL model_call: {sanitize_provider_error(exc)}")
        return 1

    if not content or not content.strip():
        print("SMOKE=FAIL empty_response")
        return 1

    print(f"SMOKE_RESPONSE_HEAD={_safe_head(content)}")
    print("SMOKE=OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
