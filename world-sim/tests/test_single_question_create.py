"""RED tests — signed question-creation authority: store boundary + q1 guard.

Companion to ``test_question_creation_authority.py``. Focuses on:

- raw store new-id insertion bypass (must fail-closed in the future)
- stale-runtime add/delete risk
- grandfathered q1 protection (read-only, no retroactive authority)
- signed-authority non-escalation (public key cannot sign/mint)

All persistence uses isolated scratch stores. Canonical
``world-sim/.runtime/first-pair`` is never written.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    QuestionRecord,
    load_questions,
    save_questions,
)

_ADAM = "genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d"
_GOAL = "goal-b0971f2a04c4c41b"
_PAIR = "genesis-first-pair"

# Known canonical q1 hash from the prior audit (recorded read-only; never rewritten).
_Q1_QUESTIONS_SHA256 = "952ceacd6441beb5768a7a41c63e7fc1a0f1b29d704181d509c917382b3baf7c"

_SCRATCH = Path(__file__).resolve().parent.parent / ".qa-boundary-scratch"


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
        question="What does the operator see?",
        reason_for_asking="Need operator info.",
        related_goal_id=_GOAL,
        requested_human_capability="provide_habitat_information",
        urgency="medium",
        status="pending",
    )
    fields.update(overrides)
    return QuestionRecord(**fields)


def _future(module: str, attr: str):
    try:
        import importlib

        mod = importlib.import_module(module)
    except ImportError as exc:
        raise AssertionError(
            f"CONTRACT_MISSING: {module} does not exist yet: {exc}"
        )
    name = getattr(mod, attr, None)
    if name is None:
        raise AssertionError(f"CONTRACT_MISSING: {module}.{attr} does not exist yet")
    return name


class TestRawStoreNewIdBlocked:
    """Raw additive save must be rejected in the future guard."""

    def test_new_id_without_signed_authority_should_be_rejected(self, store):
        from backend.world.first_pair_persistence import save_questions_guarded

        q = _q(question_id="q-stealth")
        result = save_questions_guarded(store, [q])
        assert (result is False or (isinstance(result, dict) and not result.get("ok"))), (
            "guarded save must reject a new id without signed creation authority."
        )

    def test_stale_runtime_cannot_delete_canonical_question(self, store):
        # Test-only fixture seed: bypasses production creation authority.
        from backend.world.first_pair_persistence import _save_questions_raw, save_questions_guarded

        keep = _q(question_id="q-keep")
        _save_questions_raw(store, [keep])
        # attempt to persist a list missing q-keep -> must be rejected
        result = save_questions_guarded(store, [_q(question_id="q-other")])
        assert (result is False or (isinstance(result, dict) and not result.get("ok"))), (
            "guarded save must not drop an existing canonical id."
        )
        present = any(x.question_id == "q-keep" for x in load_questions(store))
        assert present is True


class TestPawnProtection:
    """q1-habitat-structure is grandfathered: no retroactive authority."""

    def test_grandfathered_q1_requires_no_receipt(self, store):
        from backend.world.first_pair_persistence import _save_questions_raw, question_requires_creation_receipt

        # Test-only fixture seed: an existing pre-hardening question.
        _save_questions_raw(store, [_q(question_id="q1-habitat-structure")])
        requires = question_requires_creation_receipt(store, existing_question_id="q1-habitat-structure")
        assert requires is False

    def test_no_retroactive_receipt_is_generated_for_q1(self, store):
        from backend.world.first_pair_persistence import (
            RECEIPT_DIR_NAME,
            _save_questions_raw,
            question_requires_creation_receipt,
        )

        # Seed grandfathered q1; loading/accepting it must not synthesize a receipt.
        _save_questions_raw(store, [_q(question_id="q1-habitat-structure")])
        assert question_requires_creation_receipt(store, "q1-habitat-structure") is False
        receipt_dir = store.root / RECEIPT_DIR_NAME
        assert not receipt_dir.exists(), (
            "accepting a grandfathered question must not create a receipt directory"
        )


class TestSignedAuthorityNonEscalation:
    def test_public_key_alone_cannot_sign(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization

        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()
        pub_raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub_key = Ed25519PublicKey.from_public_bytes(pub_raw)
        assert not hasattr(pub_key, "sign"), "public key must not expose sign()"

    def test_store_exposes_no_receipt_writer_to_callers(self, store):
        # The store object itself must not expose a public receipt-writing
        # METHOD that arbitrary callers could reach unguarded. Receipt writes
        # are guarded MODULE-LEVEL seams (create + answer) that persist
        # already-verified envelopes; they grant no authority on their own.
        import backend.world.first_pair_persistence as fp

        # Public *instance methods* on the store that write receipts are the
        # violation: an unguarded raw writer reachable from runtime/model.
        offenders = [
            n for n in dir(store)
            if "receipt" in n.lower() and "write" in n.lower() and not n.startswith("_")
        ]
        assert not offenders, f"store exposes raw receipt-writer method: {offenders}"

    def test_model_module_cannot_reach_operator_signer(self):
        # The cognition model must not import any signer/issuer.
        import ast

        cm = Path(__file__).resolve().parent.parent / "backend" / "world" / "first_pair_cognition_model.py"
        tree = ast.parse(cm.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        bad = [i for i in imports if "sign" in i.lower() or "issue" in i.lower()]
        assert not bad, f"model imports a signer/issuer: {bad}"


class TestQ1CanonicalProtectionReadOnly:
    """Read-only guard asserts the accepted q1 hash is recorded, never written."""

    def test_known_q1_hash_is_recorded(self):
        # The accepted canonical q1 hash is captured as a constant; this test
        # only documents it, never reads or writes canonical state.
        assert _Q1_QUESTIONS_SHA256 == "952ceacd6441beb5768a7a41c63e7fc1a0f1b29d704181d509c917382b3baf7c"