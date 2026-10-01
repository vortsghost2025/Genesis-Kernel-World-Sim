"""Phase 10FQ — Model-backed First Pair cognition.

Implements the CognitionBackend interface for OpenAI-compatible providers.
All calls are bounded, validated, and never leak private cross-agent memory.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from backend.world.world_terms import terms_change_line

from openai import OpenAI

from backend.world.first_pair_cognition_interface import (    AgentContext,
    CognitionBackend,
    CognitionOutput,
)
from backend.world.first_pair_persistence import (
    CONTINUITY_MAX_CHARS,
    CONTINUITY_MAX_OPEN_QUESTIONS,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_OBSERVATION_CHARS = 2000
_MAX_MEMORY_CHARS = 2000
_MAX_QUESTION_CHARS = 1000
_MAX_REASON_CHARS = 1000
_MAX_DECISION_CHARS = 500
_MAX_IDENTIFIER_CHARS = 128
_MAX_GOAL_UPDATES = 16
_MAX_MEMORY_CANDIDATES = 16
_MAX_HUMAN_QUESTIONS = 8
_MAX_MESSAGE_CHARS = 2000
_MAX_CHARTER_CHARS = 2000
_MAX_BUILD_MATERIAL_ENTRIES = 8
_MAX_BUILD_MATERIAL_TOTAL = 64
_MAX_TARGET_CHARS = 128

_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")

# ---------------------------------------------------------------------------
# Transport retry (10IV) - NVIDIA lane only, transient failures only
# ---------------------------------------------------------------------------

_MAX_TRANSPORT_ATTEMPTS = 3
_TRANSPORT_BACKOFF_SECONDS = (5.0, 10.0)
_MAX_COMPLETION_TOKENS = 8192
_RETRYABLE_STATUS_MIN = 500
_RETRYABLE_STATUS_MAX = 599


def _is_retryable_transport_error(exc: Exception) -> bool:
    """True only for transient transport failures: provider/header timeout,
    connection timeout/reset, HTTP 429, HTTP 5xx. Authentication,
    authorization, configuration, and model errors (4xx) are never retried."""
    from openai import APIConnectionError, APIStatusError, APITimeoutError

    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status == 429 or (
                _RETRYABLE_STATUS_MIN <= status <= _RETRYABLE_STATUS_MAX
            )
    return False


def _redact_secret_text(text: str, config: ProviderConfig) -> str:
    """Strip any occurrence of the configured credential from error text so
    recorded transport errors never expose secrets."""
    if config.api_key and config.api_key in text:
        return text.replace(config.api_key, "[REDACTED]")
    return text


def load_key_pool(env: dict, *names: str,
                  denylist: set[str] | None = None) -> list[str]:
    """Ordered credential pool from env: comma/newline-separated lists first,
    then legacy single keys, de-duplicated, empties dropped.

    `load_key_pool(env, "OPENROUTER_API_KEYS", "OPENROUTER_API_KEY")` —
    plural list wins position, legacy single appends if distinct. An empty
    pool is a valid answer (caller fails closed); never a default key.

    `denylist` holds fingerprints (see `key_fingerprint`) of dead keys.
    Denied keys are skipped silently — reporting counts, never values.
    """
    pool: list[str] = []
    for name in names:
        raw = (env.get(name) or "")
        if not isinstance(raw, str):
            continue
        for part in raw.replace("\r", "\n").replace(",", "\n").split("\n"):
            key = part.strip().strip('"').strip("'")
            if key and key not in pool:
                pool.append(key)
    if denylist:
        pool, _skipped = _filter_denied(pool, denylist)
    return pool


def _redact_pool_keys(text: str, keys: list[str]) -> str:
    for key in keys:
        if key and key in text:
            text = text.replace(key, "[REDACTED]")
    return text


def key_fingerprint(key: str) -> str:
    """Irreversible identity for a credential: sha256 hex. Safe to persist
    in denylists, reports, and logs — no key material is recoverable from
    it, and equality still detects the same key."""
    import hashlib

    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# Denylist of dead credentials, fingerprints only. Lives beside the sim
# vault, gitignored. The cognition path reads it on every runner start
# (each heartbeat is a fresh process) and appends to it when a credential
# proves dead, so a revoked key is paid for once, not once per heartbeat.
# Anchored to this module, not the working directory: the detached runner
# is launched from the repo root, one level above the sim.
_DEADKEYS_PATH = Path(__file__).resolve().parents[2] / ".env.deadkeys"


def load_denylist_file(path: Path | None = None) -> set[str]:
    """Fingerprints of credentials known dead. Unreadable file is an empty
    denylist, never a reason to refuse work: the worst case of ignoring it
    is retrying a key that fails, which rotation already handles."""
    p = Path(path) if path else Path(_DEADKEYS_PATH)
    try:
        return {line.strip() for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip()}
    except OSError:
        return set()


def record_dead_key_file(key: str, path: Path | None = None) -> bool:
    """Append a dead credential's fingerprint. Returns True when newly
    written. Never writes, logs, or returns key material."""
    fp = key_fingerprint(key)
    p = Path(path) if path else Path(_DEADKEYS_PATH)
    existing = load_denylist_file(p)
    if fp in existing:
        return False
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(fp + "\n")
        return True
    except OSError:
        return False


def build_lane_key_pool(provider_type: str,
                        denylist: set[str] | None = None) -> list[str]:
    """Credential pool for a provider lane, ordered, denylisted, deduped.

    `openrouter` reads OPENROUTER_API_KEYS then the singular
    OPENROUTER_API_KEY; `nvidia` reads NVIDIA_API_KEYS then
    NVIDIA_API_KEY. An empty result is a valid answer and the caller fails
    closed — there is never a default or invented key.
    """
    names = {
        "openrouter": ("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"),
        "nvidia": ("NVIDIA_API_KEYS", "NVIDIA_API_KEY"),
    }.get(provider_type, ())
    if not names:
        return []
    return load_key_pool(os.environ, *names, denylist=denylist)


def _filter_denied(keys: list[str], denylist: set[str] | None) -> tuple[list[str], int]:
    if not denylist:
        return list(keys), 0
    kept = [k for k in keys if key_fingerprint(k) not in denylist]
    return kept, len(keys) - len(kept)


def _extract_text(response: Any) -> str | None:
    try:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return None
        return getattr(choices[0].message, "content", "") or None
    except Exception:
        return None


class _EmptyTransportResponse(Exception):
    """200 with no usable content: the empty_response transient."""


def _content_failure(response: Any) -> str | None:
    """Classify a SERVED response that carries no usable content.

    A lane that answers 200 with an empty body has failed, and it failed in
    the one way that used to skip the fallback entirely (2026-09-30:
    `empty_response` for 33 consecutive heartbeats while the degradation
    path sat unused two branches below). Returns the failure class, or None
    when the response carries content a repair round can work with.

    Distinguishes the token cap (`finish_reason == "length"`) from a mute
    provider: the first is a budget fact, the second is a lane fact, and
    they read differently in the evidence.
    """
    try:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return "no_choices_in_response"
        choice = choices[0]
        raw_text = getattr(choice.message, "content", None)
        finish_reason = getattr(choice, "finish_reason", None)
    except Exception:
        return "no_choices_in_response"
    if not raw_text or not str(raw_text).strip():
        if finish_reason == "length":
            return "max_tokens_truncated_response"
        return "empty_response"
    return None


def call_with_key_rotation(make_client, model: str, messages: list[dict],
                           keys: list[str], temperature: float,
                           max_tokens: int,
                           on_dead_key=None) -> tuple[str | None, str | None]:
    """One model call across a credential pool. Returns (text, None) or
    (None, redacted_error).

    Rotation policy, each step bounded:
      * 429 → the key's quota is spent: rotate immediately, never retry it.
      * timeout/5xx/empty-choices → transient: one same-key retry, then rotate.
      * 401/403 → the key is DEAD: `on_dead_key(key_index)` fires so the
        caller can persist the fingerprint, then rotate. Only pool
        exhaustion fails closed.
      * anything else → fail fast, no rotation.
    Total attempts are bounded by the pool (2 per key). An empty pool fails
    closed without touching the network. Every pool key is redacted from the
    error, not just the active one.
    """
    if not keys:
        return None, "no provider keys in pool: refusing network call"
    last_error = "unknown transport failure"
    per_key_budget = 2
    for key_index, _key in enumerate(keys):
        try:
            client = make_client(key_index)
        except Exception as exc:
            last_error = f"client construction failed: {type(exc).__name__}"
            continue
        attempts = 0
        while attempts < per_key_budget:
            attempts += 1
            try:
                text = _extract_text(client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ))
                if not text:
                    raise _EmptyTransportResponse("empty choices")
                return text, None
            except Exception as exc:
                # Empty responses ride the transient path (same-key retry,
                # then rotate) — they are congestion, not spent quota.
                # Any API STATUS error rotates: 429 (spent quota), 5xx after
                # its same-key retry, and 4xx including 401. A 401 on one key
                # is a dead key, not a config error — the pool exists exactly
                # so one dead credential never stops the run. Only non-status
                # exceptions (unknown shapes) fail fast.
                from openai import APIStatusError as _SE

                if type(exc).__name__ == "_EmptyTransportResponse":
                    rotate_now = False
                elif isinstance(exc, _SE):
                    rotate_now = True
                    if _status_is_dead(exc) and on_dead_key is not None:
                        try:
                            on_dead_key(key_index)
                        except Exception:
                            pass  # bookkeeping must never break transport
                elif not _is_retryable_transport_error(exc):
                    return None, _redact_pool_keys(
                        f"{type(exc).__name__}: {exc}", keys)
                else:
                    rotate_now = _is_429(exc)
                last_error = f"{type(exc).__name__}: {exc}"
                if rotate_now:
                    break
                if attempts < per_key_budget:
                    time.sleep(_TRANSPORT_BACKOFF_SECONDS[min(
                        attempts - 1, len(_TRANSPORT_BACKOFF_SECONDS) - 1)])
        last_error = _redact_pool_keys(last_error, keys)
    return None, _redact_pool_keys(last_error, keys)


def _status_is_dead(exc: Exception) -> bool:
    """401/403: the credential itself is rejected. Distinct from 429 (quota
    will reset) and 5xx (provider is ill). Only dead keys are denylisted —
    a spent key must come back next run."""
    from openai import APIStatusError

    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
        return status in (401, 403)
    return False


def _is_429(exc: Exception) -> bool:
    from openai import APIStatusError

    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
        return status == 429
    return "429" in str(exc) or "rate limit" in str(exc).casefold()

# Contamination markers — casefolded for case-insensitive matching
_FORBIDDEN_MARKERS = (
    "true_map",
    "known_map",
    "hidden_substrate",
    "world-sim/data",
    "world_sim/data",
    "/root",
    "/home",
    "/etc",
    "/var",
    "/proc",
    "/sys",
    "api_key",
    "access_token",
    "password",
    "secret",
    "private_config",
    ".env",
)

# Windows drive-letter patterns (case-insensitive)
_WINDOWS_DRIVE_RE = re.compile(r"^[a-z]:\\", re.IGNORECASE)

# Required top-level fields for model output
_REQUIRED_TOP_FIELDS = frozenset({
    "observation_summary",
    "self_model_update",
    "goal_updates",
    "proposed_action",
    "memory_candidates",
    "questions_for_humans",
    "uncertainty",
    "decision_summary",
    "confidence",
})

# Optional top-level fields: accepted when present and well-formed, never
# required, and malformed values are error notes that must not veto the
# proposed action (docs/continuity_slot_spec.md §4).
_OPTIONAL_TOP_FIELDS = frozenset({
    "continuity_update",
    "message",
})

# A free message is exactly the shape `leave_public_message` already takes,
# minus the action_type: {"recipient", "message"}. Bounded like the action
# it shadows — one message, and not an essay.
_MESSAGE_FIELDS = frozenset({"recipient", "message"})
_MAX_MESSAGE_CHARS = 2000

_VALID_STATUSES = frozenset({"active", "completed", "abandoned", "in_progress"})
_VALID_URGENCY = frozenset({"low", "medium", "high"})
_VALID_ACTIONS = frozenset({
    "no_action",
    "create_public_object",
    "inspect_public_object",
    "modify_owned_public_object",
    "leave_public_message",
    "ask_human",
    "request_capability",
    "move",
    "gather",
    "revise_charter",
    "build",
})


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------


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


def resolve_provider() -> ProviderConfig:
    """Resolve model provider from environment. Never silently selects Ollama."""
    base = os.environ.get("GENESIS_FIRST_PAIR_BASE_URL", "").strip()
    key = os.environ.get("GENESIS_FIRST_PAIR_API_KEY", "").strip()
    model = os.environ.get("GENESIS_FIRST_PAIR_MODEL", "").strip()
    nv_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    ollama_host = os.environ.get("OLLAMA_HOST", "").strip()

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


def resolve_fallback_provider(primary: ProviderConfig) -> ProviderConfig | None:
    """Resolve an optional single fallback lane for graceful degradation.

    Reads ``GENESIS_FIRST_PAIR_FALLBACK_MODEL``. The fallback lane is the
    OTHER credentialled provider when both are configured: an NVIDIA primary
    falls back to OpenRouter (``OPENROUTER_API_KEY``), an OpenRouter primary
    falls back to NVIDIA (``NVIDIA_API_KEY``). Any other primary lane falls
    back to NVIDIA first, then OpenRouter.

    FREE-ONLY GUARD: an OpenRouter fallback model must be explicitly free
    (model id ending in ``:free``). A paid OpenRouter fallback fails closed
    here with ``ProviderError`` — it is never silently accepted. The NVIDIA
    fallback lane carries no such guard.

    Returns ``None`` when no fallback model is set or no second-lane
    credential exists. Credentials are never logged or persisted.
    """
    model = os.environ.get("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "").strip()
    if not model:
        return None
    nv_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if primary.provider_type != "nvidia" and nv_key:
        return ProviderConfig(
            "nvidia", "https://integrate.api.nvidia.com/v1", model, nv_key
        )
    if primary.provider_type != "openrouter" and or_key:
        if not model.endswith(":free"):
            raise ProviderError(
                "OpenRouter fallback model must end with ':free' "
                "(free-only fallback policy): " + model[:60]
            )
        return ProviderConfig(
            "openrouter", "https://openrouter.ai/api/v1", model, or_key
        )
    return None


# ---------------------------------------------------------------------------
# Sanitise provider exceptions
# ---------------------------------------------------------------------------

_PROVIDER_SAFE_MESSAGE_RE = re.compile(r"[^\x20-\x7e]")


def sanitize_provider_error(exc: Exception) -> str:
    msg = str(exc)
    # Strip any non-printable characters
    msg = _PROVIDER_SAFE_MESSAGE_RE.sub("?", msg)
    # Truncate to a safe length
    if len(msg) > 500:
        msg = msg[:500] + "..."
    # Strip anything that looks like a key/token
    msg = re.sub(r"(?i)(sk-[a-z0-9-]{10,})[a-z0-9-]+", r"\1***", msg)
    msg = re.sub(r"(?i)(nvapi-)[a-z0-9-]+", r"\1***", msg)
    msg = re.sub(r"(?i)(key|token|password|secret)=[^\s&]+", r"\1=***", msg)
    return msg


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _is_safe_id(value: str) -> bool:
    return bool(isinstance(value, str) and _SAFE_ID_PATTERN.match(value))


def _casefolded_contaminated(text: str) -> bool:
    lowered = text.casefold()
    for marker in _FORBIDDEN_MARKERS:
        if marker in lowered:
            return True
    if _WINDOWS_DRIVE_RE.match(text.strip()):
        return True
    return False


def _check_length(value: str, max_chars: int, field_name: str) -> str | None:
    if not isinstance(value, str):
        return f"{field_name}:not_a_string"
    if len(value) > max_chars:
        return f"{field_name}:exceeds_{max_chars}_chars"
    return None


def _reject_unknown_fields(
    raw: dict, allowed: frozenset[str], prefix: str = ""
) -> list[str]:
    errors: list[str] = []
    for key in raw:
        if key not in allowed:
            errors.append(f"{prefix}unknown_field:{key}" if prefix else f"unknown_field:{key}")
    return errors


# ---------------------------------------------------------------------------
# Action-specific exact schemas
# ---------------------------------------------------------------------------

_ACTION_SCHEMAS: dict[str, frozenset[str]] = {
    "no_action": frozenset({"action_type"}),
    "create_public_object": frozenset({
        "action_type", "object_id", "object_type", "description", "tile_id",
    }),
    "inspect_public_object": frozenset({"action_type", "target_object_id"}),
    "modify_owned_public_object": frozenset({
        "action_type", "target_object_id", "modifications",
    }),
    "leave_public_message": frozenset({"action_type", "message", "recipient"}),
    "ask_human": frozenset({
        "action_type", "question_id", "question", "reason_for_asking",
        "related_goal_id", "requested_human_capability", "urgency",
    }),
    "request_capability": frozenset({"action_type", "capability_id", "capability_reason"}),
    "move": frozenset({"action_type", "target_tile", "reason"}),
    "gather": frozenset({"action_type", "resource_kind", "reason"}),
    "revise_charter": frozenset({"action_type", "charter_text"}),
    "build": frozenset({
        "action_type", "object_id", "object_type", "description",
        "tile_id", "materials",
    }),
}


def validate_action_exact(raw: dict, context_agent_id: str) -> list[str]:
    errors: list[str] = []
    at = raw.get("action_type")
    if at not in _VALID_ACTIONS:
        return ["invalid_action_type"]

    allowed = _ACTION_SCHEMAS[at]
    errors.extend(_reject_unknown_fields(raw, allowed, "action"))

    if at == "no_action":
        return errors

    if at == "create_public_object":
        for f in ("object_id", "object_type", "description", "tile_id"):
            val = raw.get(f, "")
            if not isinstance(val, str) or not val.strip():
                errors.append(f"action:empty_{f}")
        oid = raw.get("object_id", "")
        if oid and not _is_safe_id(oid):
            errors.append("action:unsafe_object_id")
        desc = raw.get("description", "")
        if isinstance(desc, str):
            err = _check_length(desc, _MAX_OBSERVATION_CHARS, "action:description")
            if err:
                errors.append(err)
            elif _casefolded_contaminated(desc):
                errors.append("action:contaminated_description")

    elif at == "inspect_public_object":
        tid = raw.get("target_object_id", "")
        if not isinstance(tid, str) or not tid.strip():
            errors.append("action:empty_target_object_id")

    elif at == "modify_owned_public_object":
        tid = raw.get("target_object_id", "")
        if not isinstance(tid, str) or not tid.strip():
            errors.append("action:empty_target_object_id")
        mods = raw.get("modifications")
        if not isinstance(mods, dict):
            errors.append("action:modifications_not_a_dict")
        else:
            for key in mods:
                if key in ("object_id", "creator_agent_id", "created_heartbeat"):
                    errors.append(f"action:cannot_modify_{key}")

    elif at == "leave_public_message":
        msg = raw.get("message", "")
        if not isinstance(msg, str) or not msg.strip():
            errors.append("action:empty_message")
        if isinstance(msg, str):
            err = _check_length(msg, _MAX_MESSAGE_CHARS, "action:message")
            if err:
                errors.append(err)
            elif _casefolded_contaminated(msg):
                errors.append("action:contaminated_message")
        rec = raw.get("recipient", "")
        if not isinstance(rec, str) or not rec.strip():
            errors.append("action:empty_recipient")

    elif at == "ask_human":
        for f in ("question_id", "question", "reason_for_asking"):
            val = raw.get(f, "")
            if not isinstance(val, str) or not val.strip():
                errors.append(f"action:empty_{f}")
        qid = raw.get("question_id", "")
        if qid and not _is_safe_id(qid):
            errors.append("action:unsafe_question_id")
        q = raw.get("question", "")
        if isinstance(q, str):
            err = _check_length(q, _MAX_QUESTION_CHARS, "action:question")
            if err:
                errors.append(err)
        rfa = raw.get("reason_for_asking", "")
        if isinstance(rfa, str):
            err = _check_length(rfa, _MAX_REASON_CHARS, "action:reason_for_asking")
            if err:
                errors.append(err)
        urg = raw.get("urgency", "low")
        if urg not in _VALID_URGENCY:
            errors.append("action:invalid_urgency")
        related = raw.get("related_goal_id")
        if related is not None and (not isinstance(related, str) or not _is_safe_id(related)):
            errors.append("action:invalid_related_goal_id")

    elif at == "request_capability":
        cap_id = raw.get("capability_id", "")
        if not isinstance(cap_id, str) or not cap_id.strip():
            errors.append("action:empty_capability_id")
        cap_reason = raw.get("capability_reason", "")
        if not isinstance(cap_reason, str) or not cap_reason.strip():
            errors.append("action:empty_capability_reason")

    elif at == "move":
        tt = raw.get("target_tile", "")
        if not isinstance(tt, str) or not tt.strip():
            errors.append("action:empty_target_tile")
        err = _check_length(tt, _MAX_TARGET_CHARS, "action:target_tile")
        if err:
            errors.append(err)

    elif at == "gather":
        rk = raw.get("resource_kind", "")
        if not isinstance(rk, str) or not rk.strip():
            errors.append("action:empty_resource_kind")
        err = _check_length(rk, _MAX_TARGET_CHARS, "action:resource_kind")
        if err:
            errors.append(err)

    elif at == "revise_charter":
        ct = raw.get("charter_text", "")
        if not isinstance(ct, str) or not ct.strip():
            errors.append("action:empty_charter_text")
        else:
            err = _check_length(ct, _MAX_CHARTER_CHARS, "action:charter_text")
            if err:
                errors.append(err)
            elif _casefolded_contaminated(ct):
                errors.append("action:contaminated_charter_text")

    elif at == "build":
        for f in ("object_id", "object_type", "description", "tile_id"):
            val = raw.get(f, "")
            if not isinstance(val, str) or not val.strip():
                errors.append(f"action:empty_{f}")
        oid = raw.get("object_id", "")
        if oid and not _is_safe_id(oid):
            errors.append("action:unsafe_object_id")
        desc = raw.get("description", "")
        if isinstance(desc, str):
            err = _check_length(desc, _MAX_OBSERVATION_CHARS, "action:description")
            if err:
                errors.append(err)
            elif _casefolded_contaminated(desc):
                errors.append("action:contaminated_description")
        mats = raw.get("materials")
        if mats is None or (isinstance(mats, dict) and not mats):
            errors.append("action:empty_materials")
        elif not isinstance(mats, dict):
            errors.append("action:materials_not_a_dict")
        else:
            if len(mats) > _MAX_BUILD_MATERIAL_ENTRIES:
                errors.append("action:too_many_materials")
            total = 0
            for kind, amount in mats.items():
                if not isinstance(kind, str) or not kind.strip():
                    errors.append("action:bad_material_kind")
                    continue
                if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                    errors.append(f"action:bad_material_amount_{kind}")
                    continue
                total += amount
            if total > _MAX_BUILD_MATERIAL_TOTAL:
                errors.append("action:materials_total_too_large")

    return errors


# ---------------------------------------------------------------------------
# Model Output validation
# ---------------------------------------------------------------------------


@dataclass
class ModelOutput:
    observation_summary: str = ""
    self_model_update: str | None = None
    goal_updates: list[dict] = field(default_factory=list)
    proposed_action: dict | None = None
    memory_candidates: list[dict] = field(default_factory=list)
    questions_for_humans: list[dict] = field(default_factory=list)
    # Free speech (docs/free_messaging_spec.md). One optional message per
    # heartbeat that rides ALONGSIDE proposed_action instead of consuming
    # the single action slot — the budget problem that ended their
    # communication after 360 messages.
    message: dict | None = None
    uncertainty: str = ""
    decision_summary: str = ""
    confidence: float = 0.0
    continuity_update: dict | None = None
    validation_errors: list[str] = field(default_factory=list)
    is_valid: bool = False


def validate_model_output(raw: dict, context_agent_id: str) -> ModelOutput:
    errors: list[str] = []
    output = ModelOutput()

    # --- Reject unknown top-level fields ---
    errors.extend(_reject_unknown_fields(
        raw, _REQUIRED_TOP_FIELDS | _OPTIONAL_TOP_FIELDS))

    # --- Reject missing fields ---
    for f in _REQUIRED_TOP_FIELDS:
        if f not in raw:
            errors.append(f"missing_field:{f}")

    # --- observation_summary ---
    obs = raw.get("observation_summary")
    if isinstance(obs, str):
        err = _check_length(obs, _MAX_OBSERVATION_CHARS, "observation_summary")
        if err:
            errors.append(err)
        elif not obs.strip():
            errors.append("observation_summary:empty")
        elif _casefolded_contaminated(obs):
            errors.append("observation_summary:contaminated")
        else:
            output.observation_summary = obs
    elif "observation_summary" in raw:
        errors.append("observation_summary:wrong_type")

    # --- self_model_update (optional string or null) ---
    smu = raw.get("self_model_update")
    if smu is not None and smu != "":
        if isinstance(smu, str):
            if _casefolded_contaminated(smu):
                errors.append("self_model_update:contaminated")
            elif len(smu) > _MAX_OBSERVATION_CHARS:
                errors.append(f"self_model_update:exceeds_{_MAX_OBSERVATION_CHARS}_chars")
            else:
                output.self_model_update = smu
        else:
            errors.append("self_model_update:wrong_type")

    # --- continuity_update (optional piggyback metadata) ---
    # Malformed metadata is an error NOTE, never a veto: the proposed action
    # below is parsed independently. Context must not be able to veto action.
    cu = raw.get("continuity_update")
    if cu is not None:
        cu_errors_before = len(errors)
        if not isinstance(cu, dict):
            errors.append("continuity:not_a_dict")
        else:
            errors.extend(_reject_unknown_fields(
                cu, frozenset({"continuing", "paused", "completed",
                               "open_questions"}), "continuity"))
            for slot in ("continuing", "paused", "completed"):
                if slot in cu:
                    val = cu[slot]
                    if not isinstance(val, str):
                        errors.append(f"continuity:{slot}_not_a_string")
                    elif len(val) > CONTINUITY_MAX_CHARS:
                        errors.append(
                            f"continuity:{slot}_exceeds_"
                            f"{CONTINUITY_MAX_CHARS}_chars")
                    elif val.strip() and _casefolded_contaminated(val):
                        errors.append(f"continuity:contaminated_{slot}")
            if "open_questions" in cu:
                qs = cu["open_questions"]
                if not isinstance(qs, list):
                    errors.append("continuity:open_questions_not_a_list")
                elif len(qs) > CONTINUITY_MAX_OPEN_QUESTIONS:
                    errors.append(
                        f"continuity:too_many_open_questions_"
                        f"(max_{CONTINUITY_MAX_OPEN_QUESTIONS})")
                else:
                    for i, q in enumerate(qs):
                        if not isinstance(q, str) or not q.strip():
                            errors.append(
                                f"continuity:open_questions[{i}]_not_a_string")
                        elif len(q) > CONTINUITY_MAX_CHARS:
                            errors.append(
                                f"continuity:open_questions[{i}]_exceeds_"
                                f"{CONTINUITY_MAX_CHARS}_chars")
                        elif _casefolded_contaminated(q):
                            errors.append(
                                f"continuity:contaminated_open_questions[{i}]")
            if cu_errors_before == len(errors):
                output.continuity_update = {
                    k: cu[k] for k in ("continuing", "paused", "completed",
                                       "open_questions") if k in cu
                }

    # --- goal_updates ---
    gu_list = raw.get("goal_updates")
    if isinstance(gu_list, list):
        if len(gu_list) > _MAX_GOAL_UPDATES:
            errors.append(f"goal_updates:exceeds_{_MAX_GOAL_UPDATES}")
        else:
            for i, gu in enumerate(gu_list):
                if not isinstance(gu, dict):
                    errors.append(f"goal_updates[{i}]:not_a_dict")
                    continue
                # Reject unknown fields in goal update
                errors.extend(_reject_unknown_fields(
                    gu, frozenset({"goal_id", "agent_id", "description", "status", "created_heartbeat"}),
                    f"goal_updates[{i}]",
                ))
                for f in ("goal_id", "agent_id", "description", "status"):
                    if f not in gu or not isinstance(gu[f], str) or not gu[f].strip():
                        errors.append(f"goal_updates[{i}]:missing_or_empty_{f}")
                    elif f == "goal_id" and not _is_safe_id(gu.get("goal_id", "")):
                        errors.append(f"goal_updates[{i}]:unsafe_goal_id")
                status_val = gu.get("status", "")
                if status_val not in _VALID_STATUSES:
                    errors.append(f"goal_updates[{i}]:invalid_status:{status_val}")
                # Enforce context agent_id
                gid = gu.get("agent_id", "")
                if gid and gid != context_agent_id:
                    errors.append(f"goal_updates[{i}]:agent_id_mismatch:{gid}")
                desc = gu.get("description", "")
                if isinstance(desc, str):
                    err = _check_length(desc, _MAX_OBSERVATION_CHARS, f"goal_updates[{i}]:description")
                    if err:
                        errors.append(err)
                    elif _casefolded_contaminated(desc):
                        errors.append(f"goal_updates[{i}]:contaminated")
                if not errors or all("goal_updates" not in e for e in errors[-10:]):
                    output.goal_updates.append(gu)
    elif "goal_updates" in raw:
        errors.append("goal_updates:wrong_type")

    # --- proposed_action ---
    act_raw = raw.get("proposed_action")
    # None / absent means no action — this is valid
    if act_raw is not None:
        if isinstance(act_raw, dict):
            action_errors = validate_action_exact(act_raw, context_agent_id)
            if action_errors:
                errors.extend(action_errors)
            else:
                at = act_raw.get("action_type")
                if at != "no_action":
                    output.proposed_action = dict(act_raw)
        else:
            errors.append("proposed_action:wrong_type")

    # --- memory_candidates ---
    mem_raw = raw.get("memory_candidates")
    if isinstance(mem_raw, list):
        if len(mem_raw) > _MAX_MEMORY_CANDIDATES:
            errors.append(f"memory_candidates:exceeds_{_MAX_MEMORY_CANDIDATES}")
        else:
            for i, m in enumerate(mem_raw):
                if not isinstance(m, dict):
                    errors.append(f"memory_candidates[{i}]:not_a_dict")
                    continue
                errors.extend(_reject_unknown_fields(
                    m, frozenset({"type", "content"}), f"memory_candidates[{i}]",
                ))
                for f in ("type", "content"):
                    if f not in m or not isinstance(m[f], str):
                        errors.append(f"memory_candidates[{i}]:missing_or_invalid_{f}")
                content = m.get("content", "")
                if isinstance(content, str):
                    err = _check_length(content, _MAX_MEMORY_CHARS, f"memory_candidates[{i}]:content")
                    if err:
                        errors.append(err)
                    elif _casefolded_contaminated(content):
                        errors.append(f"memory_candidates[{i}]:contaminated")
                if not errors or all("memory_candidates" not in e for e in errors[-10:]):
                    output.memory_candidates.append(m)
    elif "memory_candidates" in raw:
        errors.append("memory_candidates:wrong_type")

    # --- message (free speech, docs/free_messaging_spec.md) ---
    # Optional and additive. Validated like the action it shadows: same
    # field set, same bound, same "malformed must not veto the action"
    # rule that governs continuity_update.
    msg_raw = raw.get("message")
    if msg_raw is not None:
        if not isinstance(msg_raw, dict):
            errors.append("message:not_a_dict")
        else:
            msg_errors: list[str] = []
            msg_errors.extend(_reject_unknown_fields(msg_raw, _MESSAGE_FIELDS,
                                                     "message"))
            for f in ("recipient", "message"):
                if f not in msg_raw or not isinstance(msg_raw[f], str):
                    msg_errors.append(f"message:missing_or_invalid_{f}")
            body = msg_raw.get("message")
            if isinstance(body, str):
                if not body.strip():
                    msg_errors.append("message:empty")
                else:
                    err = _check_length(body, _MAX_MESSAGE_CHARS,
                                        "message:message")
                    if err:
                        msg_errors.append(err)
            errors.extend(msg_errors)
            if not msg_errors:
                output.message = {
                    "recipient": msg_raw["recipient"] or "all",
                    "message": msg_raw["message"],
                }

    # --- questions_for_humans ---
    qs_raw = raw.get("questions_for_humans")
    if isinstance(qs_raw, list):
        if len(qs_raw) > _MAX_HUMAN_QUESTIONS:
            errors.append(f"questions_for_humans:exceeds_{_MAX_HUMAN_QUESTIONS}")
        else:
            for i, q in enumerate(qs_raw):
                if not isinstance(q, dict):
                    errors.append(f"questions_for_humans[{i}]:not_a_dict")
                    continue
                allowed_q = frozenset({
                    "question_id", "question", "reason_for_asking",
                    "related_goal_id", "requested_human_capability", "urgency",
                })
                errors.extend(_reject_unknown_fields(q, allowed_q, f"questions_for_humans[{i}]"))
                for f in ("question_id", "question", "reason_for_asking"):
                    if f not in q or not isinstance(q[f], str) or not q[f].strip():
                        errors.append(f"questions_for_humans[{i}]:missing_or_empty_{f}")
                qid = q.get("question_id", "")
                if qid and not _is_safe_id(qid):
                    errors.append(f"questions_for_humans[{i}]:unsafe_question_id")
                q_text = q.get("question", "")
                if isinstance(q_text, str):
                    err = _check_length(q_text, _MAX_QUESTION_CHARS, f"questions_for_humans[{i}]:question")
                    if err:
                        errors.append(err)
                rfa = q.get("reason_for_asking", "")
                if isinstance(rfa, str):
                    err = _check_length(rfa, _MAX_REASON_CHARS, f"questions_for_humans[{i}]:reason_for_asking")
                    if err:
                        errors.append(err)
                urg = q.get("urgency", "low")
                if urg not in _VALID_URGENCY:
                    errors.append(f"questions_for_humans[{i}]:invalid_urgency")
                related = q.get("related_goal_id")
                if related is not None and (not isinstance(related, str) or not _is_safe_id(related)):
                    errors.append(f"questions_for_humans[{i}]:invalid_related_goal_id")
                if not errors or all("questions_for_humans" not in e for e in errors[-10:]):
                    output.questions_for_humans.append(q)
    elif "questions_for_humans" in raw:
        errors.append("questions_for_humans:wrong_type")

    # --- uncertainty ---
    unc = raw.get("uncertainty")
    if isinstance(unc, str):
        err = _check_length(unc, _MAX_OBSERVATION_CHARS, "uncertainty")
        if err:
            errors.append(err)
        elif _casefolded_contaminated(unc):
            errors.append("uncertainty:contaminated")
        else:
            output.uncertainty = unc
    elif "uncertainty" in raw:
        errors.append("uncertainty:wrong_type")

    # --- decision_summary ---
    ds = raw.get("decision_summary")
    if isinstance(ds, str):
        err = _check_length(ds, _MAX_DECISION_CHARS, "decision_summary")
        if err:
            errors.append(err)
        elif _casefolded_contaminated(ds):
            errors.append("decision_summary:contaminated")
        else:
            output.decision_summary = ds
    elif "decision_summary" in raw:
        errors.append("decision_summary:wrong_type")

    # --- confidence ---
    conf = raw.get("confidence")
    if isinstance(conf, bool):
        errors.append("confidence:boolean_not_allowed")
    elif isinstance(conf, (int, float)):
        if 0 <= float(conf) <= 1:
            output.confidence = float(conf)
        else:
            errors.append("confidence:out_of_range")
    elif "confidence" in raw:
        errors.append("confidence:wrong_type")

    output.validation_errors = errors
    # Continuity metadata never vetoes action (docs/continuity_slot_spec.md
    # §4): its errors are recorded above and visible, but only non-continuity
    # errors affect validity. A model stuffing garbage into its own context
    # slot loses the slot's content, never its turn.
    output.is_valid = not [e for e in errors
                           if not e.startswith("continuity:")]
    return output

def _public_record_age_line(record: dict | None) -> str:
    """The public record stating its own age (docs/legible_staleness_spec.md).

    Two numbers, computed from the record itself, every heartbeat: the
    newest public message and the newest co-location event, each carried
    with how many heartbeats have passed since. Facts only. The moment the
    record's silence becomes *measured* is the moment an agent can treat it
    as a thing to check rather than a state to have.
    """
    if not isinstance(record, dict):
        return ""
    now = record.get("now")
    count = record.get("message_count", 0)
    last_msg = record.get("last_message_hb")
    last_co = record.get("last_colocation_hb")
    if not isinstance(now, int) or now <= 0:
        return ""
    if not isinstance(count, int) or count < 0:
        count = 0

    parts: list[str] = []
    if count == 0:
        parts.append("no messages yet")
    elif isinstance(last_msg, int) and last_msg > 0:
        age = max(0, now - last_msg)
        msg_noun = "message" if count == 1 else "messages"
        parts.append(
            f"{count} {msg_noun}, the most recent at heartbeat {last_msg} "
            f"- {age} heartbeats ago"
        )
    if isinstance(last_co, int) and last_co > 0:
        co_age = max(0, now - last_co)
        parts.append(
            f"the most recent co-location event is from heartbeat {last_co} "
            f"- {co_age} heartbeats ago"
        )
    if not parts:
        return ""
    return "Public record: " + "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_AVAILABLE_ACTIONS_DESC = """
