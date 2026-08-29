"""Signed single-question answer authority — focused tests.

These prove the fail-closed operator-answer writer under the SIGNED Ed25519
answer-authorization envelope: strict answer domain/action, env-only trust
root, recomputed authorization_id, question/agent/answer binding, expiry,
single-use, consume-first receipt, inbound answer validation, and replay
rejection. The JSONL provenance lines are audit-only and grant no authority.

All mutation tests use isolated scratch persistence; the canonical
.runtime/first-pair surface is never touched. Ephemeral Ed25519 test keys only;
no production key.
"""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    QuestionRecord,
    load_questions,
    _save_questions_raw,
)
import backend.world.local_single_question_answer as a

ADAM = "genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d"
EVE = "genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211"

_SCRATCH = Path(__file__).resolve().parent.parent / ".qa-scratch-answer"


def _gen_keypair():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return priv, pub


def _canonical(value):
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_hex(value):
    import hashlib
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def trust_env(monkeypatch):
    """Install an ephemeral operator trust key for the answer authority surface."""
    priv, pub = _gen_keypair()
    monkeypatch.setenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", pub.hex())
    return priv, pub


@pytest.fixture()
def store():
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    s = FirstPairPersistenceStore(Path(_SCRATCH))
    s.root.mkdir(parents=True, exist_ok=True)
    yield s
    shutil.rmtree(_SCRATCH, ignore_errors=True)


def _signed_envelope(priv, *, question_id="q1", agent_id=ADAM, answer="Tile alpha, Tile beta.",
                     nonce="nonce-1", issued="2026-01-01T00:00:00Z",
                     expires="9999-01-01T00:00:00Z", max_writes=1,
                     operator_proof_ref="proof-1", domain=None, action=None,
                     schema=None, signature=None, drop_keys=(), mutate=None):
    """Build a signed answer-authorization envelope (ephemeral test key)."""
    payload = {
        "schema": schema or a._AUTH_SCHEMA,
        "domain": domain or a._AUTH_DOMAIN,
        "action": action or a._AUTH_ACTION,
        "question_id": question_id,
        "asking_agent_id": agent_id,
        "formatted_answer_hash": _hash_hex({"answer_material": answer.strip()}),
        "max_writes": max_writes,
        "nonce": nonce,
        "issued_at_utc": issued,
        "expires_at_utc": expires,
    }
    if operator_proof_ref is not None:
        payload["operator_proof_ref"] = operator_proof_ref
    for k in drop_keys:
        payload.pop(k, None)
    if mutate:
        payload = mutate(dict(payload))
    sig = signature
    if signature is None:
        signed_bytes = _canonical(payload).encode("utf-8")
        sig = priv.sign(signed_bytes).hex()
    env = dict(payload)
    env["signature"] = sig
    return env


def _seed(store, question_id="q1", agent_id=ADAM, status="pending"):
    q = QuestionRecord(
        question_id=question_id,
        asking_agent_id=agent_id,
        heartbeat=1,
        question="What tiles are available?",
        reason_for_asking="goal",
        related_goal_id="goal-b0971f2a04c4c41b",
        requested_human_capability="provide_habitat_information",
        urgency="medium",
        status=status,
    )
    # Test-only fixture seed: bypasses production creation authority intentionally.
    _save_questions_raw(store, [q])
    return q


def _provenance_actions(store):
    return [r.get("action") for r in a._provenance_records(store)]


def _status(store):
    return [q.status for q in load_questions(store)]


# --- normal success (D) ------------------------------------------------------

def test_normal_success(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="Tile alpha, Tile beta.")
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="Tile alpha, Tile beta.", authorization=auth
    )
    assert res["ok"] is True
    assert res["persisted"] is True
    assert _status(store) == ["answered"]
    q = load_questions(store)[0]
    assert q.provenance.get("answer") == "Tile alpha, Tile beta."
    assert "answered_at_utc" in q.provenance
    acts = _provenance_actions(store)
    assert acts.count("single_question_answer_consumed") == 1
    assert acts.count("single_question_answer_applied") == 1
    # replay blocked
    replay = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="Tile alpha, Tile beta.", authorization=auth
    )
    assert replay["ok"] is False and "authorization_already_consumed" in replay["errors"]


# --- RED/GREEN: unsigned / forged / domain / substitution ---------------------

def test_unsigned_self_consistent_auth_rejected(store, trust_env):
    # Legacy unsigned sealer output cannot authorize (no signature).
    _seed(store, question_id="q1", agent_id=ADAM)
    legacy = a.seal_question_answer_authorization(
        question_id="q1", asking_agent_id=ADAM, answer="X",
        operator_proof_ref="proof-1", authorization_timestamp="2026-08-24T00:00:00Z",
    )
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="X", authorization=legacy
    )
    assert res["ok"] is False
    assert _status(store) == ["pending"]


