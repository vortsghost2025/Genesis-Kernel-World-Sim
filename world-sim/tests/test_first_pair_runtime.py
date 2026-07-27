"""Phase 10FM — First Pair Runtime focused test suite.

Covers initialisation, identity stability, distinct agents, separate memory
lists, goal/question persistence, heartbeat resume, create_public_object
with rejection cases, world-state durability, and evidence export.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    PublicObjectRecord,
    list_unanswered_questions,
    load_goals,
    load_heartbeat_history,
    load_memory,
)
from backend.world.first_pair_runtime import FirstPairRuntime, run_first_pair_demo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / ".runtime" / "first-pair")


def _run(store: FirstPairPersistenceStore, heartbeats: int = 2) -> dict:
    rt = FirstPairRuntime(heartbeat_limit=heartbeats, store=store)
    return rt.run()


# ---------------------------------------------------------------------------
# 1 – Fresh initialisation
# ---------------------------------------------------------------------------

class TestFreshInit:
    def test_identity_and_world_created(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        result = _run(store, heartbeats=1)
        assert result["heartbeats_completed"] == 1
        v = store._read_json(store._path("identity.json"))
        assert v is not None and v["type"] == "identity_record"
        ws = store._read_json(store._path("world_state.json"))
        assert ws is not None and ws["type"] == "world_state_record"


# ---------------------------------------------------------------------------
# 2 – Root isolation
# ---------------------------------------------------------------------------

class TestRootIsolation:
    def test_distinct_roots_isolated(self, tmp_path: Path) -> None:
        a = _fresh_store(tmp_path / "alpha")
        b = _fresh_store(tmp_path / "bravo")
        _run(a, 1)
        _run(b, 1)
        assert a._path("identity.json").exists()
        assert b._path("identity.json").exists()
        assert a.root != b.root


# ---------------------------------------------------------------------------
# 3 – Stable identities across restarts
# ---------------------------------------------------------------------------

class TestIdentityRestart:
    def test_adam_id_stable(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        _run(store, 1)
        v1 = store._read_json(store._path("identity.json"))
        _run(store, 1)
        v2 = store._read_json(store._path("identity.json"))
        assert v1 == v2

    def test_adam_eve_distinct(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        av = rt._agent_view("east_adam")
        ev = rt._agent_view("east_eve")
        assert av["agent_id"] != ev["agent_id"]


# ---------------------------------------------------------------------------
# 4 – Separate persisted memory lists
# ---------------------------------------------------------------------------

class TestSeparateMemory:
    def test_memory_keys_separate(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        _run(store, 2)
        mem = load_memory(store)
        assert "east_adam" in mem
        assert "east_eve" in mem
        # At least one entry per agent after 2 heartbeats
        assert len(mem["east_adam"]) >= 1
        assert len(mem["east_eve"]) >= 1

    def test_memory_not_clobbered(self, tmp_path: Path) -> None:
        """Both lists survive after a single save_memory call."""
        store = _fresh_store(tmp_path)
        _run(store, 1)
        mem = load_memory(store)
        assert len(mem["east_adam"]) > 0
        assert len(mem["east_eve"]) > 0


# ---------------------------------------------------------------------------
# 5 – Goals persist
# ---------------------------------------------------------------------------

class TestGoalPersistence:
    def test_goals_survive_restart(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        _run(store, 2)
        goals1 = load_goals(store)
        assert len(goals1) > 0
        _run(store, 1)
        goals2 = load_goals(store)
        assert len(goals2) >= len(goals1)


# ---------------------------------------------------------------------------
# 6 – Questions persist
# ---------------------------------------------------------------------------

class TestQuestionPersistence:
    def test_pending_questions_listed(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        _run(store, 2)
        pending = list_unanswered_questions(store)
        assert isinstance(pending, list)


# ---------------------------------------------------------------------------
# 7 – Heartbeat resume
# ---------------------------------------------------------------------------

class TestHeartbeatResume:
    def test_resume_at_next_number(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        _run(store, 2)
        h1 = load_heartbeat_history(store)
        assert len(h1) == 2
        _run(store, 2)
        h2 = load_heartbeat_history(store)
        assert len(h2) == 4
        assert h2[2].heartbeat_number == 3
        assert h2[3].heartbeat_number == 4


# ---------------------------------------------------------------------------
# 8 – Exact heartbeat count
# ---------------------------------------------------------------------------

class TestHeartbeatCount:
    def test_count_exact(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        for n in (1, 3, 5):
            rt = FirstPairRuntime(heartbeat_limit=n, store=_fresh_store(tmp_path))
            r = rt.run()
            assert r["heartbeats_completed"] == n


# ---------------------------------------------------------------------------
# 9 – create_public_object
# ---------------------------------------------------------------------------

class TestCreatePublicObject:
    def test_create_succeeds(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        _run(store, 2)
        ws = store._read_json(store._path("world_state.json"))
        assert ws is not None
        public_objects = ws["data"]["public_objects"]
        assert len(public_objects) >= 1

    def test_duplicate_rejected(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        obj_id = "test-dup-1"
        rec = PublicObjectRecord(
            object_id=obj_id,
            creator_agent_id=rt._agent_view("east_adam")["agent_id"],
            tile_id="public-start-adam",
            object_type="test",
            public_description="first",
            created_heartbeat=1,
        )
        rt._world_state.public_objects[obj_id] = rec.to_envelope()
        outcome = rt._execute_create_public_object("east_adam", {
            "action_type": "create_public_object",
            "object_id": obj_id,
            "object_type": "test",
            "description": "second",
            "tile_id": "public-start-adam",
        }, 99)
        assert outcome["status"] == "rejected"
        assert "Duplicate" in outcome.get("reason", "")

    def test_disallowed_tile_rejected(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        outcome = rt._execute_create_public_object("east_adam", {
            "action_type": "create_public_object",
            "object_id": "test-007",
            "object_type": "test",
            "description": "outside",
            "tile_id": "forbidden-zone",
        }, 99)
        assert outcome["status"] == "rejected"
        assert "not in allowed tiles" in outcome.get("reason", "")

    def test_empty_sanitized_rejected(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        outcome = rt._execute_create_public_object("east_adam", {
            "action_type": "create_public_object",
            "object_id": "test-empty",
            "object_type": "test",
            "description": "",  # empty string -> sanitized empty
            "tile_id": "public-start-adam",
        }, 99)
        assert outcome["status"] == "rejected"
        assert "Empty" in outcome.get("reason", "")

    def test_object_in_observation_after_create(self, tmp_path: Path) -> None:
        """After creation, the object should appear in the creator's observation."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=2, store=store)
        rt.run()
        ws = rt._world_state
        # Find Eve's object
        objs = [o for o in ws.public_objects.values()
                if isinstance(o, dict) and o.get("creator_agent_id") == rt._agent_view("east_eve")["agent_id"]]
        assert len(objs) >= 1
        obj = objs[0]
        # Objects at Eve's tile should include it
        eve_tile = ws.tile_occupancy.get("east_eve", "")
        at_tile = [o for o in ws.public_objects.values()
                   if isinstance(o, dict) and o.get("tile_id") == eve_tile]
        assert any(o["object_id"] == obj["object_id"] for o in at_tile)

    def test_exact_heartbeat_provenance(self, tmp_path: Path) -> None:
        """Object created during heartbeat N must have created_heartbeat = N."""
        store = _fresh_store(tmp_path)
        _run(store, 2)  # Eve creates object during heartbeat 2
        ws = store._read_json(store._path("world_state.json"))
        assert ws is not None
        for oid, o in ws["data"]["public_objects"].items():
            if oid == "eve-marker-stone-1":
                assert o["created_heartbeat"] == 2, (
                    f"Expected heartbeat 2, got {o['created_heartbeat']}"
                )
                return
        pytest.fail("eve-marker-stone-1 not found in public objects")