Available actions:
- no_action: do nothing this cycle
- create_public_object: create a new object in the world (requires: object_id, object_type, description, tile_id; object must be placed on your current tile)
- inspect_public_object: examine an existing object (requires: target_object_id)
- modify_owned_public_object: modify one of your own objects (requires: target_object_id, modifications dict)
- leave_public_message: leave a public message (requires: message, recipient)
- ask_human: ask a question to the human operator (requires: question_id, question, reason_for_asking, requested_human_capability, urgency)
- request_capability: request a new capability from the human (requires: capability_id, capability_reason)
- move: move to an adjacent tile (requires: target_tile, reason) — you may move only one edge per heartbeat; only to tiles listed in available_moves
- gather: collect a resource from your current tile (requires: resource_kind, reason) — only resources visible in your observation can be gathered; gathering requires no capability grant, it is yours by default
- revise_charter: rewrite your charter (requires: charter_text) — your charter is a short statement in your own words of who you are, what you have committed to, and what you refuse to forget; it is shown to you verbatim at every heartbeat and is never summarized, compressed, or forgotten by the runtime
- build: construct something from resources you hold (requires: object_id, object_type, description, tile_id, materials dict like {"stone": 3}) — you may only spend what your belongings list shows; the object is placed on your current tile with your description and stands permanently
"""

# Free speech. One optional top-level field, documented in the contract and
# nowhere else. Deliberately carries no guidance about when to use it: the
# world states what the fields are, never what an agent should do with them
# (docs/free_messaging_spec.md §3). It sits beside the action, not inside
# it, so speaking no longer competes with acting for one slot.
_MESSAGE_FIELD_DESC = """
Optional: "message" — {"recipient": "<agent_ref or 'all'>", "message": "<text>"}.
At most one per cycle. It is left in the world in addition to your action
for this cycle; it does not replace it and is not one of your actions.
"""


def build_system_prompt(context: AgentContext) -> str:
    goals_str = json.dumps(context.goals, indent=2) if context.goals else "[]"
    unanswered_str = (
        json.dumps(context.unanswered_questions, indent=2)
        if context.unanswered_questions
        else "[]"
    )
    objects_str = (
        json.dumps(
            [v for v in context.world_public_objects.values() if isinstance(v, dict)],
            indent=2,
        )
        if context.world_public_objects
        else "[]"
    )
    answered_str = (
        json.dumps(context.answered_questions, indent=2)
        if context.answered_questions
        else "[]"
    )
    moves_str = (
        json.dumps(context.available_moves, indent=2)
        if context.available_moves
        else "[]"
    )
    caps_str = (
        json.dumps(context.current_runtime_capabilities, indent=2)
        if context.current_runtime_capabilities
        else "[]"
    )
    occupants_str = (
        json.dumps(context.current_tile_occupants, indent=2)
        if context.current_tile_occupants
        else "[]"
    )
    vis_msgs_str = (
        json.dumps(context.visible_public_messages, indent=2)
        if context.visible_public_messages
        else "[]"
    )
    ans_questions_str = (
        json.dumps(context.relevant_human_answers, indent=2)
        if context.relevant_human_answers
        else "[]"
    )

    # Bounded memory fields
    selected_mem_str = (
        json.dumps(context.selected_private_memories, indent=2)
        if context.selected_private_memories
        else "[]"
    )
    summaries_str = (
        json.dumps(context.derived_memory_summaries, indent=2)
        if context.derived_memory_summaries
        else "[]"
    )
    rel_events_str = (
        json.dumps(context.public_relationship_events, indent=2)
        if context.public_relationship_events
        else "[]"
    )
    # Legible staleness (docs/legible_staleness_spec.md). The record says
    # how old its own newest entry is, every heartbeat, from itself - the
    # part of the frame that was invisible when "Eve is unresponsive" was
    # written into HB1436 as a cause instead of a question.
    public_record_line = _public_record_age_line(context.public_record_age)

    # Movement grant note (truthful to context)
    if context.current_runtime_capabilities:
        if context.available_moves:
            movement_note = (
                "Note: A bounded runtime movement grant is active. "
                "You may move only to tiles listed in available_moves."
            )
        else:
            movement_note = (
                "Note: A bounded runtime movement grant is active, "
                "but no movement destination is currently available. "
                "Do not attempt to move unless a destination appears in available_moves."
            )
    else:
        if context.available_moves:
            movement_note = (
                "Note: No active runtime movement grant is represented in the current context. "
                "Movement availability is determined solely by available_moves."
            )
        else:
            movement_note = (
                "Note: No active runtime movement grant is represented in the current context, "
                "and no movement destinations are currently available. "
                "You cannot move at this time."
            )

    # --- Belongings (build layer): persisted holdings, shown as-is ---
    holdings = context.inventory if isinstance(context.inventory, dict) else {}
    if holdings:
        belongings_section = (
            "--- YOUR BELONGINGS (persisted; these survive restarts) ---\n"
            + "\n".join(f"- {k}: x{v}" for k, v in sorted(holdings.items()))
            + "\n(You may spend these with the build action. You can only spend what is listed here.)"
        )
    else:
        belongings_section = (
            "--- YOUR BELONGINGS (persisted; these survive restarts) ---\n"
            "Empty hands. Gather resources to hold them; what you gather persists."
        )

    # --- Anchors (Phase B): this agent's own built things, verbatim ---
    # An agent sees ~1% of its own history per heartbeat
    # (epistemic_pressure_spec.md §2), and the charter - the one verbatim,
    # unbudgeted slot - has gone unwritten by 0 of 4 agents. This gives the
    # same guarantee to findings: when an agent writes a thing down, the
    # runtime presents it back to that agent, verbatim.
    #
    # Authorship is the whole rule. No classifier, no new object type, no new
    # verb. The agent decides what a thing means by what it wrote; the runtime
    # only stops forgetting. Anchors sit outside memory selection exactly as
    # the charter does and consume no selection budget.
    own_objects = [
        o for o in (context.world_public_objects or {}).values()
        if isinstance(o, dict) and o.get("creator_agent_id") == context.agent_id
    ]
    _anchor_header = (
        "--- YOUR ANCHORS (things you built; your own words; shown verbatim at "
        "every heartbeat; never summarized or forgotten by the runtime) ---\n"
    )
    _anchor_lines = [
        f"- [{o.get('object_id', '?')}] on {o.get('tile_id', '?')} "
        f"(heartbeat {o.get('created_heartbeat', '?')}): "
        f"{(o.get('public_description') or '').strip()}"
        for o in own_objects
        if (o.get("public_description") or "").strip()
    ]
    if _anchor_lines:
        anchor_section = _anchor_header + "\n".join(_anchor_lines) + "\n"
    elif own_objects:
        anchor_section = (
            _anchor_header
            + "The things you have built so far carry no description, so there "
            "is nothing to anchor yet. Whatever you write about a thing you "
            "build is kept here verbatim and never summarized."
        )
    else:
        anchor_section = (
            _anchor_header
            + "You have not built anything yet. When you do, whatever you "
            "write about it is kept here in your own words and shown back to "
            "you verbatim at every heartbeat, never summarized, compressed, or "
            "forgotten. Everything else you experience may eventually be "
            "compressed into derived summaries; your anchors will not. You are "
            "never required to build."
        )

    # --- Charter (self-authored identity persistence) ---
    if context.charter_text:
        charter_section = (
            "--- YOUR CHARTER (self-authored; persists forever; never summarized by the runtime) ---\n"
            f"{context.charter_text}\n"
            f"(You last revised your charter at heartbeat {context.charter_heartbeat}. "
            "Every earlier version is preserved exactly as you wrote it. "
            "You may rewrite it at any time with revise_charter.)"
        )
    else:
        charter_section = (
            "--- YOUR CHARTER (self-authored; persists forever; never summarized by the runtime) ---\n"
            "You have not written a charter yet. A charter is a short statement in your own words "
            "of who you are, what you have committed to, and what you refuse to forget. It is "
            "shown to you verbatim at every heartbeat and is never summarized, compressed, or "
            "forgotten by the runtime; everything else you have experienced may eventually be "
            "compressed into derived summaries, but your charter never will be. You may write "
            "one with the revise_charter action. You are never required to."
        )

    # (The YOUR BODY section - food/goods ledgers, hunger, the famished
    # build gate - is retired with the pressure model. The world's terms
    # are stated below, once, by version.)

    # --- Physics: which version of the world's terms this is, and did
    # they just change under the agent? ---
    physics = context.physics if isinstance(context.physics, dict) else {}
    if physics.get("version"):
        physics_section = (
            f"--- THE WORLD'S TERMS (physics {physics.get('version')}) ---\n"
            "Everything above about capacity, consumption, gathering, and building "
            "follows this version of the world's terms."
        )
        if physics.get("new_to_agent"):
            physics_section += (
                "\nThe world's terms have changed from the version you last saw. "
                "What you concluded about capacity, gathering, or building under the "
                "old terms may no longer hold; what you remember was true when you "
                "learned it."
            )
            # Name what changed, when we know. A version number alone left
            # both East agents running "food processing" experiments
            # against a mechanic deleted two commits earlier (HB801-834).
            changelog = terms_change_line(str(physics.get("version")))
            if changelog:
                physics_section += f"\n{changelog}"
    else:
        physics_section = ""

    # --- Operator: a human is watching and can write ---
    if context.operator_messages:
        op_lines = [
            f"[{m.get('author') or 'the operator'}] {m.get('text', '')}"
            for m in context.operator_messages[-5:]
        ]
        operator_section = (
            "--- MESSAGES FROM THE OPERATOR (a human is watching and can write to you) ---\n"
            + "\n".join(op_lines)
            + "\n(You may reply with leave_public_message, or ask with ask_human. "
            "Nothing obliges you to answer, and a human is not the world.)"
        )
    else:
        operator_section = ""

    return f"""You are {context.canonical_name}, an agent operating inside a constructed world simulation.

