"""Pure public egress sanitizer for Phase 10AD.

Provides deterministic, side-effect-free text sanitization for world-facing
output.  No filesystem I/O, no network, no environment reads.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Replacement markers  (chosen so they never match any input pattern)
# ---------------------------------------------------------------------------

REDACTED_PATH = "[REDACTED_PATH]"
REDACTED_SECRET = "[REDACTED_SECRET]"
REDACTED_RUNTIME = "[REDACTED_RUNTIME]"
REDACTED_AGENT_TRACE = "[REDACTED_AGENT_TRACE]"
REDACTED_SKILL_REF = "[REDACTED_SKILL_REF]"

# ---------------------------------------------------------------------------
# Compiled patterns  (all flags are embedded for clarity)
# ---------------------------------------------------------------------------

# Windows absolute drive-letter paths:  C:\path,  Z:\Example Project\...
_WINDOWS_PATH_RE = re.compile(
    r"[A-Za-z]:(?:\\|\/)"
    r"(?:[^\\\/\"'|;:*?<>()\[\]{}]+(?:\\|\/))*"
    r"[^\\\/\"'|;:*?<>()\[\]{}]+"
)

# Bare Windows-path tokens that may appear without a drive letter
_WINDOWS_TOKEN_RE = re.compile(
    r"""(?x)
    (?:
        Users\\[^\s"'|;:*?<>()\[\]{}]+                              # Users\something
        | \bAppData\b
        | \bLOCALAPPDATA\b
    )
    """
)

# .env references
_DOT_ENV_RE = re.compile(r"""\.env\b""", re.IGNORECASE)

# Credential markers — label=value, label: value, or bare label
_CREDENTIAL_RE = re.compile(
    r"""(?ix)
    (?:
        (?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?)
        \s*[:=]\s*\S+
    )
    |
    \b(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?)\b
    |
    \bAPI\s+[Kk]ey\b
    """
)

# localhost / loopback / raw IPv4
_LOCALHOST_RE = re.compile(r"""\blocalhost\b""", re.IGNORECASE)
_LOOPBACK_RE = re.compile(r"""\b127\.0\.0\.1\b""")
_IPV4_RE = re.compile(
    r"""\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"""
)

# Infrastructure / host references
_SSH_RE = re.compile(r"""\bssh\b""", re.IGNORECASE)
_HOSTINGER_RE = re.compile(r"""\bHostinger\b""")
_TAILSCALE_RE = re.compile(r"""\bTailscale\b""")

# Agent-level trace markers  (Thought:, chain-of-thought, model names)
_THOUGHT_RE = re.compile(r"""\bThought:\s""")
_CHAIN_THOUGHT_RE = re.compile(r"""\bchain[- ]of[- ]thought\b""", re.IGNORECASE)
_ORCHESTRATOR_RE = re.compile(r"""\bOrchestrator\b""")
_DEEPSEEK_RE = re.compile(r"""\bDeepSeek\b""")
_MINIMAX_RE = re.compile(r"""\bMiniMax\b""")
_GPT5_RE = re.compile(r"""\bGPT-5\b""")

# Slash-skill contamination  e.g.  /agent-tools:skill   /ab-test-setup:skill
_SKILL_REF_RE = re.compile(
    r"""(?x)
    /[a-z][-a-z0-9]+:[a-z][-a-z0-9]+
    """,
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def sanitize_public_text(text: str) -> str:
    """Return *text* with private/runtime markers replaced by safe tokens.

    The function is deterministic, side-effect-free, and idempotent.
    Non-string inputs are returned unchanged.
    """
    if not isinstance(text, str):
        return text

    # Order matters — redact from most specific to least specific so later
    # passes never re-discover something already replaced.

    # 1 – Windows drive-letter paths
    text = _WINDOWS_PATH_RE.sub(REDACTED_PATH, text)
    # 2 – Bare Windows tokens
    text = _WINDOWS_TOKEN_RE.sub(REDACTED_PATH, text)
    # 3 – .env references
    text = _DOT_ENV_RE.sub(REDACTED_PATH, text)
    # 4 – Credentials
    text = _CREDENTIAL_RE.sub(REDACTED_SECRET, text)
    # 5 – localhost / IP
    text = _LOOPBACK_RE.sub(REDACTED_RUNTIME, text)
    text = _LOCALHOST_RE.sub(REDACTED_RUNTIME, text)
    text = _IPV4_RE.sub(REDACTED_RUNTIME, text)
    # 6 – Infrastructure names
    text = _SSH_RE.sub(REDACTED_RUNTIME, text)
    text = _HOSTINGER_RE.sub(REDACTED_RUNTIME, text)
    text = _TAILSCALE_RE.sub(REDACTED_RUNTIME, text)
    # 7 – Agent trace markers
    text = _THOUGHT_RE.sub(REDACTED_AGENT_TRACE, text)
    text = _CHAIN_THOUGHT_RE.sub(REDACTED_AGENT_TRACE, text)
    text = _ORCHESTRATOR_RE.sub(REDACTED_AGENT_TRACE, text)
    text = _DEEPSEEK_RE.sub(REDACTED_AGENT_TRACE, text)
    text = _MINIMAX_RE.sub(REDACTED_AGENT_TRACE, text)
    text = _GPT5_RE.sub(REDACTED_AGENT_TRACE, text)
    # 8 – Slash-skill contamination
    text = _SKILL_REF_RE.sub(REDACTED_SKILL_REF, text)

    return text


def sanitize_public_mapping(value: Any) -> Any:
    """Recursively sanitize every string inside *value*.

    Accepts nested dicts, lists, and tuples.  Non-string primitives and
    None are returned unchanged.  A new structure is always returned; the
    input is never mutated.

    String dict keys are also passed through *sanitize_public_text*.
    """
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for k, v in value.items():
            key = sanitize_public_text(k) if isinstance(k, str) else k
            result[key] = sanitize_public_mapping(v)
        return result
    if isinstance(value, list):
        return [sanitize_public_mapping(v) for v in value]
    if isinstance(value, tuple):
        return tuple(sanitize_public_mapping(v) for v in value)
    if isinstance(value, str):
        return sanitize_public_text(value)
    return value
