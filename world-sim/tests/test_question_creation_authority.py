"""RED tests — signed question-creation authority contract.

These tests specify the FUTURE question-creation authority boundary and are
expected to FAIL against the current implementation (which has no cryptographic
operator authority and no governed question-creation seam).

Important: this is a RED-only suite. The future production modules
(``local_single_question_create``, ``question_proposal``, the signed-authority
verifier, the store creation transaction) DO NOT EXIST yet. Tests that depend on
them perform the import inside the individual test (or use a precise helper) so
that a missing symbol surfaces as a FAILURE of the contract, never as a global
collection abort and never as a silent skip.

All persistence tests use isolated scratch stores. The canonical
``world-sim/.runtime/first-pair`` surface is never written.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import unicodedata
from pathlib import Path

import pytest

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    QuestionRecord,
    load_questions,
    save_questions,
)

# ---------------------------------------------------------------------------
# Deterministic futures that must eventually exist. Imported lazily so that the
# current absence is reported as a contract failure, not a collection crash.
# ---------------------------------------------------------------------------

_ADAM = "genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d"
_EVE = "genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211"
_GOAL = "goal-b0971f2a04c4c41b"
_PAIR = "genesis-first-pair"

_SCRATCH = Path(__file__).resolve().parent.parent / ".qa-creation-scratch"


@pytest.fixture()
def store():
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    s = FirstPairPersistenceStore(Path(_SCRATCH))
    s.root.mkdir(parents=True, exist_ok=True)
    yield s
    shutil.rmtree(_SCRATCH, ignore_errors=True)


def _q(**overrides) -> QuestionRecord:
    fields = dict(
        question_id="q-new",
        asking_agent_id=_ADAM,
        heartbeat=0,
        question="What does the operator see from their vantage?",
        reason_for_asking="Need operator-provided information.",
        related_goal_id=_GOAL,
        requested_human_capability="provide_habitat_information",
        urgency="medium",
        status="pending",
    )
    fields.update(overrides)
    return QuestionRecord(**fields)


def _future_symbol(module_name: str, attr: str):
    """Return the future symbol or raise a precise contract failure.

    The raise is deliberate: a missing future symbol must be a GOOD_RED
    failure (the contract is unimplemented), not a skip.
    """
    try:
        import importlib

        mod = importlib.import_module(module_name)
    except ImportError as exc:
        raise AssertionError(
            f"CONTRACT_MISSING: module {module_name} does not exist yet "
            f"(future signed question-creation authority not implemented): {exc}"
        )
    name = getattr(mod, attr, None)
    if name is None:
        raise AssertionError(
            f"CONTRACT_MISSING: {module_name}.{attr} does not exist yet"
        )
    return name


# ===========================================================================
# GROUP B — cryptographic authority contract (ephemeral test-only keys)
# ===========================================================================


def _gen_test_keypair():
    """Ephemeral, in-memory Ed25519 keypair for TEST ONLY.

    Never persisted. Never treated as production authority.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    from cryptography.hazmat.primitives import serialization

    pub_raw = pub.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return priv, pub_raw


def _create_authorized(store, envelope, pub_raw, monkeypatch=None):
    """Create via the production API with the trusted key injected through the
    ENV trust root (the only supported trust source), never a caller argument."""
    from backend.world.first_pair_persistence import create_authorized_question

    if monkeypatch is not None:
        monkeypatch.setenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", pub_raw.hex())
        return create_authorized_question(store, authorization=envelope)
    saved = os.environ.get("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX")
    os.environ["GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX"] = pub_raw.hex()
    try:
        return create_authorized_question(store, authorization=envelope)
    finally:
        if saved is None:
            os.environ.pop("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", None)
        else:
            os.environ["GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX"] = saved


