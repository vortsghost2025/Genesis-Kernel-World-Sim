"""10T verifier: duplicate detection tests.

Tests both exact event_id duplicates and logical
(tick + actor_id + action_type) duplicates.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_verifier import verify_candidate_event
from backend.world.world_event_ledger import validate_event


def make_event(**overrides) -> dict:
    """Produce a valid minimal event dict that passes validate_event."""
    event = {
        "event_id": "evt_10t_dup_001",
        "schema_version": "10T.1",
        "tick": 10,
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
    assert validate_event(event)["ok"], f"invalid event: {validate_event(event)['errors']}"
    return event


def test_exact_event_id_duplicate_rejected():
    """Same event_id as existing → blocking error."""
    existing = make_event()
    candidate = make_event(event_id="evt_10t_dup_001")  # same event_id
    result = verify_candidate_event(candidate, [existing])
    assert not result["accepted"]
    assert any("duplicate event_id" in e for e in result["errors"])


def test_logical_duplicate_rejected():
    """Same tick + actor_id + action_type → blocking error."""
    existing = make_event(event_id="evt_existing_001", tick=10)
    candidate = make_event(event_id="evt_candidate_001", tick=10)
    result = verify_candidate_event(candidate, [existing])
    assert not result["accepted"]
    assert any("duplicate: tick 10" in e for e in result["errors"])


def test_different_tick_is_not_duplicate():
    """Different tick → not a duplicate."""
    existing = make_event(event_id="evt_existing_002", tick=10)
    candidate = make_event(event_id="evt_candidate_002", tick=11)
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]


def test_different_actor_is_not_duplicate():
    """Same tick, different actor → not a duplicate."""
    existing = make_event(event_id="evt_existing_003", tick=10, actor_id="east_adam")
    candidate = make_event(event_id="evt_candidate_003", tick=10, actor_id="east_eve")
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]


def test_different_action_type_is_not_duplicate():
    """Same tick + actor, different action_type → not a duplicate."""
    existing = make_event(event_id="evt_existing_004", tick=10, action_type="observe")
    candidate = make_event(event_id="evt_candidate_004", tick=10, action_type="rest")
    result = verify_candidate_event(candidate, [existing])
    assert result["accepted"]


def test_duplicate_check_skipped_when_tick_is_none():
    """No tick provided → logical duplicate check is skipped (not a dead end)."""
    existing = make_event(event_id="evt_existing_005", tick=10, action_type="observe")
    candidate = make_event(
        event_id="evt_candidate_005", tick=None, action_type="observe", timestamp_utc="2026-01-01T00:00:00Z"
    )
    result = verify_candidate_event(candidate, [existing])
    # validate_event requires tick OR timestamp_utc, so tick=None is fine
    assert result["accepted"]