"""Bounded single-goal First-Pair write path - grounded-authorization tests.

The runtime consumer must NOT accept a caller boolean. It consumes a grounded,
single-use operator authorization artifact bound to the exact action
(operator, target agent, pair, goal text, status, heartbeat, max_writes=1).
Tests use isolated temporary persistence; never the canonical .runtime.
"""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    GoalRecord,
    load_goals,
)
from backend.world.local_first_pair_birth_candidate import (
    create_first_pair_birth_candidate,
)
import backend.world.local_single_goal_write as sgw

ADAM = "691e3c72e1318e7724c2625c03b7b7c2b04ede5f4da9eca9c252732d631238aa"
EVE = "3df3c9d905d99a7bc930ad1c61dcab27364d24e581f70a7603da5a9f8a1bef3c"
ABSENT = "21272020352a0788dc7aae39f098d8a3b9fb1388a8998d05d1038c1a4498d6c7"
RID = "genesis.first_pair.absent_state.tick0.20260824"
HID = "genesis-first-habitat"
OP_REF = "8dc714f3a66975eb2543ca780f59e35d9af02e93"
TS = "2026-08-24T03:51:00Z"


def _canonical_birth_candidate() -> dict:
    declaration = {
        "identity_schema_version": "first_pair_identity.1",
        "id_derivation_version": "sha256-full-v1",
        "pair_id": "genesis-first-pair",
        "adam_identity": {
            "canonical_name": "Adam",
            "canonical_agent_ref": "east_adam",
            "founding_role": "founding_agent",
            "provenance_commitment": ADAM,
        },
        "eve_identity": {
            "canonical_name": "Eve",
            "canonical_agent_ref": "east_eve",
            "founding_role": "founding_agent",
            "provenance_commitment": EVE,
        },
        "habitat": {
            "habitat_schema_version": "first_habitat.1",
            "habitat_id": HID,
            "allowed_tile_ids": ["public-start-adam", "public-start-eve"],
            "starting_tile_ids": {
                "east_adam": "public-start-adam",
                "east_eve": "public-start-eve",
            },
            "observation_boundaries": {
                "east_adam": ["public-start-adam"],
                "east_eve": ["public-start-eve"],
            },
            "movement_allowed": False,
        },
        "rollback_anchor": {
            "rollback_anchor_schema_version": "first_rollback_anchor.1",
            "rollback_anchor_id": RID,
            "habitat_id": HID,
            "claim_scope": "operator_proof",
            "state_commitment": ABSENT,
        },
    }
    cand = create_first_pair_birth_candidate(declaration)
    assert cand["ok"] is True
    return cand


def _seal_with(**kwargs):
    inputs = dict(
        target_agent_id="genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d",
        pair_id="genesis-first-pair",
        goal_description="Understand the shared starting habitat.",
        goal_status="active",
        created_heartbeat=0,
        operator_proof_ref=OP_REF,
        authorization_timestamp=TS,
    )
    inputs.update(kwargs)
    return sgw.seal_authorization(**inputs), inputs


_SCRATCH = Path(__file__).resolve().parent.parent / ".single-goal-auth-scratch"


@pytest.fixture()
def scratch_store():
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    store = FirstPairPersistenceStore(Path(_SCRATCH))
    store.root.mkdir(parents=True, exist_ok=True)
    yield store
    shutil.rmtree(_SCRATCH, ignore_errors=True)


_cand = _canonical_birth_candidate()
_ADAM = _cand["adam_identity"]["agent_id"]
_EVE = _cand["eve_identity"]["agent_id"]


def _valid_auth(agent_id=None, description=None):
    return _seal_with(
        target_agent_id=agent_id or _ADAM,
        goal_description=description or "Understand the shared starting habitat.",
    )[0]


# ---- deny matrix ----

def test_no_authorization_denied(scratch_store):
    res = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, target_agent_id=_ADAM,
        authorization=None, goal_description="x",
    )
    assert res["ok"] is False
    assert "missing_authorization" in res["errors"]


