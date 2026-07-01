"""10T verifier: contradiction detection tests.

Contradiction = same territory, same "X is Y" entity,
different value. Only checked for observed scope.

All existing/candidate pairs use different ticks to avoid
triggering duplicate detection.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_verifier import verify_candidate_event
from backend.world.world_event_ledger import validate_event

_COUNTER = 100


def make_event(**overrides) -> dict:
    """Produce a valid minimal event dict."""
    global _COUNTER
    _COUNTER += 1
    event = {
        "event_id": f"evt_10t_con_{_COUNTER}",
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


def test_contradiction_same_entity_different_value():
    """Same entity 'water' asserted with different values → blocking error."""
    existing = make_event(summary="water is 0.0")
    candidate = make_event(summary="water is 5.0")
    result = verify_candidate_event(candidate, [existing])
    assert not result["accepted"]
    assert any("contradiction" in e for e in result["errors"])


def test_same_entity_same_value_not_contradiction():
    """Same entity, same value → no contradiction."""
    existing = make_event(summary="water is 0.0")
    candidate = make_event(summary="water is 0.0")
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]


def test_different_entity_not_contradiction():
    """Different entities → no contradiction even if values differ."""
    existing = make_event(summary="water is 0.0")
    candidate = make_event(summary="food is 5.0")
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]


def test_different_territory_not_contradiction():
    """Different territories → no contradiction."""
    existing = make_event(territory_ref="territoryA", summary="water is 0.0")
    candidate = make_event(territory_ref="territoryB", summary="water is 5.0")
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]


def test_non_observed_scope_skips_contradiction():
    """claim_scope != 'observed' → contradiction check skipped."""
    existing = make_event(summary="water is 0.0")
    candidate = make_event(
        summary="water is 5.0",
        claim_scope="speech",
        evidence_refs=[{"category": "agent_speech", "ref": "whisper"}],
    )
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]


def test_no_is_claim_skips_contradiction():
    """Summary without 'X is Y' pattern → no contradiction check."""
    existing = make_event(summary="water is 0.0")
    candidate = make_event(summary="Adam observed the area")
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]