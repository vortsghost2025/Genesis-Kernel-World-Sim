"""Phase 10FQ / P0 Lightweight Provider Resolver.

Pure standard library: os, re, dataclasses.
Zero imports of openai, pydantic, httpx, or external frameworks.
Zero network calls.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    provider_type: str
    base_url: str
    model: str
    api_key: str | None = None


class ProviderError(Exception):
    pass


def _check_url(url: str) -> str:
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ProviderError(f"URL must start with http:// or https://: {url[:40]}")
    # Strip /v1 or /v1/ to avoid doubling
    url = re.sub(r"/v1/?$", "", url)
    return url + "/v1"


def resolve_provider(env: dict[str, str] | None = None) -> ProviderConfig:
    """Resolve model provider from environment. Never silently selects Ollama."""
    e = env if env is not None else os.environ
    base = e.get("GENESIS_FIRST_PAIR_BASE_URL", "").strip()
    key = e.get("GENESIS_FIRST_PAIR_API_KEY", "").strip()
    model = e.get("GENESIS_FIRST_PAIR_MODEL", "").strip()
    nv_key = e.get("NVIDIA_API_KEY", "").strip()
    or_key = e.get("OPENROUTER_API_KEY", "").strip()
    ollama_host = e.get("OLLAMA_HOST", "").strip()

    # --- Explicit base URL ---
    if base:
        if not model:
            raise ProviderError(
                "GENESIS_FIRST_PAIR_BASE_URL is set but GENESIS_FIRST_PAIR_MODEL is not set"
            )
        # localhost / 127.0.0.1 / [::1] may omit the API key
        url_lower = base.lower()
        is_local = any(h in url_lower for h in ("localhost", "127.0.0.1", "[::1]", "::1"))
        if not is_local and not key:
            raise ProviderError(
                "Remote GENESIS_FIRST_PAIR_BASE_URL requires GENESIS_FIRST_PAIR_API_KEY"
            )
        url = _check_url(base)
        return ProviderConfig("explicit_url", url, model, key or None)

    # --- NVIDIA ---
    if nv_key:
        if not model:
            raise ProviderError(
                "NVIDIA_API_KEY is set but GENESIS_FIRST_PAIR_MODEL is not set"
            )
        url = "https://integrate.api.nvidia.com/v1"
        return ProviderConfig("nvidia", url, model, nv_key)

    # --- OpenRouter ---
    if or_key:
        if not model:
            raise ProviderError(
                "OPENROUTER_API_KEY is set but GENESIS_FIRST_PAIR_MODEL is not set"
            )
        url = "https://openrouter.ai/api/v1"
        return ProviderConfig("openrouter", url, model, or_key)

    # --- Ollama ---
    if ollama_host:
        if not model:
            raise ProviderError(
                "OLLAMA_HOST is set but GENESIS_FIRST_PAIR_MODEL is not set"
            )
        url = _check_url(ollama_host)
        return ProviderConfig("ollama", url, model, None)

    # --- No provider ---
    raise ProviderError(
        "No usable provider configuration. Set one of: "
        "GENESIS_FIRST_PAIR_BASE_URL (+ GENESIS_FIRST_PAIR_MODEL, "
        "+ GENESIS_FIRST_PAIR_API_KEY for remote), "
        "NVIDIA_API_KEY (+ GENESIS_FIRST_PAIR_MODEL), "
        "OPENROUTER_API_KEY (+ GENESIS_FIRST_PAIR_MODEL), "
        "OLLAMA_HOST (+ GENESIS_FIRST_PAIR_MODEL)"
    )


def resolve_fallback_provider(primary: ProviderConfig, env: dict[str, str] | None = None) -> ProviderConfig | None:
    """Resolve an optional single fallback lane for graceful degradation.

    Reads ``GENESIS_FIRST_PAIR_FALLBACK_MODEL``. A ``:free`` model id is
    OpenRouter convention and rides the OpenRouter lane whenever an
    OpenRouter credential exists (10JH: it is invalid on NVIDIA direct,
    where it 404s); without one there is no viable lane and this
    returns ``None``. A non-``:free`` id keeps the legacy lanes: the
    other credentialled provider, NVIDIA first. An NVIDIA primary still
    falls back to OpenRouter (``OPENROUTER_API_KEY``).

    FREE-ONLY GUARD: an OpenRouter fallback model must be explicitly free
    (model id ending in ``:free``). A paid OpenRouter fallback fails closed
    here with ``ProviderError`` — it is never silently accepted. The NVIDIA
    fallback lane carries no such guard.

    Returns ``None`` when no fallback model is set or no second-lane
    credential exists. Credentials are never logged or persisted.
    """
    e = env if env is not None else os.environ
    model = e.get("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "").strip()
    if not model:
        return None
    nv_key = e.get("NVIDIA_API_KEY", "").strip()
    or_key = e.get("OPENROUTER_API_KEY", "").strip()

    if model.endswith(":free"):
        if not or_key:
            return None
        return ProviderConfig(
            "openrouter", "https://openrouter.ai/api/v1", model, or_key
        )
    if primary.provider_type != "nvidia" and nv_key:
        return ProviderConfig(
            "nvidia", "https://integrate.api.nvidia.com/v1", model, nv_key
        )
    if primary.provider_type != "openrouter" and or_key:
        if not model.endswith(":free"):
            raise ProviderError(
                f"fallback model {model!r} is on the OpenRouter lane but does "
                "not end with :free — refusing paid fallback"
            )
        return ProviderConfig(
            "openrouter", "https://openrouter.ai/api/v1", model, or_key
        )
    return None