def test_malformed_authorization_denied(scratch_store):
    auth = {"bad": "shape"}
    res = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, target_agent_id=_ADAM,
        authorization=auth, goal_description="Understand the shared starting habitat.",
    )
    assert res["ok"] is False
    assert "invalid_authorization" in res["errors"]


def test_authorization_id_mismatch_denied(scratch_store):
    auth, _ = _seal_with(**{"target_agent_id": _ADAM})
    # tamper authorization_id
    auth = dict(auth)
    auth["authorization_id"] = "auth-" + "a" * 16
    res = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, target_agent_id=_ADAM,
        authorization=auth, goal_description="Understand the shared starting habitat.",
    )
    assert res["ok"] is False
    assert "authorization_tampered" in res["errors"]


def test_wrong_target_agent_denied(scratch_store):
    auth, base = _seal_with(**{"target_agent_id": _ADAM})
    # pass auth bound to Adam but goal_for says Eve -> mismatch
    res = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, authorization=auth,
        target_agent_id=_EVE, goal_description=base["goal_description"],
    )
    assert res["ok"] is False
    assert "authorization_agent_mismatch" in res["errors"]


def test_wrong_goal_text_denied(scratch_store):
    auth, base = _seal_with(**{"target_agent_id": _ADAM})
    res = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, authorization=auth,
        target_agent_id=_ADAM, goal_description="A completely different goal.",
    )
    assert res["ok"] is False
    assert "authorization_goal_mismatch" in res["errors"]


def test_wrong_pair_denied(scratch_store):
    auth, base = _seal_with(**{"target_agent_id": _ADAM, "pair_id": "genesis-other"})
    res = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, authorization=auth,
        target_agent_id=_ADAM, goal_description=base["goal_description"], pair_id="genesis-other",
    )
    assert res["ok"] is False
    assert "invalid_birth_candidate" in res["errors"] or "pair_mismatch" in res["errors"]


def test_cross_agent_auth_not_reusable(scratch_store):
    # auth bound to Adam must NOT authorize Eve even via different call
    auth, base = _seal_with(**{"target_agent_id": _ADAM})
    r = sgw.write_single_goal(scratch_store, birth_candidate=_cand, authorization=auth, target_agent_id=_ADAM, goal_description=base["goal_description"])
    assert r["ok"] is True
    # Eve cannot reuse Adam's auth
    r2 = sgw.write_single_goal(scratch_store, birth_candidate=_cand, authorization=auth, target_agent_id=_EVE, goal_description=base["goal_description"])
    assert r2["ok"] is False
    assert "authorization_agent_mismatch" in r2["errors"]


def test_reused_authorization_denied(scratch_store):
    auth = _valid_auth(_ADAM)
    r1 = sgw.write_single_goal(scratch_store, birth_candidate=_cand, authorization=auth,
                               target_agent_id=_ADAM, goal_description="Understand the shared starting habitat.")
    assert r1["ok"] is True
    r2 = sgw.write_single_goal(scratch_store, birth_candidate=_cand, authorization=auth,
                               target_agent_id=_ADAM, goal_description="Understand the shared starting habitat.")
    assert r2["ok"] is False
    assert "authorization_already_consumed" in r2["errors"]
    assert len(load_goals(scratch_store)) == 1


# ---- positive + isolation ----

def test_correct_authorization_exactly_one_goal(scratch_store):
    auth = _valid_auth(_ADAM)
    res = sgw.write_single_goal(scratch_store, birth_candidate=_cand, authorization=auth,
                                target_agent_id=_ADAM, goal_description="Understand the shared starting habitat.")
    assert res["ok"] is True
    goals = load_goals(scratch_store)
    assert len(goals) == 1
    assert goals[0].agent_id == _ADAM
    assert goals[0].status == "active"
    assert res["goals_written"] == 1


def test_works_for_eve_with_its_own_auth(scratch_store):
    auth = _valid_auth(_EVE)
    res = sgw.write_single_goal(scratch_store, birth_candidate=_cand, authorization=auth,
                                target_agent_id=_EVE, goal_description="Understand the shared starting habitat.")
    assert res["ok"] is True
    goals = load_goals(scratch_store)
    assert len(goals) == 1
    assert goals[0].agent_id == _EVE


