import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_ledger import validate_event


def valid_event(**overrides):
    event = {
        "event_id": "evt_10k_boundary_001",
        "schema_version": "10K.1",
        "tick": 12,
        "timestamp_utc": None,
        "actor_id": "east_adam",
        "lens": "east",
        "territory_ref": None,
        "action_type": "goal",
        "summary": "East Adam set a goal to verify whether a hidden water source exists.",
        "evidence_refs": [{"category": "agent_action", "ref": "decision.goal"}],
        "claim_scope": "hypothesis",
        "before_ref": None,
        "after_ref": None,
        "affected_agents": ["east_adam"],
        "artifacts_created_or_changed": [],
        "relationship_delta": None,
        "consequence": None,
        "verification_status": "verified",
    }
    event.update(overrides)
    return event


def assert_invalid(event, fragment):
    result = validate_event(event)
    assert result["ok"] is False
    assert any(fragment in error for error in result["errors"])


def test_private_runtime_paths_are_rejected_as_evidence_refs():
    private_refs = [
        "kilo.jsonc",
        ".kilo/state/accepted-state-ledger.md",
        "world-sim/data/east_world_state.json",
        "world-sim/data/continuity/ACTIVE_STATE.md",
        "ACTIVE_STATE.md",
    ]

    for ref in private_refs:
        event = valid_event(evidence_refs=[{"category": "observed_world_fact", "ref": ref}])
        assert_invalid(event, "private/runtime path is not valid in-world evidence")


def test_hypotheses_about_hidden_water_are_not_observed_facts():
    event = valid_event(
        claim_scope="observed",
        summary="East Adam observed the hidden water source location.",
        evidence_refs=[{"category": "observed_world_fact", "ref": "memory.claim", "quote": "hidden water source"}],
    )

    assert_invalid(event, "hidden water claims must remain hypothesis")


def test_animal_movement_guidance_is_not_observed_without_evidence():
    event = valid_event(
        claim_scope="observed",
        summary="Dove and lamb movements are guiding Adam to water.",
        evidence_refs=[{"category": "observed_world_fact", "ref": "world.animals", "quote": "dove and lamb movements"}],
    )

    assert_invalid(event, "animal movement/guidance claims must remain hypothesis")


def test_speech_and_memory_are_distinct_from_observed_world_fact():
    speech_event = valid_event(
        action_type="whisper",
        summary="East Adam whispered a water concern to East Eve.",
        evidence_refs=[{"category": "agent_speech", "ref": "whisper:east_adam:east_eve"}],
        claim_scope="speech",
    )
    memory_event = valid_event(
        summary="East Eve remembered Adam's water concern.",
        evidence_refs=[{"category": "agent_memory", "ref": "memory:east_eve:water_concern"}],
        claim_scope="memory",
    )

    assert validate_event(speech_event) == {"ok": True, "errors": []}
    assert validate_event(memory_event) == {"ok": True, "errors": []}
