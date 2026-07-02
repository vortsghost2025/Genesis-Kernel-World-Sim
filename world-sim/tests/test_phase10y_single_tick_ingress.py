from __future__ import annotations

import sys
import json
import csv
import io
from pathlib import Path

# Set up project root import path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_candidate_mapper import candidate_from_observe_result
from backend.world.world_event_verifier import verify_candidate_event
from backend.world.world_event_ledger import read_events, append_event
from backend.world.world_event_exporter import export_events


def _make_observe_candidate(tick: int = 5, timestamp_utc: str = "2026-01-01T00:00:00Z") -> dict:
    """Helper to build a minimal observe candidate for tests."""
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


def test_observe_candidate_full_flow(tmp_path: Path) -> None:
    """Happy‑path: map → verify → append → readback → export (JSON)."""
    ledger_path = tmp_path / "ledger.jsonl"

    # 1‑3: build candidate and run verifier against an empty ledger
    candidate = _make_observe_candidate()
    assert candidate is not None
    existing = read_events(ledger_path)
    verdict = verify_candidate_event(candidate, existing)
    assert verdict["accepted"]
    assert verdict["errors"] == []

    # 4‑5: append and read back
    append_res = append_event(ledger_path, candidate)
    assert append_res["ok"]
    readback = read_events(ledger_path)
    assert len(readback) == 1
    assert readback[0]["event_id"] == candidate["event_id"]

    # 6‑7: export as strict JSON and check key values
    json_out = export_events(readback, fmt="json", strict=True)
    parsed = json.loads(json_out)
    assert isinstance(parsed, list) and len(parsed) == 1
    ev = parsed[0]
    assert ev["event_id"] == candidate["event_id"]
    assert ev["action_type"] == "observe"
    assert ev["claim_scope"] == "observed"


def test_duplicate_candidate_rejected(tmp_path: Path) -> None:
    """Same tick/actor/action is a logical duplicate → verifier rejects, no append."""
    ledger_path = tmp_path / "ledger_dup.jsonl"

    # Append first candidate
    first = _make_observe_candidate(tick=7)
    append_res = append_event(ledger_path, first)
    assert append_res["ok"]

    # Build a second candidate with identical tick/actor/action_type
    second = _make_observe_candidate(tick=7)  # same tick, same actor, same action_type = observe
    # The event_id is newly generated, but verifier should flag duplicate logic
    existing = read_events(ledger_path)
    verdict = verify_candidate_event(second, existing)
    assert not verdict["accepted"]
    # Look for the duplicate‑tick error message
    assert any("duplicate: tick" in e for e in verdict["errors"])

    # Ensure we do NOT append the rejected candidate (skip calling append_event)
    after = read_events(ledger_path)
    assert len(after) == 1  # still only the first event


def test_export_jsonl_and_csv(tmp_path: Path) -> None:
    """Export the read‑back event as JSONL and CSV – both succeed and contain the record."""
    ledger_path = tmp_path / "ledger_export.jsonl"
    candidate = _make_observe_candidate(tick=9)
    # Append valid candidate first
    assert append_event(ledger_path, candidate)["ok"]
    events = read_events(ledger_path)
    assert len(events) == 1

    # JSONL export
    jsonl_out = export_events(events, fmt="jsonl", strict=True)
    lines = jsonl_out.rstrip("\n").split("\n")
    assert len(lines) == 1
    parsed_line = json.loads(lines[0])
    assert parsed_line["event_id"] == candidate["event_id"]

    # CSV export – header + one data row
    csv_out = export_events(events, fmt="csv", strict=True)
    reader = csv.reader(io.StringIO(csv_out))
    rows = list(reader)
    # Expect header row and exactly one data row
    assert len(rows) == 2
    header, data = rows
    assert "event_id" in header
    # Locate the column index for event_id and verify value matches
    idx = header.index("event_id")
    assert data[idx] == candidate["event_id"]
