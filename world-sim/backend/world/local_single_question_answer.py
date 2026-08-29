"""Bounded governed single-question operator-answer seam (production writer).

Answers EXACTLY ONE existing pending QuestionRecord under a grounded single-use
operator authorization, fail-closed and non-replayable. This is the governed
path around the legacy/demo ``mark_question_answered`` mutation: it enforces
pending-only, owner binding, exact stripped-answer-material binding (via a
deterministic SHA-256 commitment), a consume-first commit point, inbound
(not egress) answer validation, and strict replay rejection.

Authorization model (mirrors local_single_goal_status_update.py):
- Consumes a single-use, operator-grounded, exact-question + exact-agent +
  exact-answer-material authorization artifact. Fail-closed, non-replayable.
- The answer material is bound to the exact operator answer after ONLY
  ``.strip()`` normalization. No redaction, rewriting, case folding, or
  summarization. The authorization binds a SHA-256 commitment to that exact
  normalized UTF-8 text.

Authority boundary:
- Exactly one existing pending question's answer write. No question creation,
  no goal status, no movement, no memory/ledger/world-state/relationship
  mutation, no provider/network, no Gate-7, no broad creation authority.
  Operator must authorize (Sean); this module never self-authorizes.

Failure windows (consume-first, no rollback):
- A. consumed-provenance append fails -> nothing durable; authorization reusable.
- B. consumed append succeeds, save_questions fails -> authorization burned,
     question still pending, applied provenance absent, retry blocked.
- C. consumed + save succeed, applied-provenance append fails -> authorization
     burned, question answered, retry blocked -> ANSWER_APPLIED_AUDIT_INCOMPLETE.
- D. normal success -> exactly one pending->answered, one consumed event, one
     applied event, replay blocked.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    governed_answer_transaction,
    load_questions,
)

# --- Signed answer-authority contract (V1) ---
# Strictly DISTINCT from question-creation domain/action so a creation
# signature can never be replayed as an answer signature and vice versa. The
# SAME operator public key (GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX) verifies
# both, but domain separation isolates the two authority surfaces.
_AUTH_SCHEMA = "single_question_answer_authorization.ed25519.1"
_AUTH_DOMAIN = "GENESIS_FIRST_PAIR_SINGLE_QUESTION_ANSWER_AUTH_ED25519_V1"
_AUTH_ACTION = "single_question_answer"
_OPERATOR = "Sean"  # identity constant only — NOT cryptographic authority

# Envelope keys EXCLUDED from the signed payload (metadata carried outside
# the signature, mirrored from the create-path _NON_SIGNED_KEYS convention).
_NON_SIGNED_KEYS = ("signature", "public_key_hex", "public_key_id")

# Keys REQUIRED in the signed payload in canonical order semantics (exact key
# coverage is NOT asserted here; the verifier validates the values it needs).
_SIGNED_REQUIRED_KEYS = (
    "schema",
    "domain",
    "action",
    "question_id",
    "asking_agent_id",
    "formatted_answer_hash",
    "max_writes",
    "nonce",
    "issued_at_utc",
    "expires_at_utc",
)

# operator_proof_ref is retained as a non-cryptographic audit/claim reference
# (matching the goal/status family). It participates in the signed material ONLY
# as a binding label — it proves NOTHING about operator approval on its own.
_OPERATOR_PROOF_IS_AUTHORITY = False

# Source-supported deterministic bound: same char-bound family as the model
# layer's _MAX_QUESTION_CHARS = 1000 (first_pair_cognition_model.py).
_MAX_ANSWER_CHARS = 1000

# Inbound answer contamination markers -> REJECT (never redact/rewrite). Covers
# credential / runtime contamination only; not a general sanitizer.
_CONTAMINATION_MARKERS = (
    ".env",
    "api_key",
    "apikey",
    "secret",
    "password",
    "authorization: bearer",
    "private_key",
)

_CLAIM_BOUNDARY = (
    "exactly one existing pending question answer under an operator-grounded "
    "single-use authorization; no question creation, goal status, movement, "
    "memory/ledger/world-state/relationship mutation, model, provider, "
    "network, or gate activity"
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _answer_material(answer: str) -> str:
    """*answer* normalized ONLY by stripping surrounding whitespace.

    No redaction, rewriting, case folding, or semantic transformation.
    """
    return answer.strip()


def unsigned_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    """The exact signed bytes source: envelope minus signature/metadata keys.

    Mirrors the create-path ``unsigned_payload`` convention exactly so the two
    authority surfaces share ONE crypto convention, differentiated only by
    strict domain/action literals.
    """
    return {k: v for k, v in envelope.items() if k not in _NON_SIGNED_KEYS}


def authorization_id(envelope: dict[str, Any]) -> str:
    """Deterministic replay identity derived from the COMPLETE signed material.

    ``"auth-" + sha256(canonical(unsigned_payload))[:16]``. The ID is never
    trusted from the envelope; it is recomputed on every verification. Binding
    the full unsigned payload (including nonce + issued/expires) means any
    tampering of any signed field changes the ID.
    """
    return "auth-" + hashlib.sha256(_canonical(unsigned_payload(envelope)).encode("utf-8")).hexdigest()[:16]


def validate_authorization_times(
    envelope: dict[str, Any], now_utc: "datetime | None" = None
) -> tuple[bool, str | None]:
    """Fail-closed issued/expires enforcement (mirrors the create-path semantics).

    - issued_at_utc / expires_at_utc must parse as timezone-aware UTC ISO-8601.
    - issued <= expires.
    - expires > now (defaults to current process UTC; NOT caller-controllable
      in the production path).
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
            return None
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


