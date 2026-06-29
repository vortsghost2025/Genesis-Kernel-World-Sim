import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_ledger import append_event, read_events


def valid_event(event_id="evt_10k_append_001", **overrides):
    event = {
        "event_id": event_id,
        "schema_version": "10K.1",
        "tick": 7,
        "timestamp_utc": None,
        "actor_id": "east_eve",
        "lens": "east",
        "territory_ref": None,
        "action_type": "rest",
        "summary": "East Eve rested because no grounded action was available.",
        "evidence_refs": [{"category": "agent_action", "ref": "decision.rest"}],
        "claim_scope": "observed",
        "before_ref": None,
        "after_ref": None,
        "affected_agents": ["east_eve"],
        "artifacts_created_or_changed": [],
        "relationship_delta": None,
        "consequence": None,
        "verification_status": "verified",
    }
    event.update(overrides)
    return event


def test_append_event_creates_jsonl_and_read_events_preserves_order(tmp_path):
    ledger = tmp_path / "world_events.jsonl"

    first = append_event(ledger, valid_event("evt_10k_append_001"))
    second = append_event(ledger, valid_event("evt_10k_append_002", tick=8))

    assert first["ok"] is True
    assert second["ok"] is True
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [event["event_id"] for event in read_events(ledger)] == [
        "evt_10k_append_001",
        "evt_10k_append_002",
    ]


def test_append_preserves_existing_lines_unchanged(tmp_path):
    ledger = tmp_path / "world_events.jsonl"
    existing = valid_event("evt_existing")
    existing_line = json.dumps(existing, ensure_ascii=False, sort_keys=True)
    ledger.write_text(existing_line + "\n", encoding="utf-8")

    result = append_event(ledger, valid_event("evt_new", tick=9))

    assert result["ok"] is True
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert lines[0] == existing_line
    assert json.loads(lines[1])["event_id"] == "evt_new"


def test_invalid_event_is_rejected_without_appending(tmp_path):
    ledger = tmp_path / "world_events.jsonl"
    good = valid_event("evt_existing")
    ledger.write_text(json.dumps(good, ensure_ascii=False) + "\n", encoding="utf-8")
    before = ledger.read_text(encoding="utf-8")

    invalid = valid_event("evt_invalid")
    invalid.pop("actor_id")
    result = append_event(ledger, invalid)

    assert result["ok"] is False
    assert ledger.read_text(encoding="utf-8") == before


def test_duplicate_event_id_is_rejected_without_appending(tmp_path):
    ledger = tmp_path / "world_events.jsonl"
    assert append_event(ledger, valid_event("evt_duplicate"))["ok"] is True
    before = ledger.read_text(encoding="utf-8")

    result = append_event(ledger, valid_event("evt_duplicate", tick=99))

    assert result["ok"] is False
    assert "duplicate event_id" in " ".join(result["errors"])
    assert ledger.read_text(encoding="utf-8") == before
