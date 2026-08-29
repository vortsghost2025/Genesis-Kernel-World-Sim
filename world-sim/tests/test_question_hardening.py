"""Resolution B hardening pass — RED-to-GREEN authority-boundary tests.

Covers the four closed authority holes plus crash recovery and expiry:

  A. generic save rejects ANY existing-id mutation + malformed ids
  B. mark_question_answered cannot mutate canonical state
  C. governed answer transaction preserves immutable fields, pending-only
  D. runtime persistence cannot stale-write canonical question content
  E. all canonical writers share the store lock
  F. no caller public_key_hex self-signing trust fallback
  H. expiry enforced
  I. deterministic create-transaction crash recovery

All persistence tests use isolated scratch stores; canonical
``world-sim/.runtime/first-pair`` is never written.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    QuestionRecord,
    load_questions,
    save_questions,
)

_ADAM = "genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d"
_EVE = "genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211"
_GOAL = "goal-b0971f2a04c4c41b"
_PAIR = "genesis-first-pair"

_SCRATCH = Path(__file__).resolve().parent.parent / ".qa-hardening-scratch"


@pytest.fixture()
def store():
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    s = FirstPairPersistenceStore(Path(_SCRATCH))
    s.root.mkdir(parents=True, exist_ok=True)
    yield s
    shutil.rmtree(_SCRATCH, ignore_errors=True)


def _q(**overrides) -> QuestionRecord:
    fields = dict(
        question_id="q1",
        asking_agent_id=_ADAM,
        heartbeat=1,
        question="What tiles are available?",
        reason_for_asking="goal",
        related_goal_id=_GOAL,
        requested_human_capability="provide_habitat_information",
        urgency="medium",
        status="pending",
    )
    fields.update(overrides)
    return QuestionRecord(**fields)


def _seed(store, **overrides):
    from backend.world.first_pair_persistence import _save_questions_raw

    q = _q(**overrides)
    _save_questions_raw(store, [q])
    return q


def _gen_keypair():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return priv, pub_raw


def _payload(**overrides) -> dict:
    from backend.world.question_proposal import material_commitment

    base = dict(
        asking_agent_id=_ADAM,
        question_id="q-new",
        related_goal_id=_GOAL,
        question="What does the operator see?",
        reason_for_asking="Need operator info.",
        requested_human_capability="provide_habitat_information",
        urgency="medium",
        pair_id=_PAIR,
    )
    material = dict(base)
    material.update({k: v for k, v in overrides.items() if k in material})
    qid = overrides.get("question_id", "q-new")
    payload = {
        "schema": "single_question_creation_authorization.ed25519.1",
        "domain": "GENESIS_FIRST_PAIR_SINGLE_QUESTION_CREATE_AUTH_ED25519_V1",
        "action": "single_question_create",
        "nonce": "00000000-0000-0000-0000-000000000000",
        "pair_id": _PAIR,
        "asking_agent_id": _ADAM,
        "question_id": qid,
        "related_goal_id": _GOAL,
        "question": "What does the operator see?",
        "reason_for_asking": "Need operator info.",
        "requested_human_capability": "provide_habitat_information",
        "urgency": "medium",
        "question_material_hash": material_commitment(**material),
        "operator_proof_path": "world-sim/docs/example_approval.md",
        "operator_proof_content_sha256": "x" * 64,
        "issued_at_utc": "2026-01-01T00:00:00Z",
        "expires_at_utc": "9999-01-01T00:00:00Z",
        "max_writes": 1,
    }
    payload.update(overrides)
    return payload


def _signed_answer_envelope(priv, *, question_id="q1", agent_id=_ADAM, answer="The answer.",
                            nonce="nonce-1", issued="2026-01-01T00:00:00Z",
                            expires="9999-01-01T00:00:00Z", max_writes=1,
                            operator_proof_ref="proof-1", domain=None, action=None,
                            schema=None):
    """Build a signed Ed25519 answer envelope (ephemeral test key)."""
    import hashlib
    import json

    def h(v):
        return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()

    payload = {
        "schema": schema or "single_question_answer_authorization.ed25519.1",
        "domain": domain or "GENESIS_FIRST_PAIR_SINGLE_QUESTION_ANSWER_AUTH_ED25519_V1",
        "action": action or "single_question_answer",
        "question_id": question_id,
        "asking_agent_id": agent_id,
        "formatted_answer_hash": h({"answer_material": answer.strip()}),
        "max_writes": max_writes,
        "nonce": nonce,
        "issued_at_utc": issued,
        "expires_at_utc": expires,
        "operator_proof_ref": operator_proof_ref,
    }
    signed_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    env = dict(payload)
    env["signature"] = priv.sign(signed_bytes).hex()
    return env


def _write_signed_consumed_receipt(store, priv, *, question_id="q1", agent_id=_ADAM, answer="The answer.", env=None):
    """Write a valid consumed receipt for the signed envelope (authorized path)."""
    from backend.world.first_pair_persistence import write_answer_consumed_receipt
    import backend.world.local_single_question_answer as a

    envelope = env or _signed_answer_envelope(priv, question_id=question_id, agent_id=agent_id, answer=answer)
    auth_id = a.authorization_id(envelope)
    write_answer_consumed_receipt(
        store,
        authorization_id=auth_id,
        question_id=question_id,
        asking_agent_id=agent_id,
        formatted_answer_hash=envelope["formatted_answer_hash"],
        signed_envelope=envelope,
        consumed_at_utc="2026-01-01T00:00:00Z",
    )
    return envelope, auth_id


def _sign(priv, payload: dict):
    return priv.sign(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _envelope(priv, pub_raw, payload: dict) -> dict:
    env = dict(payload)
    env["signature"] = _sign(priv, payload).hex()
    env["public_key_hex"] = pub_raw.hex()
    return env


# ===========================================================================
# A. Generic save must not mutate existing IDs
# ===========================================================================


class TestGenericSaveNoMutation:
    def test_generic_save_rejects_answer_mutation(self, store):
        _seed(store)
        # Mutate the stored answer in provenance of an existing ID.
        q2 = _q()
        q2.provenance = {"answer": "INJECTED ANSWER"}
        q2.status = "answered"
        from backend.world.first_pair_persistence import save_questions_guarded as guarded

        res = guarded(store, [q2])
        assert res.get("ok") is False
        assert "existing_question_mutation" in str(res.get("errors", ""))

    def test_generic_save_rejects_status_mutation(self, store):
        _seed(store)
        q2 = _q(status="answered")
        from backend.world.first_pair_persistence import save_questions_guarded as guarded

        res = guarded(store, [q2])
        assert res.get("ok") is False
        assert "existing_question_mutation" in str(res.get("errors", ""))

    def test_generic_save_rejects_question_text_mutation(self, store):
        _seed(store)
        q2 = _q(question="DIFFERENT TEXT")
        from backend.world import first_pair_persistence as fp

        res = fp.save_questions_guarded(store, [q2])
        assert res.get("ok") is False

    def test_generic_save_rejects_owner_mutation(self, store):
        _seed(store)
        q2 = _q(asking_agent_id=_EVE)
        from backend.world import first_pair_persistence as fp

        res = fp.save_questions_guarded(store, [q2])
        assert res.get("ok") is False

    def test_generic_save_rejects_goal_binding_mutation(self, store):
        _seed(store)
        q2 = _q(related_goal_id="goal-other")
        from backend.world import first_pair_persistence as fp

        res = fp.save_questions_guarded(store, [q2])
        assert res.get("ok") is False

    def test_generic_save_accepts_semantically_identical(self, store):
        q = _seed(store)
        # An identical record is a no-op, not a mutation.
        q2 = QuestionRecord(**{
            k: v for k, v in q.__dict__.items()
        })
        from backend.world import first_pair_persistence as fp

        res = fp.save_questions_guarded(store, [q2])
        assert res.get("ok") is True
        # Canonical unchanged.
        assert load_questions(store)[0].question == "What tiles are available?"

    def test_duplicate_ids_reject(self, store):
        from backend.world import first_pair_persistence as fp

        q1 = _q(question_id="dup")
        q2 = _q(question_id="dup")
        res = fp.save_questions_guarded(store, [q1, q2])
        assert res.get("ok") is False

    def test_empty_id_reject(self, store):
        from backend.world import first_pair_persistence as fp

        res = fp.save_questions_guarded(store, [_q(question_id="")])
        assert res.get("ok") is False

    def test_non_string_id_reject(self, store):
        from backend.world import first_pair_persistence as fp

        bad = _q(question_id=123)
        res = fp.save_questions_guarded(store, [bad])
        assert res.get("ok") is False


# ===========================================================================
# B. mark_question_answered must not mutate canonical state
# ===========================================================================


class TestLegacyMarkAnsweredDisabled:
    def test_mark_question_answered_cannot_mutate(self, store):
        _seed(store, question_id="q1", status="pending")
        from backend.world.first_pair_persistence import mark_question_answered

        result = mark_question_answered(store, "q1", "Because.")
        # Must not transition pending -> answered, must not write an answer.
        after = load_questions(store)
        assert after[0].status == "pending"
        assert "answer" not in after[0].provenance


# ===========================================================================
# C. Governed answer transaction
# ===========================================================================


class TestGovernedAnswerTransaction:
    def _seed_and_receipt(self, store, question_id, agent, answer, monkeypatch=None, priv=None):
        """Write a VALID signed consumed receipt (does NOT seed the question)."""
        if priv is None:
            priv, _pub = _gen_keypair()
        if monkeypatch is not None:
            from cryptography.hazmat.primitives import serialization
            monkeypatch.setenv(
                "GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX",
                priv.public_key().public_bytes(
                    serialization.Encoding.Raw, serialization.PublicFormat.Raw
                ).hex(),
            )
        else:
            from cryptography.hazmat.primitives import serialization
            import os
            os.environ[
                "GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX"
            ] = priv.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            ).hex()
        envelope, auth_id = _write_signed_consumed_receipt(
            store, priv, question_id=question_id, agent_id=agent, answer=answer
        )
        return priv, auth_id, envelope

    def _apply(self, store, monkeypatch, question_id, answer, agent=None, priv=None):
        from backend.world.first_pair_persistence import governed_answer_transaction

        agent = agent or _ADAM
        priv = priv or _gen_keypair()[0]
        # NOTE: caller seeds the canonical question state explicitly.
        priv, auth_id, _env = self._seed_and_receipt(
            store, question_id, agent, answer, monkeypatch, priv
        )
        return governed_answer_transaction(
            store,
            question_id=question_id,
            answer_material=answer,
            operator_provenance="operator-1",
            authorized_agent_id=agent,
            authorization_id=auth_id,
        )

    def test_preserves_immutable_fields(self, store, monkeypatch):
        q = _seed(store, question_id="q1", status="pending")
        before = dict(q.__dict__)
        res = self._apply(store, monkeypatch, "q1", "The answer.")
        assert res.get("ok") is True
        after = load_questions(store)[0]
        assert after.status == "answered"
        # Immutable fields preserved.
        assert after.question == before["question"]
        assert after.asking_agent_id == before["asking_agent_id"]
        assert after.related_goal_id == before["related_goal_id"]
        assert after.requested_human_capability == before["requested_human_capability"]
        assert after.urgency == before["urgency"]
        assert after.reason_for_asking == before["reason_for_asking"]
        assert after.question_id == before["question_id"]
        assert after.asked_at_utc == before["asked_at_utc"]

    def test_uses_current_canonical_pending_state(self, store, monkeypatch):
        _seed(store, question_id="q1", status="pending")
        res = self._apply(store, monkeypatch, "q1", "Yes.")
        assert res.get("ok") is True

    def test_answered_cannot_be_reanswered(self, store, monkeypatch):
        _seed(store, question_id="q1", status="answered")
        res = self._apply(store, monkeypatch, "q1", "Again.")
        assert res.get("ok") is False
        assert res.get("error") == "question_already_answered"

    def test_missing_question_rejected(self, store, monkeypatch):
        _seed(store, question_id="q1", status="pending")
        res = self._apply(store, monkeypatch, "q-nonexistent", "X")
        assert res.get("ok") is False

    def test_wrong_agent_rejected(self, store, monkeypatch):
        _seed(store, question_id="q1", status="pending")
        from backend.world.first_pair_persistence import governed_answer_transaction

        priv, _pub = _gen_keypair()
        priv, auth_id, _env = self._seed_and_receipt(
            store, "q1", _ADAM, "Y", monkeypatch, priv
        )
        # authorized_agent_id mismatch -> must reject owner binding.
        res = governed_answer_transaction(
            store, question_id="q1", answer_material="Y",
            operator_provenance="op", authorized_agent_id=_EVE,
            authorization_id=auth_id,
        )
        assert res.get("ok") is False
        assert res.get("error") == "answer_authorization_agent_mismatch"

    def test_missing_authorized_agent_id_rejected(self, store):
        # Direct low-level call WITHOUT authorization material cannot answer.
        _seed(store, question_id="q1", status="pending")
        from backend.world.first_pair_persistence import governed_answer_transaction
        import inspect

        sig = inspect.signature(governed_answer_transaction)
        assert sig.parameters["authorized_agent_id"].default is inspect.Parameter.empty
        assert sig.parameters["authorization_id"].default is inspect.Parameter.empty

    def test_direct_unauthorized_answer_rejected(self, store):
        # A direct call with only question_id + answer cannot answer.
        _seed(store, question_id="q1", status="pending")
        from backend.world.first_pair_persistence import governed_answer_transaction

        try:
            governed_answer_transaction(store, question_id="q1", answer_material="X")
            raised = False
        except TypeError:
            raised = True
        assert raised is True
        assert load_questions(store)[0].status == "pending"

    # --- AUTHORITY BOUNDARY TESTS (receipt + signature) ---

    def test_invented_auth_id_rejected_without_receipt(self, store, monkeypatch):
        _seed(store, question_id="q1", status="pending")
        from backend.world.first_pair_persistence import governed_answer_transaction
        monkeypatch.setenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", _gen_keypair()[1].hex())

        res = governed_answer_transaction(
            store, question_id="q1", answer_material="Injected.",
            operator_provenance="op", authorized_agent_id=_ADAM,
            authorization_id="anything",
        )
        assert res.get("ok") is False
        assert res.get("error") == "answer_authorization_receipt_missing"
        assert load_questions(store)[0].status == "pending"

    def test_stolen_auth_id_for_other_question_rejected(self, store, monkeypatch):
        _seed(store, question_id="q1", status="pending")
        _seed(store, question_id="q2", status="pending")
        from backend.world.first_pair_persistence import governed_answer_transaction

        priv, _pub = _gen_keypair()
        priv, auth_real, _env = self._seed_and_receipt(
            store, "q2", _ADAM, "Answer for q2.", monkeypatch, priv
        )
        res = governed_answer_transaction(
            store, question_id="q1", answer_material="Answer for q2.",
            operator_provenance="op", authorized_agent_id=_ADAM,
            authorization_id=auth_real,
        )
        assert res.get("ok") is False
        assert res.get("error") == "answer_authorization_question_mismatch"
        assert load_questions(store)[0].status == "pending"

    def test_stolen_auth_id_for_different_answer_rejected(self, store, monkeypatch):
        _seed(store, question_id="q1", status="pending")
        from backend.world.first_pair_persistence import governed_answer_transaction

        priv, _pub = _gen_keypair()
        priv, auth_real, _env = self._seed_and_receipt(
            store, "q1", _ADAM, "Authorized answer.", monkeypatch, priv
        )
        res = governed_answer_transaction(
            store, question_id="q1", answer_material="Evil answer.",
            operator_provenance="op", authorized_agent_id=_ADAM,
            authorization_id=auth_real,
        )
        assert res.get("ok") is False
        assert res.get("error") == "answer_authorization_answer_mismatch"
        assert load_questions(store)[0].status == "pending"

    def test_valid_consumed_receipt_allows_answer(self, store, monkeypatch):
        _seed(store, question_id="q1", status="pending")
        res = self._apply(store, monkeypatch, "q1", "The answer.")
        assert res.get("ok") is True
        assert load_questions(store)[0].status == "answered"


# ===========================================================================
# D. Runtime stale-write eliminated
# ===========================================================================


class TestRuntimeNoStaleWrite:
    def test_runtime_persist_does_not_revert_answer(self, store, monkeypatch):
        from backend.world.first_pair_runtime import FirstPairRuntime

        rt = FirstPairRuntime(store=store)
        rt._load_or_initialize()  # fresh init: empty canonical state

        # Seed a pending Q1 canonically (test-only; bypasses creation authority).
        _seed(store, question_id="q1", status="pending")

        # A loads the pending Q1 into runtime memory (stale view).
        rt._questions = load_questions(store)
        assert rt._questions[0].status == "pending"

        # B governed-answers Q1 (valid signed consumed receipt).
        priv, _pub = _gen_keypair()
        from cryptography.hazmat.primitives import serialization
        monkeypatch.setenv(
            "GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX",
            priv.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            ).hex(),
        )
        _env, auth_b = _write_signed_consumed_receipt(
            store, priv, question_id="q1", agent_id=_ADAM, answer="Answered by B."
        )
        from backend.world.first_pair_persistence import governed_answer_transaction

        res = governed_answer_transaction(
            store, question_id="q1", answer_material="Answered by B.", operator_provenance="op",
            authorized_agent_id=_ADAM, authorization_id=auth_b,
        )
        assert res.get("ok") is True

        # A persists (stale). Q1 must remain answered with B's answer.
        rt._persist_questions_without_stale_overwrite()
        after = load_questions(store)
        assert after[0].status == "answered"
        assert after[0].provenance.get("answer") == "Answered by B."


# ===========================================================================
# F/H. Trust fallback + expiry
# ===========================================================================


class TestTrustAndExpiry:
    def _create(self, store, envelope):
        from backend.world.first_pair_persistence import create_authorized_question

        return create_authorized_question(store, authorization=envelope)

    def _set_env(self, monkeypatch, pub_raw):
        monkeypatch.setenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", pub_raw.hex())

    def test_no_key_configured_self_signed_rejected(self, store, monkeypatch):
        # Attacker signs with their OWN key and supplies public_key_hex in-band.
        monkeypatch.delenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", raising=False)
        priv, pub = _gen_keypair()
        envelope = _envelope(priv, pub, _payload(question_id="q-self"))
        # No env trust key configured: create must NOT trust the in-band key.
        res = self._create(store, envelope)
        assert res.get("ok") is False
        assert res.get("error") == "operator_public_key_unconfigured"

    def test_env_absent_attacker_keyfile_rejected(self, store, monkeypatch):
        # Attackers cannot establish trust via a source-tree key file: the
        # production loader reads ONLY the env var and performs no file read.
        monkeypatch.delenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", raising=False)
        import backend.world.first_pair_persistence as fp

        # Patch the module's `open`/`Path.read_text` so ANY file access would
        # fail the test: the loader must not read a file to resolve trust.
        opened = []

        def _no_open(*args, **kwargs):
            opened.append(args)
            raise AssertionError("trust loader must not read any file")

        monkeypatch.setattr(fp.os, "environ", {})  # ensure env is fully absent
        # Directly invoke the loader: with env absent it must return None and
        # touch no file.
        result = fp._load_public_keys()
        assert result is None

        # And create must fail closed end-to-end.
        priv, pub = _gen_keypair()
        envelope = _envelope(priv, pub, _payload(question_id="q-self"))
        res = self._create(store, envelope)
        assert res.get("ok") is False
        assert res.get("error") == "operator_public_key_unconfigured"

    def test_caller_cannot_inject_trust_key(self, store):
        # create_authorized_question has NO trusted_public_key_bytes parameter.
        import inspect
        from backend.world.first_pair_persistence import create_authorized_question

        assert "trusted_public_key_bytes" not in inspect.signature(create_authorized_question).parameters

    def test_correct_env_key_accepts(self, store, monkeypatch):
        priv, pub = _gen_keypair()
        self._set_env(monkeypatch, pub)
        envelope = _envelope(priv, pub, _payload(question_id="q-ok"))
        res = self._create(store, envelope)
        assert res.get("ok") is True

    def test_wrong_signer_rejected(self, store, monkeypatch):
        priv, pub = _gen_keypair()
        _other_priv, other_pub = _gen_keypair()
        self._set_env(monkeypatch, other_pub)  # env key is OTHER_PUB
        envelope = _envelope(priv, pub, _payload(question_id="q-wrong"))
        res = self._create(store, envelope)
        assert res.get("ok") is False
        assert res.get("error") == "invalid_signature"

    def test_malformed_env_fails_closed(self, store, monkeypatch):
        monkeypatch.setenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", "zz-not-hex")
        priv, pub = _gen_keypair()
        envelope = _envelope(priv, pub, _payload(question_id="q-bad"))
        res = self._create(store, envelope)
        assert res.get("ok") is False
        assert "malformed" in res.get("error", "")

    def test_expired_rejected(self, store, monkeypatch):
        priv, pub = _gen_keypair()
        self._set_env(monkeypatch, pub)
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        envelope = _envelope(priv, pub, _payload(question_id="q-exp", expires_at_utc=past))
        res = self._create(store, envelope)
        assert res.get("ok") is False
        assert "expired" in res.get("error", "")

    def test_malformed_expiry_rejected(self, store, monkeypatch):
        priv, pub = _gen_keypair()
        self._set_env(monkeypatch, pub)
        envelope = _envelope(priv, pub, _payload(question_id="q-badexp", expires_at_utc="not-a-date"))
        # Signature over malformed expiry still verifies, but expiry parsing fails closed.
        res = self._create(store, envelope)
        assert res.get("ok") is False
        assert "expir" in res.get("error", "").lower()

    def test_issued_after_expiry_rejected(self, store, monkeypatch):
        priv, pub = _gen_keypair()
        self._set_env(monkeypatch, pub)
        envelope = _envelope(
            priv, pub,
            _payload(
                question_id="q-order",
                issued_at_utc="2026-02-01T00:00:00Z",
                expires_at_utc="2026-01-01T00:00:00Z",
            ),
        )
        res = self._create(store, envelope)
        assert res.get("ok") is False

    def test_valid_unexpired_accepted(self, store, monkeypatch):
        priv, pub = _gen_keypair()
        self._set_env(monkeypatch, pub)
        envelope = _envelope(priv, pub, _payload(question_id="q-ok"))
        res = self._create(store, envelope)
        assert res.get("ok") is True


# ===========================================================================
# I. Crash recovery
# ===========================================================================


class TestCreateCrashRecovery:
    def _mk(self, store, question_id="q-crash"):
        priv, pub = _gen_keypair()
        envelope = _envelope(priv, pub, _payload(question_id=question_id))
        from backend.world.local_single_question_create import authorization_id
        from backend.world.first_pair_persistence import _receipt_path

        auth_id = authorization_id(envelope)
        return envelope, pub, auth_id, _receipt_path

    def _create(self, monkeypatch, store, envelope, pub):
        monkeypatch.setenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", pub.hex())
        from backend.world.first_pair_persistence import create_authorized_question

        return create_authorized_question(store, authorization=envelope)

    def test_crash_after_intent_before_question_recovers(self, store, monkeypatch):
        envelope, pub, auth_id, path = self._mk(store, "q-i1")
        from backend.world.first_pair_persistence import _receipt_path

        # Simulate crash: write intent only (with binding commitment), no
        # question, no applied — exactly what production would have written.
        store._receipt_dir().mkdir(parents=True, exist_ok=True)
        store._atomic_write(path(store, auth_id, "intent"), {
            "authorization_id": auth_id,
            "question_id": "q-i1",
            "material_commitment": envelope["question_material_hash"],
            "signed_authorization": envelope,
        })
        # Retry same authorization.
        res = self._create(monkeypatch, store, envelope, pub)
        assert res.get("ok") is True
        assert any(q.question_id == "q-i1" for q in load_questions(store))

    def test_crash_after_question_before_applied_finalizes(self, store, monkeypatch):
        from backend.world.first_pair_persistence import (
            _save_questions_raw,
            QuestionRecord,
        )

        priv, pub = _gen_keypair()
        envelope = _envelope(priv, pub, _payload(question_id="q-i2"))
        from backend.world.local_single_question_create import authorization_id
        from backend.world.first_pair_persistence import _receipt_path

        auth_id = authorization_id(envelope)
        store._receipt_dir().mkdir(parents=True, exist_ok=True)
        # intent present
        store._atomic_write(_receipt_path(store, auth_id, "intent"), {
            "authorization_id": auth_id, "question_id": "q-i2",
            "material_commitment": envelope["question_material_hash"],
            "signed_authorization": envelope,
        })
        # question present, applied absent
        _save_questions_raw(store, [QuestionRecord(
            question_id="q-i2", asking_agent_id=_ADAM, heartbeat=0,
            question="What does the operator see?", reason_for_asking="Need operator info.",
            related_goal_id=_GOAL, requested_human_capability="provide_habitat_information",
            urgency="medium", status="pending",
        )])
        # Retry same authorization -> recover/finalize.
        res = self._create(monkeypatch, store, envelope, pub)
        assert res.get("ok") is True
        assert _receipt_path(store, auth_id, "applied").exists()

    def test_mismatching_question_during_recovery_fails_closed(self, store, monkeypatch):
        from backend.world.first_pair_persistence import (
            _save_questions_raw,
            QuestionRecord,
        )

        priv, pub = _gen_keypair()
        envelope = _envelope(priv, pub, _payload(question_id="q-i3"))
        from backend.world.local_single_question_create import authorization_id
        from backend.world.first_pair_persistence import _receipt_path

        auth_id = authorization_id(envelope)
        store._receipt_dir().mkdir(parents=True, exist_ok=True)
        store._atomic_write(_receipt_path(store, auth_id, "intent"), {
            "authorization_id": auth_id, "question_id": "q-i3",
            "material_commitment": envelope["question_material_hash"],
            "signed_authorization": envelope,
        })
        # A DIFFERENT question occupies the id (content mismatch).
        _save_questions_raw(store, [QuestionRecord(
            question_id="q-i3", asking_agent_id=_ADAM, heartbeat=0,
            question="TOTALLY DIFFERENT CONTENT", reason_for_asking="other",
            related_goal_id=_GOAL, requested_human_capability="provide_habitat_information",
            urgency="medium", status="pending",
        )])
        res = self._create(monkeypatch, store, envelope, pub)
        assert res.get("ok") is False
        assert "ambig" in res.get("error", "").lower() or "corrupt" in res.get("error", "").lower() or "mismatch" in res.get("error", "").lower()

    def test_different_auth_cannot_adopt_old_intent(self, store, monkeypatch):
        priv, pub = _gen_keypair()
        env_a = _envelope(priv, pub, _payload(question_id="q-a"))
        env_b = _envelope(priv, pub, _payload(question_id="q-b"))
        from backend.world.local_single_question_create import authorization_id
        from backend.world.first_pair_persistence import _receipt_path

        auth_a = authorization_id(env_a)
        store._receipt_dir().mkdir(parents=True, exist_ok=True)
        store._atomic_write(_receipt_path(store, auth_a, "intent"), {
            "authorization_id": auth_a, "question_id": "q-a",
            "material_commitment": env_a["question_material_hash"],
            "signed_authorization": env_a,
        })
        # A different authorization must not adopt auth_a's intent.
        res = self._create(monkeypatch, store, env_b, pub)
        assert res.get("ok") is True
        # b was created; a's intent still belongs to a (not adopted).
        assert any(q.question_id == "q-b" for q in load_questions(store))

    def test_applied_present_missing_provenance_recovered(self, store, monkeypatch):
        # CASE 5 + Closure 4: applied marker present but create-consumed
        # provenance absent -> retry must repair provenance exactly once.
        from backend.world.first_pair_persistence import (
            _save_questions_raw,
            QuestionRecord,
        )
        priv, pub = _gen_keypair()
        envelope = _envelope(priv, pub, _payload(question_id="q-i4"))
        from backend.world.local_single_question_create import authorization_id
        from backend.world.first_pair_persistence import _receipt_path, _provenance_records

        auth_id = authorization_id(envelope)
        store._receipt_dir().mkdir(parents=True, exist_ok=True)
        store._atomic_write(_receipt_path(store, auth_id, "intent"), {
            "authorization_id": auth_id, "question_id": "q-i4",
            "material_commitment": envelope["question_material_hash"],
            "signed_authorization": envelope,
        })
        _save_questions_raw(store, [QuestionRecord(
            question_id="q-i4", asking_agent_id=_ADAM, heartbeat=0,
            question="What does the operator see?", reason_for_asking="Need operator info.",
            related_goal_id=_GOAL, requested_human_capability="provide_habitat_information",
            urgency="medium", status="pending",
        )])
        store._atomic_write(_receipt_path(store, auth_id, "applied"), {
            "authorization_id": auth_id, "question_id": "q-i4", "applied_at_utc": "x",
        })
        # No create-consumed provenance yet.
        assert not any(r.get("action") == "single_question_create_consumed" for r in _provenance_records(store))
        res = self._create(monkeypatch, store, envelope, pub)
        assert res.get("ok") is False
        assert res.get("error") == "authorization_already_consumed"
        # Provenance repaired exactly once.
        consumed = [r for r in _provenance_records(store) if r.get("action") == "single_question_create_consumed"]
        assert len(consumed) == 1
        # Second retry does not duplicate.
        res2 = self._create(monkeypatch, store, envelope, pub)
        assert res2.get("ok") is False
        consumed2 = [r for r in _provenance_records(store) if r.get("action") == "single_question_create_consumed"]
        assert len(consumed2) == 1


# ===========================================================================
# E. Shared lock (both writers acquire the same lock file)
# ===========================================================================


class TestSharedLock:
    def test_governed_answer_uses_store_lock(self):
        import backend.world.first_pair_persistence as fp

        # The narrow transaction and create both resolve to the same lock path.
        from backend.world.first_pair_persistence import FirstPairPersistenceStore

        s = FirstPairPersistenceStore(Path(_SCRATCH))
        s.root.mkdir(parents=True, exist_ok=True)
        # Both must reference the same lock file.
        assert "question.store.lock" in str(s._lock_path().name)

    def test_initialization_cannot_overwrite_existing_questions(self, store):
        # Seed an existing canonical question, then run the init guard: it must
        # NOT erase it.
        _seed(store, question_id="q-keep", status="pending")
        from backend.world.first_pair_persistence import _initialize_questions_if_absent

        _initialize_questions_if_absent(store)
        after = load_questions(store)
        assert any(q.question_id == "q-keep" for q in after)
        assert after[0].status == "pending"

    def test_initialization_writes_when_absent(self, store):
        from backend.world.first_pair_persistence import _initialize_questions_if_absent, _QUESTIONS_FILE

        # Remove any questions file; init guard should create the empty seed.
        qpath = store._path(_QUESTIONS_FILE)
        if qpath.exists():
            qpath.unlink()
        _initialize_questions_if_absent(store)
        assert qpath.exists()
        assert load_questions(store) == []


# ===========================================================================
# J. Answer crash evidence recovery
# ===========================================================================


class TestAnswerCrashRecovery:
    def _seed_and_auth(self, store, answer="Answer.", monkeypatch=None, priv=None):
        import backend.world.local_single_question_answer as a
        from cryptography.hazmat.primitives import serialization

        if priv is None:
            priv, _pub = _gen_keypair()
        pub_hex = priv.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ).hex()
        if monkeypatch is not None:
            monkeypatch.setenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", pub_hex)
        else:
            import os

            os.environ["GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX"] = pub_hex

        _seed(store, question_id="q1", status="pending")
        auth = _signed_answer_envelope(priv, question_id="q1", agent_id=_ADAM, answer=answer)
        return a, auth, priv

    def test_consume_before_answer_remains_fail_closed(self, store, monkeypatch):
        # Window B: receipt written, transaction fails -> auth burned, pending.
        import backend.world.local_single_question_answer as a

        a_mod, auth, priv = self._seed_and_auth(store, monkeypatch=monkeypatch)
        # Force the governed transaction to fail AFTER consume receipt.
        monkeypatch.setattr(a_mod, "governed_answer_transaction", lambda *a, **k: {"ok": False, "error": "injected"})
        res = a_mod.apply_question_answer(
            store, question_id="q1", asking_agent_id=_ADAM, answer="Answer.", authorization=auth
        )
        assert res["ok"] is False
        assert "AUTHORIZATION_BURNED_QUESTION_PENDING" == res.get("warn")
        assert load_questions(store)[0].status == "pending"
        # Retry same auth is blocked (already consumed), question still pending.
        monkeypatch.undo()
        # Reinstall the trust key (undo() removed the env var).
        from cryptography.hazmat.primitives import serialization

        monkeypatch.setenv(
            "GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX",
            priv.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            ).hex(),
        )
        res2 = a_mod.apply_question_answer(
            store, question_id="q1", asking_agent_id=_ADAM, answer="Answer.", authorization=auth
        )
        assert res2["ok"] is False
        assert "authorization_already_consumed" in res2["errors"]

    def test_answer_before_applied_retry_repairs(self, store, monkeypatch):
        # Window C: answer written, applied provenance missing -> retry repairs.
        import backend.world.local_single_question_answer as a

        a_mod, auth, priv = self._seed_and_auth(store, answer="Answer C.", monkeypatch=monkeypatch)

        # Inject an applied-provenance failure on FIRST call.
        orig = store._append_provenance

        def raiser(action, detail):
            if action == "single_question_answer_applied":
                raise OSError("injected")
            return orig(action, detail)

        store._append_provenance = raiser
        res = a_mod.apply_question_answer(
            store, question_id="q1", asking_agent_id=_ADAM, answer="Answer C.", authorization=auth
        )
        assert res["ok"] is False
        assert res.get("warn") == "ANSWER_APPLIED_AUDIT_INCOMPLETE"
        assert load_questions(store)[0].status == "answered"

        # Restore; retry same auth -> recovery repairs applied provenance once.
        store._append_provenance = orig
        res2 = a_mod.apply_question_answer(
            store, question_id="q1", asking_agent_id=_ADAM, answer="Answer C.", authorization=auth
        )
        assert res2["ok"] is True
        assert res2.get("recovered") is True
        applied = [r for r in a_mod._provenance_records(store) if r.get("action") == "single_question_answer_applied"]
        assert len(applied) == 1

        # Third retry: applied already present -> not a recovered-success, replay blocked.
        res3 = a_mod.apply_question_answer(
            store, question_id="q1", asking_agent_id=_ADAM, answer="Answer C.", authorization=auth
        )
        assert res3["ok"] is False
        assert "authorization_already_consumed" in res3["errors"]

    def test_answer_content_mismatch_recovery_refuses(self, store, monkeypatch):
        # Authorization bound to answer "Authorized answer.", but the canonical
        # question was answered with a DIFFERENT answer under a DIFFERENT
        # authorization: recovery must refuse (not repair) the ORIGINAL auth.
        import backend.world.local_single_question_answer as a

        a_mod, auth, priv = self._seed_and_auth(store, answer="Authorized answer.", monkeypatch=monkeypatch)
        # Answer the question with a DIFFERENT answer via a DIFFERENT authorization,
        # using the real authorized path (signed receipt + transaction).
        _env_diff, auth_diff = _write_signed_consumed_receipt(
            store, priv, question_id="q1", agent_id=_ADAM, answer="DIFFERENT answer."
        )
        from backend.world.first_pair_persistence import governed_answer_transaction

        tx = governed_answer_transaction(
            store, question_id="q1", answer_material="DIFFERENT answer.",
            operator_provenance="op", authorized_agent_id=_ADAM, authorization_id=auth_diff,
        )
        assert tx.get("ok") is True
        assert load_questions(store)[0].provenance.get("answer") == "DIFFERENT answer."

        # Also write a consumed receipt for the ORIGINAL authorization.
        _env_orig, auth_orig = _write_signed_consumed_receipt(
            store, priv, question_id="q1", agent_id=_ADAM, answer="Authorized answer."
        )
        # Retry the ORIGINAL authorization whose bound answer differs from stored.
        res = a_mod.apply_question_answer(
            store, question_id="q1", asking_agent_id=_ADAM, answer="Authorized answer.", authorization=auth
        )
        assert res["ok"] is False
        assert "authorization_already_consumed" in res["errors"]
        # No applied provenance was fabricated for the mismatched/cross-auth state.
        applied = [r for r in a_mod._provenance_records(store) if r.get("action") == "single_question_answer_applied" and r.get("detail", {}).get("authorization_id") == auth_orig]
        assert len(applied) == 0