def verify_question_answer_authorization(
    trusted_public_key_bytes: bytes, envelope: dict[str, Any]
) -> tuple[bool, str | None]:
    """Verify a signed single-question-answer authorization envelope.

    Returns (ok, error). ``ok`` is True ONLY when:
      - schema/domain/action match the ANSWER contract literals EXACTLY
        (strictly distinct from the question-creation domain/action, so a
        creation signature can never replay as an answer authorization)
      - max_writes == 1
      - a 64-byte Ed25519 signature verifies over the canonical unsigned payload
        against the GIVEN public key (the key comes from the env trust root,
        never from the envelope/caller)
      - a nonce is present (replay-freshness binding)

    This is verify-only: it never manufactures authority. It does NOT enforce
    expiry (the store evaluates expiry at consumption, mirroring creation).
    """
    if not isinstance(envelope, dict):
        return False, "invalid_authorization"
    if envelope.get("schema") != _AUTH_SCHEMA:
        return False, "invalid_schema"
    if envelope.get("domain") != _AUTH_DOMAIN:
        return False, "invalid_domain"
    if envelope.get("action") != _AUTH_ACTION:
        return False, "invalid_action"
    if envelope.get("max_writes") != 1:
        return False, "invalid_authorization"
    nonce = envelope.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        return False, "missing_nonce"

    signature_hex = envelope.get("signature")
    if not isinstance(signature_hex, str):
        return False, "missing_signature"
    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError:
        return False, "malformed_signature"
    if len(signature) != 64:
        return False, "malformed_signature"

    signed_bytes = _canonical(unsigned_payload(envelope)).encode("utf-8")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub_key = Ed25519PublicKey.from_public_bytes(trusted_public_key_bytes)
        pub_key.verify(signature, signed_bytes)
    except Exception:
        return False, "invalid_signature"

    return True, None


def seal_question_answer_authorization(
    *,
    question_id: str,
    asking_agent_id: str,
    answer: str,
    operator_proof_ref: str,
    authorization_timestamp: str,
) -> dict[str, Any]:
    """LEGACY / NON-AUTHORITATIVE producer (unsigned, self-consistent hash).

    Retained ONLY for existing test compatibility. Its output carries NO
    signature and therefore CANNOT pass ``verify_question_answer_authorization``
    and CANNOT authorize a canonical answer write. Production answer authority
    is an Ed25519-signed envelope produced by the EXTERNAL operator signer;
    Genesis is verify-only and never calls this to mint authority.
    """
    answer_material = _answer_material(answer)
    return {
        "schema_version": "single_question_answer_authorization.1",  # legacy, unsigned
        "domain_separator": "GENESIS_FIRST_PAIR_SINGLE_QUESTION_ANSWER_AUTH_V1",
        "operator": _OPERATOR,
        "action": _AUTH_ACTION,
        "question_id": question_id,
        "asking_agent_id": asking_agent_id,
        "answer_text": answer_material,
        "formatted_answer_hash": _hash({"answer_material": answer_material}),
        "max_writes": 1,
        "operator_proof_ref": operator_proof_ref,
        "authorization_timestamp": authorization_timestamp,
        "authorization_id": "auth-" + _hash(
            {
                "question_id": question_id,
                "asking_agent_id": asking_agent_id,
                "formatted_answer_hash": _hash({"answer_material": answer_material}),
                "operator_proof_ref": operator_proof_ref,
                "authorization_timestamp": authorization_timestamp,
            }
        )[:16],
        # NOTE: no signature, no nonce, no issued/expires -> non-authoritative.
    }