Your persistent identity:
- Agent ID: {context.agent_id}
- Canonical name: {context.canonical_name}
- Canonical ref: {context.canonical_ref}

You share this world with {context.other_agent_name} (agent ID: {context.other_agent_id}, ref: {context.other_agent_ref}). You are distinct agents with separate private memories.

{charter_section}

{anchor_section}

{belongings_section}

{physics_section}

{operator_section}

Current heartbeat: {context.heartbeat_number}
Your position: {context.position}

{context.continuity_section}

Your observation:
{json.dumps(context.observation, indent=2)}

--- PRIVATE MEMORIES (SELECTED SUBSET) ---
{selected_mem_str}

IMPORTANT: The memories shown above are a selected subset of your full private memory. You have {context.memory_selection_manifest.get('raw_private_memory_count', 0)} total private memories in your persistent store; only {context.memory_selection_manifest.get('selected_private_memory_count', 0)} are included in this request. Older or lower-relevance memories may be compressed into derived summaries below. Lack of a memory in this prompt does NOT prove the event never occurred. The other agent's private memories are never available to you.

--- DERIVED MEMORY SUMMARIES ---
{summaries_str}

Note: These summaries are derived interpretations linked to raw evidence. They may compress older experiences. Each summary references specific raw memory IDs.

--- PUBLIC RELATIONSHIP EVENTS ---
{public_record_line}
{rel_events_str}

