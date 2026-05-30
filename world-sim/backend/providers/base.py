"""
Provider interface for World Sim agents.

Supports mock responses and live NVIDIA NIM calls.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("world.provider")


class ProviderCallLog:
    """Structured provider call log — never includes secrets."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(
        self,
        provider: str,
        agent: str,
        tick: int,
        success: bool,
        latency_ms: float | None = None,
        error: str | None = None,
        model: str = "",
    ) -> None:
        """Record a provider call. Never logs API keys or auth headers."""
        entry = {
            "provider": provider,
            "agent": agent,
            "tick": tick,
            "model": model,
            "success": success,
            "latency_ms": latency_ms,
        }
        if error:
            entry["error"] = error
        self.calls.append(entry)
        logger.info(
            "provider_call: provider=%s agent=%s tick=%s model=%s success=%s latency_ms=%s",
            provider, agent, tick, model, success, latency_ms,
        )

    def summary(self) -> dict[str, Any]:
        """Return a summary of provider calls."""
        total = len(self.calls)
        successes = sum(1 for c in self.calls if c["success"])
        failures = total - successes
        latencies = [c["latency_ms"] for c in self.calls if c.get("latency_ms") is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        by_provider: dict[str, int] = {}
        by_agent: dict[str, int] = {}
        for c in self.calls:
            by_provider[c["provider"]] = by_provider.get(c["provider"], 0) + 1
            by_agent[c["agent"]] = by_agent.get(c["agent"], 0) + 1

        return {
            "total_calls": total,
            "successes": successes,
            "failures": failures,
            "avg_latency_ms": round(avg_latency, 1) if avg_latency else None,
            "by_provider": by_provider,
            "by_agent": by_agent,
        }

    def clear(self) -> None:
        """Clear the call log."""
        self.calls = []

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        """Return the n most recent calls."""
        return self.calls[-n:] if self.calls else []


# Global provider call log
call_log = ProviderCallLog()


class BaseProvider(ABC):
    """Abstract base for LLM providers."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def generate(self, prompt: str, agent: str, tick: int, world_state: dict[str, Any] | None = None) -> str:
        """Generate a response. Must log the call without secrets."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


class MockProvider(BaseProvider):
    """
    Mock provider — returns deterministic responses.
    Default for development and testing.
    """

    def __init__(self, name: str = "mock") -> None:
        super().__init__(name)
        self._call_count = 0

    def generate(self, prompt: str, agent: str, tick: int, world_state: dict[str, Any] | None = None) -> str:
        """Return a mock response. No external calls."""
        start = time.monotonic()
        self._call_count += 1

        response = json.dumps({
            "thought": f"[mock:{agent}:{tick}] Processing world state...",
            "action": f"{agent} performs a mock action for tick {tick}.",
        })

        elapsed_ms = (time.monotonic() - start) * 1000
        call_log.record(
            provider=self.name,
            agent=agent,
            tick=tick,
            success=True,
            latency_ms=round(elapsed_ms, 2),
        )
        return response

    @property
    def call_count(self) -> int:
        return self._call_count


class NvidiaNimProvider(BaseProvider):
    """
    NVIDIA NIM provider for live agent cognition.
    """

    def __init__(
        self,
        name: str = "nvidia_nim",
        api_key_env: str = "NVIDIA_NIM_KEY",
        model: str = "meta/llama-3.1-8b-instruct",
        base_url: str = "https://integrate.api.nvidia.com/v1",
        mode: str = "nim-live",
    ) -> None:
        super().__init__(name)
        self._api_key_env = api_key_env
        self._model = model
        self._base_url = base_url
        self._mode = mode
        self._call_count = 0

    def generate(self, prompt: str, agent: str, tick: int, world_state: dict[str, Any] | None = None) -> str:
        """Generate via NIM."""
        start = time.monotonic()
        self._call_count += 1

        import os
        api_key = os.environ.get(self._api_key_env, "")

        if self._mode == "nim-live":
            if not api_key:
                elapsed_ms = (time.monotonic() - start) * 1000
                call_log.record(
                    provider=self.name,
                    agent=agent,
                    tick=tick,
                    success=False,
                    latency_ms=round(elapsed_ms, 2),
                    error="No API key configured",
                    model=self._model,
                )
                return json.dumps({
                    "thought": f"[nim-no-key:{agent}:{tick}] No API key configured.",
                    "action": f"{agent} waits — no API key.",
                })

            return self._live_call(prompt, agent, tick, api_key, start)
        elif self._mode == "nim-dry-run":
            return self._dry_run(prompt, agent, tick, api_key, start)
        else:
            return self._mock_fallback(prompt, agent, tick, start)

    def _live_call(
        self, prompt: str, agent: str, tick: int, api_key: str, start: float
    ) -> str:
        """Make a live NIM API call."""
        try:
            payload = {
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 500,
                "response_format": {"type": "json_object"},
            }

            url = f"{self._base_url}/chat/completions"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {api_key}")

            with urllib.request.urlopen(req, timeout=60) as response:
                raw = response.read().decode("utf-8")
                result = json.loads(raw)

            choices = result.get("choices", [])
            if not choices:
                raise ValueError("No choices in NIM response")

            message = choices[0].get("message", {})
            content = message.get("content", "")

            elapsed_ms = (time.monotonic() - start) * 1000
            usage = result.get("usage", {})
            self._call_count += 1

            call_log.record(
                provider=self.name,
                agent=agent,
                tick=tick,
                success=True,
                latency_ms=round(elapsed_ms, 2),
                model=self._model,
            )

            logger.info(
                "NIM live call: agent=%s model=%s latency_ms=%.0f prompt_tokens=%s completion_tokens=%s",
                agent, self._model, elapsed_ms,
                usage.get("prompt_tokens"), usage.get("completion_tokens"),
            )

            return content

        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            call_log.record(
                provider=self.name,
                agent=agent,
                tick=tick,
                success=False,
                latency_ms=round(elapsed_ms, 2),
                error=f"Live call failed: {type(e).__name__}",
                model=self._model,
            )
            logger.error("NIM live call failed: agent=%s tick=%s error=%s", agent, tick, type(e).__name__)
            raise

    def _dry_run(
        self, prompt: str, agent: str, tick: int, api_key: str, start: float
    ) -> str:
        """Build real payload but don't send."""
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
        }

        elapsed_ms = (time.monotonic() - start) * 1000
        call_log.record(
            provider=self.name,
            agent=agent,
            tick=tick,
            success=True,
            latency_ms=round(elapsed_ms, 2),
            model=self._model,
        )

        logger.info(
            "NIM dry-run: agent=%s model=%s payload_chars=%d key_present=%s",
            agent, self._model, len(json.dumps(payload)), bool(api_key),
        )

        return json.dumps({
            "thought": f"[nim-dry-run:{agent}:{tick}] Payload built but not sent. Model: {self._model}",
            "action": f"{agent} performs a dry-run action for tick {tick}.",
        })

    def _mock_fallback(
        self, prompt: str, agent: str, tick: int, start: float
    ) -> str:
        """Fallback mock response."""
        elapsed_ms = (time.monotonic() - start) * 1000
        call_log.record(
            provider=self.name,
            agent=agent,
            tick=tick,
            success=True,
            latency_ms=round(elapsed_ms, 2),
            model=self._model,
        )
        return json.dumps({
            "thought": f"[nim-mock-fallback:{agent}:{tick}] {prompt[:30]}...",
            "action": f"{agent} performs a mock action for tick {tick}.",
        })

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def has_api_key(self) -> bool:
        """Check if API key is configured (without revealing it)."""
        import os
        key = os.environ.get(self._api_key_env, "")
        return bool(key)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def model(self) -> str:
        return self._model
