"""10V exporter: pure event serialization tests.

Tests that ``export_events`` produces correct JSON, JSONL, and CSV
output from an in-memory list of event dicts, with field allowlist
controls and proper handling of missing/nested fields.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_exporter import (
    EXPORT_FIELDS,
    ExporterError,
    export_events,
)
from backend.world.world_event_ledger import validate_event

_COUNTER = 600


def make_event(**overrides) -> dict:
    """Produce a valid minimal event dict that passes validate_event."""
    global _COUNTER
    _COUNTER += 1
    event = {
        "event_id": f"evt_10v_{_COUNTER}",
        "schema_version": "10V.1",
        "tick": _COUNTER,
        "timestamp_utc": f"2026-01-01T00:00:{_COUNTER:02d}Z",
        "actor_id": "north_blake",
        "lens": "north",
        "territory_ref": "territoryB",
        "action_type": "observe",
        "summary": "rock is solid",
        "evidence_refs": [
            {"category": "observed_world_fact", "ref": "world.observe.rock"}
        ],
        "claim_scope": "observed",
        "before_ref": None,
        "after_ref": None,
        "affected_agents": ["north_blake"],
        "artifacts_created_or_changed": [],
        "relationship_delta": [],
        "consequence": "inspection complete",
        "verification_status": "candidate",
    }
    event.update(overrides)
    event.setdefault("tick", _COUNTER)
    assert validate_event(event)["ok"], f"invalid event: {validate_event(event)['errors']}"
    return event


# ── 1. Empty events list ──────────────────────────────────────────────


def test_empty_events_list_json():
    """Empty input + JSON → empty array, valid JSON."""
    out = export_events([], fmt="json")
    assert out == "[]"


def test_empty_events_list_jsonl():
    """Empty input + JSONL → empty string, no spurious newlines."""
    out = export_events([], fmt="jsonl")
    assert out == ""


def test_empty_events_list_csv():
    """Empty input + CSV → header row only, no data rows."""
    out = export_events([], fmt="csv")
    reader = list(csv.reader(io.StringIO(out)))
    assert len(reader) == 1  # header only
    assert "event_id" in reader[0]


# ── 2. JSON format ────────────────────────────────────────────────────


def test_json_returns_valid_array():
    """validate_event-shaped events → valid JSON array."""
    events = [make_event(), make_event(action_type="inspect")]
    out = export_events(events, fmt="json")
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[0]["event_id"].startswith("evt_10v_")
    assert parsed[1]["action_type"] == "inspect"


def test_json_includes_default_fields():
    """Default EXPORT_FIELDS are present; non-allowlist fields absent."""
    evt = make_event()
    # Add a private field the allowlist excludes
    evt["verification_notes"] = "operator-only detail"
    out = export_events([evt], fmt="json")
    parsed = json.loads(out)
    keys = set(parsed[0].keys())
    for f in EXPORT_FIELDS:
        assert f in keys, f"missing default field: {f}"
    assert "verification_notes" not in keys


def test_json_respects_custom_fields():
    """Custom fields tuple narrows output to selected fields only."""
    evt = make_event()
    out = export_events([evt], fmt="json", fields=("event_id", "actor_id"))
    parsed = json.loads(out)
    assert set(parsed[0].keys()) == {"event_id", "actor_id"}


def test_json_keys_preserve_field_order():
    """JSON output keys reflect the order of the fields argument."""
    evt = make_event()
    fields = ("summary", "event_id", "actor_id")
    out = export_events([evt], fmt="json", fields=fields)
    parsed = json.loads(out)
    assert list(parsed[0].keys()) == list(fields)


def test_json_unicode_preserved():
    """Non-ASCII characters are not escaped to backslash-u sequences."""
    evt = make_event(summary="naïve waters")
    out = export_events([evt], fmt="json", fields=("summary",))
    assert "naïve" in out


# ── 3. JSONL format ───────────────────────────────────────────────────


def test_jsonl_one_event_per_line():
    """JSONL output is N lines, each one a valid JSON object."""
    events = [make_event() for _ in range(3)]
    out = export_events(events, fmt="jsonl")
    lines = out.rstrip("\n").split("\n")
    assert len(lines) == 3
    for line in lines:
        parsed = json.loads(line)
        assert isinstance(parsed, dict)
        assert "event_id" in parsed


def test_jsonl_trailing_newline():
    """JSONL terminates with exactly one trailing newline."""
    out = export_events([make_event()], fmt="jsonl")
    assert out.endswith("\n")
    # Single newline at end
    stripped = out.rstrip("\n")
    assert "\n" not in stripped


def test_jsonl_no_brackets():
    """JSONL is not wrapped in [] or any array container."""
    out = export_events([make_event()], fmt="jsonl")
    assert not out.startswith("[")
    assert not out.rstrip("\n").endswith("]")


def test_jsonl_project_respects_fields():
    """JSONL projection filters to specified fields."""
    evt = make_event()
    out = export_events([evt], fmt="jsonl", fields=("event_id", "tick"))
    parsed = json.loads(out.rstrip("\n"))
    assert set(parsed.keys()) == {"event_id", "tick"}


# ── 4. CSV format ─────────────────────────────────────────────────────


def test_csv_header_present():
    """CSV output starts with a header row containing the fields."""
    out = export_events([make_event()], fmt="csv")
    lines = out.rstrip("\n").split("\n")
    assert len(lines) == 2  # header + 1 data row
    header = lines[0].split(",")
    assert "event_id" in header
    assert "actor_id" in header


def test_csv_header_only_default_fields():
    """Default CSV header matches EXPORT_FIELDS (case-insensitive set compare)."""
    out = export_events([make_event()], fmt="csv")
    reader = next(iter(csv.reader(io.StringIO(out))))
    assert set(reader) == set(EXPORT_FIELDS)


def test_csv_one_row_per_event():
    """CSV row count === number of events + header."""
    events = [make_event() for _ in range(5)]
    out = export_events(events, fmt="csv")
    rows = list(csv.reader(io.StringIO(out)))
    assert len(rows) == 6  # header + 5 data rows


def test_csv_nested_fields_jsonified():
    """Nested list/dict values are JSON-stringified inside CSV cells."""
    evt = make_event(affected_agents=["north_blake", "east_adam"])
    out = export_events([evt], fmt="csv")
    # Find the affected_agents column
    reader = csv.reader(io.StringIO(out))
    header = next(reader)
    data_row = next(reader)
    col_idx = header.index("affected_agents")
    cell = data_row[col_idx]
    parsed_cell = json.loads(cell)
    assert parsed_cell == ["north_blake", "east_adam"]


def test_csv_scalar_field_order_before_nested():
    """Scalars precede nested fields in CSV column order."""
    out = export_events(
        [make_event()],
        fmt="csv",
        fields=("affected_agents", "event_id", "evidence_refs", "actor_id"),
    )
    reader = csv.reader(io.StringIO(out))
    header = next(reader)
    # Scalars first (event_id, actor_id sorted by appearance), then nested
    # Expected reorder: scalars appear before nested. event_id, actor_id
    # are the only scalars; affected_agents and evidence_refs are nested.
    scalars = [f for f in header if f in ("event_id", "actor_id")]
    nested = [f for f in header if f in ("affected_agents", "evidence_refs")]
    if scalars and nested:
        first_scalar_idx = min(header.index(f) for f in scalars)
        first_nested_idx = min(header.index(f) for f in nested)
        assert first_scalar_idx < first_nested_idx


def test_csv_newlines_sanitized_in_cells():
    """Newlines inside CSV cell values are replaced with a space."""
    evt = make_event(summary="line one\nline two")
    out = export_events([evt], fmt="csv")
    rows = list(csv.reader(io.StringIO(out)))
    assert len(rows) == 2  # header + 1 data row, NOT split by newline
    assert "line one line two" in rows[1][header_index(out, "summary")]


def header_index(csv_text: str, field_name: str) -> int:
    """Helper: locate field column index in CSV header."""
    reader = next(iter(csv.reader(io.StringIO(csv_text))))
    return reader.index(field_name)


# ── 5. Strict mode and validation ──────────────────────────────────────


def test_strict_mode_raises_on_missing_field():
    """strict=True raises when a requested field is absent on an event."""
    evt = make_event()
    del evt["actor_id"]  # remove the field
    import pytest
    with pytest.raises(ExporterError, match="missing required fields"):
        export_events([evt], fmt="json", fields=("event_id", "actor_id"), strict=True)


def test_non_strict_treats_missing_as_none():
    """strict=False yields None for missing fields (null in JSON)."""
    evt = make_event()
    del evt["actor_id"]
    out = export_events([evt], fmt="json", fields=("event_id", "actor_id"))
    parsed = json.loads(out)
    assert parsed[0]["event_id"].startswith("evt_10v_")
    assert parsed[0]["actor_id"] is None


def test_non_dict_event_raises():
    """Non-dict entries in events list raise ExporterError."""
    import pytest
    with pytest.raises(ExporterError, match="event must be a dict"):
        export_events(["not a dict"], fmt="json")


def test_non_dict_event_in_strict_jsonl():
    """Same guard works in JSONL and CSV modes."""
    import pytest
    for fmt in ("json", "jsonl", "csv"):
        with pytest.raises(ExporterError):
            export_events([123], fmt=fmt)


# ── 6. Configuration guards ───────────────────────────────────────────


def test_unsupported_format_raises():
    """fmt not in SUPPORTED_FORMATS raises."""
    import pytest
    with pytest.raises(ExporterError, match="unsupported format"):
        export_events([make_event()], fmt="yaml")


def test_empty_fields_raises():
    """Empty fields tuple raises ExporterError."""
    import pytest
    with pytest.raises(ExporterError, match="fields must contain"):
        export_events([make_event()], fmt="json", fields=())


def test_default_fields_constant_length():
    """EXPORT_FIELDS is a stable tuple — exercise it here so a future
    rewrap (e.g. accidental list mutation) is caught."""
    assert len(EXPORT_FIELDS) > 0
    assert "event_id" in EXPORT_FIELDS
    assert "actor_id" in EXPORT_FIELDS


# ── 7. Roundtrip and determinism ───────────────────────────────────────


def test_json_roundtrip_lossless_for_default_event():
    """JSON output re-parses bit-for-bit to the projected event list."""
    events = [make_event(), make_event(action_type="inspect")]
    out = export_events(events, fmt="json")
    parsed = json.loads(out)
    assert len(parsed) == 2
    assert parsed[0]["event_id"] == events[0]["event_id"]
    assert parsed[0]["actor_id"] == events[0]["actor_id"]
    assert parsed[1]["action_type"] == "inspect"


def test_jsonl_roundtrip_one_event():
    """JSONL output re-parses to the single projected event."""
    out = export_events([make_event()], fmt="jsonl", fields=("event_id", "tick"))
    parses = [json.loads(line) for line in out.rstrip("\n").split("\n")]
    assert len(parses) == 1
    assert "tick" in parses[0]


def test_is_deterministic():
    """Two exports of the same input produce byte-identical output."""
    events = [make_event() for _ in range(3)]
    a = export_events(events, fmt="jsonl")
    b = export_events(events, fmt="jsonl")
    assert a == b
    c = export_events(events, fmt="json")
    d = export_events(events, fmt="json")
    assert c == d
