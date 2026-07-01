"""10T verifier: claim/evidence consistency tests.

Verifies that the required evidence category matches the claim_scope.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_verifier import verify_candidate_event
from backend.world.world_event_ledger import validate_event


def make_event(**overrides) -> dict:
    """Produce a valid minimal event dict."""
    event = {
        "event_id": "evt_10t_con_001",
        "schema_version": "10T.1",
        "tick": 15,
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
    # Only run validate_event check if there's a chance it passes
    # (some test events intentionally fail schema)
    return event


def test_observed_missing_valid_evidence():
    """observed scope with evidence that has no observed/action/artifact/territory category → blocking."""
    candidate = make_event(
        event_id="evt_con_observed_001",
        claim_scope="observed",
        evidence_refs=[{"category": "agent_memory", "ref": "mem1"}],
    )
    # Ensure event passes schema
    assert validate_event(candidate)["ok"]
    result = verify_candidate_event(candidate, [])
    assert not result["accepted"]
    assert any("consistency" in e and "observed" in e for e in result["errors"])


def test_speech_missing_agent_speech():
    """speech scope without agent_speech evidence → blocking."""
    candidate = make_event(
        event_id="evt_con_speech_001",
        action_type="whisper",
        claim_scope="speech",
        evidence_refs=[{"category": "agent_memory", "ref": "mem1"}],
    )
    assert validate_event(candidate)["ok"]
    result = verify_candidate_event(candidate, [])
    assert not result["accepted"]
    assert any("consistency" in e and "speech" in e for e in result["errors"])


def test_memory_missing_agent_memory():
    """memory scope without agent_memory evidence → blocking."""
    candidate = make_event(
        event_id="evt_con_memory_001",
        claim_scope="memory",
        evidence_refs=[{"category": "agent_speech", "ref": "whisper"}],
    )
    assert validate_event(candidate)["ok"]
    result = verify_candidate_event(candidate, [])
    assert not result["accepted"]
    assert any("consistency" in e and "memory" in e for e in result["errors"])


def test_operator_proof_missing_operator_proof():
    """operator_proof scope without operator_proof evidence → blocking."""
    candidate = make_event(
        event_id="evt_con_op_001",
        claim_scope="operator_proof",
        evidence_refs=[{"category": "agent_action", "ref": "commit.abc"}],
    )
    assert validate_event(candidate)["ok"]
    result = verify_candidate_event(candidate, [])
    assert not result["accepted"]
    assert any("consistency" in e and "operator_proof" in e for e in result["errors"])


def test_hypothesis_with_observed_world_fact():
    """hypothesis scope with observed_world_fact evidence → blocking."""
    candidate = make_event(
        event_id="evt_con_hypothesis_001",
        claim_scope="hypothesis",
        evidence_refs=[{"category": "observed_world_fact", "ref": "world.observe.water"}],
    )
    assert validate_event(candidate)["ok"]
    result = verify_candidate_event(candidate, [])
    assert not result["accepted"]
    assert any("consistency" in e and "hypothesis" in e for e in result["errors"])


def test_hypothesis_with_non_observed_evidence():
    """hypothesis with non-observed evidence → passes."""
    candidate = make_event(
        event_id="evt_con_hypothesis_002",
        claim_scope="hypothesis",
        evidence_refs=[{"category": "agent_memory", "ref": "mem1"}],
    )
    assert validate_event(candidate)["ok"]
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]


def test_unknown_scope_has_no_consistency_rule():
    """unknown claim_scope → no consistency rule applied, passes."""
    candidate = make_event(
        event_id="evt_con_unknown_001",
        claim_scope="unknown",
        evidence_refs=[],
    )
    assert validate_event(candidate)["ok"]
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]


def test_observed_with_correct_evidence_passes():
    """observed with observed_world_fact → passes consistency."""
    candidate = make_event(
        event_id="evt_con_observed_002",
        claim_scope="observed",
        evidence_refs=[{"category": "observed_world_fact", "ref": "world.observe.water"}],
    )
    result = verify_candidate_event(candidate, [])
    assert result["accepted"]