def _canonical_payload(**overrides) -> dict:
    from backend.world.question_proposal import material_commitment

    base = dict(
        asking_agent_id=_ADAM,
        question_id="q-new",
        related_goal_id=_GOAL,
        question="What does the operator see from their vantage?",
        reason_for_asking="Need operator-provided information.",
        requested_human_capability="provide_habitat_information",
        urgency="medium",
        pair_id=_PAIR,
    )
    if overrides and any(k in overrides for k in base):
        material = dict(base)
        material.update({k: v for k, v in overrides.items() if k in base})
    else:
        material = base
    question_material_hash = (
        overrides.pop("question_material_hash")
        if "question_material_hash" in overrides
        else material_commitment(**material)
    )
    payload = {
        "schema": "single_question_creation_authorization.ed25519.1",
        "domain": "GENESIS_FIRST_PAIR_SINGLE_QUESTION_CREATE_AUTH_ED25519_V1",
        "action": "single_question_create",
        "nonce": "00000000-0000-0000-0000-000000000000",
        "pair_id": _PAIR,
        "asking_agent_id": _ADAM,
        "question_id": "q-new",
        "related_goal_id": _GOAL,
        "question": "What does the operator see from their vantage?",
        "reason_for_asking": "Need operator-provided information.",
        "requested_human_capability": "provide_habitat_information",
        "urgency": "medium",
        "question_material_hash": question_material_hash,
        "operator_proof_path": "world-sim/docs/example_approval.md",
        "operator_proof_content_sha256": "x" * 64,
        "issued_at_utc": "2026-01-01T00:00:00Z",
        "expires_at_utc": "9999-01-01T00:00:00Z",
        "max_writes": 1,
    }
    payload.update(overrides)
    return payload


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sign_bytes(priv, payload: dict) -> bytes:
    """Sign the canonical unsigned payload bytes (payload lacks a signature)."""
    return priv.sign(_canonical_json(payload).encode("utf-8"))


def _signed_envelope(priv, pub_raw, payload: dict) -> dict:
    sig = _sign_bytes(priv, payload)
    envelope = dict(payload)
    envelope["signature"] = sig.hex()
    envelope["public_key_hex"] = pub_raw.hex()
    return envelope


class TestSignedAuthorizationContract:
    """Future verifier contract. All assert a future API; expected to fail RED."""

    def _future_verifier(self):
        return _future_symbol(
            "backend.world.local_single_question_create",
            "verify_question_creation_authorization",
        )

    def test_valid_signature_exact_material_succeeds(self):
        verify = self._future_verifier()
        priv, pub = _gen_test_keypair()
        payload = _canonical_payload()
        envelope = _signed_envelope(priv, pub, payload)
        ok, _ = verify(pub, envelope)
        assert ok is True

    def test_unsigned_authorization_rejected(self):
        verify = self._future_verifier()
        priv, pub = _gen_test_keypair()
        payload = _canonical_payload()
        envelope = dict(payload)  # no signature
        envelope["public_key_hex"] = pub.hex()
        ok, err = verify(pub, envelope)
        assert ok is False and err

    def test_malformed_signature_rejected(self):
        verify = self._future_verifier()
        priv, pub = _gen_test_keypair()
        payload = _canonical_payload()
        envelope = _signed_envelope(priv, pub, payload)
        envelope["signature"] = "00" * 64  # wrong bytes, right length
        ok, _ = verify(pub, envelope)
        assert ok is False

    def test_signature_from_unknown_key_rejected(self):
        verify = self._future_verifier()
        priv, pub = _gen_test_keypair()
        _, other_pub = _gen_test_keypair()
        payload = _canonical_payload()
        envelope = _signed_envelope(priv, pub, payload)
        ok, _ = verify(other_pub, envelope)
        assert ok is False

    def test_one_bit_payload_mutation_rejected(self):
        verify = self._future_verifier()
        priv, pub = _gen_test_keypair()
        payload = _canonical_payload()
        envelope = _signed_envelope(priv, pub, payload)
        # mutate a single payload char *after* signing
        envelope = json.loads(json.dumps(envelope))
        envelope["urgency"] = ("high" if envelope["urgency"] == "medium" else "medium")
        ok, _ = verify(pub, envelope)
        assert ok is False


