"""Signed question-creation authorization CONSUMER (verification-only).

This module validates an Ed25519-signed single-question-creation authorization.
It is the CONSUMER side of the authority boundary: it holds and uses PUBLIC
verification material only.

It MUST NOT import, expose, or implement any private-key signing primitive,
private-key loading, key generation, or authority minting helper.

The operator private key lives off-host. Genesis validates and consumes the
signature; it never manufactures one.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from backend.world.question_proposal import (
    canonicalize_proposal_json,
    canonicalize_proposal_material,
)


SCHEMA = "single_question_creation_authorization.ed25519.1"
DOMAIN = "GENESIS_FIRST_PAIR_SINGLE_QUESTION_CREATE_AUTH_ED25519_V1"
ACTION = "single_question_create"

# Envelope keys that are NOT part of the signed material.
_SIGNED_REQUIRED_KEYS = (
    "schema",
    "domain",
    "action",
    "nonce",
    "pair_id",
    "asking_agent_id",
    "question_id",
    "related_goal_id",
    "question",
    "reason_for_asking",
    "requested_human_capability",
    "urgency",
    "question_material_hash",
    "operator_proof_path",
    "operator_proof_content_sha256",
    "issued_at_utc",
    "max_writes",
)

# Envelope keys EXCLUDED from the signed payload (metadata carried outside the
# signature). expires_at_utc is deliberately PART of the signed payload, because
# the expiry is a binding property of the authorization itself.
_NON_SIGNED_KEYS = ("signature", "public_key_hex", "public_key_id")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def unsigned_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    """The exact signed bytes source: envelope minus signature/metadata keys."""
    return {k: v for k, v in envelope.items() if k not in _NON_SIGNED_KEYS}


def authorization_id(envelope: dict[str, Any]) -> str:
    """Deterministic replay identity: hash of the canonical unsigned payload.

    The ID is only a transaction/replay key. The Ed25519 signature is the
    authority; the ID never is.
    """
    payload = unsigned_payload(envelope)
    material = _canonical_json(payload)
    return "auth-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def public_key_id(pub_key_bytes: bytes) -> str:
    """Deterministic fingerprint of a raw 32-byte Ed25519 public key."""
    return "opk-" + hashlib.sha256(pub_key_bytes).hexdigest()[:16]


def validate_authorization_times(envelope: dict[str, Any], now_utc: "datetime | None" = None) -> tuple[bool, str | None]:
    """Enforce issued/expiry timestamps fail-closed.

    - ``expires_at_utc`` and ``issued_at_utc`` must both parse as timezone-aware
      UTC ISO-8601.
    - ``issued_at_utc`` must be <= ``expires_at_utc``.
    - ``expires_at_utc`` must be > ``now_utc`` (defaults to current UTC).

    ``now_utc`` is an internal-only clock seam for tests; the production path
    never supplies it, so expiry cannot be bypassed by caller-supplied time.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    issued_raw = envelope.get("issued_at_utc")
    expires_raw = envelope.get("expires_at_utc")
    if not isinstance(issued_raw, str) or not issued_raw:
        return False, "invalid_issued_at"
    if not isinstance(expires_raw, str) or not expires_raw:
        return False, "invalid_expires_at"

    def _parse(value: str) -> "datetime | None":
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return None  # naive time is not accepted; reject
        return dt.astimezone(timezone.utc)

    issued = _parse(issued_raw)
    expires = _parse(expires_raw)
    if issued is None:
        return False, "invalid_issued_at"
    if expires is None:
        return False, "invalid_expires_at"
    if issued > expires:
        return False, "issued_after_expiry"
    if expires <= now_utc:
        return False, "authorization_expired"
    return True, None


def verify_question_creation_authorization(
    trusted_public_key_bytes: bytes, envelope: dict[str, Any]
) -> tuple[bool, str | None]:
    """Verify a signed single-question-creation authorization envelope.

    Returns (ok, error). ``ok`` is True only when every binding checks out:
    schema/domain/action, signature over the exact canonical payload, and
    material hash consistency. No authority is granted by this function; it only
    validates a signature against the given PUBLIC key.

    Expiry is NOT enforced here (the store evaluates expiry against initial
    consumption, not at this pure-verify layer).
    """
    if not isinstance(envelope, dict):
        return False, "invalid_authorization"

    if envelope.get("schema") != SCHEMA:
        return False, "invalid_schema"
    if envelope.get("domain") != DOMAIN:
        return False, "invalid_domain"
    if envelope.get("action") != ACTION:
        return False, "invalid_action"
    if envelope.get("max_writes") != 1:
        return False, "invalid_authorization"

    signature_hex = envelope.get("signature")
    if not isinstance(signature_hex, str):
        return False, "missing_signature"
    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError:
        return False, "malformed_signature"
    if len(signature) != 64:
        return False, "malformed_signature"

    # Canonical signed bytes = canonical JSON of the unsigned payload.
    signed_bytes = canonicalize_proposal_json(unsigned_payload(envelope)).encode("utf-8")

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub_key = Ed25519PublicKey.from_public_bytes(trusted_public_key_bytes)
        pub_key.verify(signature, signed_bytes)
    except Exception:
        return False, "invalid_signature"

    # Material-hash consistency: the committed hash must equal a recompute of
    # the exact authorized fields as normalised by the proposal module.
    expected_material = canonicalize_proposal_material(
        pair_id=envelope.get("pair_id"),
        asking_agent_id=envelope.get("asking_agent_id"),
        question_id=envelope.get("question_id"),
        related_goal_id=envelope.get("related_goal_id"),
        question=envelope.get("question"),
        reason_for_asking=envelope.get("reason_for_asking"),
        requested_human_capability=envelope.get("requested_human_capability"),
        urgency=envelope.get("urgency"),
    )
    expected_hash = hashlib.sha256(
        canonicalize_proposal_json(expected_material).encode("utf-8")
    ).hexdigest()
    if envelope.get("question_material_hash") != expected_hash:
        return False, "material_mismatch"

    return True, None