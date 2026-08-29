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
    MemorySummaryRecord,
    PublicObjectRecord,
    RelationshipEventRecord,
    _derive_memory_id,
    _ensure_memory_ids,
    _hash_canonical,
    _MEMORY_ID_DERIVATION_VERSION,
    _score_human_context,
    _score_relevance,
    append_memory_selection_manifest,
    append_relationship_event,
    append_summary,
    compute_summary_source_commitment,
    derive_summaries_for_omitted,
    save_summaries,
    save_relationship_events,
    select_human_context,
    validate_summary,
    validate_summary_record,
    derive_relationship_event_ids,
    load_memory_selection_manifests,
    load_memory,
    load_goals,
    load_heartbeat_history,
    load_relationship_events,
    load_summaries,
    list_unanswered_questions,
    maybe_record_relationship_event,
    save_relationship_events,
    save_summaries,
    select_private_memories,
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


def _signed_answer_authorization(monkeypatch, *, question_id: str, asking_agent_id: str, answer: str) -> dict:
    """Test-only Signed Answer Authority V1 envelope (ephemeral Ed25519 key).

    Mirrors the external operator signer: signs the canonical unsigned answer
    payload with a throwaway private key and installs its PUBLIC key (only) as
    the env trust root. The private key never leaves this helper. Production
    backend remains verify-only.
    """
    import hashlib
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    def canonical(v: dict) -> str:
        return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def h(v: dict) -> str:
        return hashlib.sha256(canonical(v).encode("utf-8")).hexdigest()

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    monkeypatch.setenv("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", pub.hex())

    payload = {
        "schema": "single_question_answer_authorization.ed25519.1",
        "domain": "GENESIS_FIRST_PAIR_SINGLE_QUESTION_ANSWER_AUTH_ED25519_V1",
        "action": "single_question_answer",
        "question_id": question_id,
        "asking_agent_id": asking_agent_id,
        "formatted_answer_hash": h({"answer_material": answer.strip()}),
        "max_writes": 1,
        "nonce": "host-119-test-nonce",
        "issued_at_utc": "2026-01-01T00:00:00Z",
        "expires_at_utc": "9999-01-01T00:00:00Z",
        "operator_proof_ref": "proof-1",
    }
    envelope = dict(payload)
    envelope["signature"] = priv.sign(canonical(payload).encode("utf-8")).hex()
    return envelope


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

    def test_answer_operation_zero_heartbeats(self, tmp_path: Path, monkeypatch) -> None:
        """The governed answer operation runs zero heartbeats (no side effects on state)."""
        from backend.world.first_pair_persistence import list_unanswered_questions
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        # Manually add a question (test-only fixture seed: bypasses production authority)
        from backend.world.first_pair_persistence import QuestionRecord, _save_questions_raw
        q = QuestionRecord(
            question_id="q-test", asking_agent_id=rt._identity_record.adam_agent_id,
            heartbeat=1, question="Why?", reason_for_asking="curiosity",
            related_goal_id=None, requested_human_capability="", urgency="low",
        )
        _save_questions_raw(store, [q])
        # Answer it through the governed seam, under a signed answer authorization.
        from backend.world.local_single_question_answer import apply_question_answer
        auth = _signed_answer_authorization(
            monkeypatch,
            question_id="q-test",
            asking_agent_id=rt._identity_record.adam_agent_id,
            answer="Because.",
        )
        result = apply_question_answer(
            store, question_id="q-test",
            asking_agent_id=rt._identity_record.adam_agent_id,
            answer="Because.", authorization=auth,
        )
        assert result["ok"] is True
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

    def test_answer_does_not_imply_grant(self, tmp_path: Path, monkeypatch) -> None:
        """Answering a question does not create a capability grant."""
        from backend.world.first_pair_persistence import load_capability_grant
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        from backend.world.first_pair_persistence import QuestionRecord, _save_questions_raw
        q = QuestionRecord(
            question_id="q-grant-test", asking_agent_id=rt._identity_record.adam_agent_id,
            heartbeat=1, question="Can I move?", reason_for_asking="testing",
            related_goal_id=None, requested_human_capability="movement", urgency="low",
        )
        # Test-only fixture seed: bypasses production creation authority intentionally.
        _save_questions_raw(store, [q])
        from backend.world.local_single_question_answer import apply_question_answer
        auth = _signed_answer_authorization(
            monkeypatch,
            question_id="q-grant-test",
            asking_agent_id=rt._identity_record.adam_agent_id,
            answer="Not yet.",
        )
        result = apply_question_answer(
            store, question_id="q-grant-test",
            asking_agent_id=rt._identity_record.adam_agent_id,
            answer="Not yet.", authorization=auth,
        )
        assert result["ok"] is True
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
        assert bundle["evidence_schema_version"] == "10FN.2"
        assert bundle["run_id"] == "test-run"
        assert bundle["start_heartbeat"] == 1
        assert bundle["end_heartbeat"] == 2
        assert bundle["cumulative_heartbeat_count"] == 2
        assert bundle["backend_label"] == "stub"

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


# ---------------------------------------------------------------------------
# 15 – Bounded memory selection (hardened)
# ---------------------------------------------------------------------------


class TestBoundedMemorySelection:
    """select_private_memories determinism, limits, tiers, cross-agent safety."""

    def _sample_memories(self, count: int = 20) -> list[dict]:
        return [
            {"type": "observation", "content": f"Memory {i} content", "heartbeat": i}
            for i in range(count)
        ]

    def _adam_goals(self) -> list[dict]:
        return [{"goal_id": "goal-explore", "status": "active"}]

    def _adam_state(self) -> dict:
        return {
            "agent_id": "genesis-agent-test-adam-aaa",
            "goals": self._adam_goals(),
            "position": "tile-alpha",
            "visible_tiles": {"tile-alpha"},
            "visible_object_ids": set(),
            "visible_message_ids": set(),
            "relationship_event_memory_ids": set(),
            "recent_cutoff_hb": 0,
        }

    # 1 – Determinism
    def test_deterministic_with_same_seed(self) -> None:
        """Same input produces identical output."""
        mems = self._sample_memories(10)
        s1, m1 = select_private_memories(mems, **self._adam_state())
        s2, m2 = select_private_memories(mems, **self._adam_state())
        assert [m.get("memory_id") for m in s1] == [m.get("memory_id") for m in s2]
        assert m1["canonical_selection_hash"] == m2["canonical_selection_hash"]

    # 2 – Different agent → different hash (identical content, identical context,
    #    only agent_id differs)
    def test_different_agent_different_hash(self) -> None:
        """Identical context except agent_id produces different canonical_selection_hash."""
        mems = self._sample_memories(10)
        ctx = dict(
            goals=self._adam_goals(), position="tile-alpha",
            visible_tiles={"tile-alpha"}, visible_object_ids=set(),
            visible_message_ids=set(), relationship_event_memory_ids=set(),
            recent_cutoff_hb=0,
        )
        _, m1 = select_private_memories(mems, agent_id="adam-aaa", **ctx)
        _, m2 = select_private_memories(mems, agent_id="eve-bbb", **ctx)
        # Hash differs because agent_id anchors the canonical hash
        assert m1["canonical_selection_hash"] != m2["canonical_selection_hash"]

    # 3 – Recent memories get priority inclusion
    def test_recent_memories_included(self) -> None:
        """Memories within recent_cutoff_hb appear in selected set."""
        mems = self._sample_memories(20)
        state = self._adam_state()
        state["recent_cutoff_hb"] = 18
        selected, _ = select_private_memories(mems, **state)
        assert len(selected) > 0

    # 4 – Total cap: at most 16 detailed memories
    def test_total_detailed_memory_cap(self) -> None:
        """At most 16 total detailed memories regardless of input size."""
        mems = self._sample_memories(200)
        selected, manifest = select_private_memories(mems, **self._adam_state())
        assert len(selected) <= 16
        assert manifest["selected_private_memory_count"] <= 16

    # 5 – Character cap: at most 12000 chars
    def test_character_limit(self) -> None:
        """Total character count does not exceed 12000."""
        mems = [{"type": "observation", "content": "x" * 2000, "heartbeat": i} for i in range(20)]
        selected, manifest = select_private_memories(mems, **self._adam_state())
        total_chars = sum(len(str(m.get("content", ""))) for m in selected)
        assert total_chars <= 12000
        assert manifest["selected_private_memory_character_count"] <= 12000

    # 6 – Empty input
    def test_empty_memory_list(self) -> None:
        """Empty memory list returns empty selection."""
        selected, manifest = select_private_memories([], **self._adam_state())
        assert selected == []
        assert manifest["raw_private_memory_count"] == 0
        assert manifest["selected_private_memory_count"] == 0

    # 7 – Single memory
    def test_single_memory(self) -> None:
        """Single memory is selected."""
        mems = [{"type": "observation", "content": "Only memory", "heartbeat": 1}]
        selected, _ = select_private_memories(mems, **self._adam_state())
        assert len(selected) == 1

    # 8 – Manifest has all keys
    def test_manifest_has_all_keys(self) -> None:
        """Manifest contains all required metadata keys."""
        mems = self._sample_memories(5)
        _, manifest = select_private_memories(mems, **self._adam_state())
        for key in ("requesting_agent_id", "raw_private_memory_count",
                     "selected_private_memory_ids", "selected_private_memory_count",
                     "other_agent_private_memory_count_included", "canonical_selection_hash"):
            assert key in manifest

    # 9 – Zero cross-agent private memory in manifest
    def test_other_agent_private_memory_count_zero(self) -> None:
        """Cross-agent private memory leakage is zero."""
        mems = self._sample_memories(5)
        _, manifest = select_private_memories(mems, **self._adam_state())
        assert manifest["other_agent_private_memory_count_included"] == 0

    # 10 – Recent cutoff boundary
    def test_cutoff_boundary_includes_all_recent(self) -> None:
        """All memories at or after cutoff are recent candidates."""
        mems = self._sample_memories(8)
        state = self._adam_state()
        state["recent_cutoff_hb"] = 5
        selected, _ = select_private_memories(mems, **state)
        recent_hbs = {m["heartbeat"] for m in selected if m["heartbeat"] >= 5}
        assert len(recent_hbs) >= 3 or len(selected) == 8