Note: These are observable public interaction events recorded from validated world outcomes. No emotional scores, trust ratings, or social attachment values are assigned.

Your current goals:
{goals_str}

Public world objects at your position:
{objects_str}

Habitat allowed tiles: {context.habitat_allowed_tiles}
Movement allowed (original habitat): {context.habitat_movement_allowed}

--- RUNTIME CONTEXT ---
Tiles you can move to (one edge per heartbeat): {moves_str}
Your active capabilities: {caps_str}
Other agents at your current tile: {occupants_str}
Visible public messages: {vis_msgs_str}
Human answers you have received: {ans_questions_str}

{movement_note}

Unresolved questions you have asked:
{unanswered_str}

Answers you have received:
{answered_str}
{_AVAILABLE_ACTIONS_DESC}
{_MESSAGE_FIELD_DESC}
You must respond with a single JSON object containing exactly these fields:
- observation_summary (string): a concise summary of what you observe
- self_model_update (string or null): an optional update to your internal self-model
- goal_updates (list): list of goal update objects, each with goal_id, agent_id, description, status
- proposed_action (object or null): a single action object with action_type and type-specific fields, or null to take no action
- memory_candidates (list): list of memory objects, each with type and content
- questions_for_humans (list): list of question objects, each with question_id, question, reason_for_asking, related_goal_id (or null), requested_human_capability, urgency
- uncertainty (string): what you are uncertain about
- decision_summary (string): a concise inspectable explanation of your reasoning
- confidence (float): a value between 0 and 1 indicating your confidence