def _provenance_records(store: FirstPairPersistenceStore) -> list[dict[str, Any]]:
    from pathlib import Path

    from backend.world.first_pair_persistence import _PROVENANCE_FILE

    path: Path = store._path(_PROVENANCE_FILE)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _is_consumed(store: FirstPairPersistenceStore, authorization_id: str) -> bool:
    """True only when a consumed AUTHORITY RECEIPT exists for the authorization_id.

    Provenance is NOT the consumption predicate — the signed-envelope receipt is.
    """
    from backend.world.first_pair_persistence import load_answer_consumed_receipt

    return load_answer_consumed_receipt(store, authorization_id) is not None


def _ensure_answer_applied_provenance(
    store: FirstPairPersistenceStore,
    authorization_id: str,
    question_id: str,
    asking_agent_id: str,
) -> None:
    """Idempotently ensure EXACTLY ONE ``single_question_answer_applied`` event.

    Stable identity = (action == "single_question_answer_applied") AND
    (detail.authorization_id == authorization_id). Repeated calls (including
    crash-recovery retries) never append a duplicate.
    """
    action = "single_question_answer_applied"
    for r in _provenance_records(store):
        if r.get("action") == action and r.get("detail", {}).get("authorization_id") == authorization_id:
            return
    store._append_provenance(
        action,
        {
            "authorization_id": authorization_id,
            "question_id": question_id,
            "asking_agent_id": asking_agent_id,
            "status": "answered",
        },
    )


def _recover_answer_applied(
    store: FirstPairPersistenceStore,
    authorization: dict[str, Any],
    question_id: str,
    asking_agent_id: str,
    bound_answer: str,
) -> dict[str, Any] | None:
    """Crash recovery for an already-consumed (receipted) answer authorization.

    Authority here is the VALID SIGNED envelope in the consumed receipt, NOT a
    provenance line. Recovery succeeds only when:
      - the consumed receipt exists for this authorization_id
      - its stored signed envelope re-verifies against the env trust root
      - the canonical question is ALREADY answered
      - persisted bindings (owner + answer) EXACTLY match the signed material
    In that case it idempotently ensures the applied audit provenance exists
    exactly once.

    Returns ``None`` (caller fails closed as already-consumed) otherwise.
    """
    from backend.world.first_pair_persistence import (
        load_answer_consumed_receipt,
    )

    auth_id = authorization_id(authorization)
    receipt = load_answer_consumed_receipt(store, auth_id)
    if receipt is None:
        return None
    signed_envelope = receipt.get("signed_envelope")
    if not isinstance(signed_envelope, dict):
        return None

    # Re-verify the STORED signed envelope against the env trust root.
    from backend.world.first_pair_persistence import _load_public_keys

    try:
        keys = _load_public_keys()
    except ValueError:
        return None
    if not keys:
        return None
    verify_key = next(iter(keys.values()))
    ok, _err = verify_question_answer_authorization(verify_key, signed_envelope)
    if not ok:
        return None

    # Identity: the receipt's authorization_id must match the recomputed id.
    if receipt.get("authorization_id") != auth_id:
        return None

    # Recovery must NOT mask a genuine replay: if the applied evidence already
    # exists, a replay is already-consumed, not a recovered success.
    if any(
        r.get("action") == "single_question_answer_applied"
        and r.get("detail", {}).get("authorization_id") == auth_id
        for r in _provenance_records(store)
    ):
        return None

    try:
        questions = load_questions(store)
    except Exception:
        return None
    target = next((q for q in questions if q.question_id == question_id), None)
    if target is None or target.status != "answered":
        return None
    if target.asking_agent_id != asking_agent_id:
        return None
    if target.provenance.get("answer") != bound_answer:
        return None
    # The signed envelope must also bind this exact answer material.
    if signed_envelope.get("formatted_answer_hash") != _hash({"answer_material": bound_answer}):
        return None
    # Exact match: repair missing applied provenance idempotently.
    try:
        _ensure_answer_applied_provenance(store, auth_id, question_id, asking_agent_id)
    except OSError:
        return None
    return {
        "ok": True,
        "errors": [],
        "persisted": True,
        "recovered": True,
        "question_id": question_id,
        "asking_agent_id": asking_agent_id,
        "status": "answered",
        "questions_mutated": 0,
        "consumed_event": "single_question_answer_consumed",
        "applied_event": "single_question_answer_applied",
        "movement_performed": False,
        "memory_written": False,
        "world_state_mutated": False,
        "relationship_changed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
    }


