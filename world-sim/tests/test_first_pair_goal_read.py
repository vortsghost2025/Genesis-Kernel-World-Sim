"""Smallest safe First-Pair goal-read seam - focused tests (TDD).

Batch reads one explicit agent's ACTIVE goals only, via the authoritative
FirstPairPersistenceStore, deterministically ordered and fail-closed on
malformed records. Zero writes, no movement, no memory/relationship/provialder
mutation. Tests use isolated scratch persistence; never the canonical .runtime.
"""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    GoalRecord,
    load_goals,
    save_goals,
)
from backend.world.local_first_pair_goal_read import read_active_goals_for_agent

ADAM = "genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d"
EVE = "genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211"

_SCRATCH = Path(__file__).resolve().parent.parent / ".goal-read-scratch"


@pytest.fixture()
def store():
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    s = FirstPairPersistenceStore(Path(_SCRATCH))
    s.root.mkdir(parents=True, exist_ok=True)
    yield s
    shutil.rmtree(_SCRATCH, ignore_errors=True)


def test_read_adam_active_goal(store):
    save_goals(store, [
        GoalRecord(goal_id="goal-111", agent_id=ADAM, description="Understand the shared starting habitat.", status="active", created_heartbeat=0),
    ])
    res = read_active_goals_for_agent(store, ADAM)
    assert res["ok"] is True
    assert res["agent_id"] == ADAM
    assert res["active_goal_count"] == 1
    assert len(res["active_goals"]) == 1
    g = res["active_goals"][0]
    assert g["goal_id"] == "goal-111"
    assert g["description"] == "Understand the shared starting habitat."
    assert g["status"] == "active"
    assert g["created_heartbeat"] == 0
    assert g["related_question_id"] is None
    assert g["metadata"] == {}


def test_agent_identity_isolation(store):
    save_goals(store, [
        GoalRecord(goal_id="goal-adam", agent_id=ADAM, description="Adam goal", status="active", created_heartbeat=0),
        GoalRecord(goal_id="goal-eve", agent_id=EVE, description="Eve goal", status="active", created_heartbeat=0),
    ])
    a = read_active_goals_for_agent(store, ADAM)
    e = read_active_goals_for_agent(store, EVE)
    assert a["active_goal_count"] == 1
    assert a["active_goals"][0]["goal_id"] == "goal-adam"
    assert e["active_goal_count"] == 1
    assert e["active_goals"][0]["goal_id"] == "goal-eve"


def test_non_active_goals_excluded(store):
    save_goals(store, [
        GoalRecord(goal_id="goal-active", agent_id=ADAM, description="A", status="active", created_heartbeat=0),
        GoalRecord(goal_id="goal-done", agent_id=ADAM, description="B", status="completed", created_heartbeat=0),
        GoalRecord(goal_id="goal-abandoned", agent_id=ADAM, description="C", status="abandoned", created_heartbeat=0),
        GoalRecord(goal_id="goal-progress", agent_id=ADAM, description="D", status="in_progress", created_heartbeat=0),
    ])
    res = read_active_goals_for_agent(store, ADAM)
    ids = [g["goal_id"] for g in res["active_goals"]]
    assert ids == ["goal-active"]
    assert res["active_goal_count"] == 1


def test_deterministic_ordering(store):
    save_goals(store, [
        GoalRecord(goal_id="goal-c", agent_id=ADAM, description="C", status="active", created_heartbeat=0),
        GoalRecord(goal_id="goal-a", agent_id=ADAM, description="A", status="active", created_heartbeat=0),
        GoalRecord(goal_id="goal-b", agent_id=ADAM, description="B", status="active", created_heartbeat=0),
    ])
    r1 = read_active_goals_for_agent(store, ADAM)
    r2 = read_active_goals_for_agent(store, ADAM)
    ids1 = [g["goal_id"] for g in r1["active_goals"]]
    ids2 = [g["goal_id"] for g in r2["active_goals"]]
    assert ids1 == sorted(ids1) == ["goal-a", "goal-b", "goal-c"]
    assert ids2 == ids1


def test_fail_closed_on_malformed_record(store):
    # hand-write a goals.json with one record missing required fields
    import json
    data = {
        "type": "goals_record",
        "schema_version": "10FM.1",
        "data": [{"goal_id": "goal-bad", "agent_id": ADAM, "status": "active"}],  # missing description + created_heartbeat
    }
    store._atomic_write(store._path("goals.json"), data)
    # the authoritative load_goals would raise here; the seam must turn it into
    # a fail-closed result, not a crash, and return NO partial goals.
    res = read_active_goals_for_agent(store, ADAM)
    assert res["ok"] is False
    assert res["active_goal_count"] == 0
    assert res["active_goals"] == []
    assert any("malformed" in e or "invalid" in e or "not_a_goal" in e for e in res["errors"])


def test_fail_closed_on_unsafe_goal_id(store):
    # write a valid-enough record through raw json with a non-safe goal_id
    import json
    data = {
        "type": "goals_record",
        "schema_version": "10FM.1",
        "data": [{"goal_id": "../bad/field", "agent_id": ADAM, "description": "x", "status": "active", "created_heartbeat": 0}],
    }
    store._atomic_write(store._path("goals.json"), data)
    res = read_active_goals_for_agent(store, ADAM)
    assert res["ok"] is False
    assert any("unsafe" in e or "malformed" in e for e in res["errors"])


def test_zero_writes(store):
    save_goals(store, [GoalRecord(goal_id="goal-1", agent_id=ADAM, description="x", status="active", created_heartbeat=0)])
    before_files = sorted(p.name for p in store.root.rglob("*") if p.is_file())
    import hashlib
    before_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in store.root.rglob("*") if p.is_file()
    }
    res = read_active_goals_for_agent(store, ADAM)
    assert res["ok"] is True
    after_files = sorted(p.name for p in store.root.rglob("*") if p.is_file())
    after_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in store.root.rglob("*") if p.is_file()
    }
    assert before_files == after_files
    assert before_hashes == after_hashes


def test_no_provider_import_for_read(store):
    # the seam must not depend on any provider/model/network module
    src = Path(__file__).resolve().parent.parent / "backend" / "world" / "local_first_pair_goal_read.py"
    text = src.read_text(encoding="utf-8")
    for bad in ("openai", "requests", "socket", "http", "resolve_provider"):
        assert bad not in text, f"goal-read seam must not import provider/network: {bad}"
    save_goals(store, [GoalRecord(goal_id="goal-1", agent_id=ADAM, description="x", status="active", created_heartbeat=0)])
    res = read_active_goals_for_agent(store, ADAM)
    assert res["ok"] is True