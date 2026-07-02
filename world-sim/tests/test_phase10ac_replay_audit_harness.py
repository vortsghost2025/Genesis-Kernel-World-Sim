"""Phase 10AC — Replay / Audit Harness.

Tempdir-only replay-and-export audit for the 10AA/10AB two-agent
echo model.  Proves that reading the ledger twice yields identical
order, distinct event IDs, stable claim_scope values, resolvable
world_event provenance, no truth inheritance, deterministic export,
and stable aggregator summary.

Test-only, tempdir-only, no production code changed.
"""

from __future__ import annotations

import json
import sys
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
from backend.world.world_event_aggregator import summarize_events


# ---------------------------------------------------------------------------
# Helper factories (mirror 10AA / 10AB)
# ---------------------------------------------------------------------------

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
    return candidate_from_whisper_decision(
        actor_id,
        decision,
        target_resolved=True,
        target_actor_id="east_adam",
        tick=tick,
        timestamp_utc=timestamp_utc,
    )


# ---------------------------------------------------------------------------
# Replay / Audit test
# ---------------------------------------------------------------------------

def test_replay_audit_harness(tmp_path: Path) -> None:
    """Prove ledger replay stability, provenance resolution, and
    deterministic export/aggregation for a two-agent echo round."""
    ledger_path = tmp_path / "ledger.jsonl"

    # ── 1 & 2: append Adam observed ──────────────────────────────────────
    adam_candidate = _make_observe_candidate()
    existing = read_events(ledger_path)
    verdict = verify_candidate_event(adam_candidate, existing)
    assert verdict["accepted"], f"Adam rejected: {verdict['errors']}"
    append_res = append_event(ledger_path, adam_candidate)
    assert append_res["ok"], f"Adam append: {append_res['errors']}"

    # ── 3: append Eve whisper echoing Adam ───────────────────────────────
    ev1 = read_events(ledger_path)[0]
    eve_candidate = _make_whisper_candidate(prior_event_id=ev1["event_id"])
    existing = read_events(ledger_path)
    verdict = verify_candidate_event(eve_candidate, existing)
    assert verdict["accepted"], f"Eve rejected: {verdict['errors']}"
    append_res = append_event(ledger_path, eve_candidate)
    assert append_res["ok"], f"Eve append: {append_res['errors']}"

    # ── 4: read/replay the ledger twice ──────────────────────────────────
    replay_a = read_events(ledger_path)
    replay_b = read_events(ledger_path)

    assert len(replay_a) == 2
    assert len(replay_b) == 2

    # ── 5: prove replay order is stable ──────────────────────────────────
    assert replay_a[0]["event_id"] == replay_b[0]["event_id"]
    assert replay_a[1]["event_id"] == replay_b[1]["event_id"]

    # ── 6: prove event_ids remain distinct ───────────────────────────────
    assert replay_a[0]["event_id"] != replay_a[1]["event_id"]
    assert replay_b[0]["event_id"] != replay_b[1]["event_id"]

    adam_event = replay_a[0]
    eve_event = replay_a[1]

    # ── 7: prove claim_scope values remain unchanged ─────────────────────
    assert adam_event["claim_scope"] == "observed"
    assert eve_event["claim_scope"] == "speech"

    # ── 8: prove Eve's world_event provenance resolves to Adam's event_id ─
    world_ref_ids = [
        e.get("reference")
        for e in eve_event.get("evidence_refs", [])
        if e.get("category") == "world_event"
    ]
    assert adam_event["event_id"] in world_ref_ids, (
        f"Eve's world_event provenance does not reference Adam's event_id "
        f"{adam_event['event_id']}; got {world_ref_ids}"
    )

    # ── 9: prove Eve does not inherit observed truth ─────────────────────
    assert eve_event["claim_scope"] != "observed"
    observed_cats = {
        e.get("category")
        for e in eve_event.get("evidence_refs", [])
    }
    assert "observed_world_fact" not in observed_cats, (
        "Eve's echo must not carry observed_world_fact evidence"
    )

    # ── 10: prove export is deterministic across repeated reads ──────────
    for fmt in ("json", "jsonl", "csv"):
        export_a = export_events(replay_a, fmt=fmt, strict=True)
        export_b = export_events(replay_b, fmt=fmt, strict=True)
        assert export_a == export_b, (
            f"Export mismatch for format {fmt!r} across repeated reads"
        )

    # ── 11: aggregator read-only proof that counts/scopes are stable ─────
    summary_a = summarize_events(replay_a)
    summary_b = summarize_events(replay_b)

    # Must be identical across replays
    assert summary_a == summary_b, "Aggregator summary differs across replays"

    # Total events = 2
    assert summary_a["total_events"] == 2

    # By claim_scope: observed=1, speech=1
    assert summary_a["by_claim_scope"] == {"observed": 1, "speech": 1}, (
        f"Unexpected scope distribution: {summary_a['by_claim_scope']}"
    )

    # By action_type: observe=1, whisper=1
    assert summary_a["by_action_type"] == {"observe": 1, "whisper": 1}, (
        f"Unexpected action_type distribution: {summary_a['by_action_type']}"
    )

    # By actor: each appears once
    assert summary_a["by_actor"] == {"east_adam": 1, "east_eve": 1}, (
        f"Unexpected actor distribution: {summary_a['by_actor']}"
    )

    # By evidence_category:
    #   Adam: 1 observed_world_fact
    #   Eve:  1 agent_speech + 1 world_event
    assert summary_a["by_evidence_category"] == {
        "observed_world_fact": 1,
        "agent_speech": 1,
        "world_event": 1,
    }, f"Unexpected evidence distribution: {summary_a['by_evidence_category']}"

    # tick_range: tick 1 → 2
    assert summary_a["tick_range"] == {"min_tick": 1, "max_tick": 2}, (
        f"Unexpected tick_range: {summary_a['tick_range']}"
    )

    # mutation_count should be 0 (neither event is mutating)
    assert summary_a["mutation_count"] == 0

    # world_state_deltas — Adam's observed summary ("observe water level")
    # does not use the "X is Y" pattern that _parse_is_claim looks for,
    # so no deltas are emitted. This is correct aggregator behavior.
    deltas = summary_a["world_state_deltas"]
    assert len(deltas) == 0
    # Eve's speech echo must NOT appear in world_state_deltas either
    assert all(
        d["actor_id"] != "east_eve" for d in deltas
    ), "Eve's speech echo must not produce world_state_deltas"

    # recent_events should contain both events sorted by tick descending
    recent = summary_a["recent_events"]
    assert len(recent) == 2
    assert recent[0]["event_id"] == eve_event["event_id"], (
        "Most recent event (tick 2) should be first in recent_events"
    )
    assert recent[1]["event_id"] == adam_event["event_id"]

    # ── Final sanity: third replay still identical ───────────────────────
    replay_c = read_events(ledger_path)
    assert len(replay_c) == 2
    assert replay_c[0]["event_id"] == adam_event["event_id"]
    assert replay_c[1]["event_id"] == eve_event["event_id"]

    export_c_json = export_events(replay_c, fmt="json", strict=True)
    export_a_json = export_events(replay_a, fmt="json", strict=True)
    assert export_c_json == export_a_json, (
        "Third replay export differs from first replay export"
    )
