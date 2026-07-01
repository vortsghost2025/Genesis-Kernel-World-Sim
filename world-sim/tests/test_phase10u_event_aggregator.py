"""10U aggregator: pure event aggregation tests.

Tests that ``summarize_events`` produces correct derived summaries
from an in-memory list of event dicts.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_aggregator import summarize_events
from backend.world.world_event_ledger import validate_event

_COUNTER = 500


def make_event(**overrides) -> dict:
    """Produce a valid minimal event dict that passes validate_event."""
    global _COUNTER
    _COUNTER += 1
    event = {
        "event_id": f"evt_10u_{_COUNTER}",
        "schema_version": "10U.1",
        "tick": _COUNTER,
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
    event.setdefault("tick", _COUNTER)
    assert validate_event(event)["ok"], f"invalid event: {validate_event(event)['errors']}"
    return event


# ── 1. Empty events list ──────────────────────────────────────────────


def test_empty_events_list():
    """Empty list → zero counts and no recent events."""
    result = summarize_events([], top_n=5)
    assert result["total_events"] == 0
    assert result["by_claim_scope"] == {}
    assert result["by_action_type"] == {}
    assert result["by_actor"] == {}
    assert result["by_territory"] == {}
    assert result["by_evidence_category"] == {}
    assert result["recent_events"] == []
    assert result["tick_range"] == {"min_tick": None, "max_tick": None}
    assert result["mutation_count"] == 0
    assert result["world_state_deltas"] == []


# ── 2. Total event count ──────────────────────────────────────────────


def test_total_event_count():
    """Three events → total_events == 3."""
    events = [make_event(), make_event(), make_event()]
    result = summarize_events(events)
    assert result["total_events"] == 3


# ── 3. by_claim_scope counts ──────────────────────────────────────────


def test_by_claim_scope_counts():
    """Mix of observed, speech, memory → correct per-scope counts."""
    e1 = make_event(claim_scope="observed")
    e2 = make_event(claim_scope="speech",
                    action_type="whisper",
                    evidence_refs=[{"category": "agent_speech", "ref": "whisper"}])
    e3 = make_event(claim_scope="memory",
                    evidence_refs=[{"category": "agent_memory", "ref": "mem1"}])
    e4 = make_event(claim_scope="observed")
    result = summarize_events([e1, e2, e3, e4])
    assert result["by_claim_scope"] == {"observed": 2, "speech": 1, "memory": 1}


# ── 4. by_action_type counts ──────────────────────────────────────────


def test_by_action_type_counts():
    """Mix of observe, rest, gather → correct per-action counts."""
    e1 = make_event(action_type="observe")
    e2 = make_event(action_type="rest",
                    claim_scope="hypothesis",
                    evidence_refs=[{"category": "agent_memory", "ref": "mem1"}],
                    summary="rested")
    e3 = make_event(action_type="gather",
                    evidence_refs=[{"category": "agent_action", "ref": "gather"}],
                    before_ref="md5:a", after_ref="md5:b")
    e4 = make_event(action_type="observe")
    result = summarize_events([e1, e2, e3, e4])
    assert result["by_action_type"] == {"observe": 2, "rest": 1, "gather": 1}


# ── 5. by_actor counts ────────────────────────────────────────────────


def test_by_actor_counts():
    """Multiple actors → correct per-actor counts."""
    e1 = make_event(actor_id="east_adam")
    e2 = make_event(actor_id="east_eve")
    e3 = make_event(actor_id="east_adam")
    result = summarize_events([e1, e2, e3])
    assert result["by_actor"] == {"east_adam": 2, "east_eve": 1}


# ── 6. by_territory counts ────────────────────────────────────────────


def test_by_territory_counts():
    """Multiple territories → correct per-territory counts."""
    e1 = make_event(territory_ref="territoryA")
    e2 = make_event(territory_ref="territoryB")
    e3 = make_event(territory_ref="territoryA")
    result = summarize_events([e1, e2, e3])
    assert result["by_territory"] == {"territoryA": 2, "territoryB": 1}


# ── 7. by_evidence_category counts ────────────────────────────────────


def test_by_evidence_category_counts():
    """Multiple evidence categories → correct per-category counts."""
    e1 = make_event(evidence_refs=[{"category": "observed_world_fact", "ref": "w1"},
                                    {"category": "agent_action", "ref": "a1"}])
    e2 = make_event(claim_scope="speech", action_type="whisper",
                    evidence_refs=[{"category": "agent_speech", "ref": "s1"}],
                    summary="hello")
    result = summarize_events([e1, e2])
    assert result["by_evidence_category"] == {
        "observed_world_fact": 1,
        "agent_action": 1,
        "agent_speech": 1,
    }


# ── 8. recent_events ordering ─────────────────────────────────────────


def test_recent_events_ordering():
    """Events sorted by tick descending in recent_events."""
    e1 = make_event(tick=10)
    e2 = make_event(tick=30)
    e3 = make_event(tick=20)
    result = summarize_events([e1, e2, e3], top_n=3)
    ticks = [e["tick"] for e in result["recent_events"]]
    assert ticks == [30, 20, 10]


def test_recent_events_none_tick_sorts_last():
    """Event with None tick appears after all numeric ticks."""
    e1 = make_event(tick=10)
    e2 = make_event(tick=None, timestamp_utc="2026-01-01T00:00:00Z")
    e3 = make_event(tick=20)
    result = summarize_events([e1, e2, e3], top_n=3)
    ticks = [e["tick"] for e in result["recent_events"]]
    assert ticks == [20, 10, None]


# ── 9. recent_events top_n ────────────────────────────────────────────


def test_recent_events_top_n():
    """top_n=2 returns only 2 most recent events."""
    events = [make_event(tick=i) for i in range(10)]
    result = summarize_events(events, top_n=2)
    assert len(result["recent_events"]) == 2
    # Most recent = highest tick
    assert result["recent_events"][0]["tick"] == 9
    assert result["recent_events"][1]["tick"] == 8


# ── 10. tick_range ────────────────────────────────────────────────────


def test_tick_range():
    """tick_range reports min and max numeric ticks."""
    events = [make_event(tick=5), make_event(tick=20), make_event(tick=10)]
    result = summarize_events(events)
    assert result["tick_range"] == {"min_tick": 5, "max_tick": 20}


def test_tick_range_with_none():
    """Events with None tick do not affect tick_range."""
    events = [
        make_event(tick=5),
        make_event(tick=None, timestamp_utc="2026-01-01T00:00:00Z"),
    ]
    result = summarize_events(events)
    assert result["tick_range"] == {"min_tick": 5, "max_tick": 5}


def test_tick_range_no_ticked_events():
    """Only None-tick events → both min and max are None."""
    events = [
        make_event(tick=None, timestamp_utc="2026-01-01T00:00:00Z"),
    ]
    result = summarize_events(events)
    assert result["tick_range"] == {"min_tick": None, "max_tick": None}


# ── 11. mutation_count ────────────────────────────────────────────────


def test_mutation_count():
    """Events with both before_ref and after_ref truthy are counted."""
    e1 = make_event(action_type="gather",
                    evidence_refs=[{"category": "agent_action", "ref": "gather"}],
                    before_ref="md5:a", after_ref="md5:b")
    e2 = make_event()  # no before/after
    e3 = make_event(action_type="move",
                    evidence_refs=[{"category": "agent_action", "ref": "move"}],
                    before_ref="md5:c", after_ref="md5:d")
    result = summarize_events([e1, e2, e3])
    assert result["mutation_count"] == 2


def test_mutation_count_only_before_ref():
    """before_ref truthy but after_ref falsy → not a mutation."""
    e = make_event(action_type="observe",
                   evidence_refs=[{"category": "observed_world_fact", "ref": "w1"}],
                   before_ref="md5:a", after_ref=None)
    result = summarize_events([e])
    assert result["mutation_count"] == 0


def test_mutation_count_only_after_ref():
    """after_ref truthy but before_ref falsy → not a mutation."""
    e = make_event(action_type="observe",
                   evidence_refs=[{"category": "observed_world_fact", "ref": "w1"}],
                   before_ref=None, after_ref="md5:b")
    result = summarize_events([e])
    assert result["mutation_count"] == 0


# ── 12. world_state_deltas observed only ──────────────────────────────


def test_world_state_deltas_observed_only():
    """Only observed-scope 'X is Y' summaries appear in deltas."""
    e_obs = make_event(claim_scope="observed", summary="water is 0.0", territory_ref="territoryA")
    e_speech = make_event(claim_scope="speech", action_type="whisper",
                          evidence_refs=[{"category": "agent_speech", "ref": "whisper"}],
                          summary="food is 5.0")
    e_hyp = make_event(claim_scope="hypothesis",
                        evidence_refs=[{"category": "agent_memory", "ref": "mem1"}],
                        summary="water is underground")
    result = summarize_events([e_obs, e_speech, e_hyp])
    assert len(result["world_state_deltas"]) == 1
    assert result["world_state_deltas"][0]["entity"] == "water"


def test_world_state_deltas_non_is_summary_skipped():
    """Observed event without 'X is Y' → no delta."""
    e = make_event(summary="Adam observed the area")
    result = summarize_events([e])
    assert result["world_state_deltas"] == []


def test_world_state_deltas_extracts_all_fields():
    """Delta entry contains all expected keys."""
    e = make_event(claim_scope="observed", summary="water is 0.0",
                   territory_ref="territoryA", tick=42, actor_id="east_adam")
    result = summarize_events([e])
    assert len(result["world_state_deltas"]) == 1
    d = result["world_state_deltas"][0]
    assert d["entity"] == "water"
    assert d["value"] == "0.0"
    assert d["territory_ref"] == "territoryA"
    assert d["tick"] == 42
    assert d["actor_id"] == "east_adam"
    assert d["event_id"] is not None


# ── 13. scope_filter ──────────────────────────────────────────────────


def test_scope_filter():
    """scope_filter returns only matching scope, total reflects filtered."""
    e1 = make_event(claim_scope="observed")
    e2 = make_event(claim_scope="speech", action_type="whisper",
                    evidence_refs=[{"category": "agent_speech", "ref": "whisper"}])
    e3 = make_event(claim_scope="observed")
    result = summarize_events([e1, e2, e3], scope_filter="observed")
    assert result["total_events"] == 2
    assert result["by_claim_scope"] == {"observed": 2}


# ── 14. actor_filter ──────────────────────────────────────────────────


def test_actor_filter():
    """actor_filter returns only matching actor."""
    e1 = make_event(actor_id="east_adam")
    e2 = make_event(actor_id="east_eve")
    e3 = make_event(actor_id="east_adam")
    result = summarize_events([e1, e2, e3], actor_filter="east_adam")
    assert result["total_events"] == 2
    assert result["by_actor"] == {"east_adam": 2}


# ── 15. territory_filter ──────────────────────────────────────────────


def test_territory_filter():
    """territory_filter returns only matching territory."""
    e1 = make_event(territory_ref="territoryA")
    e2 = make_event(territory_ref="territoryB")
    e3 = make_event(territory_ref="territoryA")
    result = summarize_events([e1, e2, e3], territory_filter="territoryA")
    assert result["total_events"] == 2
    assert result["by_territory"] == {"territoryA": 2}


# ── 16. tick_range_filter ─────────────────────────────────────────────


def test_tick_range_filter():
    """tick_start and tick_end filter correctly."""
    events = [make_event(tick=5), make_event(tick=10), make_event(tick=15)]
    result = summarize_events(events, tick_start=8, tick_end=12)
    assert result["total_events"] == 1
    assert result["recent_events"][0]["tick"] == 10


def test_tick_start_filters_out_none():
    """Events with None tick are excluded when tick_start is set."""
    e1 = make_event(tick=5)
    e2 = make_event(tick=None, timestamp_utc="2026-01-01T00:00:00Z")
    result = summarize_events([e1, e2], tick_start=1)
    assert result["total_events"] == 1


# ── 17. return_shape_has_expected_keys ────────────────────────────────


def test_return_shape_has_expected_keys():
    """Return dict contains all expected keys."""
    result = summarize_events([])
    expected_keys = {
        "total_events", "by_claim_scope", "by_action_type", "by_actor",
        "by_territory", "by_evidence_category", "recent_events",
        "tick_range", "mutation_count", "world_state_deltas",
    }
    assert set(result.keys()) == expected_keys
    assert isinstance(result["total_events"], int)
    assert isinstance(result["by_claim_scope"], dict)
    assert isinstance(result["by_action_type"], dict)
    assert isinstance(result["by_actor"], dict)
    assert isinstance(result["by_territory"], dict)
    assert isinstance(result["by_evidence_category"], dict)
    assert isinstance(result["recent_events"], list)
    assert isinstance(result["tick_range"], dict)
    assert isinstance(result["mutation_count"], int)
    assert isinstance(result["world_state_deltas"], list)