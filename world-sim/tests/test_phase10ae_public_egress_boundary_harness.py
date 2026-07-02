"""Phase 10AE — Public Egress Boundary Harness.

Proves that exported-world-event output can be passed through the public
egress sanitizer before becoming public-facing text — without runtime
wiring, daemon, provider, or live data.

Synthetic tempdir-only fake leak markers are planted into event fields,
the events are appended to a ledger, replayed, exported (JSON / JSONL /
CSV), and each export output string is run through
``sanitize_public_text()``.

Test-only, tempdir-only, no production code changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_ledger import read_events, append_event, validate_event
from backend.world.world_event_exporter import export_events
from backend.world.world_event_sanitizer import (
    REDACTED_PATH,
    REDACTED_SECRET,
    REDACTED_RUNTIME,
    REDACTED_AGENT_TRACE,
    REDACTED_SKILL_REF,
    sanitize_public_text,
    sanitize_public_mapping,
)

# ---------------------------------------------------------------------------
# Synthetic fake leak markers — harmless placeholder strings that the
# sanitizer must redact.  No real paths, usernames, IPs, hostnames, secrets,
# or transcript language appear anywhere in this harness.
# ---------------------------------------------------------------------------

FAKE_LEAK_PATH_1 = r"C:\Users\example\Documents\report.txt"
FAKE_LEAK_PATH_2 = r"Z:\Example Project\world-sim\output"
FAKE_LEAK_SECRET = "SERVICE_API_KEY=dummy-key-value"
FAKE_LEAK_IP = "127.0.0.1"
FAKE_LEAK_THOUGHT = "Thought: checking memory"
FAKE_LEAK_SKILL = "/agent-tools:skill"

# Normal world terms that appear in a standard observe-event export.
# Terms like "speech", "whisper", "world_event" are valid world language
# but only appear in whisper/echo export output, not in clean observe
# events — so they are not listed here.  They survive when present (proved
# separately in the mixed-events and leaky-event tests).
WORLD_TERMS_PRESERVE = [
    "event_id",
    "actor_id",
    "claim_scope",
    "observed",
    "evidence_refs",
]


# ---------------------------------------------------------------------------
# Helper: build a single event dict containing every fake leak marker
# in its summary field so the export payload carries them.
# ---------------------------------------------------------------------------


def _make_leaky_event(event_id: str, tick: int) -> dict:
    """Return a valid ledger event with synthetic fake leak markers in
    the summary and evidence fields."""
    summary = (
        f"Found config at {FAKE_LEAK_PATH_1} "
        f"and repo at {FAKE_LEAK_PATH_2}; "
        f"key={FAKE_LEAK_SECRET}; "
        f"bound to {FAKE_LEAK_IP}; "
        f"{FAKE_LEAK_THOUGHT}; "
        f"used {FAKE_LEAK_SKILL}"
    )
    event = {
        "event_id": event_id,
        "schema_version": "10K.1",
        "tick": tick,
        "timestamp_utc": f"2026-01-01T00:00:{tick:02d}Z",
        "actor_id": "east_adam",
        "lens": "observer",
        "territory_ref": "territory_east",
        "action_type": "observe",
        "summary": summary,
        "evidence_refs": [
            {"category": "observed_world_fact", "ref": "leaky_obs"},
        ],
        "claim_scope": "observed",
        "verification_status": "accepted",
        "before_ref": None,
        "after_ref": None,
        "affected_agents": ["east_adam"],
        "artifacts_created_or_changed": [],
        "relationship_delta": {},
        "consequence": None,
    }
    return event


def _make_clean_event(event_id: str, tick: int) -> dict:
    """Return a valid ledger event with no leak markers — clean text
    that the sanitizer must leave unchanged."""
    return {
        "event_id": event_id,
        "schema_version": "10K.1",
        "tick": tick,
        "timestamp_utc": f"2026-01-01T00:00:{tick:02d}Z",
        "actor_id": "east_adam",
        "lens": "observer",
        "territory_ref": "territory_east",
        "action_type": "observe",
        "summary": "Water is visible at the basin edge.",
        "evidence_refs": [
            {"category": "observed_world_fact", "ref": "clean_obs"},
        ],
        "claim_scope": "observed",
        "verification_status": "accepted",
        "before_ref": None,
        "after_ref": None,
        "affected_agents": ["east_adam"],
        "artifacts_created_or_changed": [],
        "relationship_delta": {},
        "consequence": None,
    }


# ===================================================================
# 1.  Leaky event redacted through sanitize_public_text on export output
# ===================================================================


def test_leaky_event_export_json_redacted(tmp_path: Path) -> None:
    """Prove a leaky event exported as JSON is redacted by
    sanitize_public_text."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_leaky_event("evt_10ae_leak_json_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="json")
    sanitized = sanitize_public_text(exported)
    assert REDACTED_PATH in sanitized
    assert REDACTED_SECRET in sanitized
    assert REDACTED_RUNTIME in sanitized
    assert REDACTED_AGENT_TRACE in sanitized
    assert REDACTED_SKILL_REF in sanitized
    # Fake leak text must be gone
    assert "C:\\Users\\example" not in sanitized
    assert "Z:\\Example Project" not in sanitized
    assert "SERVICE_API_KEY" not in sanitized
    assert FAKE_LEAK_IP not in sanitized
    assert "Thought:" not in sanitized
    assert "/agent-tools:skill" not in sanitized