# ---------------------------------------------------------------------------
# 10 – World state persists after restart
# ---------------------------------------------------------------------------

class TestWorldStateDurability:
    def test_objects_survive_restart(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        _run(store, 2)
        raw1 = store._read_json(store._path("world_state.json"))
        objs1 = len(raw1["data"]["public_objects"]) if raw1 else 0
        _run(store, 1)
        raw2 = store._read_json(store._path("world_state.json"))
        objs2 = len(raw2["data"]["public_objects"]) if raw2 else 0
        assert objs2 >= objs1


# ---------------------------------------------------------------------------
# 11 – No world-sim/data access
# ---------------------------------------------------------------------------

class TestNoDataLeakage:
    def test_no_data_path_touched(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        _run(store, 1)
        data_root = Path("world-sim/data")
        if data_root.exists():
            contents = list(data_root.rglob("*"))
            assert not any(
                p.is_file() and "first_pair" in str(p).lower()
                for p in contents
            )


# ---------------------------------------------------------------------------
# 12 – Evidence export
# ---------------------------------------------------------------------------

class TestEvidenceExport:
    def test_export_valid_json(self, tmp_path: Path) -> None:
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        export_path = tmp_path / "evidence.json"
        bundle = rt.export_evidence(export_path)
        assert "adam_identity" in bundle
        assert "eve_identity" in bundle
        assert "heartbeat_log" in bundle
        assert isinstance(json.dumps(bundle), str)

    def test_run_first_pair_demo_export(self, tmp_path: Path) -> None:
        export_path = tmp_path / "demo_evidence.json"
        results = run_first_pair_demo(
            heartbeats=1,
            persistence_root=tmp_path / "demo",
            export_path=export_path,
        )
        assert results["heartbeats_completed"] == 1
        assert export_path.exists()
        with open(export_path, "r") as f:
            bundle = json.load(f)
        assert "adam_identity" in bundle
        assert "eve_identity" in bundle
        assert "heartbeat_log" in bundle


# ---------------------------------------------------------------------------
# 13 – Demo helper
# ---------------------------------------------------------------------------

class TestDemoHelper:
    def test_demo_completes(self, tmp_path: Path) -> None:
        results = run_first_pair_demo(heartbeats=3, persistence_root=tmp_path / "demo")
        assert results["heartbeats_completed"] == 3
        assert "errors" in results


# ---------------------------------------------------------------------------
# 14 – Deterministic stub output
# ---------------------------------------------------------------------------

class TestDeterministicStub:
    def test_identical_context_yields_identical_output(self) -> None:
        from backend.world.first_pair_cognition_stub import DeterministicStubBackend
        from backend.world.first_pair_cognition_interface import AgentContext

        ctx = AgentContext(
            agent_id="test-agent-1",
            canonical_name="Test",
            canonical_ref="test",
            heartbeat_number=1,
            position="tile-1",
            observation={"tile_id": "tile-1", "objects_here": []},
            memory=[],
            goals=[],
            unanswered_questions=[],
            world_public_objects={},
            habitat_allowed_tiles=["tile-1"],
            habitat_movement_allowed=False,
            previous_action=None,
            timestamp_utc="2025-01-01T00:00:00Z",
        )
        backend = DeterministicStubBackend(seed=42)
        output1 = backend.observe_and_orient(ctx)
        backend2 = DeterministicStubBackend(seed=42)
        output2 = backend2.observe_and_orient(ctx)

        assert output1.action == output2.action
        assert output1.memory_write == output2.memory_write
        assert output1.goal_updates == output2.goal_updates
        assert output1.questions_raised == output2.questions_raised
        assert output1.internal_reasoning == output2.internal_reasoning

    def test_alternating_stub_question_id_deterministic(self) -> None:
        """AlternatingStubBackend question IDs must not contain random components."""
        from backend.world.first_pair_cognition_stub import AlternatingStubBackend
        from backend.world.first_pair_cognition_interface import AgentContext

        ctx = AgentContext(
            agent_id="test-adam",
            canonical_name="Adam",
            canonical_ref="east_adam",
            heartbeat_number=2,
            position="public-start-adam",
            observation={"tile_id": "public-start-adam", "objects_here": []},
            memory=[{"type": "observation", "content": "seen tile"}],
            goals=[{"goal_id": "adam-goal-1", "description": "map", "status": "active"}],
            unanswered_questions=[],
            world_public_objects={},
            habitat_allowed_tiles=["public-start-adam", "public-start-eve"],
            habitat_movement_allowed=False,
            previous_action=None,
            timestamp_utc="2025-01-01T00:00:00Z",
        )
        backend = AlternatingStubBackend("east_adam")
        out1 = backend.observe_and_orient(ctx)
        backend2 = AlternatingStubBackend("east_adam")
        out2 = backend2.observe_and_orient(ctx)

        qid1 = out1.questions_raised[0]["question_id"] if out1.questions_raised else None
        qid2 = out2.questions_raised[0]["question_id"] if out2.questions_raised else None
        assert qid1 is not None
        assert qid1 == qid2, f"Question IDs differ: {qid1} vs {qid2}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