class TestSignedMaterialBinding:
    """Signed payload must bind exact material; any drift must invalidate."""

    def _future_verifier(self):
        return _future_symbol(
            "backend.world.local_single_question_create",
            "verify_question_creation_authorization",
        )

    def _expect_rejection(self, mutate):
        verify = self._future_verifier()
        priv, pub = _gen_test_keypair()
        payload = _canonical_payload()
        envelope = _signed_envelope(priv, pub, payload)
        envelope = json.loads(json.dumps(envelope))
        mutate(envelope)
        ok, _ = verify(pub, envelope)
        assert ok is False

    def test_changed_question_text_rejected(self):
        self._expect_rejection(lambda e: e.update(question="Totally different?"))

    def test_changed_question_id_rejected(self):
        self._expect_rejection(lambda e: e.update(question_id="q-other"))

    def test_changed_asking_agent_rejected(self):
        self._expect_rejection(lambda e: e.update(asking_agent_id=_EVE))

    def test_changed_related_goal_rejected(self):
        self._expect_rejection(lambda e: e.update(related_goal_id="goal-other"))

    def test_replay_rejected(self, store):
        from backend.world.first_pair_persistence import create_authorized_question

        priv, pub = _gen_test_keypair()
        payload = _canonical_payload(question_id="q-replay")
        envelope = _signed_envelope(priv, pub, payload)
        first = _create_authorized(store, envelope, pub)
        assert first.get("ok") is True
        second = _create_authorized(store, envelope, pub)
        assert second.get("ok") is False
        assert second.get("error") in ("authorization_already_consumed", "question_id_already_exists")

    def test_invalid_signature_fails_before_receipt(self, store):
        from backend.world.first_pair_persistence import create_authorized_question

        priv, pub = _gen_test_keypair()
        _, bad_pub = _gen_test_keypair()
        payload = _canonical_payload(question_id="q-badsig")
        envelope = _signed_envelope(priv, pub, payload)
        result = _create_authorized(store, envelope, bad_pub)
        assert result.get("ok") is False
        # No intent receipt may exist for a rejected/bad-signature authorization.
        from backend.world.local_single_question_create import authorization_id
        from backend.world.first_pair_persistence import _receipt_path

        auth_id = authorization_id(envelope)
        assert not _receipt_path(store, auth_id, "intent").exists()

    def test_public_key_alone_cannot_mint(self):
        # Ed25519PublicKey has no sign(); the boundary is "public key only".
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        priv, pub = _gen_test_keypair()
        pub_key = Ed25519PublicKey.from_public_bytes(pub)
        assert not hasattr(pub_key, "sign"), (
            "Ed25519PublicKey exposes sign(); public-key-only boundary violated"
        )


# ===========================================================================
# GROUP D — proposal semantics (future question_proposal module)
# ===========================================================================


class TestQuestionProposalSemantics:
    def _proposal(self):
        return _future_symbol("backend.world.question_proposal", "QuestionProposal")

    def test_proposal_is_noncanonical_type(self):
        QP = self._proposal()
        p = QP(
            question_id="q-new",
            asking_agent_id=_ADAM,
            related_goal_id=_GOAL,
            question="What does the operator see?",
            reason_for_asking="Need info.",
            requested_human_capability="provide_habitat_information",
            urgency="medium",
        )
        # A proposal must not be a QuestionRecord-like canonical persisted type.
        assert not isinstance(p, QuestionRecord)

    def test_proposal_grants_no_authority(self):
        QP = self._proposal()
        p = QP(
            question_id="q-new",
            asking_agent_id=_ADAM,
            related_goal_id=_GOAL,
            question="What does the operator see?",
            reason_for_asking="Need info.",
            requested_human_capability="provide_habitat_information",
            urgency="medium",
        )
        assert not hasattr(p, "authorization_id") or getattr(p, "authorization_id", None) is None

    def test_proposal_material_is_deterministically_canonicalized(self):
        canonicalize = _future_symbol("backend.world.question_proposal", "canonicalize_proposal_material")
        a = canonicalize(
            question="  What does the operator see?  ",
            reason_for_asking="  Need info.  ",
            requested_human_capability="provide_habitat_information",
            urgency="medium",
            question_id="q-new",
            asking_agent_id=_ADAM,
            related_goal_id=_GOAL,
            pair_id=_PAIR,
        )
        b = canonicalize(
            question="What does the operator see?",
            reason_for_asking="Need info.",
            requested_human_capability="provide_habitat_information",
            urgency="medium",
            question_id="q-new",
            asking_agent_id=_ADAM,
            related_goal_id=_GOAL,
            pair_id=_PAIR,
        )
        assert a == b

    def test_material_mutation_changes_commitment(self):
        canonicalize = _future_symbol("backend.world.question_proposal", "material_commitment")
        h1 = canonicalize(
            question="What does the operator see?",
            reason_for_asking="Need info.",
            requested_human_capability="provide_habitat_information",
            urgency="medium",
            question_id="q-new",
            asking_agent_id=_ADAM,
            related_goal_id=_GOAL,
            pair_id=_PAIR,
        )
        h2 = canonicalize(
            question="What does the operator see, really?",
            reason_for_asking="Need info.",
            requested_human_capability="provide_habitat_information",
            urgency="medium",
            question_id="q-new",
            asking_agent_id=_ADAM,
            related_goal_id=_GOAL,
            pair_id=_PAIR,
        )
        assert h1 != h2