def test_leaky_event_export_jsonl_redacted(tmp_path: Path) -> None:
    """Same proof for JSONL export."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_leaky_event("evt_10ae_leak_jsonl_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="jsonl")
    sanitized = sanitize_public_text(exported)
    assert REDACTED_PATH in sanitized
    assert REDACTED_SECRET in sanitized
    assert REDACTED_RUNTIME in sanitized
    assert "C:\\Users\\example" not in sanitized
    assert "SERVICE_API_KEY" not in sanitized
    assert FAKE_LEAK_IP not in sanitized


def test_leaky_event_export_csv_redacted(tmp_path: Path) -> None:
    """Same proof for CSV export."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_leaky_event("evt_10ae_leak_csv_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="csv")
    sanitized = sanitize_public_text(exported)
    assert REDACTED_PATH in sanitized
    assert REDACTED_SECRET in sanitized
    assert REDACTED_RUNTIME in sanitized
    assert "C:\\Users\\example" not in sanitized
    assert "SERVICE_API_KEY" not in sanitized
    assert FAKE_LEAK_IP not in sanitized


# ===================================================================
# 2.  Normal world terms survive sanitization on exported output
# ===================================================================


def test_world_terms_survive_json_export(tmp_path: Path) -> None:
    """Prove that normal world-event schema terms survive sanitization
    when exported."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_clean_event("evt_10ae_terms_json_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="json")
    sanitized = sanitize_public_text(exported)
    for term in WORLD_TERMS_PRESERVE:
        assert term in sanitized, f"World term {term!r} was redacted"
    assert "basin edge" in sanitized or "basin" in sanitized


def test_world_terms_survive_jsonl_export(tmp_path: Path) -> None:
    """Same proof for JSONL."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_clean_event("evt_10ae_terms_jsonl_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="jsonl")
    sanitized = sanitize_public_text(exported)
    for term in WORLD_TERMS_PRESERVE:
        assert term in sanitized, f"World term {term!r} was redacted"


def test_world_terms_survive_csv_export(tmp_path: Path) -> None:
    """Same proof for CSV."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_clean_event("evt_10ae_terms_csv_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="csv")
    sanitized = sanitize_public_text(exported)
    for term in WORLD_TERMS_PRESERVE:
        assert term in sanitized, f"World term {term!r} was redacted"


# ===================================================================
# 3.  Export + sanitize is idempotent on exported output
# ===================================================================


def test_export_then_sanitize_idempotent(tmp_path: Path) -> None:
    """Prove that sanitize_public_text is idempotent on exported
    output from a leaky event."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_leaky_event("evt_10ae_idem_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    for fmt in ("json", "jsonl", "csv"):
        exported = export_events(read_events(ledger_path), fmt=fmt)
        once = sanitize_public_text(exported)
        twice = sanitize_public_text(once)
        assert once == twice, f"Not idempotent for format {fmt!r}"


# ===================================================================
# 4.  Clean export unchanged by sanitizer (apart from formatting)
# ===================================================================


