"""Tests for the mystery reveal mechanic (scratch-only, pure).

Proves the hard guarantees: no leak before threshold, occupancy-only
accrual, one accrual per tick, exact reveal at threshold, idempotence,
per-agent independence, prompt-safe projection, fail-closed on unknown
kinds.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "mystery_reveal", WORLD_SIM / "scripts" / "world_content" / "mystery_reveal.py")
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)

ECHO = {"mystery_id": "mst_east_echo", "tile_id": "cont_a_east_000",
        "kind": "repeating_sound", "reveal_threshold": 3}
LIGHT = {"mystery_id": "mst_west_light", "tile_id": "cont_b_west_001",
         "kind": "distant_light", "reveal_threshold": 3}


def fresh_map(agent_id="east_adam"):
    return {
        "schema_version": "7B.1", "agent_id": agent_id,
        "known_tiles": {}, "known_landmarks": {}, "named_places": {},
        "routes": [], "hypotheses": [], "myths": [], "contact_evidence": [],
        "last_observation_tick": 0,
    }


def on_tile(tile):
    return {"tile_id": tile, "agent_id": "east_adam", "active": True,
            "schema_version": "7B.1", "continent_id": "cont_a",
            "region_id": None, "coordinates": {"x": 0, "y": 0},
            "facing": "north", "movement_mode": "walk",
            "travel_capabilities": ["walk_local"], "last_moved_tick": 0}


def test_no_evidence_no_projection():
    km = fresh_map()
    assert mr.project_unsettled_reports(km) == []
    assert not mr.check_reveal(km, ECHO)


def test_occupancy_only_accrues():
    km = fresh_map()
    km, acc = mr.accrue_mystery_evidence(km, ECHO, on_tile("cont_a_origin_000"), 5)
    assert not acc  # on a different tile: nothing accrues
    assert km["myths"] == []
    assert mr.project_unsettled_reports(km) == []


def test_first_visit_gives_vague_hint_no_reveal():
    km = fresh_map()
    km, acc = mr.accrue_mystery_evidence(km, ECHO, on_tile("cont_a_east_000"), 10)
    assert acc
    reports = mr.project_unsettled_reports(km)
    assert len(reports) == 1
    txt = reports[0]["report"].lower()
    assert "tone" in txt or "sound" in txt
    # absolutely no identifiers / mechanism words in agent-facing text
    for bad in mr.FORBIDDEN_PROJECTION_SUBSTRINGS:
        assert bad not in reports[0]["report"]
    assert not mr.check_reveal(km, ECHO)
    km2, lm = mr.apply_reveal(km, ECHO, 10)
    assert lm is None and km2["known_landmarks"] == {}


def test_reveal_exactly_at_threshold():
    km = fresh_map()
    for tick in (10, 11, 12):  # three visits
        km, _ = mr.accrue_mystery_evidence(km, ECHO, on_tile("cont_a_east_000"), tick)
    assert mr.check_reveal(km, ECHO)
    km, lm = mr.apply_reveal(km, ECHO, 12)
    assert lm is not None
    assert lm["kind"] == "singing_rock"
    assert "Singing Stone" in lm["description"]
    myth = next(m for m in km["myths"] if m["id"] == "myth_mst_east_echo")
    assert myth["status"] == "confirmed"
    # the myth is no longer a live 'unsettled report'
    assert mr.project_unsettled_reports(km) == []


def test_reveal_idempotent():
    km = fresh_map()
    for tick in (10, 11, 12):
        km, _ = mr.accrue_mystery_evidence(km, ECHO, on_tile("cont_a_east_000"), tick)
    km, first = mr.apply_reveal(km, ECHO, 12)
    km, second = mr.apply_reveal(km, ECHO, 13)
    assert first is not None and second is None
    assert len(km["known_landmarks"]) == 1


def test_one_accrual_per_tick():
    km = fresh_map()
    km, a1 = mr.accrue_mystery_evidence(km, ECHO, on_tile("cont_a_east_000"), 10)
    km, a2 = mr.accrue_mystery_evidence(km, ECHO, on_tile("cont_a_east_000"), 10)
    assert a1 and not a2
    rec = km["myths"][0]
    assert rec["evidence"] == 1


def test_hint_deepens_before_reveal():
    km = fresh_map()
    km, _ = mr.accrue_mystery_evidence(km, ECHO, on_tile("cont_a_east_000"), 10)
    first = mr.project_unsettled_reports(km)[0]["report"]
    km, _ = mr.accrue_mystery_evidence(km, ECHO, on_tile("cont_a_east_000"), 11)
    second = mr.project_unsettled_reports(km)[0]["report"]
    assert first != second  # the story deepens
    assert not mr.check_reveal(km, ECHO)  # but stays vague


def test_per_agent_independence():
    adam = fresh_map("east_adam")
    eve = fresh_map("east_eve")
    for tick in (10, 11, 12):
        adam, _ = mr.accrue_mystery_evidence(adam, ECHO, on_tile("cont_a_east_000"), tick)
    adam, lm = mr.apply_reveal(adam, ECHO, 12)
    assert lm is not None
    assert mr.project_unsettled_reports(eve) == []
    eve, lm_e = mr.apply_reveal(eve, ECHO, 12)
    assert lm_e is None


def test_unknown_kind_fails_closed():
    weird = {"mystery_id": "mst_unknown", "tile_id": "x",
             "kind": "unauthored_kind", "reveal_threshold": 1}
    km = fresh_map()
    km, acc = mr.accrue_mystery_evidence(km, weird, on_tile("x"), 1)
    # unknown kind: nothing accrues, nothing reveals, nothing crashes
    assert not acc and km["myths"] == []
    km2, lm = mr.apply_reveal(km, weird, 1)
    assert lm is None


def test_projection_drops_contaminated_claim():
    km = fresh_map()
    km["myths"].append({
        "id": "myth_bad", "created_tick": 1, "basis": "test",
        "claim": "the mystery_id is mst_east_echo", "confidence": 0.5,
        "status": "gathering",
    })
    # a contaminated claim is dropped, never shown
    assert mr.project_unsettled_reports(km) == []


def test_both_canonical_mysteries_have_content():
    for m in (ECHO, LIGHT):
        assert m["kind"] in mr.MYSTERY_LIBRARY
        assert set(mr.MYSTERY_LIBRARY[m["kind"]]["hints"]).issuperset({1, 2})
        assert mr.MYSTERY_LIBRARY[m["kind"]]["reveal"]["name"]