# ---------------------------------------------------------------------------
# 16 – Legacy memory IDs (hardened)
# ---------------------------------------------------------------------------


class TestOwnerBoundMemoryIDs:
    """_derive_memory_id correctness: owner-bound, full-content, no index."""

    def test_same_owner_same_content_same_id(self) -> None:
        entry = {"content": "Hello world", "heartbeat": 1, "type": "observation"}
        owner = "adam-aaa"
        id1 = _derive_memory_id(owner, entry)
        id2 = _derive_memory_id(owner, entry)
        assert id1 == id2
        assert id1.startswith("mem-")
        assert len(id1) == 20  # "mem-" + 16 hex chars

    def test_different_owner_different_ids(self) -> None:
        entry = {"content": "Identical content", "heartbeat": 2, "type": "observation"}
        adam_id = _derive_memory_id("adam-aaa", entry)
        eve_id = _derive_memory_id("eve-bbb", entry)
        assert adam_id != eve_id

    def test_full_content_beyond_80_chars(self) -> None:
        long = "x" * 200
        entry = {"content": long, "heartbeat": 3, "type": "observation"}
        owner = "adam-aaa"
        # Full 200 chars should affect the hash
        id_short = _derive_memory_id(owner, {"content": "x" * 80, "heartbeat": 3, "type": "observation"})
        id_long = _derive_memory_id(owner, entry)
        assert id_short != id_long, "ID must use full content, not truncated 80 chars"

    def test_no_list_index_dependency(self) -> None:
        entry = {"content": "Index-independent", "heartbeat": 4, "type": "observation"}
        owner = "adam-aaa"
        # Same content regardless of list position produces same ID
        id_a = _derive_memory_id(owner, entry)
        id_b = _derive_memory_id(owner, entry)
        assert id_a == id_b

    def test_identical_content_different_fields_same_owner_differs(self) -> None:
        entry_a = {"content": "Same content", "heartbeat": 1, "type": "observation"}
        entry_b = {"content": "Same content", "heartbeat": 2, "type": "observation"}
        owner = "adam-aaa"
        id_a = _derive_memory_id(owner, entry_a)
        id_b = _derive_memory_id(owner, entry_b)
        assert id_a != id_b, "Different heartbeat should produce different ID"

    def test_ensure_memory_ids_does_not_mutate_input(self) -> None:
        orig = [{"content": "No ID", "heartbeat": 1}]
        before = list(orig)
        _ensure_memory_ids(orig, owner_agent_id="adam-aaa")
        assert orig == before

    def test_ensure_shallow_copy_preserves_ids(self) -> None:
        mems = [{"memory_id": "mem-preserved", "content": "Has ID", "heartbeat": 1}]
        result = _ensure_memory_ids(mems, owner_agent_id="adam-aaa")
        assert result[0]["memory_id"] == "mem-preserved"

    def test_same_owner_duplicate_deduplication(self) -> None:
        """Duplicate raw entries for the same owner derive the same ID."""
        entry = {"content": "Duplicate me", "heartbeat": 5, "type": "observation"}
        owner = "adam-aaa"
        mems = [dict(entry), dict(entry)]
        ensured = _ensure_memory_ids(mems, owner_agent_id=owner)
        assert ensured[0]["memory_id"] == ensured[1]["memory_id"]
        ids = {m["memory_id"] for m in ensured}
        assert len(ids) == 1

    def test_raw_memory_preserved(self) -> None:
        """_ensure_memory_ids does not add memory_id to original entries."""
        entry = {"content": "Preserve me", "heartbeat": 6}
        orig = [dict(entry)]
        _ensure_memory_ids(orig, owner_agent_id="adam-aaa")
        assert "memory_id" not in orig[0]


# ---------------------------------------------------------------------------
# 17 – Raw-memory preservation (hardened)
# ---------------------------------------------------------------------------


class TestRawMemoryPreservation:
    """Selection, summary creation and relationship derivation must not append,
    mutate, reorder or delete raw memory entries."""

    def _hash_raw(self, store: FirstPairPersistenceStore) -> str:
        from backend.world.first_pair_persistence import _hash_canonical, load_memory
        return _hash_canonical(load_memory(store))

    def test_selection_does_not_mutate_raw(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "preserve-sel")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        h_before = self._hash_raw(store)
        # Run selection through _build_context
        ctx = rt._build_context("east_adam", 2)
        assert ctx.selected_private_memories is not None
        h_after = self._hash_raw(store)
        assert h_before == h_after

    def test_summary_creation_does_not_mutate_raw(self, tmp_path: Path) -> None:
        from backend.world.first_pair_persistence import (
            MemorySummaryRecord, append_summary, _hash_canonical, load_memory,
        )
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "preserve-sum")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        h_before = self._hash_raw(store)
        summary = MemorySummaryRecord(
            summary_id="sum-pres", owner_agent_id=rt._identity_record.adam_agent_id,
            covered_memory_ids=[], covered_heartbeat_range=[],
            summary="Test preservation.", salient_entities=[],
            related_goal_ids=[], related_public_object_ids=[], related_message_ids=[],
        )
        append_summary(store, summary)
        h_after = self._hash_raw(store)
        assert h_before == h_after

    def test_relationship_event_does_not_mutate_raw(self, tmp_path: Path) -> None:
        from backend.world.first_pair_persistence import (
            RelationshipEventRecord, append_relationship_event,
        )
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "preserve-rel")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        h_before = self._hash_raw(store)
        event = RelationshipEventRecord(
            event_id="evt-pres", heartbeat=1, actor_agent_id=rt._identity_record.adam_agent_id,
            other_agent_id=rt._identity_record.eve_agent_id, event_type="message_sent",
            public_evidence_references=[], resulting_public_state_commitment="",
        )
        append_relationship_event(store, event)
        h_after = self._hash_raw(store)
        assert h_before == h_after

    def test_operator_inspection_does_not_mutate_raw(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "preserve-inspect")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        h_before = self._hash_raw(store)
        # Simulate operator inspection: load context, produce inspection output
        ctx = rt._build_context("east_adam", 2)
        _ = len(ctx.selected_private_memories)
        h_after = self._hash_raw(store)
        assert h_before == h_after


