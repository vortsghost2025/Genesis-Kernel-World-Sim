"""10T verifier: reference integrity tests.

Confirms that the verifier does NOT perform reference-integrity
cross-checks against event_id (deferred to a future phase because
before_ref/after_ref store md5 content hashes, not event_id UUIDs).

The verifier relies on validate_event to ensure before_ref/after_ref
are truthy for mutation action types.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_verifier import verify_candidate_event
from backend.world.world_event_ledger import validate_event

_COUNTER = 200


def valid_event(**overrides) -> dict:
    """Produce a valid minimal event dict that passes validate_event."""
    global _COUNTER
    _COUNTER += 1
    event = {
        "event_id": f"evt_10t_ref_{_COUNTER}",
        "schema_version": "10T.1",
        "tick": _COUNTER,
        "timestamp_utc": None,
        "actor_id": "east_adam",
        "lens": "east",
        "territory_ref": "territoryA",
        "action_type": "observe",
        "summary": "food is 0.5",
        "evidence_refs": [
            {"category": "observed_world_fact", "ref": "world.observe.food"}
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


def test_verifier_does_not_check_before_ref_against_event_ids():
    """before_ref with md5 content hash (not an event_id) passes.

    No reference-integrity cross-check happens at 10T scope.
    """
    # Build the existing event manually — non-mutation action_type so
    # before/after refs are not required.
    existing = valid_event(
        action_type="goal",
        summary="verify resources",
        evidence_refs=[{"category": "agent_action", "ref": "decision.goal"}],
        claim_scope="hypothesis",
    )
    # The candidate is a gather with md5 before/after refs.
    candidate = valid_event(
        action_type="gather",
        summary="gathered food",
        evidence_refs=[{"category": "agent_action", "ref": "execute_action.gather"}],
        before_ref="md5:abc123",
        after_ref="md5:def456",
    )
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]


def test_mutation_missing_after_ref_rejected_by_validate_event():
    """Mutation with before_ref but no after_ref → validate_event catches it.

    The candidate is built directly (not through valid_event) because
    it intentionally fails validate_event.
    """
    candidate = {
        "event_id": "evt_ref_bad_002",
        "schema_version": "10T.1",
        "tick": 210,
        "timestamp_utc": None,
        "actor_id": "east_adam",
        "lens": "east",
        "territory_ref": "territoryA",
        "action_type": "gather",
        "summary": "gathered food",
        "evidence_refs": [{"category": "agent_action", "ref": "execute_action.gather"}],
        "claim_scope": "observed",
        "before_ref": "md5:abc123",
        "after_ref": None,
        "affected_agents": ["east_adam"],
        "artifacts_created_or_changed": [],
        "relationship_delta": [],
        "consequence": "",
        "verification_status": "candidate",
    }
    schema_result = validate_event(candidate)
    assert not schema_result["ok"]
    assert any("before_ref and after_ref" in e for e in schema_result["errors"])


def test_mutation_missing_before_ref_rejected_by_validate_event():
    """Mutation with after_ref but no before_ref → validate_event catches it."""
    candidate = {
        "event_id": "evt_ref_bad_003",
        "schema_version": "10T.1",
        "tick": 211,
        "timestamp_utc": None,
        "actor_id": "east_adam",
        "lens": "east",
        "territory_ref": "territoryA",
        "action_type": "gather",
        "summary": "gathered food",
        "evidence_refs": [{"category": "agent_action", "ref": "execute_action.gather"}],
        "claim_scope": "observed",
        "before_ref": None,
        "after_ref": "md5:def456",
        "affected_agents": ["east_adam"],
        "artifacts_created_or_changed": [],
        "relationship_delta": [],
        "consequence": "",
        "verification_status": "candidate",
    }
    schema_result = validate_event(candidate)
    assert not schema_result["ok"]
    assert any("before_ref and after_ref" in e for e in schema_result["errors"])


def test_non_mutation_skips_before_after_validation():
    """Non-mutation action_type with empty before/after → passes."""
    candidate = valid_event(
        action_type="whisper",
        summary="hello",
        evidence_refs=[{"category": "agent_speech", "ref": "whisper"}],
        claim_scope="speech",
        before_ref="",
        after_ref="",
    )
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]