# ===========================================================================
# GROUP C — authority architecture (AST/import-based, not substring matching)
# ===========================================================================

_WORLD_DIR = Path(__file__).resolve().parent.parent / "backend" / "world"


def _py_modules(root: Path):
    return sorted(root.rglob("*.py"))


def _imports_of(module_path: Path):
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    return names


def _import_from_names(module_path: Path):
    """Return the exact imported names of every ImportFrom node (precise, not
    substring/naive)."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.append(alias.name)
    return names


class TestAuthorityArchitecture:
    def test_backend_world_imports_no_ed25519_private_key(self):
        offenders = []
        for p in _py_modules(_WORLD_DIR):
            # Precise: flag any import FROM wealth of an Ed25519 private-key symbol.
            imported_names = _import_from_names(p)
            if any("Ed25519PrivateKey" in n for n in imported_names):
                offenders.append(str(p))
        assert not offenders, f"backend/world imports Ed25519PrivateKey: {offenders}"

    def test_backend_world_has_no_sign_function(self):
        offenders = []
        for p in _py_modules(_WORLD_DIR):
            src = p.read_text(encoding="utf-8")
            if ".sign(" in src or "def sign(" in src:
                offenders.append(str(p))
        assert not offenders, f"backend/world contains signing code: {offenders}"

    def test_first_pair_runtime_cannot_import_operator_signer(self):
        rt = _WORLD_DIR / "first_pair_runtime.py"
        imports = _imports_of(rt)
        bad = [i for i in imports if "sign" in i.lower() or "authoriz" in i.lower() and "issue" in i.lower()]
        assert not bad, f"runtime imports a signer/issuer: {bad}"

    def test_cognition_model_cannot_import_operator_signer(self):
        cm = _WORLD_DIR / "first_pair_cognition_model.py"
        imports = _imports_of(cm)
        bad = [i for i in imports if "sign" in i.lower()]
        assert not bad, f"cognition model imports a signer: {bad}"


# ===========================================================================
# GROUP E — transaction / receipt contract (future store, RED)
# ===========================================================================


class TestCreationTransactionContract:
    def _create(self):
        return _future_symbol(
            "backend.world.first_pair_persistence", "create_authorized_question"
        )

    def test_same_authorization_succeeds_at_most_once(self, store):
        from backend.world.first_pair_persistence import create_authorized_question

        priv, pub = _gen_test_keypair()
        payload = _canonical_payload(question_id="q-once")
        envelope = _signed_envelope(priv, pub, payload)
        first = _create_authorized(store, envelope, pub)
        assert first.get("ok") is True
        second = _create_authorized(store, envelope, pub)
        assert second.get("ok") is False

    def test_intent_durable_before_canonical_apply(self, store):
        # Verify the receipt protocol lays down intent and applied markers
        # atomically per stage, and a successful create leaves both + the question.
        from backend.world.first_pair_persistence import (
            create_authorized_question,
            load_questions,
            _receipt_path,
        )
        from backend.world.local_single_question_create import authorization_id

        priv, pub = _gen_test_keypair()
        payload = _canonical_payload(question_id="q-intent")
        envelope = _signed_envelope(priv, pub, payload)
        auth_id = authorization_id(envelope)
        result = _create_authorized(store, envelope, pub)
        assert result.get("ok") is True
        # Both markers and the question exist after a successful transaction.
        assert _receipt_path(store, auth_id, "intent").exists()
        assert _receipt_path(store, auth_id, "applied").exists()
        assert any(q.question_id == "q-intent" for q in load_questions(store))

    def test_grandfathered_q1_requires_no_receipt(self, store):
        from backend.world.first_pair_persistence import (
            question_requires_creation_receipt,
            _save_questions_raw,
        )

        # Seed a pre-hardening existing question (representing grandfathered q1).
        _save_questions_raw(store, [QuestionRecord(
            question_id="q1-habitat-structure",
            asking_agent_id=_ADAM,
            heartbeat=1,
            question="What is the habitat structure?",
            reason_for_asking="goal",
            related_goal_id=_GOAL,
            requested_human_capability="provide_habitat_information",
            urgency="medium",
            status="answered",
        )])
        # An existing id never requires a creation receipt.
        assert question_requires_creation_receipt(store, "q1-habitat-structure") is False


# ===========================================================================
# GROUP A — current ungoverned creation (proves current behavior)
# ===========================================================================


class TestCurrentUngovernedCreation:
    """GREEN regression: the future contract now HOLDS for the previously-weak routes.

    These were bug-proof RED tests during the RED phase. They are now converted
    to regression assertions for the APPROVED future contract: raw save rejects
    new IDs and deletions, and ask_human/questions_raised produce noncanonical
    proposals rather than canonical/runtime persistent question state.
    """

    def test_raw_save_questions_rejects_new_id_without_authority(self, store):
        q = _q(question_id="q-unauthorized")
        with pytest.raises(ValueError):
            save_questions(store, [q])  # must now fail closed
        loaded = load_questions(store)
        assert not any(x.question_id == "q-unauthorized" for x in loaded)

    def test_raw_save_questions_rejects_deletion(self, store):
        seed = _q(question_id="q-keep")
        # Seed directly via the private raw primitive (test fixture only).
        from backend.world.first_pair_persistence import _save_questions_raw

        _save_questions_raw(store, [seed])
        # Attempt to overwrite the list dropping q-keep -> must be rejected.
        with pytest.raises(ValueError):
            save_questions(store, [_q(question_id="q-other")])
        loaded = load_questions(store)
        assert any(x.question_id == "q-keep" for x in loaded)

    def test_execute_ask_human_produces_noncanonical_proposal(self):
        from backend.world.first_pair_runtime import FirstPairRuntime

        rt = FirstPairRuntime(heartbeat_limit=1, store=FirstPairPersistenceStore(_SCRATCH))
        rt._load_or_initialize()
        outcome = rt._execute_ask_human(
            "east_adam",
            {
                "question_id": "q-ask",
                "question": "What is the habitat?",
                "reason_for_asking": "need info",
                "requested_human_capability": "provide_habitat_information",
                "urgency": "medium",
            },
            0,
        )
        assert outcome.get("status") == "proposed"
        # Noncanonical: NOT present in canonical self._questions.
        assert not any(q.question_id == "q-ask" for q in rt._questions)
        # It IS recorded as a noncanonical proposal.
        assert any(p.question_id == "q-ask" for p in rt._question_proposals)

    def test_questions_raised_produces_noncanonical_proposal(self):
        from backend.world.first_pair_runtime import FirstPairRuntime
        from backend.world.first_pair_cognition_interface import CognitionOutput

        rt = FirstPairRuntime(heartbeat_limit=1, store=FirstPairPersistenceStore(_SCRATCH))
        rt._load_or_initialize()

        output = CognitionOutput(
            action=None,
            memory_write=[],
            goal_updates=[],
            questions_raised=[
                {
                    "question_id": "q-raised",
                    "question": "What is the habitat?",
                    "reason_for_asking": "need info",
                    "related_goal_id": _GOAL,
                    "requested_human_capability": "provide_habitat_information",
                    "urgency": "medium",
                }
            ],
            internal_reasoning="",
            confidence=0.0,
            observation_summary="",
            decision_summary="",
            uncertainty="",
        )
        rt._apply_cognition_output("east_adam", output, 0)

        # Noncanonical: NOT present in canonical self._questions.
        assert not any(q.question_id == "q-raised" for q in rt._questions)
        assert any(p.question_id == "q-raised" for p in rt._question_proposals)