def test_no_unrelated_writes(scratch_store):
    auth = _valid_auth(_ADAM)
    res = sgw.write_single_goal(scratch_store, birth_candidate=_cand, authorization=auth,
                                target_agent_id=_ADAM, goal_description="Understand the shared starting habitat.")
    assert res["ok"] is True
    names = {p.name for p in scratch_store.root.iterdir()}
    assert {"goals.json"} <= names
    assert "memory.json" not in names
    assert "world_state.json" not in names
    assert "relationship_ledger.json" not in names
    assert res["memory_written"] is False
    assert res["world_state_mutated"] is False
    assert res["relationship_changed"] is False
    assert res["movement_performed"] is False


# ---- partial-failure / replay safety ----
# A realized provenance append failure AFTER a successful goal persistence must
# not allow a retry with the SAME authorization to create a second GoalRecord.

def test_replay_after_first_provenance_append_fails_creates_no_second_goal(
    scratch_store, monkeypatch
):
    _GOAL = "Understand the shared starting habitat."
    auth = _valid_auth(_ADAM)

    original_append = scratch_store._append_provenance

    counter = {"n": 0}

    def wrapper(action, detail=None):
        counter["n"] += 1
        if counter["n"] == 1:
            raise OSError("simulated provenance append failure")
        return original_append(action, detail)

    monkeypatch.setattr(scratch_store, "_append_provenance", wrapper)

    with pytest.raises(OSError):
        sgw.write_single_goal(
            scratch_store, birth_candidate=_cand, target_agent_id=_ADAM,
            goal_description=_GOAL, authorization=auth,
        )

    # Goal was persisted (save_goals ran before the append), but NO authorization
    # consumption marker was recorded.
    assert len(load_goals(scratch_store)) == 1

    monkeypatch.undo()  # restore the healthy provenance append

    # Retry with the SAME authorization must NOT create a second GoalRecord.
    res2 = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, target_agent_id=_ADAM,
        goal_description=_GOAL, authorization=auth,
    )
    assert res2["ok"] is False
    assert "duplicate_goal" in res2["errors"]
    assert len(load_goals(scratch_store)) == 1


def test_replay_after_consumed_marker_append_fails_creates_no_second_goal(
    scratch_store, monkeypatch
):
    _GOAL = "Understand the shared starting habitat."
    auth = _valid_auth(_ADAM)

    original_append = scratch_store._append_provenance
    counter = {"n": 0}

    def wrapper(action, detail=None):
        counter["n"] += 1
        if counter["n"] == 2:  # fail on the consumed-marker append
            raise OSError("simulated consumed-marker append failure")
        return original_append(action, detail)

    monkeypatch.setattr(scratch_store, "_append_provenance", wrapper)

    with pytest.raises(OSError):
        sgw.write_single_goal(
            scratch_store, birth_candidate=_cand, target_agent_id=_ADAM,
            goal_description=_GOAL, authorization=auth,
        )

    # Goal persisted, single_goal_created recorded, but consumed marker missing.
    assert len(load_goals(scratch_store)) == 1

    monkeypatch.undo()

    res2 = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, target_agent_id=_ADAM,
        goal_description=_GOAL, authorization=auth,
    )
    assert res2["ok"] is False
    assert "duplicate_goal" in res2["errors"]
    assert len(load_goals(scratch_store)) == 1

    # And the same authorization is not usable for a DIFFERENT goal or agent.
    r_diff_goal = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, target_agent_id=_ADAM,
        goal_description="A different goal text.", authorization=auth,
    )
    assert r_diff_goal["ok"] is False
    assert "authorization_goal_mismatch" in r_diff_goal["errors"]
    r_diff_agent = sgw.write_single_goal(
        scratch_store, birth_candidate=_cand, target_agent_id=_EVE,
        goal_description=_GOAL, authorization=auth,
    )
    assert r_diff_agent["ok"] is False
    assert "authorization_agent_mismatch" in r_diff_agent["errors"]
    assert len(load_goals(scratch_store)) == 1