def test_wrong_operator_signer_rejected(store, trust_env):
    priv, pub = trust_env
    _other_priv, _other_pub = _gen_keypair()
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(_other_priv, question_id="q1", agent_id=ADAM, answer="A")
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="A", authorization=auth
    )
    assert res["ok"] is False
    assert "invalid_signature" in res["errors"]
    assert _status(store) == ["pending"]


def test_question_create_domain_signature_rejected_as_answer(store, trust_env):
    # A signature over the CREATE domain must not authorize an answer.
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(
        priv, question_id="q1", agent_id=ADAM, answer="A",
        domain="GENESIS_FIRST_PAIR_SINGLE_QUESTION_CREATE_AUTH_ED25519_V1",
        schema="single_question_creation_authorization.ed25519.1",
        action="single_question_create",
    )
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="A", authorization=auth
    )
    assert res["ok"] is False
    assert "invalid_domain" in res["errors"] or "invalid_schema" in res["errors"] or "invalid_action" in res["errors"]
    assert _status(store) == ["pending"]


def test_question_substitution_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q2", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="A")
    res = a.apply_question_answer(
        store, question_id="q2", asking_agent_id=ADAM, answer="A", authorization=auth
    )
    assert res["ok"] is False
    assert "authorization_question_mismatch" in res["errors"]


def test_agent_substitution_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=EVE)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="A")
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=EVE, answer="A", authorization=auth
    )
    assert res["ok"] is False
    assert "authorization_agent_mismatch" in res["errors"]


def test_answer_substitution_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="Intended.")
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="Different.", authorization=auth
    )
    assert res["ok"] is False
    assert "authorization_answer_mismatch" in res["errors"]


def test_authorization_id_tampering_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    good = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="A")
    # Tamper a signed field AFTER signing -> signature no longer verifies.
    tampered = dict(good)
    tampered["question_id"] = "q1"
    tampered["answer_text"] = "HIJACKED"  # extra field is signed -> breaks signature
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="A", authorization=tampered
    )
    assert res["ok"] is False
    assert "invalid_signature" in res["errors"] or "authorization" in "".join(res["errors"])


def test_expired_authorization_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    from datetime import datetime, timezone, timedelta
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="A",
                            issued="2026-01-01T00:00:00Z", expires=past)
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="A", authorization=auth
    )
    assert res["ok"] is False
    assert "authorization_expired" in res["errors"]


def test_malformed_timestamp_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="A",
                            issued="not-a-time", expires="9999-01-01T00:00:00Z")
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="A", authorization=auth
    )
    assert res["ok"] is False
    assert "invalid_issued_at" in res["errors"]


def test_issued_after_expiry_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="A",
                            issued="2026-02-01T00:00:00Z", expires="2026-01-01T00:00:00Z")
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="A", authorization=auth
    )
    assert res["ok"] is False
    assert "issued_after_expiry" in res["errors"]


def test_max_writes_not_one_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="A", max_writes=2)
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="A", authorization=auth
    )
    assert res["ok"] is False
    assert "invalid_authorization" in res["errors"]


# --- receipt authority evidence ----------------------------------------------

def test_valid_envelope_creates_consumed_receipt(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="A")
    res = a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="A", authorization=auth
    )
    assert res["ok"] is True
    from backend.world.first_pair_persistence import load_answer_consumed_receipt
    from backend.world.local_single_question_answer import authorization_id as aid
    receipt = load_answer_consumed_receipt(store, aid(auth))
    assert receipt is not None
    assert receipt["signed_envelope"] == auth
    assert receipt["question_id"] == "q1"
    assert receipt["asking_agent_id"] == ADAM
    assert receipt["formatted_answer_hash"] == auth["formatted_answer_hash"]


def test_receipt_stores_full_signed_envelope(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="Full envelope.")
    a.apply_question_answer(
        store, question_id="q1", asking_agent_id=ADAM, answer="Full envelope.", authorization=auth
    )
    from backend.world.first_pair_persistence import load_answer_consumed_receipt
    from backend.world.local_single_question_answer import authorization_id as aid
    receipt = load_answer_consumed_receipt(store, aid(auth))
    # The stored envelope is identical to the signed input (full envelope persisted).
    assert receipt["signed_envelope"] == auth
    assert receipt["signed_envelope"].get("signature") == auth["signature"]