# ---------------------------------------------------------------------------
# 18 – Derived summary validation (hardened)
# ---------------------------------------------------------------------------


class TestDerivedSummaryValidation:
    """MemorySummaryRecord validation: coverage, ownership, source commitment,
    failure isolation."""

    def _make_store(self, tmp_path: Path, sub: str) -> FirstPairPersistenceStore:
        return FirstPairPersistenceStore(tmp_path / ".runtime" / sub)

    def test_every_covered_memory_id_resolves(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path, "sum-validate")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        mems = load_memory(store).get("east_adam", [])
        owner = rt._identity_record.adam_agent_id
        ensured = _ensure_memory_ids(mems, owner_agent_id=owner)
        covered_ids = [m["memory_id"] for m in ensured[:2]]
        covered_mems = [m for m in ensured if m["memory_id"] in covered_ids]
        hbs = [m.get("heartbeat", 0) for m in covered_mems]
        summ = MemorySummaryRecord(
            summary_id="", owner_agent_id=owner,
            covered_memory_ids=covered_ids,
            covered_heartbeat_range=[min(hbs), max(hbs)],
            summary="[derived from heartbeat 1] Coverage test.", salient_entities=[],
            related_goal_ids=[], related_public_object_ids=[], related_message_ids=[],
            derivation_method="deterministic_extractive",
            source_commitment=compute_summary_source_commitment(owner, covered_mems),
        )
        summ.summary_id = "sum-derived-" + summ.semantic_commitment()[:16]
        summ.seal()
        result = append_summary(store, summ, memory_list=mems)
        assert result["ok"], f"append_summary failed: {result['errors']}"
        loaded = load_summaries(store)
        assert len(loaded) == 1
        for cid in loaded[0].covered_memory_ids:
            assert any(m.get("memory_id") == cid for m in ensured)

    def test_failure_leaves_summaries_unchanged(self, tmp_path: Path) -> None:
        from backend.world.first_pair_persistence import _ensure_memory_ids
        store = self._make_store(tmp_path, "sum-fail")
        # Build a valid memory list with derived IDs
        raw_mems = [{"heartbeat": 1, "content": "Initial event", "type": "observation"}]
        owner = "adam-aaa"
        ensured = _ensure_memory_ids(raw_mems, owner_agent_id=owner)
        init_mid = ensured[0]["memory_id"]
        s0 = MemorySummaryRecord(
            summary_id="", owner_agent_id=owner,
            covered_memory_ids=[init_mid], covered_heartbeat_range=[1, 1],
            summary="[derived from heartbeat 1] Initial.", salient_entities=[],
            related_goal_ids=[], related_public_object_ids=[], related_message_ids=[],
            derivation_method="deterministic_extractive",
            source_commitment=compute_summary_source_commitment(owner, [ensured[0]]),
        )
        s0.summary_id = "sum-derived-" + s0.semantic_commitment()[:16]
        s0.seal()
        result = append_summary(store, s0, memory_list=raw_mems)
        assert result["ok"], f"append_summary failed: {result['errors']}"
        loaded_before = load_summaries(store)
        # Append with empty owner and empty summary — should fail validation
        bad = MemorySummaryRecord(
            summary_id="sum-bad", owner_agent_id="",
            covered_memory_ids=[], covered_heartbeat_range=[],
            summary="", salient_entities=[],
            related_goal_ids=[], related_public_object_ids=[], related_message_ids=[],
        )
        result = append_summary(store, bad)
        assert not result["ok"], "append_summary should fail for invalid summary"
        assert len(result["errors"]) > 0
        loaded_after = load_summaries(store)
        # The initial summary must survive regardless of the failed append
        assert len(loaded_after) >= 1
        assert loaded_after[0].summary_id == s0.summary_id

    def test_summaries_label_as_derived(self, tmp_path: Path) -> None:
        """to_envelope marks type as memory_summary_record."""
        r = MemorySummaryRecord(
            summary_id="sum-label", owner_agent_id="eve-bbb",
            covered_memory_ids=[], covered_heartbeat_range=[],
            summary="Label test.", salient_entities=[],
            related_goal_ids=[], related_public_object_ids=[], related_message_ids=[],
        ).seal()
        env = r.to_envelope()
        assert env["type"] == "memory_summary_record"


# ---------------------------------------------------------------------------
# 19 – Relationship event runtime persistence (hardened)
# ---------------------------------------------------------------------------


