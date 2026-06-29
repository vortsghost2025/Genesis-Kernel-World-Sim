import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_ledger import validate_event


def valid_event(**overrides):
    event = {
        "event_id": "evt_10k_schema_001",
        "schema_version": "10K.1",
        "tick": 1,
        "timestamp_utc": None,
        "actor_id": "east_adam",
        "lens": "east",
        "territory_ref": None,
        "action_type": "observe",
        "summary": "East Adam observed the current world snapshot.",
        "evidence_refs": [
            {
                "category": "observed_world_fact",
                "ref": "world.observe.resources.water",
                "quote": "water is 0.0",
            }
        ],
        "claim_scope": "observed",
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


def test_valid_minimal_observed_event_passes():
    result = validate_event(valid_event())

    assert result == {"ok": True, "errors": []}


def test_required_fields_are_validated():
    for field in [
        "event_id",
        "schema_version",
        "actor_id",
        "lens",
        "territory_ref",
        "action_type",
        "summary",
        "evidence_refs",
        "claim_scope",
        "affected_agents",
        "artifacts_created_or_changed",
        "relationship_delta",
        "consequence",
        "verification_status",
    ]:
        event = valid_event()
        event.pop(field)

        assert_invalid(event, f"missing required field: {field}")


def test_requires_tick_or_timestamp_utc():
    assert_invalid(valid_event(tick=None, timestamp_utc=None), "requires tick or timestamp_utc")


def test_claim_scope_and_evidence_category_are_validated():
    assert_invalid(valid_event(claim_scope="provider_truth"), "invalid claim_scope")


    event = valid_event(
        evidence_refs=[{"category": "provider_response", "ref": "provider.raw", "quote": "model said so"}]
    )
    assert_invalid(event, "invalid evidence category")


def test_mutation_events_require_before_and_after_refs():
    missing_after = valid_event(
        action_type="gather",
        summary="East Adam gathered available food from a temp copy.",
        evidence_refs=[{"category": "agent_action", "ref": "execute_action.gather"}],
        before_ref="md5:before",
        after_ref=None,
    )
    assert_invalid(missing_after, "mutation event requires before_ref and after_ref")

    valid_mutation = valid_event(
        action_type="gather",
        summary="East Adam gathered available food from a temp copy.",
        evidence_refs=[{"category": "agent_action", "ref": "execute_action.gather"}],
        before_ref="md5:before",
        after_ref="md5:after",
    )
    assert validate_event(valid_mutation) == {"ok": True, "errors": []}