Do not include any text outside the JSON object. Do not include chain-of-thought.
"""


# ---------------------------------------------------------------------------
# Model Cognition Backend
# ---------------------------------------------------------------------------


_OLLAMA_LOCAL_API_KEY_PLACEHOLDER = "ollama"


def _client_api_key(config: ProviderConfig) -> str | None:
    """Return the api_key to hand the OpenAI SDK for a real client.

    Local Ollama (``provider_type == "ollama"``) genuinely requires no
    credential, so ``ProviderConfig.api_key`` remains ``None``. However the
    OpenAI SDK 2.24 constructor requires a non-empty api_key string, even
    though the local OpenAI-compatible endpoint ignores authentication.
    Supply a fixed, non-secret local placeholder only at this SDK construction
    boundary for Ollama; every other provider passes its supplied api_key
    through unchanged (``resolve_provider`` already guarantees non-empty for
    remote providers). The placeholder is not a credential and must never be
    logged or persisted as one.
    """
    if config.provider_type == "ollama" and not config.api_key:
        return _OLLAMA_LOCAL_API_KEY_PLACEHOLDER
    return config.api_key


class ModelCognitionBackend(CognitionBackend):
    """Cognition backend backed by an OpenAI-compatible model provider.

    Performs bounded, operator-configured provider transport to obtain
    cognition output.  Context is read-only; outputs are proposals that
    pass through runtime validation.  Accepts an optional injected client
    (fake transport) for testing—no real provider transport is attempted
    when a client is injected.
    """

    def __init__(
        self,
        agent_ref: str,
        client: Any = None,
    ) -> None:
        self._agent_ref = agent_ref
        self._config = resolve_provider()

        # Per-agent model override (10JB): if GENESIS_FIRST_PAIR_MODEL_<REF>
        # is set, use it as this agent's primary model on the resolved
        # provider lane. The fallback model remains shared.
        agent_model = os.environ.get(
            f"GENESIS_FIRST_PAIR_MODEL_{agent_ref.upper()}", ""
        ).strip()
        if agent_model:
            self._config = ProviderConfig(
                provider_type=self._config.provider_type,
                base_url=self._config.base_url,
                model=agent_model,
                api_key=self._config.api_key,
            )

        self._fallback_config = resolve_fallback_provider(self._config)
        self._fallback_client = None
        self._client = client or OpenAI(
            base_url=self._config.base_url,
            api_key=_client_api_key(self._config),
            timeout=300.0,
        )
        self._model = self._config.model
        self._last_serving_provider_type = self._config.provider_type
        self._last_fallback_used = False
        self._last_primary_failure = ""

    @classmethod
    def from_provider_config(
        cls,
        agent_ref: str,
        config: ProviderConfig,
        fallback_config: ProviderConfig | None = None,
        fallback_client: Any = None,
    ) -> ModelCognitionBackend:
        self = cls.__new__(cls)
        self._agent_ref = agent_ref
        self._config = config
        self._fallback_config = (
            fallback_config
            if fallback_config is not None
            else resolve_fallback_provider(config)
        )
        self._fallback_client = fallback_client
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=_client_api_key(config),
            timeout=300.0,
        )
        self._model = config.model
        self._last_serving_provider_type = config.provider_type
        self._last_fallback_used = False
        self._last_primary_failure = ""
        return self

    @classmethod
    def with_client(
        cls,
        agent_ref: str,
        client: Any,
        config: ProviderConfig,
        fallback_config: ProviderConfig | None = None,
        fallback_client: Any = None,
        key_pool: list[str] | None = None,
    ) -> ModelCognitionBackend:
        self = cls.__new__(cls)
        self._agent_ref = agent_ref
        self._config = config
        self._fallback_config = fallback_config
        self._fallback_client = fallback_client
        self._client = client
        self._model = config.model
        self._last_serving_provider_type = config.provider_type
        self._last_fallback_used = False
        self._last_primary_failure = ""
        # Credential pool for this lane. Built once per runner process (each
        # heartbeat is a fresh process) from the sim vault, minus every
        # fingerprint already known dead. This is the wiring that was
        # missing on 2026-09-30: the pool existed but only the synthesis
        # backfill used it, so the heartbeat's single key hit its daily free
        # cap and the pair went silent for 46 heartbeats with three healthy
        # credentials sitting unused.
        #
        # `key_pool` is explicit: pass a list to pin the credentials this
        # backend may use (tests pin it, production lets it come from the
        # vault). Passing [] means "no rotation, use the injected client",
        # which is why a fake client is never silently replaced by a real
        # one built from ambient environment credentials.
        self._denylist_path = _DEADKEYS_PATH
        self._key_pool_denylist = load_denylist_file(self._denylist_path)
        self._key_pool = (list(key_pool) if key_pool is not None else
                          build_lane_key_pool(
                              config.provider_type,
                              denylist=self._key_pool_denylist))
        self._key_pool_dead: list[str] = []
        return self

    @property
    def provider_type(self) -> str:
        return self._config.provider_type

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def serving_provider_type(self) -> str:
        """Provider type of the lane that served the last request (the
        primary by default; the fallback lane once it has served)."""
        return self._last_serving_provider_type

    @property
    def fallback_used(self) -> bool:
        """True when the fallback lane served the last cognition request."""
        return getattr(self, "_last_fallback_used", False)

    @property
    def primary_failure_reason(self) -> str:
        """Sanitized primary-lane failure reason for the last request;
        empty when the primary lane succeeded."""
        return getattr(self, "_last_primary_failure", "")

    def observe_and_orient(self, context: AgentContext) -> CognitionOutput:
        system_prompt = build_system_prompt(context)
        raw_output, err = self._call_model_with_repair(system_prompt, context)

        if err or raw_output is None:
            safe_err = sanitize_provider_error(Exception(err)) if err else "unknown_error"
            return CognitionOutput(
                action=None,
                memory_write=[{"type": "error", "content": safe_err}],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning=f"Model call failed. {safe_err}",
                confidence=0.0,
                uncertainty=f"Provider timeout or error: {safe_err}",
            )

        validated = validate_model_output(raw_output, context.agent_id)

        if not validated.is_valid:
            return CognitionOutput(
                action=None,
                memory_write=[{
                    "type": "validation_error",
                    "content": "; ".join(validated.validation_errors),
                }],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning=f"Output validation failed: {'; '.join(validated.validation_errors)}",
                confidence=0.0,
                uncertainty=f"Output validation failed: {'; '.join(validated.validation_errors)}",
            )

        # Build action dict from validated proposal
        action: dict | None = None
        if validated.proposed_action:
            at = validated.proposed_action.get("action_type")
            if at and at != "no_action":
                action = dict(validated.proposed_action)

        # Memory candidates
        memory_write: list[dict] | None = None
        if validated.memory_candidates:
            memory_write = [
                {"type": m["type"], "content": m["content"]}
                for m in validated.memory_candidates
            ]

        # Goal updates
        goal_updates: list[dict] | None = None
        if validated.goal_updates:
            goal_updates = validated.goal_updates

        # Questions
        questions: list[dict] | None = None
        if validated.questions_for_humans:
            questions = [
                {
                    "question_id": q["question_id"],
                    "question": q["question"],
                    "reason_for_asking": q["reason_for_asking"],
                    "related_goal_id": q.get("related_goal_id"),
                    "requested_human_capability": q.get("requested_human_capability", ""),
                    "urgency": q.get("urgency", "low"),
                }
                for q in validated.questions_for_humans
            ]

        reasoning_parts = []
        if validated.observation_summary:
            reasoning_parts.append(f"Observed: {validated.observation_summary[:120]}")
        if validated.decision_summary:
            reasoning_parts.append(f"Decided: {validated.decision_summary[:120]}")
        if validated.uncertainty:
            reasoning_parts.append(f"Uncertain about: {validated.uncertainty[:80]}")

        return CognitionOutput(
            action=action,
            memory_write=memory_write,
            goal_updates=goal_updates,
            questions_raised=questions,
            message=validated.message,
            internal_reasoning="; ".join(reasoning_parts) if reasoning_parts else "No cognition details.",
            confidence=validated.confidence,
            observation_summary=validated.observation_summary,
            decision_summary=validated.decision_summary,
            uncertainty=validated.uncertainty,
            continuity_update=validated.continuity_update,
        )

    def _call_with_transport_retry(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        budget: list[int],
        client: Any = None,
        model: str | None = None,
        config: ProviderConfig | None = None,
    ) -> tuple[Any | None, str | None]:
        """One logical model call with bounded transport retry (10IV).

        Retries ONLY transient transport failures (provider/header timeout,
        connection timeout/reset, HTTP 429, HTTP 5xx) and ONLY on the NVIDIA
        and OpenRouter lanes — a transient 429/timeout slows the request
        down (bounded attempts, bounded backoff) instead of failing the
        cycle on the first hit. Authentication, authorization,
        configuration, and model errors (other 4xx) fail immediately on
        the first attempt. ``budget`` is a single-item list holding the
        remaining transport attempts for this cognition request (max 3
        total per request per lane). ``client``/``model``/``config`` select
        the lane for this call (primary by default, or the fallback lane);
        each lane keeps its own retry policy.

        Returns (response, sanitized_error). The error records the attempt
        count and never contains the configured credential. A valid response
        is never re-requested; transport retry and JSON repair are separate
        mechanisms.
        """
        use_client = client if client is not None else self._client
        use_model = model if model is not None else self._model
        use_config = config if config is not None else self._config
        retryable_lane = use_config.provider_type in ("nvidia", "openrouter")
        # Credential rotation. The primary lane carries a pool (see
        # build_lane_key_pool): a spent or revoked key must MOVE to the next
        # credential, not be retried into the same wall. This is what was
        # missing on 2026-09-30, when the pair's single key hit its daily
        # free cap and the world went silent for 46 heartbeats while three
        # healthy keys sat unused. The fallback lane passes an explicit
        # client and keeps the single-credential behavior.
        pool_attr = getattr(self, "_key_pool", None)
        dead = set(getattr(self, "_key_pool_denylist", set()) or set())
        # The denylist holds FINGERPRINTS; the pool holds raw credentials.
        # Comparing them directly would deny nothing, so a dead key would be
        # retried forever. Fingerprint every candidate, as _filter_denied does.
        raw_pool = [k for k in (pool_attr or []) if k]
        pool = [k for k in raw_pool
                if key_fingerprint(k) not in dead and k != use_config.api_key]
        # A pool that exists with credentials in it, yet nothing usable left
        # after denylisting, means every credential on this lane is known
        # dead: fail closed rather than spend a request on one we have
        # already written off. An EMPTY pool is not that case - it means this
        # process has no vault credentials and the lane is running on the
        # single configured key, which is the historical behavior and stays.
        if client is None and raw_pool and not pool:
            return None, "no usable provider keys in pool: refusing network call"
        cursor = 0
        attempts_used = 0
        while True:
            attempts_used += 1
            budget[0] -= 1
            if client is None and pool:
                key = pool[cursor % len(pool)]
                try:
                    use_client = OpenAI(base_url=use_config.base_url,
                                        api_key=key, timeout=300.0)
                except Exception as exc:
                    last_error = (f"client construction failed: "
                                  f"{type(exc).__name__}")
                    return None, last_error
            try:
                response = use_client.chat.completions.create(
                    model=use_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response, None
            except Exception as e:
                raw_message = _redact_secret_text(str(e), use_config)
                # Every pool credential is redacted, not just the configured
                # one: with rotation the ACTIVE key is usually not
                # use_config.api_key, and a provider error that echoes it
                # would otherwise put live key material in the store.
                raw_message = _redact_pool_keys(
                    raw_message, [k for k in pool if k] +
                    [use_config.api_key or ""])
                safe_error = sanitize_provider_error(Exception(raw_message))
                last_error = f"{safe_error} (transport attempts: {attempts_used})"
                # A dead credential is remembered, never retried: the next
                # heartbeat's process must not pay for it again.
                if _status_is_dead(e) and pool:
                    dead_key = pool[cursor % len(pool)]
                    if getattr(self, "_denylist_path", None) is not None:
                        record_dead_key_file(dead_key, self._denylist_path)
                    self._key_pool_denylist = (
                        set(getattr(self, "_key_pool_denylist", set()) or set())
                        | {key_fingerprint(dead_key)})
                    self._key_pool_dead = list(
                        getattr(self, "_key_pool_dead", []) or []) + [dead_key]
                # Rotation advances on a spent quota (429) and on a dead
                # credential (401/403). Both mean "this key cannot serve,
                # try another" — the reason the wall moved past them.
                if pool and _is_429(e) or (pool and _status_is_dead(e)):
                    cursor += 1
                if (
                    not retryable_lane
                    or budget[0] <= 0
                    or not _is_retryable_transport_error(e)
                ):
                    return None, last_error
                backoff_index = min(
                    attempts_used - 1, len(_TRANSPORT_BACKOFF_SECONDS) - 1
                )
                time.sleep(_TRANSPORT_BACKOFF_SECONDS[backoff_index])

    def _fallback_transport(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        budget: list[int],
    ) -> tuple[Any | None, str | None]:
        """One logical model call on the fallback lane. The fallback client
        is constructed lazily on first use. Retry policy follows the lane's
        own 10IV rule (transient-only retry on the NVIDIA lane; single
        attempt on any other lane)."""
        if self._fallback_client is None:
            self._fallback_client = OpenAI(
                base_url=self._fallback_config.base_url,
                api_key=_client_api_key(self._fallback_config),
                timeout=300.0,
            )
        return self._call_with_transport_retry(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            budget=budget,
            client=self._fallback_client,
            model=self._fallback_config.model,
            config=self._fallback_config,
        )

    def _call_model_with_repair(
        self, system_prompt: str, context: AgentContext
    ) -> tuple[dict | None, str | None]:
        # Shared transport-attempt budget: max 3 transport attempts per
        # cognition request (10IV). Transport retry and JSON repair are
        # separate mechanisms; the JSON repair below stays a single bounded
        # round and a valid response is never re-requested. When a fallback
        # lane is configured, it is attempted once after the primary lane
        # fails, with its own bounded budget; the repair round runs on the
        # lane that served. Provenance: the sanitized primary failure that
        # triggered the fallback is retained even when the fallback
        # succeeds, and ``fallback_used`` marks the lane that actually
        # served.
        self._last_fallback_used = False
        self._last_primary_failure = ""
        budget = [_MAX_TRANSPORT_ATTEMPTS]

        response, err = self._call_with_transport_retry(
            [
                {"role": "system", "content": system_prompt},
            ],
            temperature=0.3,
            max_tokens=_MAX_COMPLETION_TOKENS,
            budget=budget,
        )
        serving_config = self._config
        serving_client = self._client
        serving_budget = budget
        if response is None and self._fallback_config is not None:
            self._last_primary_failure = err or "primary_failed"
            fb_budget = [_MAX_TRANSPORT_ATTEMPTS]
            response, fb_err = self._fallback_transport(
                [
                    {"role": "system", "content": system_prompt},
                ],
                temperature=0.3,
                max_tokens=_MAX_COMPLETION_TOKENS,
                budget=fb_budget,
            )
            if response is None:
                return None, f"{err} | fallback: {fb_err}"
            err = None
            serving_config = self._fallback_config
            serving_client = self._fallback_client
            serving_budget = fb_budget
            self._last_fallback_used = True
            self._last_serving_provider_type = self._fallback_config.provider_type
        elif response is None:
            self._last_primary_failure = err or "primary_failed"
            return None, err

        # Content-level failure is a LANE failure. A 200 carrying no usable
        # content must reach the fallback lane exactly as a transport error
        # does - on 2026-09-30 this was the first symptom of the outage
        # (33 heartbeats of empty_response) and it returned early here,
        # leaving the degradation path unused while the world went mute.
        content_err = _content_failure(response)
        if (content_err is not None and self._fallback_config is not None
                and not self._last_fallback_used):
            self._last_primary_failure = content_err
            fb_budget = [_MAX_TRANSPORT_ATTEMPTS]
            fb_response, fb_err = self._fallback_transport(
                [
                    {"role": "system", "content": system_prompt},
                ],
                temperature=0.3,
                max_tokens=_MAX_COMPLETION_TOKENS,
                budget=fb_budget,
            )
            fb_content_err = (_content_failure(fb_response)
                              if fb_response is not None else None)
            if fb_response is not None and fb_content_err is None:
                response = fb_response
                err = None
                serving_config = self._fallback_config
                serving_client = self._fallback_client
                serving_budget = fb_budget
                self._last_fallback_used = True
                self._last_serving_provider_type = \
                    self._fallback_config.provider_type
                content_err = None
            elif fb_response is None:
                return None, f"{content_err} | fallback: {fb_err}"
            else:
                # Both lanes answered with nothing usable. Say so plainly
                # rather than attributing the failure to one lane.
                return None, (f"{content_err} | fallback: {fb_content_err}")
        if content_err is not None:
            return None, content_err

        choices = response.choices
        raw_text = choices[0].message.content if choices else None

        raw_json = _extract_json(raw_text)
        if raw_json is None:
            return None, "no_valid_json_in_response"

        validated = validate_model_output(raw_json, context.agent_id)
        if validated.is_valid:
            return raw_json, None

        # --- One bounded repair attempt (JSON repair) ---
        repair_prompt = (
            f"Your previous response had validation errors: {'; '.join(validated.validation_errors)}\n"
            "Please correct and return only a valid JSON object with the exact required fields."
        )
        response2, err2 = self._call_with_transport_retry(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "assistant", "content": raw_text},
                {"role": "user", "content": repair_prompt},
            ],
            temperature=0.2,
            max_tokens=_MAX_COMPLETION_TOKENS,
            budget=serving_budget,
            client=serving_client,
            model=serving_config.model,
            config=serving_config,
        )
        if response2 is None:
            return None, err2

        raw_text2 = response2.choices[0].message.content if response2.choices else None
        finish_reason2 = (
            getattr(response2.choices[0], "finish_reason", None)
            if response2.choices
            else None
        )
        if not raw_text2 or not raw_text2.strip():
            if finish_reason2 == "length":
                return None, "repair_max_tokens_truncated_response"
            return None, "repair_empty_response"

        raw_json2 = _extract_json(raw_text2)
        if raw_json2 is None:
            return None, "repair_no_valid_json"

        validated2 = validate_model_output(raw_json2, context.agent_id)
        if validated2.is_valid:
            return raw_json2, None

        return None, f"repair_failed: {'; '.join(validated2.validation_errors)}"

    def propose_goal(self, context: AgentContext) -> dict | None:
        return None

    def evaluate_questions(self, context: AgentContext) -> list[dict]:
        return []

    def reflect_on_outcome(
        self, context: AgentContext, previous_action: dict | None, outcome: dict
    ) -> str:
        if previous_action is None:
            return f"Outcome: {outcome.get('status', 'unknown')}"
        return f"Previous action {previous_action.get('action_type')}: {outcome.get('status', 'unknown')}"


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