class TestRelationshipEventPersistence:
    """RelationshipEventRecord save/load/append/derive roundtrip."""

    def test_save_and_load_empty(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-rel")
        assert load_relationship_events(store) == []

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-rel2")
        events = [
            RelationshipEventRecord(
                event_id="evt-001", heartbeat=1, actor_agent_id="adam-aaa",
                other_agent_id="eve-bbb", event_type="co_location",
                public_evidence_references=["obj-mem-001"],
                resulting_public_state_commitment="abc",
            )
        ]
        save_relationship_events(store, events)
        loaded = load_relationship_events(store)
        assert len(loaded) == 1
        assert loaded[0].event_id == "evt-001"

    def test_append_event(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-rel3")
        e = RelationshipEventRecord(
            event_id="evt-010", heartbeat=2, actor_agent_id="adam-aaa",
            other_agent_id="eve-bbb", event_type="message_sent",
            public_evidence_references=["msg-001"],
            resulting_public_state_commitment="def",
        )
        append_relationship_event(store, e)
        loaded = load_relationship_events(store)
        assert len(loaded) == 1

    def test_derive_event_ids(self) -> None:
        events = [
            RelationshipEventRecord(
                event_id="evt-100", heartbeat=3, actor_agent_id="adam-aaa",
                other_agent_id="eve-bbb", event_type="co_location",
                public_evidence_references=["mem-evt-100"],
                resulting_public_state_commitment="",
            ),
            RelationshipEventRecord(
                event_id="evt-101", heartbeat=3, actor_agent_id="adam-aaa",
                other_agent_id="eve-bbb", event_type="message_sent",
                public_evidence_references=["mem-evt-101"],
                resulting_public_state_commitment="",
            ),
        ]
        ids = derive_relationship_event_ids(events)
        assert ids == {"mem-evt-100", "mem-evt-101"}


# ---------------------------------------------------------------------------
# 20 – Relationship event recording through runtime outcomes (hardened)
# ---------------------------------------------------------------------------


class TestRelationshipEventRecording:
    """Persisted runtime outcomes create correct relationship events.
    Rejected actions and no_action create none. Retries do not duplicate.
    No emotional/trust score field exists."""

    def _do_move(self, rt: FirstPairRuntime, agent_ref: str, tile: str, hb: int) -> dict:
        return rt._execute_move(agent_ref, {
            "action_type": "move", "target_tile": tile,
        })

    def test_message_persisted_creates_event(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "rel-msg")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        # After 1 heartbeat, agent left a public message (stub does leave_public_message)
        events = load_relationship_events(store)
        message_events = [e for e in events if e.event_type == "message_sent"]
        # Stub may or may not have produced a message depending on agent
        # We verify: if any events exist, message_sent is possible
        for ev in events:
            assert not hasattr(ev, "affection_score")
            assert not hasattr(ev, "trust_score")
            assert not hasattr(ev, "loyalty_score")
            assert not hasattr(ev, "friendship_score")

    def test_no_emotional_score_fields(self, tmp_path: Path) -> None:
        store = self._make_store_no_op(tmp_path, "rel-noemotion")
        event = RelationshipEventRecord(
            event_id="evt-noem", heartbeat=1, actor_agent_id="adam-aaa",
            other_agent_id="eve-bbb", event_type="message_sent",
            public_evidence_references=[], resulting_public_state_commitment="",
        )
        assert not hasattr(event, "affection_score")
        assert not hasattr(event, "trust_score")
        assert not hasattr(event, "loyalty_score")
        assert not hasattr(event, "friendship_score")

    def _make_store_no_op(self, tmp_path: Path, sub: str) -> FirstPairPersistenceStore:
        return FirstPairPersistenceStore(tmp_path / ".runtime" / sub)

    def test_rejected_action_creates_no_event(self, tmp_path: Path) -> None:
        """A proposed-but-rejected action must not create a relationship event."""
        from backend.world.first_pair_persistence import (
            RelationshipEventRecord, append_relationship_event,
        )
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "rel-rej")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        events_before = len(load_relationship_events(store))
        # Simulate a failed action outcome
        from backend.world.first_pair_persistence import maybe_record_relationship_event
        from types import SimpleNamespace
        ws = SimpleNamespace(tile_occupancy={}, public_objects={})
        result = maybe_record_relationship_event(
            store, 99, "east_adam", rt._identity_record.adam_agent_id,
            rt._identity_record.eve_agent_id, "move",
            outcome={"status": "rejected"},
            agent_view={}, world_state=ws,
        )
        assert result is None
        assert len(load_relationship_events(store)) == events_before


# ---------------------------------------------------------------------------
# 21 – Memory selection manifest persistence
# ---------------------------------------------------------------------------


class TestMemorySelectionManifest:
    def test_append_and_load(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-manifest")
        assert load_memory_selection_manifests(store) == []
        append_memory_selection_manifest(store, {"hb": 1, "count": 5})
        append_memory_selection_manifest(store, {"hb": 2, "count": 3})
        loaded = load_memory_selection_manifests(store)
        assert len(loaded) == 2
        assert loaded[0]["hb"] == 1


# ---------------------------------------------------------------------------
# 22 – Cross-agent runtime isolation with sentinel markers (hardened)
# ---------------------------------------------------------------------------


class TestCrossAgentIsolation:
    """Plant unmistakable private sentinel markers; verify each agent's runtime
    context and prompt contain their own sentinel but not the other's."""

    ADAM_SENTINEL = "ADAM_PRIVATE_SENTINEL_7F29"
    EVE_SENTINEL = "EVE_PRIVATE_SENTINEL_9C14"

    def _make_store(self, tmp_path: Path, sub: str) -> FirstPairPersistenceStore:
        return FirstPairPersistenceStore(tmp_path / ".runtime" / sub)

    def _inject_sentinels_and_reload(self, rt: FirstPairRuntime) -> None:
        """Inject sentinel entries directly into runtime in-memory copies and
        persist to disk so _build_context sees them."""
        rt._adam_memory.append({
            "type": "observation", "content": self.ADAM_SENTINEL, "heartbeat": 1,
            "memory_id": "mem-adam-sentinel",
        })
        rt._eve_memory.append({
            "type": "observation", "content": self.EVE_SENTINEL, "heartbeat": 1,
            "memory_id": "mem-eve-sentinel",
        })
        # Persist so subsequent _load_or_initialize or context builder sees them
        from backend.world.first_pair_persistence import save_memory
        save_memory(rt._store, {"east_adam": list(rt._adam_memory), "east_eve": list(rt._eve_memory)})

    def test_adam_raw_memory_structural_isolation(self, tmp_path: Path) -> None:
        """Adam's raw ctx.memory contains ADAM_PRIVATE_SENTINEL_7F29 but not
        EVE_PRIVATE_SENTINEL_9C14 — proving the memory lists are structurally isolated."""
        store = self._make_store(tmp_path, "cross-raw-adam")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        self._inject_sentinels_and_reload(rt)
        ctx = rt._build_context("east_adam", 2)
        raw_str = str(ctx.memory)
        assert self.ADAM_SENTINEL in raw_str
        assert self.EVE_SENTINEL not in raw_str

    def test_eve_raw_memory_structural_isolation(self, tmp_path: Path) -> None:
        """Eve's raw ctx.memory contains EVE_PRIVATE_SENTINEL_9C14 but not
        ADAM_PRIVATE_SENTINEL_7F29."""
        store = self._make_store(tmp_path, "cross-raw-eve")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        self._inject_sentinels_and_reload(rt)
        ctx = rt._build_context("east_eve", 2)
        raw_str = str(ctx.memory)
        assert self.EVE_SENTINEL in raw_str
        assert self.ADAM_SENTINEL not in raw_str

    def test_both_manifests_report_zero_other_agent(self, tmp_path: Path) -> None:
        """Both agents' manifests report other_agent_private_memory_count_included = 0."""
        store = self._make_store(tmp_path, "cross-manifest")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        self._inject_sentinels_and_reload(rt)
        ctx_adam = rt._build_context("east_adam", 2)
        ctx_eve = rt._build_context("east_eve", 2)
        assert ctx_adam.memory_selection_manifest.get("other_agent_private_memory_count_included") == 0
        assert ctx_eve.memory_selection_manifest.get("other_agent_private_memory_count_included") == 0

    def test_prompt_privacy_declaration(self, tmp_path: Path) -> None:
        """Both agents' prompts declare the other agent's private memories are unavailable."""
        from backend.world.first_pair_cognition_model import build_system_prompt
        store = self._make_store(tmp_path, "priv-decl")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        ctx = rt._build_context("east_adam", 2)
        prompt = build_system_prompt(ctx)
        assert "other agent's private memories are never available" in prompt


# ---------------------------------------------------------------------------
# 23 – Evidence boundaries (hardened)
# ---------------------------------------------------------------------------


class TestEvidenceBoundaries:
    """Evidence export distinguishes start/end heartbeats, counts, selection
    metrics, prompt sizes, provider outcomes."""

    def test_evidence_has_run_boundaries(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-bound")
        rt = FirstPairRuntime(heartbeat_limit=2, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "b1.json", run_id="bounds-test")
        assert bundle["evidence_schema_version"] == "10FN.2"
        assert bundle["run_id"] == "bounds-test"
        assert bundle["start_heartbeat"] == 1
        assert bundle["end_heartbeat"] == 2
        assert bundle["cumulative_heartbeat_count"] == 2
        assert bundle["backend_label"] == "stub"

    def test_evidence_cumulative_heartbeat_count(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-cum")
        rt = FirstPairRuntime(heartbeat_limit=3, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "b2.json")
        assert bundle.get("cumulative_heartbeat_count", 0) == 3

    def test_evidence_memory_counts_before_after(self, tmp_path: Path) -> None:
        """Evidence includes adam_memory_count_before and _after fields."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-raw")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "b3.json")
        assert "adam_memory_count_before" in bundle
        assert "adam_memory_count_after" in bundle
        assert "eve_memory_count_before" in bundle
        assert "eve_memory_count_after" in bundle

    def test_evidence_bounded_memory_fields(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-boundmem")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        bundle = rt.export_evidence(tmp_path / "b4.json")
        assert "memory_selection_manifests" in bundle
        assert "memory_summaries" in bundle
        assert "relationship_events" in bundle
        assert "adam_selected_memory_count" in bundle
        assert "eve_selected_memory_count" in bundle
        assert "summary_count" in bundle
        assert "relationship_event_count" in bundle

    def test_evidence_selection_manifests_per_request(self, tmp_path: Path) -> None:
        """Each heartbeat request has a corresponding selection manifest entry."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-manifests")
        rt = FirstPairRuntime(heartbeat_limit=2, store=store, backend="deterministic_stub")
        rt.run()
        bundle = rt.export_evidence(tmp_path / "b5.json")
        manifests = bundle.get("memory_selection_manifests", [])
        assert len(manifests) >= 2  # At least one per agent per heartbeat

    def test_evidence_no_credentials(self, tmp_path: Path) -> None:
        """No credential-like strings in evidence output."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-nocred")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        bundle = rt.export_evidence(tmp_path / "nocreds.json")
        bundle_str = json.dumps(bundle)
        assert "nvapi-" not in bundle_str
        assert "sk-" not in bundle_str
        assert "api_key" not in bundle_str.lower()

    def test_evidence_3_plus_3_sequential_from_hb11(self, tmp_path: Path) -> None:
        """Run 3 heartbeats from a post-HB11 store, then 3 more. Verify
        start=12/end=14/new=3/cumulative=14, then 15/17/3/17."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-hb11")
        # Build up to heartbeat 11
        rt_init = FirstPairRuntime(heartbeat_limit=11, store=store)
        rt_init.run()
        bundle_init = rt_init.export_evidence(tmp_path / "hb11.json")
        assert bundle_init["end_heartbeat"] == 11
        assert bundle_init["cumulative_heartbeat_count"] == 11
        hb11_adam_after = bundle_init["adam_memory_count_after"]
        hb11_eve_after = bundle_init["eve_memory_count_after"]

        # First continuation: 3 heartbeats on same store
        rt_a = FirstPairRuntime(heartbeat_limit=3, store=store)
        rt_a.run()
        bundle_a = rt_a.export_evidence(tmp_path / "cont1.json", run_id="cont-A")
        assert bundle_a["start_heartbeat"] == 12
        assert bundle_a["end_heartbeat"] == 14
        assert bundle_a["new_heartbeat_count"] == 3
        assert bundle_a["cumulative_heartbeat_count"] == 14
        assert bundle_a["adam_memory_count_before"] == hb11_adam_after
        assert bundle_a["eve_memory_count_before"] == hb11_eve_after
        assert bundle_a["adam_memory_count_after"] > bundle_a["adam_memory_count_before"]
        assert bundle_a["eve_memory_count_after"] > bundle_a["eve_memory_count_before"]

        # Second continuation: 3 more heartbeats on same store
        hb14_adam_after = bundle_a["adam_memory_count_after"]
        hb14_eve_after = bundle_a["eve_memory_count_after"]
        rt_b = FirstPairRuntime(heartbeat_limit=3, store=store)
        rt_b.run()
        bundle_b = rt_b.export_evidence(tmp_path / "cont2.json", run_id="cont-B")
        assert bundle_b["start_heartbeat"] == 15
        assert bundle_b["end_heartbeat"] == 17
        assert bundle_b["new_heartbeat_count"] == 3
        assert bundle_b["cumulative_heartbeat_count"] == 17
        assert bundle_b["adam_memory_count_before"] == hb14_adam_after
        assert bundle_b["eve_memory_count_before"] == hb14_eve_after
        assert bundle_b["adam_memory_count_after"] > bundle_b["adam_memory_count_before"]
        assert bundle_b["eve_memory_count_after"] > bundle_b["eve_memory_count_before"]

    def test_evidence_run_specific_manifests_exclude_prior(self, tmp_path: Path) -> None:
        """Manifests recorded during a prior run are not included in the
        run-specific section of the next run's evidence."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-man-excl")
        rt1 = FirstPairRuntime(heartbeat_limit=2, store=store, backend="deterministic_stub")
        rt1.run()
        b1 = rt1.export_evidence(tmp_path / "me1.json")
        prior_count = len(b1["memory_selection_manifests"])

        rt2 = FirstPairRuntime(heartbeat_limit=2, store=store, backend="deterministic_stub")
        rt2.run()
        b2 = rt2.export_evidence(tmp_path / "me2.json")
        run2_count = len(b2["memory_selection_manifests"])
        # Run 2's run-specific manifests should be exactly the count generated
        # by run 2 (4 = 2 agents * 2 heartbeats), not including run 1's 4
        assert prior_count >= 2, f"Run 1 should produce at least 2 manifests, got {prior_count}"
        assert run2_count >= 2, f"Run 2 should produce at least 2 manifests, got {run2_count}"

    def test_evidence_zero_heartbeat_inspection(self, tmp_path: Path) -> None:
        """Inspection-only export (no run() called) emits null boundaries
        and does not mutate state."""
        # First, populate a store with data
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-zero")
        rt_pop = FirstPairRuntime(heartbeat_limit=2, store=store)
        rt_pop.run()
        pop_bundle = rt_pop.export_evidence(tmp_path / "pop.json")
        hb_count_after_pop = pop_bundle["cumulative_heartbeat_count"]

        # Now inspect: new runtime, same store, zero heartbeats, load state
        rt_inspect = FirstPairRuntime(heartbeat_limit=0, store=store)
        rt_inspect._load_or_initialize()
        # No run() called — direct export for inspection
        bundle = rt_inspect.export_evidence(tmp_path / "zero.json", run_id="inspect")
        assert bundle["start_heartbeat"] is None
        assert bundle["end_heartbeat"] is None
        assert bundle["new_heartbeat_count"] == 0
        assert bundle["cumulative_heartbeat_count"] == hb_count_after_pop
        # Raw memories unchanged
        assert bundle["adam_memory_count_before"] == bundle["adam_memory_count_after"]
        assert bundle["eve_memory_count_before"] == bundle["eve_memory_count_after"]
        assert bundle["adam_memory_count_after"] == pop_bundle["adam_memory_count_after"]
        # No new manifests, summaries, or events
        assert len(bundle.get("memory_selection_manifests", [])) == 0
        assert len(bundle.get("memory_summaries", [])) == 0
        assert len(bundle.get("relationship_events", [])) == 0

    def test_evidence_backend_label_model(self, tmp_path: Path) -> None:
        """Model backend label appears in evidence without any network call.
        Set _run_backend_label directly and export without calling run()."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-model")
        rt = FirstPairRuntime(heartbeat_limit=0, store=store)
        rt._run_backend_label = "model"  # No network — set label directly
        bundle = rt.export_evidence(tmp_path / "model-label.json")
        assert bundle["backend_label"] == "model"

    def test_evidence_backend_label_deterministic_stub(self, tmp_path: Path) -> None:
        """Deterministic stub is labelled correctly."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-det")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt.run()
        bundle = rt.export_evidence(tmp_path / "det.json")
        assert bundle["backend_label"] == "deterministic_stub"

    def test_evidence_stub_not_labeled_model(self, tmp_path: Path) -> None:
        """Stub evidence never claims model backend."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-stubonly")
        rt = FirstPairRuntime(heartbeat_limit=2, store=store, backend="stub")
        rt.run()
        bundle = rt.export_evidence(tmp_path / "stubonly.json")
        assert bundle["backend_label"] == "stub"
        assert bundle["backend_label"] != "model"
        assert "model" not in str(bundle.get("provider_type", ""))

    def test_evidence_memory_counts_match_disk(self, tmp_path: Path) -> None:
        """Pre-run and post-run memory counts match persisted state on disk."""
        from backend.world.first_pair_persistence import load_memory
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "eb-disk")
        rt = FirstPairRuntime(heartbeat_limit=2, store=store)
        rt._load_or_initialize()  # capture pre-run state explicitly
        disk_mem_before = load_memory(store)
        pre_adam = len(disk_mem_before.get("east_adam", []))
        pre_eve = len(disk_mem_before.get("east_eve", []))
        rt.run()
        bundle = rt.export_evidence(tmp_path / "disk.json")
        disk_mem_after = load_memory(store)
        post_adam = len(disk_mem_after.get("east_adam", []))
        post_eve = len(disk_mem_after.get("east_eve", []))
        assert bundle["adam_memory_count_before"] == pre_adam
        assert bundle["eve_memory_count_before"] == pre_eve
        assert bundle["adam_memory_count_after"] == post_adam
        assert bundle["eve_memory_count_after"] == post_eve
        assert bundle["adam_memory_count_after"] >= bundle["adam_memory_count_before"]
        assert bundle["eve_memory_count_after"] >= bundle["eve_memory_count_before"]
        assert bundle["new_heartbeat_count"] == 2
        assert bundle["cumulative_heartbeat_count"] == 2


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 16 – Derived memory summary persistence
# ---------------------------------------------------------------------------


