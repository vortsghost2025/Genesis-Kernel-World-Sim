from __future__ import annotations

import sys
import json
from pathlib import Path

# Set up project root import path (same as other tests)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# tests folder is under world-sim/tests, so parents[2] goes to world-sim
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_candidate_mapper import (
    candidate_from_observe_result,
    candidate_from_whisper_decision,
)
from backend.world.world_event_verifier import verify_candidate_event
from backend.world.world_event_ledger import read_events, append_event

# ---------------------------------------------------------------------------
# Helper factories (mirroring test_phase10aa)
# ---------------------------------------------------------------------------

def _make_observe_candidate(
    tick: int = 1,
    timestamp_utc: str = "2026-01-01T00:00:01Z",
) -> dict:
    """Build a minimal observe candidate for Adam (east_adam)."""
    actor_id = "east_adam"
    action_text = "observe water level"
    result = {
        "territory_ref": "territoryA",
        "evidence_used": [
            {"category": "observed_world_fact", "reference": "water_obs"}
        ],
    }
    return candidate_from_observe_result(
        actor_id,
        action_text,
        result,
        tick=tick,
        timestamp_utc=timestamp_utc,
    )


def _make_whisper_candidate(
    prior_event_id: str,
    tick: int = 2,
    timestamp_utc: str = "2026-01-01T00:00:02Z",
) -> dict:
    """Build a whisper candidate for Eve that references Adam's event."""
    actor_id = "east_eve"
    decision = {
        "content": "Eve mentions Adam's water observation",
        "evidence_used": [
            {"category": "agent_speech", "reference": "eve_whisper"},
            {"category": "world_event", "reference": prior_event_id},
        ],
    }
    return candidate_from_whisper_decision(
        actor_id,
        decision,
        target_resolved=True,
        target_actor_id="east_adam",
        tick=tick,
        timestamp_utc=timestamp_utc,
    )

# ---------------------------------------------------------------------------
# Test‑level helpers
# ---------------------------------------------------------------------------

def _append_valid_adam_event(ledger_path: Path) -> dict:
    """Create Adam's observe event, verify it passes, append and return the persisted event."""
    adam_candidate = _make_observe_candidate()
    # Verify against current (empty) ledger
    existing = read_events(ledger_path)
    verdict = verify_candidate_event(adam_candidate, existing)
    assert verdict["accepted"], f"Adam candidate was rejected: {verdict['errors']}"
    append_res = append_event(ledger_path, adam_candidate)
    assert append_res["ok"], f"Append failed: {append_res['errors']}"
    # Read back the single event
    events = read_events(ledger_path)
    assert len(events) == 1
    return events[0]


def _verify_rejected_without_append(ledger_path: Path, candidate: dict) -> None:
    """Run verifier, assert rejection, and ensure the ledger unchanged (still only Adam)."""
    existing = read_events(ledger_path)
    verdict = verify_candidate_event(candidate, existing)
    assert not verdict["accepted"], "Candidate was unexpectedly accepted"
    # Do NOT call append_event – just verify ledger still has only Adam's event
    after = read_events(ledger_path)
    assert len(after) == 1, "Ledger changed despite rejection"
    assert after[0]["actor_id"] == "east_adam"

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_rejects_echo_that_claims_observed_scope(tmp_path: Path) -> None:
    """Eve's echo tries to claim an observed scope – should be rejected."""
    ledger_path = tmp_path / "ledger.jsonl"
    adam_event = _append_valid_adam_event(ledger_path)

    eve_candidate = _make_whisper_candidate(prior_event_id=adam_event["event_id"])
    # Mutate the claim_scope to "observed" (illegal for an echo)
    eve_candidate["claim_scope"] = "observed"
    _verify_rejected_without_append(ledger_path, eve_candidate)


def test_rejects_speech_echo_missing_agent_speech_evidence(tmp_path: Path) -> None:
    """Eve's echo without any agent_speech evidence should be rejected."""
    ledger_path = tmp_path / "ledger.jsonl"
    adam_event = _append_valid_adam_event(ledger_path)

    eve_candidate = _make_whisper_candidate(prior_event_id=adam_event["event_id"])
    # Remove any agent_speech evidence entries
    eve_candidate["evidence_refs"] = [
        ev for ev in eve_candidate.get("evidence_refs", []) if ev.get("category") != "agent_speech"
    ]
    _verify_rejected_without_append(ledger_path, eve_candidate)


def test_rejects_speech_echo_missing_world_event_provenance(tmp_path: Path) -> None:
    """Eve's echo without a world_event provenance should be rejected.
    (Current production may accept this – a failure signals a blocker.)
    """
    ledger_path = tmp_path / "ledger.jsonl"
    adam_event = _append_valid_adam_event(ledger_path)

    eve_candidate = _make_whisper_candidate(prior_event_id=adam_event["event_id"])
    # Strip world_event evidence, keep agent_speech
    eve_candidate["evidence_refs"] = [
        ev for ev in eve_candidate.get("evidence_refs", []) if ev.get("category") != "world_event"
    ]
    _verify_rejected_without_append(ledger_path, eve_candidate)


def test_rejects_echo_that_reuses_observed_world_fact_as_truth_transfer(tmp_path: Path) -> None:
    """Eve re‑uses Adam's observed_world_fact as truth transfer – should be rejected."""
    ledger_path = tmp_path / "ledger.jsonl"
    adam_event = _append_valid_adam_event(ledger_path)

    eve_candidate = _make_whisper_candidate(prior_event_id=adam_event["event_id"])
    # Add the observed_world_fact evidence from Adam's event into Eve's evidence_refs
    observed_fact = next(
        (ev for ev in adam_event.get("evidence_refs", []) if ev.get("category") == "observed_world_fact"),
        None,
    )
    if observed_fact:
        eve_candidate["evidence_refs"].append(observed_fact)
    # Switch claim_scope to observed to model truth‑transfer attempt
    eve_candidate["claim_scope"] = "observed"
    _verify_rejected_without_append(ledger_path, eve_candidate)