def test_forged_receipt_without_valid_signature_cannot_authorize(store, trust_env):
    # Plant a receipt whose stored envelope has an INVALID signature, then call the
    # locked transaction directly: it must fail closed.
    priv, pub = trust_env
    _other_priv, _other_pub = _gen_keypair()
    _seed(store, question_id="q1", agent_id=ADAM)
    answer = "A"
    # Build an envelope signed by the WRONG key, store it as a "receipt".
    forged = _signed_envelope(_other_priv, question_id="q1", agent_id=ADAM, answer=answer)
    from backend.world.first_pair_persistence import (
        write_answer_consumed_receipt,
        governed_answer_transaction,
    )
    from backend.world.local_single_question_answer import authorization_id as aid
    aid_forged = aid(forged)
    write_answer_consumed_receipt(
        store, authorization_id=aid_forged, question_id="q1",
        asking_agent_id=ADAM, formatted_answer_hash=forged["formatted_answer_hash"],
        signed_envelope=forged, consumed_at_utc="2026-01-01T00:00:00Z",
    )
    res = governed_answer_transaction(
        store, question_id="q1", answer_material=answer,
        authorized_agent_id=ADAM, authorization_id=aid_forged,
        operator_provenance="op",
    )
    assert res["ok"] is False
    assert res.get("error") == "invalid_signature"
    assert _status(store) == ["pending"]


def test_forged_provenance_without_receipt_cannot_authorize(store, trust_env):
    # Append forged consumed/applied provenance lines, then try the locked
    # transaction with an invented authorization_id: must fail (no receipt).
    from backend.world.first_pair_persistence import governed_answer_transaction
    _seed(store, question_id="q1", agent_id=ADAM)
    store._append_provenance(
        "single_question_answer_consumed",
        {"authorization_id": "auth-invented", "question_id": "q1", "asking_agent_id": ADAM,
         "formatted_answer_hash": a._hash({"answer_material": "X"})},
    )
    res = governed_answer_transaction(
        store, question_id="q1", answer_material="X",
        authorized_agent_id=ADAM, authorization_id="auth-invented",
        operator_provenance="op",
    )
    assert res["ok"] is False
    assert res.get("error") == "answer_authorization_receipt_missing"
    assert _status(store) == ["pending"]


def test_locked_transaction_reverifies_receipt_signature(store, trust_env):
    # A valid signed envelope in the receipt satisfies the locked transaction.
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="A")
    from backend.world.first_pair_persistence import governed_answer_transaction
    from backend.world.local_single_question_answer import authorization_id as aid
    auth_id = aid(auth)
    from backend.world.first_pair_persistence import write_answer_consumed_receipt
    write_answer_consumed_receipt(
        store, authorization_id=auth_id, question_id="q1",
        asking_agent_id=ADAM, formatted_answer_hash=auth["formatted_answer_hash"],
        signed_envelope=auth, consumed_at_utc="2026-01-01T00:00:00Z",
    )
    res = governed_answer_transaction(
        store, question_id="q1", answer_material="A",
        authorized_agent_id=ADAM, authorization_id=auth_id, operator_provenance="op",
    )
    assert res["ok"] is True
    assert _status(store) == ["answered"]


# --- pending-only / re-answer ------------------------------------------------

def test_missing_question_rejected_before_consumption(store, trust_env):
    priv, pub = trust_env
    auth = _signed_envelope(priv, question_id="nope", agent_id=ADAM, answer="X")
    res = a.apply_question_answer(store, question_id="nope", asking_agent_id=ADAM, answer="X", authorization=auth)
    assert res["ok"] is False and "question_not_found" in res["errors"]
    assert _provenance_actions(store) == []
    assert load_questions(store) == []


def test_already_answered_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM, status="answered")
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="First.")
    res = a.apply_question_answer(store, question_id="q1", asking_agent_id=ADAM, answer="First.", authorization=auth)
    assert res["ok"] is False and "question_already_answered" in res["errors"]
    assert "single_question_answer_consumed" not in _provenance_actions(store)


# --- answer validation -------------------------------------------------------

def test_answer_validation_rejects_empty(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="")
    res = a.apply_question_answer(store, question_id="q1", asking_agent_id=ADAM, answer="   ", authorization=auth)
    assert res["ok"] is False and "invalid_answer" in res["errors"]


def test_answer_stored_exact_stripped_only(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="  Tile alpha at 10.0.0.5  ")
    res = a.apply_question_answer(store, question_id="q1", asking_agent_id=ADAM, answer="  Tile alpha at 10.0.0.5  ", authorization=auth)
    assert res["ok"] is True
    assert load_questions(store)[0].provenance.get("answer") == "Tile alpha at 10.0.0.5"


def test_contamination_rejected(store, trust_env):
    priv, pub = trust_env
    _seed(store, question_id="q1", agent_id=ADAM)
    auth = _signed_envelope(priv, question_id="q1", agent_id=ADAM, answer="secret is ABC123")
    res = a.apply_question_answer(store, question_id="q1", asking_agent_id=ADAM, answer="secret is ABC123", authorization=auth)
    assert res["ok"] is False and "invalid_answer" in res["errors"]


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]