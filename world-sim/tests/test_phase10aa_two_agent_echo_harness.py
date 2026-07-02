from __future__ import annotations

import sys
import json
from pathlib import Path

# Set up project root import path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_candidate_mapper import (
    candidate_from_observe_result,
    candidate_from_whisper_decision,
)
from backend.world.world_event_verifier import verify_candidate_event
from backend.world.world_event_ledger import read_events, append_event
from backend.world.world_event_exporter import export_events


def _make_observe_candidate(
    tick: int = 1,
    timestamp_utc: str = "2026-01-01T00:00:01Z",
) -> dict:
    """Build a minimal observe candidate for Adam."""
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
    # target_resolved with target_actor_id so Eve's whisper affects Adam
    return candidate_from_whisper_decision(
        actor_id,
        decision,
        target_resolved=True,
        target_actor_id="east_adam",
        tick=tick,
        timestamp_utc=timestamp_utc,
    )


def test_two_agent_echo_harness(tmp_path: Path) -> None:
    """End‑to‑end harness exercising observe → whisper interaction.

    The final JSON export assertion validates that ``evidence_refs`` are present
    in the exported events.
    """
    ledger_path = tmp_path / "ledger.jsonl"

    # Tick 1 – Adam observes
    adam_candidate = _make_observe_candidate()
    assert adam_candidate is not None
    existing = read_events(ledger_path)
    verdict = verify_candidate_event(adam_candidate, existing)
    assert verdict["accepted"]
    assert verdict["errors"] == []
    append_res = append_event(ledger_path, adam_candidate)
    assert append_res["ok"]

    # Verify first event persisted correctly
    readback = read_events(ledger_path)
    assert len(readback) == 1
    ev1 = readback[0]
    assert ev1["event_id"] == adam_candidate["event_id"]
    assert ev1["claim_scope"] == "observed"
    assert ev1["action_type"] == "observe"
    assert any(
        e.get("category") == "observed_world_fact" for e in ev1.get("evidence_refs", [])
    )

    # Tick 2 – Eve whispers, referencing Adam's event
    eve_candidate = _make_whisper_candidate(prior_event_id=ev1["event_id"])
    assert eve_candidate is not None
    existing = read_events(ledger_path)
    verdict = verify_candidate_event(eve_candidate, existing)
    assert verdict["accepted"]
    assert verdict["errors"] == []
    append_res = append_event(ledger_path, eve_candidate)
    assert append_res["ok"]

    # Verify both events are present and distinct
    readback2 = read_events(ledger_path)
    assert len(readback2) == 2
    ev1, ev2 = readback2
    assert ev1["event_id"] != ev2["event_id"]

    # Event 1 checks (already partly done above)
    assert ev1["claim_scope"] == "observed"
    assert ev1["action_type"] == "observe"
    assert any(
        e.get("category") == "observed_world_fact" for e in ev1.get("evidence_refs", [])
    )

    # Event 2 checks
    assert ev2["claim_scope"] == "speech"
    assert ev2["action_type"] == "whisper"
    # Eve's whisper should affect Adam
    assert "east_adam" in ev2.get("affected_agents", [])
    # Evidence must include both agent_speech and world_event referencing Adam's ID
    evidence_cats = {e.get("category") for e in ev2.get("evidence_refs", [])}
    assert "agent_speech" in evidence_cats
    assert "world_event" in evidence_cats
    # Ensure the world_event reference points to Adam's event_id
    world_refs = [
        e.get("reference")
        for e in ev2.get("evidence_refs", [])
        if e.get("category") == "world_event"
    ]
    assert ev1["event_id"] in world_refs

    # Tick 2 must NOT inherit observed truth
    assert ev2["claim_scope"] != "observed"
    assert not any(
        e.get("category") == "observed_world_fact" for e in ev2.get("evidence_refs", [])
    )

    # Export and verify evidence_refs are present
    json_out = export_events(readback2, fmt="json", strict=True)
    parsed = json.loads(json_out)
    assert isinstance(parsed, list) and len(parsed) == 2
    exported_ev2 = parsed[1]
    # Verify that evidence_refs were exported correctly
    assert "evidence_refs" in exported_ev2
    world_refs_export = [
        e.get("reference")
        for e in exported_ev2.get("evidence_refs", [])
        if e.get("category") == "world_event"
    ]
    assert ev1["event_id"] in world_refs_export