def _validate_answer(answer: Any) -> tuple[str, list[str]]:
    """Inbound answer validation. No rewriting/redaction; only reject or normalize."""
    if type(answer) is not str:
        return "", ["invalid_answer"]
    stripped = answer.strip()
    if not stripped:
        return "", ["invalid_answer"]
    if len(stripped) > _MAX_ANSWER_CHARS:
        return "", ["invalid_answer"]
    lowered = stripped.casefold()
    if any(marker in lowered for marker in _CONTAMINATION_MARKERS):
        return "", ["invalid_answer"]
    return stripped, []


def _fail(question_id: str, asking_agent_id: str, errors: list[str], **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "errors": sorted(set(errors)),
        "persisted": False,
        "question_id": question_id,
        "asking_agent_id": asking_agent_id,
        "questions_mutated": 0,
        "movement_performed": False,
        "memory_written": False,
        "world_state_mutated": False,
        "relationship_changed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
    }
    result.update(extra)
    return result


def apply_question_answer(
    store: FirstPairPersistenceStore,
    *,
    question_id: str,
    asking_agent_id: str,
    answer: str,
    authorization: dict[str, Any],
) -> dict[str, Any]:
    """Answer exactly one existing pending question under a SIGNED authorization.

    ``authorization`` is the complete Ed25519-signed answer envelope produced by
    the EXTERNAL operator signer. This module VERIFIES it (signature against the
    env-only trust root, recomputed authorization_id, strict answer
    schema/domain/action, time validity, question/agent/answer bindings) and
    never mints authority itself.

    Writes nothing durable on any failure. The consumed AUTHORITY RECEIPT stores
    the full signed envelope; the JSONL provenance lines remain audit-only.
    """
    errors: list[str] = []

    if not isinstance(question_id, str) or not question_id:
        errors.append("invalid_question_id")
    if not isinstance(asking_agent_id, str) or not asking_agent_id:
        errors.append("invalid_agent_id")

    answer_material, answer_errors = _validate_answer(answer)
    errors += answer_errors
    if answer_errors:
        answer_material = ""
    bound_answer = answer.strip() if type(answer) is str else ""

    # 1. Obtain the env-only operator public key (fail closed).
    verify_key: "bytes | None" = None
    if not errors:
        from backend.world.first_pair_persistence import _load_public_keys

        try:
            keys = _load_public_keys()
        except ValueError as exc:
            errors.append(str(exc))
            keys = None
        if keys:
            verify_key = next(iter(keys.values()))
        elif not errors:
            errors.append("operator_public_key_unconfigured")

    # 2. Cryptographic verification of the signed envelope.
    auth_id = ""
    if not errors and verify_key is not None:
        ok, sig_err = verify_question_answer_authorization(verify_key, authorization)
        if not ok:
            errors.append(sig_err or "invalid_authorization")
        else:
            # 3. Enforce issued/expires time validity (production "now" internal).
            time_ok, time_err = validate_authorization_times(authorization)
            if not time_ok:
                errors.append(time_err)
            # 4. Bind the signed fields to the requested material EXACTLY.
            if authorization.get("question_id") != question_id:
                errors.append("authorization_question_mismatch")
            if authorization.get("asking_agent_id") != asking_agent_id:
                errors.append("authorization_agent_mismatch")
            if authorization.get("formatted_answer_hash") != _hash({"answer_material": bound_answer}):
                errors.append("authorization_answer_mismatch")
            # 5. Recompute authorization_id (never trust a label).
            auth_id = authorization_id(authorization)

    # 6. Replay / single-use: a consumed receipt already exists?
    consumed_already = False
    if not errors and auth_id:
        consumed_already = _is_consumed(store, auth_id)
        if consumed_already:
            recovery = _recover_answer_applied(
                store, authorization, question_id, asking_agent_id, bound_answer
            )
            if recovery is not None:
                return recovery
            errors.append("authorization_already_consumed")

    questions = []
    if not errors:
        try:
            questions = load_questions(store)
        except Exception as exc:
            errors.append(f"malformed_questions_store: {type(exc).__name__}")

    target = None
    if not errors:
        target = next((q for q in questions if q.question_id == question_id), None)
        if target is None:
            errors.append("question_not_found")
        elif target.asking_agent_id != asking_agent_id:
            errors.append("question_agent_mismatch")
        elif target.status != "pending":
            errors.append("question_already_answered")

    if errors:
        return _fail(question_id, asking_agent_id, errors)

    # 7. Persist the consumed AUTHORITY RECEIPT (full signed envelope) BEFORE the
    #    canonical mutation, so a crash after this point is recoverable via the
    #    receipt (not a forgeable provenance line).
    from backend.world.first_pair_persistence import write_answer_consumed_receipt

    try:
        write_answer_consumed_receipt(
            store,
            authorization_id=auth_id,
            question_id=question_id,
            asking_agent_id=asking_agent_id,
            formatted_answer_hash=authorization["formatted_answer_hash"],
            signed_envelope=authorization,
            consumed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
    except OSError:
        # Window A: nothing durable changed for authority; authorization reusable.
        return _fail(question_id, asking_agent_id, ["consumed_receipt_write_failed"])

    # Also record the CONSUMED audit provenance (audit-only, never authority).
    try:
        store._append_provenance(
            "single_question_answer_consumed",
            {
                "authorization_id": auth_id,
                "question_id": question_id,
                "asking_agent_id": asking_agent_id,
                "formatted_answer_hash": _hash({"answer_material": answer_material}),
            },
        )
    except OSError:
        # Receipt already written (authority consumed); provenance is audit-only,
        # so a failure here degrades audit surface, not authority. Continue.
        pass

    # 8. Narrow governed, locked mutation re-verifies the stored receipt/signature
    #    independently under _store_lock before mutating canonical state.
    try:
        tx = governed_answer_transaction(
            store,
            question_id=question_id,
            answer_material=answer_material,
            operator_provenance=authorization.get("operator_proof_ref", "operator"),
            authorized_agent_id=asking_agent_id,
            authorization_id=auth_id,
        )
    except OSError as exc:
        return _fail(
            question_id,
            asking_agent_id,
            [f"governed_answer_failed: {type(exc).__name__}"],
            warn="AUTHORIZATION_BURNED_QUESTION_PENDING",
        )
    if not tx.get("ok"):
        return _fail(
            question_id,
            asking_agent_id,
            [f"governed_answer_{tx.get('error', 'failed')}"],
            warn="AUTHORIZATION_BURNED_QUESTION_PENDING",
        )

    # 9. Idempotently ensure the APPLIED audit provenance exists exactly once.
    try:
        _ensure_answer_applied_provenance(store, auth_id, question_id, asking_agent_id)
    except OSError:
        return _fail(
            question_id,
            asking_agent_id,
            ["applied_provenance_append_failed"],
            warn="ANSWER_APPLIED_AUDIT_INCOMPLETE",
            questions_mutated=1,
        )

    return {
        "ok": True,
        "errors": [],
        "persisted": True,
        "question_id": question_id,
        "asking_agent_id": asking_agent_id,
        "status": "answered",
        "questions_mutated": 1,
        "consumed_event": "single_question_answer_consumed",
        "applied_event": "single_question_answer_applied",
        "movement_performed": False,
        "memory_written": False,
        "world_state_mutated": False,
        "relationship_changed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
    }