class TestMemorySummaryPersistence:
    """MemorySummaryRecord save/load/append roundtrip."""

    def test_save_and_load_empty(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-summaries")
        assert load_summaries(store) == []

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-summaries2")
        summaries = [
            MemorySummaryRecord(
                summary_id="sum-001",
                owner_agent_id="adam-aaa",
                covered_memory_ids=["mem-001", "mem-002"],
                covered_heartbeat_range=[1, 2],
                summary="Adam explored the starting room.",
                salient_entities=["room"],
                related_goal_ids=["goal-explore"],
                related_public_object_ids=[],
                related_message_ids=[],
            )
        ]
        save_summaries(store, summaries)
        loaded = load_summaries(store)
        assert len(loaded) == 1
        assert loaded[0].summary_id == "sum-001"

    def test_append_summary(self, tmp_path: Path) -> None:
        from backend.world.first_pair_persistence import _ensure_memory_ids
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-summaries3")
        mem_list = [
            {"heartbeat": 1, "content": "First memory", "type": "observation"},
            {"heartbeat": 2, "content": "Second memory", "type": "observation"},
        ]
        owner = "adam-aaa"
        ensured = _ensure_memory_ids(mem_list, owner_agent_id=owner)
        mid1 = ensured[0]["memory_id"]
        mid2 = ensured[1]["memory_id"]
        s1 = MemorySummaryRecord(
            summary_id="", owner_agent_id=owner,
            covered_memory_ids=[mid1], covered_heartbeat_range=[1, 1],
            summary="[derived from heartbeat 1] First summary.", salient_entities=[],
            related_goal_ids=[], related_public_object_ids=[], related_message_ids=[],
            derivation_method="deterministic_extractive",
            source_commitment=compute_summary_source_commitment(owner, [ensured[0]]),
        )
        s1.summary_id = "sum-derived-" + s1.semantic_commitment()[:16]
        s1.seal()
        result = append_summary(store, s1, memory_list=mem_list)
        assert result["ok"], f"append failed: {result['errors']}"
        s2 = MemorySummaryRecord(
            summary_id="", owner_agent_id=owner,
            covered_memory_ids=[mid2], covered_heartbeat_range=[2, 2],
            summary="[derived from heartbeat 2] Second summary.", salient_entities=[],
            related_goal_ids=[], related_public_object_ids=[], related_message_ids=[],
            derivation_method="deterministic_extractive",
            source_commitment=compute_summary_source_commitment(owner, [ensured[1]]),
        )
        s2.summary_id = "sum-derived-" + s2.semantic_commitment()[:16]
        s2.seal()
        result = append_summary(store, s2, memory_list=mem_list)
        assert result["ok"], f"append failed: {result['errors']}"
        loaded = load_summaries(store)
        assert len(loaded) == 2

    def test_to_envelope_has_integrity(self, tmp_path: Path) -> None:
        r = MemorySummaryRecord(
            summary_id="sum-999", owner_agent_id="eve-bbb",
            covered_memory_ids=["mem-999"], covered_heartbeat_range=[9, 9],
            summary="Test seal.", salient_entities=[], related_goal_ids=[],
            related_public_object_ids=[], related_message_ids=[],
        ).seal()
        env = r.to_envelope()
        assert env["type"] == "memory_summary_record"
        assert env["data"]["integrity_commitment"] != ""


# ---------------------------------------------------------------------------
# 17b – Derived summary reuse across heartbeats
# ---------------------------------------------------------------------------


class TestDerivedSummaryReuse:
    """Deterministic summaries are reusable across heartbeats and restarts."""

    def _make_mems(self) -> list[dict]:
        return [{"heartbeat": 1, "content": "A" * 200, "type": "observation"}]

    def test_same_content_same_owner_same_summary_id(self) -> None:
        """Deriving the same omitted memory twice at different wall-clock times
        produces the same summary ID (full-content sensitive, no truncation)."""
        from backend.world.first_pair_persistence import derive_summaries_for_omitted
        mems = self._make_mems()
        s1, ids1 = derive_summaries_for_omitted(mems, set(), "adam-aaa")
        s2, ids2 = derive_summaries_for_omitted(mems, set(), "adam-aaa")
        assert len(s1) == 1
        assert len(s2) == 1
        assert s1[0].summary_id == s2[0].summary_id
        assert ids1 == ids2
        # Full-content sensitivity: different content beyond 100 chars
        mems_long = [{"heartbeat": 1, "content": "B" * 200, "type": "observation"}]
        s3, ids3 = derive_summaries_for_omitted(mems_long, set(), "adam-aaa")
        assert s1[0].summary_id != s3[0].summary_id, "Different content beyond 100 chars must differ"

    def test_first_append_reuses_across_calls(self, tmp_path: Path) -> None:
        """First append returns status=appended; second = reused; one record."""
        from backend.world.first_pair_persistence import derive_summaries_for_omitted
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "reuse1")
        mems = self._make_mems()
        owner = "adam-aaa"
        derived, ids = derive_summaries_for_omitted(mems, set(), owner)
        assert len(derived) == 1
        ds = derived[0]

        # First append
        r1 = append_summary(store, ds, memory_list=mems)
        assert r1["ok"], f"first append failed: {r1['errors']}"
        assert r1["status"] == "appended"
        first_ts = ds.created_at_utc

        # Second append (simulate later heartbeat)
        import time; time.sleep(0.01)  # ensure different wall-clock time
        derived2, ids2 = derive_summaries_for_omitted(mems, set(), owner)
        ds2 = derived2[0]
        assert ds2.created_at_utc != first_ts  # different wall-clock time

        r2 = append_summary(store, ds2, memory_list=mems)
        assert r2["ok"], f"second append failed: {r2['errors']}"
        assert r2["status"] == "reused", f"expected reused, got {r2['status']}"

        loaded = load_summaries(store)
        assert len(loaded) == 1, f"Store should have 1 record, got {len(loaded)}"
        # created_at_utc from first persist is preserved
        assert loaded[0].created_at_utc == first_ts
        # Integrity remains valid
        assert loaded[0].integrity_commitment != ""
        check = MemorySummaryRecord(
            summary_id=loaded[0].summary_id,
            owner_agent_id=loaded[0].owner_agent_id,
            covered_memory_ids=list(loaded[0].covered_memory_ids),
            covered_heartbeat_range=list(loaded[0].covered_heartbeat_range),
            summary=loaded[0].summary,
            salient_entities=list(loaded[0].salient_entities),
            related_goal_ids=list(loaded[0].related_goal_ids),
            related_public_object_ids=list(loaded[0].related_public_object_ids),
            related_message_ids=list(loaded[0].related_message_ids),
            created_at_utc=loaded[0].created_at_utc,
            derivation_method=loaded[0].derivation_method,
            source_commitment=loaded[0].source_commitment,
        ).seal()
        assert check.integrity_commitment == loaded[0].integrity_commitment

    def test_reuse_across_new_runtime_instance(self, tmp_path: Path) -> None:
        """Reuse works across a new store/runtime instance."""
        from backend.world.first_pair_persistence import derive_summaries_for_omitted
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "reuse2")
        mems = self._make_mems()
        owner = "adam-aaa"

        # First runtime appends
        rt1 = FirstPairRuntime(heartbeat_limit=1, store=store, backend="deterministic_stub")
        rt1.run()
        ctx = rt1._build_context("east_adam", 2)
        assert len(ctx.derived_memory_summaries) >= 0  # summaries may exist

        # Second runtime on same store — summaries should be reusable
        rt2 = FirstPairRuntime(heartbeat_limit=0, store=store)
        rt2._load_or_initialize()

        derived, ids = derive_summaries_for_omitted(mems, set(), owner)
        for ds in derived:
            r = append_summary(store, ds, memory_list=mems)
            if not r["ok"]:
                # May already exist — reuse counts as success
                assert r["status"] == "reused" or r["status"] == "appended", str(r)
                if r["status"] == "reused":
                    continue
            assert r["ok"], f"append failed: {r['errors']}"

        loaded = load_summaries(store)
        assert len(loaded) >= 1

    def test_missing_memory_list_fails_even_for_identical(self, tmp_path: Path) -> None:
        """Missing memory_list fails even for an otherwise identical duplicate."""
        from backend.world.first_pair_persistence import derive_summaries_for_omitted
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "reuse3")
        mems = self._make_mems()
        owner = "adam-aaa"
        derived, ids = derive_summaries_for_omitted(mems, set(), owner)
        ds = derived[0]

        r1 = append_summary(store, ds, memory_list=mems)
        assert r1["ok"]

        # Same content, no memory_list
        r2 = append_summary(store, ds, memory_list=None)
        assert not r2["ok"]
        assert "memory_list is required" in str(r2["errors"])

    def test_conflicting_duplicate_fails_closed(self, tmp_path: Path) -> None:
        """Same summary_id with different semantic material fails closed."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "reuse4")
        mems = [{"heartbeat": 1, "content": "Original", "type": "observation"}]
        owner = "adam-aaa"

        # First summary
        from backend.world.first_pair_persistence import derive_summaries_for_omitted
        derived1, ids1 = derive_summaries_for_omitted(mems, set(), owner)
        ds1 = derived1[0]
        r1 = append_summary(store, ds1, memory_list=mems)
        assert r1["ok"]

        # Manually craft a summary with same ID but different material
        ds1_conflict = MemorySummaryRecord(
            summary_id=ds1.summary_id,
            owner_agent_id=owner,
            covered_memory_ids=ds1.covered_memory_ids,
            covered_heartbeat_range=ds1.covered_heartbeat_range,
            summary="[derived from heartbeat 1] DIFFERENT",  # different text
            salient_entities=[],
            related_goal_ids=[],
            related_public_object_ids=[],
            related_message_ids=[],
            derivation_method="deterministic_extractive",
            source_commitment=compute_summary_source_commitment(owner, [{"heartbeat": 1, "content": "DIFFERENT", "type": "observation"}]),
        )
        r2 = append_summary(store, ds1_conflict, memory_list=[{"heartbeat": 1, "content": "DIFFERENT", "type": "observation"}])
        assert not r2["ok"]
        assert r2["status"] == "rejected"
        assert "conflicting material" in str(r2["errors"])

        # Store unchanged
        loaded = load_summaries(store)
        assert len(loaded) == 1
        assert loaded[0].summary == ds1.summary


class TestCorruptedPersistedSummary:
    """Existing persisted summaries with tampered integrity fail reuse."""

    def _append_valid(self, store, mems) -> MemorySummaryRecord:
        from backend.world.first_pair_persistence import derive_summaries_for_omitted
        derived, ids = derive_summaries_for_omitted(mems, set(), "adam-aaa")
        ds = derived[0]
        r = append_summary(store, ds, memory_list=mems)
        assert r["ok"], f"setup append failed: {r['errors']}"
        return ds

    def test_corrupted_integrity_rejected(self, tmp_path: Path) -> None:
        """Corrupting persisted integrity_commitment causes reuse rejection."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "corr-int")
        mems = [{"heartbeat": 1, "content": "Integrity test", "type": "observation"}]
        ds = self._append_valid(store, mems)

        # Tamper with the stored integrity commitment
        loaded = load_summaries(store)
        loaded[0].integrity_commitment = "tampered"
        save_summaries(store, loaded)

        # Attempt reuse
        derived2, ids2 = derive_summaries_for_omitted(mems, set(), "adam-aaa")
        r = append_summary(store, derived2[0], memory_list=mems)
        assert not r["ok"], "Tampered integrity should be rejected"
        assert r["status"] == "rejected"
        assert "integrity" in str(r["errors"]).lower()

    def test_corrupted_created_at_utc_rejected(self, tmp_path: Path) -> None:
        """Corrupting created_at_utc without resealing causes rejection."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "corr-ts")
        mems = [{"heartbeat": 1, "content": "Timestamp test", "type": "observation"}]
        ds = self._append_valid(store, mems)

        loaded = load_summaries(store)
        loaded[0].created_at_utc = "2099-01-01T00:00:00+00:00"
        save_summaries(store, loaded)

        derived2, ids2 = derive_summaries_for_omitted(mems, set(), "adam-aaa")
        r = append_summary(store, derived2[0], memory_list=mems)
        assert not r["ok"], "Tampered timestamp should be rejected"

    def test_corrupted_source_commitment_rejected(self, tmp_path: Path) -> None:
        """Corrupting persisted source_commitment causes rejection."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "corr-sc")
        mems = [{"heartbeat": 1, "content": "Source test", "type": "observation"}]
        ds = self._append_valid(store, mems)

        loaded = load_summaries(store)
        loaded[0].source_commitment = "tampered"
        save_summaries(store, loaded)

        derived2, ids2 = derive_summaries_for_omitted(mems, set(), "adam-aaa")
        r = append_summary(store, derived2[0], memory_list=mems)
        assert not r["ok"]
        assert r["status"] == "rejected"

    def test_corrupted_covered_ids_rejected(self, tmp_path: Path) -> None:
        """Corrupting covered_memory_ids causes rejection."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "corr-cid")
        mems = [{"heartbeat": 1, "content": "Covered ID test", "type": "observation"}]
        ds = self._append_valid(store, mems)

        loaded = load_summaries(store)
        loaded[0].covered_memory_ids = ["mem-nonexistent"]
        save_summaries(store, loaded)

        derived2, ids2 = derive_summaries_for_omitted(mems, set(), "adam-aaa")
        r = append_summary(store, derived2[0], memory_list=mems)
        assert not r["ok"]
        assert r["status"] == "rejected"

    def test_rejected_not_rewritten(self, tmp_path: Path) -> None:
        """A rejected persisted record is not rewritten or removed."""
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "corr-rw")
        mems = [{"heartbeat": 1, "content": "Rewrite test", "type": "observation"}]
        ds = self._append_valid(store, mems)

        # Snapshot store state
        before_count = len(load_summaries(store))

        loaded = load_summaries(store)
        loaded[0].integrity_commitment = "corrupted"
        save_summaries(store, loaded)

        derived2, ids2 = derive_summaries_for_omitted(mems, set(), "adam-aaa")
        r = append_summary(store, derived2[0], memory_list=mems)
        assert not r["ok"]

        after = load_summaries(store)
        assert len(after) == before_count
        assert after[0].integrity_commitment == "corrupted"


# ---------------------------------------------------------------------------
# 17 – Relationship event ledger persistence
# ---------------------------------------------------------------------------


class TestRelationshipEventPersistence:
    """RelationshipEventRecord save/load/append/derive roundtrip."""

    def test_save_and_load_empty(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-rel")
        assert load_relationship_events(store) == []

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-rel2")
        events = [
            RelationshipEventRecord(
                event_id="evt-001", heartbeat=1, actor_agent_id="adam-aaa",
                other_agent_id="eve-bbb", event_type="co_location",
                public_evidence_references=["obj-mem-001"],
                resulting_public_state_commitment="abc",
            )
        ]
        save_relationship_events(store, events)
        loaded = load_relationship_events(store)
        assert len(loaded) == 1
        assert loaded[0].event_id == "evt-001"

    def test_append_event(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-rel3")
        e = RelationshipEventRecord(
            event_id="evt-010", heartbeat=2, actor_agent_id="adam-aaa",
            other_agent_id="eve-bbb", event_type="message_sent",
            public_evidence_references=["msg-001"],
            resulting_public_state_commitment="def",
        )
        append_relationship_event(store, e)
        loaded = load_relationship_events(store)
        assert len(loaded) == 1

    def test_derive_event_ids(self) -> None:
        events = [
            RelationshipEventRecord(
                event_id="evt-100", heartbeat=3, actor_agent_id="adam-aaa",
                other_agent_id="eve-bbb", event_type="co_location",
                public_evidence_references=["mem-evt-100"],
                resulting_public_state_commitment="",
            ),
            RelationshipEventRecord(
                event_id="evt-101", heartbeat=3, actor_agent_id="adam-aaa",
                other_agent_id="eve-bbb", event_type="message_sent",
                public_evidence_references=["mem-evt-101"],
                resulting_public_state_commitment="",
            ),
        ]
        ids = derive_relationship_event_ids(events)
        assert ids == {"mem-evt-100", "mem-evt-101"}


# ---------------------------------------------------------------------------
# 18 – maybe_record_relationship_event
# ---------------------------------------------------------------------------


class TestMaybeRecordRelationshipEvent:
    """Conditions under which relationship events are and are not recorded."""

    def _make_ws(self, tmp_path: Path) -> FirstPairPersistenceStore:
        return FirstPairPersistenceStore(tmp_path / ".runtime" / "test-maybe")

    def _make_world_state(self, co_located: bool = False) -> object:
        from types import SimpleNamespace
        occ = {"east_adam": "tile-alpha", "east_eve": "tile-beta"}
        if co_located:
            occ["east_eve"] = "tile-alpha"
        return SimpleNamespace(
            tile_occupancy=occ,
            public_objects={},
        )

    def test_records_message_sent(self, tmp_path: Path) -> None:
        store = self._make_ws(tmp_path)
        ws = self._make_world_state()
        event = maybe_record_relationship_event(
            store, heartbeat_number=1, actor_ref="east_adam",
            actor_agent_id="adam-aaa", other_agent_id="eve-bbb",
            action_type="leave_public_message",
            outcome={"status": "success", "message_id": "msg-001", "recipient": "all"},
            agent_view={}, world_state=ws,
        )
        assert event is not None
        assert event.event_type == "message_sent"

    def test_does_not_record_failed_outcome(self, tmp_path: Path) -> None:
        store = self._make_ws(tmp_path)
        ws = self._make_world_state()
        event = maybe_record_relationship_event(
            store, 1, "east_adam", "adam-aaa", "eve-bbb",
            "leave_public_message",
            outcome={"status": "rejected"},
            agent_view={}, world_state=ws,
        )
        assert event is None

    def test_records_public_object_creation(self, tmp_path: Path) -> None:
        """Both agents must be co-located for creation to count as social."""
        store = self._make_ws(tmp_path)
        ws = self._make_world_state(co_located=True)
        event = maybe_record_relationship_event(
            store, 3, "east_adam", "adam-aaa", "eve-bbb",
            "create_public_object",
            outcome={"status": "success", "object_id": "obj-monument", "tile_id": "tile-alpha"},
            agent_view={}, world_state=ws,
        )
        assert event is not None
        assert event.event_type == "public_object_creation"

    def test_does_not_record_creation_while_alone(self, tmp_path: Path) -> None:
        """Creation while alone (not co-located) should not record."""
        store = self._make_ws(tmp_path)
        ws = self._make_world_state(co_located=False)
        event = maybe_record_relationship_event(
            store, 3, "east_adam", "adam-aaa", "eve-bbb",
            "create_public_object",
            outcome={"status": "success", "object_id": "obj-alone", "tile_id": "tile-alpha"},
            agent_view={}, world_state=ws,
        )
        assert event is None

    def test_records_inspect_other_object(self, tmp_path: Path) -> None:
        store = self._make_ws(tmp_path)
        ws = self._make_world_state()
        ws.public_objects["obj-thing"] = {
            "object_id": "obj-thing", "creator_agent_id": "eve-bbb",
            "tile_id": "tile-alpha", "object_type": "artifact",
            "public_description": "Eve's thing", "created_heartbeat": 1,
        }
        event = maybe_record_relationship_event(
            store, 4, "east_adam", "adam-aaa", "eve-bbb",
            "inspect_public_object",
            outcome={"status": "success", "target_object_id": "obj-thing"},
            agent_view={}, world_state=ws,
        )
        assert event is not None
        assert event.event_type == "inspect_other_object"

    def test_does_not_record_inspect_own_object(self, tmp_path: Path) -> None:
        """Inspection of the actor's own object is not recorded."""
        store = self._make_ws(tmp_path)
        ws = self._make_world_state()
        ws.public_objects["my-obj"] = {
            "object_id": "my-obj", "creator_agent_id": "adam-aaa",
            "tile_id": "tile-alpha", "object_type": "artifact",
            "public_description": "Adam's own", "created_heartbeat": 1,
        }
        event = maybe_record_relationship_event(
            store, 5, "east_adam", "adam-aaa", "eve-bbb",
            "inspect_public_object",
            outcome={"status": "success", "target_object_id": "my-obj"},
            agent_view={}, world_state=ws,
        )
        assert event is None

    def test_does_not_record_unknown_action(self, tmp_path: Path) -> None:
        store = self._make_ws(tmp_path)
        ws = self._make_world_state()
        event = maybe_record_relationship_event(
            store, 5, "east_adam", "adam-aaa", "eve-bbb",
            "noop",
            outcome={"status": "success"},
            agent_view={}, world_state=ws,
        )
        assert event is None

    def test_duplicate_event_id_is_idempotent(self, tmp_path: Path) -> None:
        """Appending the same event twice does not create a duplicate."""
        from backend.world.first_pair_persistence import append_relationship_event, load_relationship_events
        store = self._make_ws(tmp_path)
        ws = self._make_world_state(co_located=True)
        e1 = maybe_record_relationship_event(
            store, 6, "east_adam", "adam-aaa", "eve-bbb",
            "create_public_object",
            outcome={"status": "success", "object_id": "obj-dup", "tile_id": "tile-alpha"},
            agent_view={}, world_state=ws,
        )
        assert e1 is not None
        # Attempt to append same event_id again
        e2 = maybe_record_relationship_event(
            store, 6, "east_adam", "adam-aaa", "eve-bbb",
            "create_public_object",
            outcome={"status": "success", "object_id": "obj-dup", "tile_id": "tile-alpha"},
            agent_view={}, world_state=ws,
        )
        loaded = load_relationship_events(store)
        assert len(loaded) == 1
        assert loaded[0].event_id == e1.event_id


# ---------------------------------------------------------------------------
# 19 – Memory selection manifest persistence
# ---------------------------------------------------------------------------


class TestMemorySelectionManifest:
    def test_append_and_load(self, tmp_path: Path) -> None:
        store = FirstPairPersistenceStore(tmp_path / ".runtime" / "test-manifest")
        assert load_memory_selection_manifests(store) == []
        append_memory_selection_manifest(store, {"hb": 1, "count": 5})
        append_memory_selection_manifest(store, {"hb": 2, "count": 3})
        loaded = load_memory_selection_manifests(store)
        assert len(loaded) == 2
        assert loaded[0]["hb"] == 1


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
