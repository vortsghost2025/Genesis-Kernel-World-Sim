"""10T verifier: end-to-end acceptance tests.

Tests that valid, non-duplicate, non-contradictory, consistent
candidates are accepted by the verifier.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_candidate_mapper import candidate_from_gather_result
from backend.world.world_event_verifier import verify_candidate_event
from backend.world.world_event_ledger import validate_event

_COUNTER = 300


def make_event(**overrides) -> dict:
    """Produce a valid minimal event dict that passes validate_event."""
    global _COUNTER
    _COUNTER += 1
    event = {
        "event_id": f"evt_10t_acc_{_COUNTER}",
        "schema_version": "10T.1",
        "tick": _COUNTER,
        "timestamp_utc": None,
        "actor_id": "east_adam",
        "lens": "east",
        "territory_ref": "territoryA",
        "action_type": "observe",
        "summary": "water is 0.0",
        "evidence_refs": [
            {"category": "observed_world_fact", "ref": "world.observe.water"}
        ],
        "claim_scope": "observed",
        "before_ref": None,
        "after_ref": None,
        "affected_agents": ["east_adam"],
        "artifacts_created_or_changed": [],
        "relationship_delta": [],
        "consequence": "",
        "verification_status": "candidate",
    }
    event.update(overrides)
    event.setdefault("tick", _COUNTER)
    assert validate_event(event)["ok"], f"invalid event: {validate_event(event)['errors']}"
    return event


def test_empty_ledger_accepts():
    """A valid candidate with no existing events → accepted."""
    candidate = make_event()
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]
    assert result["errors"] == []


def test_unrelated_existing_events_accepts():
    """Valid candidate with unrelated existing events → accepted."""
    existing = make_event(summary="food is 0.5")
    candidate = make_event()
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]
    assert result["errors"] == []


def test_accepts_speech_with_agent_speech():
    """speech scope with agent_speech + world_event evidence → accepted.

    Under the echo model (10AB) all whisper events require world_event
    provenance in addition to agent_speech evidence.
    """
    candidate = make_event(
        action_type="whisper",
        claim_scope="speech",
        summary="hello",
        evidence_refs=[
            {"category": "agent_speech", "ref": "whisper"},
            {"category": "world_event", "ref": "prior_event_id"},
        ],
    )
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]


def test_accepts_memory_with_agent_memory():
    """memory scope with agent_memory evidence → accepted."""
    candidate = make_event(
        claim_scope="memory",
        summary="remembered water is 0.0",
        evidence_refs=[{"category": "agent_memory", "ref": "mem1"}],
    )
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]


def test_accepts_hypothesis_without_observed():
    """hypothesis scope without observed_world_fact → accepted."""
    candidate = make_event(
        claim_scope="hypothesis",
        summary="maybe water is underground",
        evidence_refs=[{"category": "agent_memory", "ref": "mem1"}],
    )
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]


def test_accepts_operator_proof():
    """operator_proof scope with operator_proof evidence → accepted."""
    candidate = make_event(
        claim_scope="operator_proof",
        summary="commit abc123 verified",
        evidence_refs=[{"category": "operator_proof", "ref": "git:abc123"}],
    )
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]


def test_accepts_gather_mutation():
    """Mutation event with valid structure → accepted."""
    candidate = make_event(
        action_type="gather",
        summary="gathered food",
        evidence_refs=[{"category": "agent_action", "ref": "execute_action.gather"}],
        before_ref="md5:abc123",
        after_ref="md5:def456",
    )
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]


def test_return_shape_has_expected_keys():
    """Verify the return dict has all expected keys."""
    result = verify_candidate_event(make_event(), [])
    assert "accepted" in result
    assert "errors" in result
    assert "warnings" in result
    assert isinstance(result["accepted"], bool)
    assert isinstance(result["errors"], list)
    assert isinstance(result["warnings"], list)


def test_mapper_gather_accepted_by_verifier():
    """Integration: real 10L gather mapper output → 10T verifier accepts.

    Proves that the broadened ``observed`` allow set in the verifier
    (which includes ``agent_action``) matches what
    ``candidate_from_gather_result`` actually emits.
    """
    result = candidate_from_gather_result(
        actor_id="east_adam",
        action_text="gathered food",
        result={
            "ok": True,
            "before_md5": "abc123",
            "after_md5": "def456",
            "evidence_used": [{"category": "agent_action", "ref": "execute_action.gather"}],
            "territory_ref": "territoryA",
            "consequence": "",
        },
        tick=400,
    )
    assert result is not None, "mapper returned None — gather should be accepted"
    assert result["claim_scope"] == "observed"
    cats = {ev["category"] for ev in result["evidence_refs"]}
    assert "agent_action" in cats, f"expected agent_action in evidence, got {cats}"

    verdict = verify_candidate_event(result, [])
    assert verdict["accepted"], f"verifier rejected mapper output: {verdict['errors']}"