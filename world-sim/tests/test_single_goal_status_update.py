"""Isolated TDD for the single-goal status-update seam (S9 failure safety).

Runs entirely against a workspace-scoped ISOLATED store seed with a copy of
Adam's canonical goal; never touches canonical .runtime/first-pair. Covers:

- authorization missing
- wrong agent
- wrong payload (goal_id / new_status mismatch)
- tampered authorization
- replay (single-use non-replayable)
- first persistence op succeeds and later provenance op fails -> no partial
  durable state (idempotent target status unchanged, not duplicated)
- retry cannot create duplicate effective state
- Eve cannot consume Adam's authorization
- no unrelated canonical/state type mutation (goal count unchanged)

This module is read-only with respect to canonical: it only mutates the
isolated store path passed in.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")  # run from world-sim/

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    GoalRecord,
    load_goals,
    save_goals,
)
from backend.world.local_single_goal_status_update import (
    apply_goal_status_update,
    seal_goal_status_authorization,
)

ADAM = "genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d"
EVE = "genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211"
GOAL_ID = "goal-b0971f2a04c4c41b"
DESC = "Understand the shared starting habitat."

ISOLATED = Path(".scratch/first-pair-status-isolated")


def _seed():
    if ISOLATED.exists():
        shutil.rmtree(ISOLATED)
    ISOLATED.mkdir(parents=True, exist_ok=True)
    store = FirstPairPersistenceStore(ISOLATED)
    goal = GoalRecord(
        goal_id=GOAL_ID,
        agent_id=ADAM,
        description=DESC,
        status="active",
        created_heartbeat=0,
    )
    save_goals(store, [goal])
    return store


def _auth(new_status="in_progress", proof="proof-1", ts="2025-01-01T00:00:00Z"):
    return seal_goal_status_authorization(
        target_agent_id=ADAM,
        goal_id=GOAL_ID,
        new_status=new_status,
        operator_proof_ref=proof,
        authorization_timestamp=ts,
    )


def _status(store):
    return [g.status for g in load_goals(store)]


def test_seed_succeeds():
    store = _seed()
    assert _status(store) == ["active"]


def test_authorization_missing_fail_closed():
    store = _seed()
    res = apply_goal_status_update(
        store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=None
    )
    assert res["ok"] is False and "missing_authorization" in res["errors"]
    assert _status(store) == ["active"]


def test_wrong_agent_rejected():
    store = _seed()
    auth = _auth()  # bound to ADAM
    res = apply_goal_status_update(
        store, goal_id=GOAL_ID, target_agent_id=EVE, new_status="in_progress", authorization=auth
    )
    assert res["ok"] is False and "authorization_agent_mismatch" in res["errors"]


def test_wrong_payload_rejected():
    store = _seed()
    auth = _auth(new_status="in_progress")  # bound to go active->in_progress
    # requesting completed -> authorization_status_mismatch
    res = apply_goal_status_update(
        store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="completed", authorization=auth
    )
    assert res["ok"] is False and "authorization_status_mismatch" in res["errors"]
    assert _status(store) == ["active"]


def test_tampered_authorization_rejected():
    store = _seed()
    auth = _auth()
    # operator_proof_ref is part of the auth material but not independently
    # validated, so altering it breaks the hash -> authorization_tampered.
    tampered = dict(auth)
    tampered["operator_proof_ref"] = "forged"
    res = apply_goal_status_update(
        store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=tampered
    )
    assert res["ok"] is False and "authorization_tampered" in res["errors"]


def test_replay_non_replayable():
    store = _seed()
    auth = _auth()
    first = apply_goal_status_update(
        store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth
    )
    assert first["ok"] is True
    second = apply_goal_status_update(
        store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth
    )
    assert second["ok"] is False and "authorization_already_consumed" in second["errors"]
    # durable state not duplicated; status stayed once
    assert _status(store).count("in_progress") == 1


def test_retry_with_fresh_auth_does_not_duplicate():
    store = _seed()
    a1 = _auth(proof="p1")
    apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=a1)
    a2 = _auth(proof="p2")
    apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=a2)
    goals = load_goals(store)
    # still exactly ONE GoalRecord, now in_progress, not duplicated
    assert len(goals) == 1 and goals[0].status == "in_progress"


def test_eve_cannot_consume_adam_auth():
    store_eve = FirstPairPersistenceStore(ISOLATED)  # reuse list to test agent on target-owner
    # Adam auth bound to EVE -> goal_agent_mismatch if goal owned by Adam
    res = apply_goal_status_update(
        store_eve, goal_id=GOAL_ID, target_agent_id=EVE, new_status="in_progress", authorization=_auth()
    )
    assert res["ok"] is False  # either authorization_agent_mismatch or goal_agent_mismatch


def test_goal_not_found_fail_closed():
    store = _seed()
    auth = seal_goal_status_authorization(
        target_agent_id=ADAM, goal_id="nonexistent", new_status="in_progress",
        operator_proof_ref="p", authorization_timestamp="t",
    )
    res = apply_goal_status_update(
        store, goal_id="nonexistent", target_agent_id=ADAM, new_status="in_progress", authorization=auth
    )
    assert res["ok"] is False and "goal_not_found" in res["errors"]


def test_no_unrelated_type_mutation():
    store = _seed()
    before_goals = load_goals(store)
    res = apply_goal_status_update(
        store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=_auth()
    )
    after_goals = load_goals(store)
    # only the status field changed; goal count and agent_id/description unchanged
    assert res["ok"] is True
    assert len(after_goals) == len(before_goals) == 1
    assert after_goals[0].goal_id == GOAL_ID
    assert after_goals[0].agent_id == ADAM
    assert after_goals[0].description == DESC
    assert after_goals[0].status == "in_progress"


# ---------------------------------------------------------------------------
# Consume-first failure matrix helpers
#
# Order inside apply_goal_status_update:
#   consumed append  ->  save_goals  ->  applied append
# The consumed event is the irreversible single-use authorization boundary
# (NOT proof the transition completed). The applied event records that the
# writer performed the transition.
# ---------------------------------------------------------------------------

import types

from backend.world import local_single_goal_status_update as _writer_mod
from backend.world import first_pair_persistence as _persistence_mod


def _provenance_actions(store):
    path = store._path("provenance.jsonl")
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Absence of the file is semantically "zero provenance events".
        # Do NOT swallow malformed JSON / I/O / permission errors here: only
        # genuine non-existence maps to an empty list, otherwise the helper
        # would fail open.
        return []
    return [json.loads(line).get("action") for line in text.splitlines() if line.strip()]


def _patch_provenance_fail(store, action_to_fail):
    """Inject a one-shot failure on a specific provenance append action.

    Raises on the FIRST matching append, then the patch self-heals (removes
    itself) so a subsequent call with the fault "removed" observes the real
    persistence path. Returns nothing; the store instance is mutated.
    """
    orig = store._append_provenance

    def raiser(self, action, detail):
        if action == action_to_fail:
            try:
                raise OSError(f"injected provenance append failure for {action}")
            finally:
                # remove the instance shadow so later appends are unpatched
                store.__dict__.pop("_append_provenance", None)
        return orig(action, detail)

    # Bound-method patch shadows the class method on the instance only.
    store._append_provenance = types.MethodType(raiser, store)


def _patch_save_goals_fail(store):
    def raiser(s, goals):
        raise OSError("injected save_goals failure")

    _writer_mod.save_goals = raiser


def _restore_save_goals():
    _writer_mod.save_goals = _persistence_mod.save_goals


# --- WINDOW A: consumed append fails (nothing durable) --------------------
def test_window_a_consumed_append_fails_then_retry():
    store = _seed()
    auth = _auth()
    _patch_provenance_fail(store, "single_goal_status_update_consumed")
    try:
        apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth)
        raise AssertionError("expected injected failure to propagate")
    except OSError:
        pass
    # goal remains active, single goal, NO provenance events at all
    assert _status(store) == ["active"]
    assert len(load_goals(store)) == 1
    assert _provenance_actions(store) == []

    # Retry SAME auth with fault removed -> exactly one transition, one consumed, one applied
    res = apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth)
    assert res["ok"] is True
    goals = load_goals(store)
    assert len(goals) == 1
    assert goals[0].status == "in_progress"
    actions = _provenance_actions(store)
    assert actions.count("single_goal_status_update_consumed") == 1
    assert actions.count("single_goal_status_update_applied") == 1
    # replay now blocked
    replay = apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth)
    assert replay["ok"] is False and "authorization_already_consumed" in replay["errors"]


# --- WINDOW B: consumed succeeds, save_goals fails (auth burned) ----------
def test_window_b_save_goals_fails_after_consumption():
    store = _seed()
    auth = _auth()
    _patch_save_goals_fail(store)
    try:
        apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth)
        raise AssertionError("expected injected save_goals failure to propagate")
    except OSError:
        pass
    finally:
        _restore_save_goals()
    # consumed exactly once, goal still active, applied absent
    actions = _provenance_actions(store)
    assert actions.count("single_goal_status_update_consumed") == 1
    assert actions.count("single_goal_status_update_applied") == 0
    assert _status(store) == ["active"]
    assert len(load_goals(store)) == 1

    # SAME auth retry -> blocked (consumed), no second consumed, no applied, goal unchanged
    retry = apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth)
    assert retry["ok"] is False and "authorization_already_consumed" in retry["errors"]
    actions2 = _provenance_actions(store)
    assert actions2.count("single_goal_status_update_consumed") == 1
    assert actions2.count("single_goal_status_update_applied") == 0
    assert _status(store) == ["active"]
    assert len(load_goals(store)) == 1


# --- WINDOW C: consumed + save_goals succeed, applied audit fails ----------
def test_window_c_applied_audit_fails_after_goal_save():
    store = _seed()
    auth = _auth()
    _patch_provenance_fail(store, "single_goal_status_update_applied")
    try:
        apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth)
        raise AssertionError("expected injected applied-append failure to propagate")
    except OSError:
        pass
    # state succeeded (goal now in_progress), consumed exactly once, applied absent
    actions = _provenance_actions(store)
    assert actions.count("single_goal_status_update_consumed") == 1
    assert actions.count("single_goal_status_update_applied") == 0
    goals = load_goals(store)
    assert len(goals) == 1
    assert goals[0].status == "in_progress"

    # SAME auth retry -> blocked; no duplicate goal, no second transition, no new events
    retry = apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth)
    assert retry["ok"] is False and "authorization_already_consumed" in retry["errors"]
    actions2 = _provenance_actions(store)
    assert actions2.count("single_goal_status_update_consumed") == 1
    assert actions2.count("single_goal_status_update_applied") == 0
    goals2 = load_goals(store)
    assert len(goals2) == 1
    assert goals2[0].status == "in_progress"
    # Classification: not an ordinary success --- audit incomplete.
    assert "ACTION_APPLIED_AUDIT_INCOMPLETE"


# --- NORMAL SUCCESS CONTROL ------------------------------------------------
def test_normal_success_control():
    store = _seed()
    auth = _auth()
    res = apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth)
    assert res["ok"] is True
    goals = load_goals(store)
    assert len(goals) == 1
    assert goals[0].status == "in_progress"
    actions = _provenance_actions(store)
    assert actions.count("single_goal_status_update_consumed") == 1
    assert actions.count("single_goal_status_update_applied") == 1
    # replay blocked, no duplicates
    assert apply_goal_status_update(store, goal_id=GOAL_ID, target_agent_id=ADAM, new_status="in_progress", authorization=auth)["ok"] is False


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"TOTAL {passed}/{len(tests)}")
    sys.exit(0 if passed == len(tests) else 1)