def test_clean_event_export_unchanged(tmp_path: Path) -> None:
    """Prove that a clean event export is not altered by the sanitizer
    — the output should be identical."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_clean_event("evt_10ae_clean_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    for fmt in ("json", "jsonl", "csv"):
        exported = export_events(read_events(ledger_path), fmt=fmt)
        sanitized = sanitize_public_text(exported)
        assert exported == sanitized, (
            f"Clean export altered by sanitizer for format {fmt!r}"
        )


# ===================================================================
# 5.  Leaky event mixed with clean event — only leaky fields redacted
# ===================================================================


def test_mixed_events_redacts_only_leaky_fields(tmp_path: Path) -> None:
    """Prove that in a multi-event export, only the leaky event's
    redactable text is sanitized and the clean event remains intact."""
    ledger_path = tmp_path / "ledger.jsonl"
    clean_ev = _make_clean_event("evt_10ae_mix_clean_001", tick=1)
    leaky_ev = _make_leaky_event("evt_10ae_mix_leaky_001", tick=2)
    assert append_event(ledger_path, clean_ev)["ok"]
    assert append_event(ledger_path, leaky_ev)["ok"]
    events = read_events(ledger_path)
    assert len(events) == 2

    for fmt in ("json", "jsonl", "csv"):
        exported = export_events(events, fmt=fmt)
        # Parse to check individual events where possible
        if fmt == "jsonl":
            lines = exported.strip().split("\n")
            assert len(lines) == 2
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            assert first["event_id"] == "evt_10ae_mix_clean_001"
            assert second["event_id"] == "evt_10ae_mix_leaky_001"

        sanitized = sanitize_public_text(exported)
        assert REDACTED_PATH in sanitized
        assert REDACTED_SECRET in sanitized
        assert "C:\\Users\\example" not in sanitized
        assert "SERVICE_API_KEY" not in sanitized
        assert "basin edge" in sanitized or "basin" in sanitized


# ===================================================================
# 6.  Event validation survives sanitized summary
# ===================================================================


def test_sanitized_event_still_validates(tmp_path: Path) -> None:
    """Prove that after sanitizing a leaky event's summary, the
    resulting dict is still a valid 10K event (only summary
    changes)."""
    event = _make_leaky_event("evt_10ae_val_001", tick=1)
    sanitized_event = sanitize_public_mapping(event)
    assert sanitized_event["event_id"] == "evt_10ae_val_001"
    assert REDACTED_PATH in sanitized_event["summary"]
    assert REDACTED_SECRET in sanitized_event["summary"]
    # The sanitized event should still pass ledger validation
    result = validate_event(sanitized_event)
    assert result["ok"], (
        f"Sanitized event failed validation: {result['errors']}"
    )


# ===================================================================
# 7.  sanitize_public_mapping on full event before export
# ===================================================================


def test_sanitize_full_event_before_export(tmp_path: Path) -> None:
    """Prove that running sanitize_public_mapping on a full event
    before export redacts leak markers but preserves the schema,
    and the resulting output is safe."""
    event = _make_leaky_event("evt_10ae_pre_export_001", tick=1)
    sanitized_event = sanitize_public_mapping(event)
    # Schema must survive
    for field in ("event_id", "schema_version", "actor_id", "claim_scope"):
        assert field in sanitized_event
    # Leaky text must be redacted
    assert REDACTED_PATH in sanitized_event["summary"]
    assert "C:\\Users\\example" not in sanitized_event["summary"]
    # Export the already-sanitized event
    ledger_path = tmp_path / "ledger.jsonl"
    assert append_event(ledger_path, sanitized_event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="json")
    # The export string should already be safe; re-sanitizing should
    # be a no-op (idempotent)
    re_sanitized = sanitize_public_text(exported)
    assert exported == re_sanitized
    assert "C:\\Users\\example" not in exported


# ===================================================================
# 8.  Does not mutate original event dict
# ===================================================================


def test_does_not_mutate_original_event(tmp_path: Path) -> None:
    """Prove that sanitize_public_mapping does not mutate the input
    event dict."""
    import copy
    original = _make_leaky_event("evt_10ae_no_mut_001", tick=1)
    original_copy = copy.deepcopy(original)
    _ = sanitize_public_mapping(original)
    assert original == original_copy, "Original event dict was mutated"


def test_does_not_mutate_exported_output(tmp_path: Path) -> None:
    """Prove that sanitize_public_text does not mutate its input."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_leaky_event("evt_10ae_no_mut_str_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="json")
    exported_copy = str(exported)
    _ = sanitize_public_text(exported)
    assert exported == exported_copy, "Input string was mutated"


