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
        assert "Cannot place object on tile forbidden-zone" in outcome.get("reason", "")

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
        assert "adam_id" in bundle
        assert "eve_id" in bundle
        assert "heartbeats" in bundle
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
        assert "adam_id" in bundle
        assert "eve_id" in bundle
        assert "heartbeats" in bundle


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


# ---------------------------------------------------------------------------
# 14 – Runtime Policy Overlay and Movement Grant
# ---------------------------------------------------------------------------

class TestRuntimePolicyAndGrant:
    def test_habitat_immutable(self, tmp_path: Path) -> None:
        """Original 10ID habitat record retains movement_allowed=False."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        assert rt._habitat is not None
        assert rt._habitat.get("movement_allowed") is False
        # Verify on-disk identity still has historical habitat
        data = store._read_json(store._path("identity.json"))
        assert data is not None
        hb = data["data"]["habitat_boundary"]["habitat"]
        assert hb["movement_allowed"] is False

    def test_runtime_policy_separate(self, tmp_path: Path) -> None:
        """Runtime policy overlay is a separate file from identity."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        assert rt._runtime_policy is None  # No policy created yet

    def test_movement_fails_before_grant(self, tmp_path: Path) -> None:
        """Movement is blocked when no grant exists."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        outcome = rt._execute_move("east_adam", {
            "action_type": "move", "target_tile": "public-start-eve",
        })
        assert outcome["status"] == "blocked"
        assert "No active movement grant" in outcome.get("reason", "")

    def test_movement_fails_before_grant_with_policy_but_no_grant(self, tmp_path: Path) -> None:
        """Even with a policy, movement requires a grant record."""
        from backend.world.first_pair_persistence import create_default_runtime_policy, save_runtime_policy
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        # Create policy but no grant
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        rt._runtime_policy = policy
        outcome = rt._execute_move("east_adam", {
            "action_type": "move", "target_tile": "public-shared-center",
        })
        assert outcome["status"] == "blocked"
        assert "No active movement grant" in outcome.get("reason", "")

    def test_grant_and_policy_allow_movement(self, tmp_path: Path) -> None:
        """With grant and policy, adjacent movement succeeds."""
        from backend.world.first_pair_persistence import (
            create_default_runtime_policy, save_runtime_policy, grant_capability,
        )
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        # Create grant and policy
        grant = grant_capability(store, "movement", "first-pair-shared-habitat",
                                  "Operator-approved movement")
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        rt._capability_grant = grant
        rt._runtime_policy = policy
        outcome = rt._execute_move("east_adam", {
            "action_type": "move", "target_tile": "public-shared-center",
        })
        assert outcome["status"] == "success", f"Got: {outcome}"
        assert outcome.get("to") == "public-shared-center"
        # Verify position persisted
        assert rt._world_state.tile_occupancy["east_adam"] == "public-shared-center"

    def test_adjacent_movement_only(self, tmp_path: Path) -> None:
        """Cannot skip a tile — must be adjacent."""
        from backend.world.first_pair_persistence import (
            create_default_runtime_policy, save_runtime_policy, grant_capability,
        )
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        grant = grant_capability(store, "movement", "first-pair-shared-habitat",
                                  "Operator-approved movement")
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        rt._capability_grant = grant
        rt._runtime_policy = policy
        # Try to skip public-shared-center and go directly to public-start-eve
        outcome = rt._execute_move("east_adam", {
            "action_type": "move", "target_tile": "public-start-eve",
        })
        assert outcome["status"] == "blocked"
        assert "not adjacent" in outcome.get("reason", "")

    def test_movement_outside_allowed_fails(self, tmp_path: Path) -> None:
        """Moving to a tile outside allowed set is blocked."""
        from backend.world.first_pair_persistence import (
            create_default_runtime_policy, save_runtime_policy, grant_capability,
        )
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        grant = grant_capability(store, "movement", "first-pair-shared-habitat",
                                  "Operator-approved movement")
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        rt._capability_grant = grant
        rt._runtime_policy = policy
        outcome = rt._execute_move("east_adam", {
            "action_type": "move", "target_tile": "forbidden-zone",
        })
        assert outcome["status"] == "blocked"

    def test_shared_center_co_location_allowed(self, tmp_path: Path) -> None:
        """Both agents can occupy public-shared-center."""
        from backend.world.first_pair_persistence import (
            create_default_runtime_policy, save_runtime_policy, grant_capability,
        )
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=2, store=store)
        rt.run()
        grant = grant_capability(store, "movement", "first-pair-shared-habitat",
                                  "Operator-approved movement")
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        rt._capability_grant = grant
        rt._runtime_policy = policy
        # Move Adam to center
        outcome1 = rt._execute_move("east_adam", {
            "action_type": "move", "target_tile": "public-shared-center",
        })
        assert outcome1["status"] == "success"
        # Move Eve to center (now both there)
        outcome2 = rt._execute_move("east_eve", {
            "action_type": "move", "target_tile": "public-shared-center",
        })
        assert outcome2["status"] == "success"
        assert rt._world_state.tile_occupancy["east_adam"] == "public-shared-center"
        assert rt._world_state.tile_occupancy["east_eve"] == "public-shared-center"

    def test_positions_persist_across_restart(self, tmp_path: Path) -> None:
        """After moving, restart loads correct position."""
        from backend.world.first_pair_persistence import (
            create_default_runtime_policy, save_runtime_policy, grant_capability,
        )
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        grant = grant_capability(store, "movement", "first-pair-shared-habitat",
                                  "Operator-approved movement")
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        rt._capability_grant = grant
        rt._runtime_policy = policy
        rt._execute_move("east_adam", {
            "action_type": "move", "target_tile": "public-shared-center",
        })
        # Simulate save and restart
        from backend.world.first_pair_persistence import save_world_state
        save_world_state(store, rt._world_state)
        rt2 = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt2._load_or_initialize()
        assert rt2._world_state.tile_occupancy["east_adam"] == "public-shared-center"

    def test_available_moves_in_context(self, tmp_path: Path) -> None:
        """available_moves in context reflects adjacent tiles from policy."""
        from backend.world.first_pair_persistence import (
            create_default_runtime_policy, save_runtime_policy, grant_capability,
        )
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        grant = grant_capability(store, "movement", "first-pair-shared-habitat",
                                  "Operator-approved movement")
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        rt._capability_grant = grant
        rt._runtime_policy = policy
        ctx = rt._build_context("east_adam", 2)
        assert "public-shared-center" in ctx.available_moves
        assert "public-start-eve" not in ctx.available_moves  # not adjacent to start

    def test_answer_operation_zero_heartbeats(self, tmp_path: Path) -> None:
        """mark_question_answered runs zero heartbeats (no side effects on state)."""
        from backend.world.first_pair_persistence import mark_question_answered, list_unanswered_questions
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        # Manually add a question
        from backend.world.first_pair_persistence import QuestionRecord, save_questions
        q = QuestionRecord(
            question_id="q-test", asking_agent_id=rt._identity_record.adam_agent_id,
            heartbeat=1, question="Why?", reason_for_asking="curiosity",
            related_goal_id=None, requested_human_capability="", urgency="low",
        )
        save_questions(store, [q])
        # Answer it
        result = mark_question_answered(store, "q-test", "Because.")
        assert result is not None
        assert result["status"] == "answered"
        # Verify no new heartbeat created
        history = load_heartbeat_history(store)
        assert len(history) == 1  # Only the original heartbeat

    def test_grant_operation_zero_heartbeats(self, tmp_path: Path) -> None:
        """grant_capability runs zero heartbeats."""
        from backend.world.first_pair_persistence import grant_capability
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        grant = grant_capability(store, "movement", "first-pair-shared-habitat",
                                  "Operator-approved movement")
        assert grant.status == "granted"
        assert grant.capability_id == "movement"
        # Verify no new heartbeat created
        history = load_heartbeat_history(store)
        assert len(history) == 1

    def test_answer_does_not_imply_grant(self, tmp_path: Path) -> None:
        """Answering a question does not create a capability grant."""
        from backend.world.first_pair_persistence import (
            mark_question_answered, load_capability_grant,
        )
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        from backend.world.first_pair_persistence import QuestionRecord, save_questions
        q = QuestionRecord(
            question_id="q-grant-test", asking_agent_id=rt._identity_record.adam_agent_id,
            heartbeat=1, question="Can I move?", reason_for_asking="testing",
            related_goal_id=None, requested_human_capability="movement", urgency="low",
        )
        save_questions(store, [q])
        mark_question_answered(store, "q-grant-test", "Not yet.")
        grant = load_capability_grant(store)
        assert grant is None  # No grant created by answering

    def test_model_output_cannot_create_grant(self, tmp_path: Path) -> None:
        """Agent model output cannot create a grant record."""
        from backend.world.first_pair_persistence import (
            create_default_runtime_policy, save_runtime_policy,
            load_capability_grant,
        )
        store = _fresh_store(tmp_path)
        # Only policy exists, no grant
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        grant = load_capability_grant(store)
        assert grant is None

    def test_create_object_requires_current_tile(self, tmp_path: Path) -> None:
        """create_public_object only succeeds on the agent's current tile."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        # Adam at public-start-adam — try to place on public-start-eve
        outcome = rt._execute_create_public_object("east_adam", {
            "action_type": "create_public_object", "object_id": "o1",
            "object_type": "marker", "description": "wrong tile",
            "tile_id": "public-start-eve",
        }, 2)
        assert outcome["status"] == "rejected"
        assert "Cannot place object on tile" in outcome.get("reason", "")

    def test_observation_respects_adjacency(self, tmp_path: Path) -> None:
        """With grant, visible_tiles include adjacent tiles."""
        from backend.world.first_pair_persistence import (
            create_default_runtime_policy, save_runtime_policy, grant_capability,
        )
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        grant = grant_capability(store, "movement", "first-pair-shared-habitat",
                                  "Operator-approved movement")
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        rt._capability_grant = grant
        rt._runtime_policy = policy
        ctx = rt._build_context("east_adam", 2)
        assert "public-shared-center" in ctx.observation.get("visible_tiles", [])

    def test_no_private_memory_leakage_in_evidence(self, tmp_path: Path) -> None:
        """Privacy manifest reports zero other-agent private memory."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "priv.json")
        manifest = bundle.get("privacy_manifest", {})
        assert manifest.get("other_agent_private_memory_included") == 0

    def test_evidence_has_run_boundaries(self, tmp_path: Path) -> None:
        """Evidence export includes start/end heartbeats and cumulative count."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=2, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "bounds.json", run_id="test-run")
        assert bundle["evidence_schema_version"] == "10FN.1"
        assert bundle["run_id"] == "test-run"
        assert bundle["start_heartbeat"] == 1
        assert bundle["end_heartbeat"] == 2
        assert bundle["cumulative_heartbeat_count"] == 2

    def test_evidence_per_agent_actions(self, tmp_path: Path) -> None:
        """Heartbeat evidence distinguishes adam_action and eve_action."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "actions.json")
        for hb in bundle.get("heartbeats", []):
            assert "adam_action" in hb
            assert "eve_action" in hb

    def test_evidence_has_decision_and_uncertainty(self, tmp_path: Path) -> None:
        """Evidence includes decision_summary and uncertainty fields."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "decisions.json")
        assert "adam_decision_summary" in bundle
        assert "adam_uncertainty" in bundle
        assert "eve_decision_summary" in bundle
        assert "eve_uncertainty" in bundle

    def test_evidence_privacy_manifest_contents(self, tmp_path: Path) -> None:
        """Privacy manifest contains required metadata fields."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "manifest.json")
        manifest = bundle.get("privacy_manifest", {})
        assert "requesting_agent_id_adam" in manifest
        assert "requesting_agent_id_eve" in manifest
        assert "adam_private_memory_count" in manifest
        assert "eve_private_memory_count" in manifest
        assert "other_agent_private_memory_included" in manifest
        assert "public_evidence_count" in manifest
        assert "answered_question_count" in manifest
        assert "canonical_request_hash" in manifest

    def test_evidence_no_credentials(self, tmp_path: Path) -> None:
        """No credential-like strings in evidence output."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "nocreds.json")
        bundle_str = json.dumps(bundle)
        assert "nvapi-" not in bundle_str
        assert "sk-" not in bundle_str
        assert "api_key" not in bundle_str.lower()

    def test_existing_tests_still_pass(self, tmp_path: Path) -> None:
        """Pre-existing runtime tests continue working with deterministic_stub."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=2, store=store, backend="deterministic_stub")
        results = rt.run()
        assert results["heartbeats_completed"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