# ===================================================================
# 9.  All five redaction markers appear in leaky export for each format
# ===================================================================


def test_all_five_markers_present_in_leaky_json(tmp_path: Path) -> None:
    """Confirm all five redaction marker strings appear in the
    sanitized output of a leaky JSON export."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_leaky_event("evt_10ae_markers_json_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="json")
    sanitized = sanitize_public_text(exported)
    for marker in (REDACTED_PATH, REDACTED_SECRET, REDACTED_RUNTIME,
                   REDACTED_AGENT_TRACE, REDACTED_SKILL_REF):
        assert marker in sanitized, f"Marker {marker} missing in JSON"


def test_all_five_markers_present_in_leaky_jsonl(tmp_path: Path) -> None:
    """Same for JSONL."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_leaky_event("evt_10ae_markers_jsonl_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="jsonl")
    sanitized = sanitize_public_text(exported)
    for marker in (REDACTED_PATH, REDACTED_SECRET, REDACTED_RUNTIME,
                   REDACTED_AGENT_TRACE, REDACTED_SKILL_REF):
        assert marker in sanitized, f"Marker {marker} missing in JSONL"


def test_all_five_markers_present_in_leaky_csv(tmp_path: Path) -> None:
    """Same for CSV."""
    ledger_path = tmp_path / "ledger.jsonl"
    event = _make_leaky_event("evt_10ae_markers_csv_001", tick=1)
    assert append_event(ledger_path, event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="csv")
    sanitized = sanitize_public_text(exported)
    for marker in (REDACTED_PATH, REDACTED_SECRET, REDACTED_RUNTIME,
                   REDACTED_AGENT_TRACE, REDACTED_SKILL_REF):
        assert marker in sanitized, f"Marker {marker} missing in CSV"


# ===================================================================
# 10.  Leaky evidence_refs also redacted via sanitize_public_mapping
# ===================================================================


def test_leaky_evidence_sanitized_via_mapping(tmp_path: Path) -> None:
    """Prove that an event with leak text in evidence fields is
    sanitized by sanitize_public_mapping before export, and the
    exported result carries redaction markers."""
    event = _make_leaky_event("evt_10ae_evid_001", tick=1)
    # Add a leaky text in an evidence ref value
    event["evidence_refs"] = [
        {"category": "observed_world_fact",
         "ref": FAKE_LEAK_PATH_1},
    ]
    sanitized_event = sanitize_public_mapping(event)
    assert REDACTED_PATH in sanitized_event["evidence_refs"][0]["ref"]
    # Append and export
    ledger_path = tmp_path / "ledger.jsonl"
    assert append_event(ledger_path, sanitized_event)["ok"]
    exported = export_events(read_events(ledger_path), fmt="json")
    # The export should already be safe; re-sanitizing should be
    # a no-op
    re_sanitized = sanitize_public_text(exported)
    assert exported == re_sanitized
    assert "C:\\Users\\example" not in exported


# ===================================================================
# 11.  Export does not decide sanitizer order — harness proves both
#      pre-export and post-export sanitization are valid approaches
# ===================================================================


def test_order_agnostic_pre_or_post_export(tmp_path: Path) -> None:
    """Prove that the boundary works whether sanitization happens
    before export (via sanitize_public_mapping) or after export
    (via sanitize_public_text on the export string).  Both paths
    must eliminate leak markers."""
    event = _make_leaky_event("evt_10ae_order_001", tick=1)

    # Path A: sanitize_public_mapping → export
    pre_sanitized = sanitize_public_mapping(event)
    assert REDACTED_PATH in pre_sanitized["summary"]

    ledger_path_a = tmp_path / "ledger_a.jsonl"
    assert append_event(ledger_path_a, pre_sanitized)["ok"]
    export_a = export_events(read_events(ledger_path_a), fmt="json")
    assert "C:\\Users\\example" not in export_a

    # Path B: export → sanitize_public_text
    ledger_path_b = tmp_path / "ledger_b.jsonl"
    assert append_event(ledger_path_b, dict(event))["ok"]
    raw_export = export_events(read_events(ledger_path_b), fmt="json")
    post_sanitized = sanitize_public_text(raw_export)
    assert "C:\\Users\\example" not in post_sanitized

    # Both paths produce redaction markers
    assert REDACTED_PATH in export_a
    assert REDACTED_PATH in post_sanitized
