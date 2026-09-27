"""Arc census export - the committed evidence for what the world did.

TDD suite for scripts/export_arc_census.py. Covers the census math over
synthetic stores (holdings split, knowledge growth, action census,
rejection tally, housekeeping detection) and the read-only guarantee
that matters most: exporting must not change the world it measures.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.export_arc_census import (
    arc_id,
    build_index,
    census_pair,
    export,
    food_units,
    goods_units,
    is_housekeeping,
    render_census,
)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")


def _hb(hb, actions=None, outcomes=None):
    return {
        "heartbeat_number": hb,
        "action_taken": actions or {},
        "action_outcomes": outcomes or {},
    }


class TestHoldingsMath:
    def test_food_and_goods_split(self):
        h = {"wild_berries": 3, "stone": 2, "fish": 1}
        assert food_units(h) == 4
        assert goods_units(h) == 2

    def test_malformed_ignored(self):
        assert food_units({"wild_berries": "x", "stone": True}) == 0
        assert food_units(None) == 0
        assert goods_units(None) == 0

    def test_zero_not_counted(self):
        assert food_units({"wild_berries": 0}) == 0


class TestHousekeepingDetection:
    def test_detects_the_phrases_the_agents_actually_used(self):
        assert is_housekeeping("Clay cairn built from excess clay inventory "
                               "to reduce goods overcapacity")
        assert is_housekeeping("Stone cairn built from excess stone inventory "
                               "to reduce goods overcapacity")

    def test_does_not_flag_ordinary_objects(self):
        assert not is_housekeeping("Woven fiber basket for storing gathered materials")
        assert not is_housekeeping("Test build on grassland - marker to verify")
        assert not is_housekeeping("")

    def test_is_case_insensitive(self):
        assert is_housekeeping("Built to REDUCE GOODS capacity")


class TestCensusPair:
    def _store(self, tmp_path, name="first-pair"):
        store = tmp_path / name
        store.mkdir(parents=True, exist_ok=True)
        return store

    def test_missing_store_is_tolerated(self, tmp_path):
        result = census_pair(tmp_path / "nope", 1, 10)
        assert result["agents"] == {}
        assert result["builds"] == []

    def test_counts_only_the_arc_window(self, tmp_path):
        store = self._store(tmp_path)
        _write(store / "heartbeat.json", {"data": [
            _hb(99, {"a": {"action_type": "gather"}}),
            _hb(100, {"a": {"action_type": "gather"}}),
            _hb(101, {"a": {"action_type": "move"}}),
            _hb(102, {"a": {"action_type": "move"}}),
        ]})
        result = census_pair(store, 100, 101)
        assert result["arc_ticks"] == 2
        assert result["actions"] == {"a:gather": 1, "a:move": 1}

    def test_tally_rejections_by_reason(self, tmp_path):
        store = self._store(tmp_path)
        hbs = [
            _hb(100 + i,
                {"a": {"action_type": "gather"}},
                {"a": {"status": "rejected", "reason": "No wild_berries available"}})
            for i in range(3)
        ]
        _write(store / "heartbeat.json", {"data": hbs})
        result = census_pair(store, 100, 200)
        assert result["rejections"]["No wild_berries available"] == 3

    def test_records_builds_with_materials_and_purpose(self, tmp_path):
        store = self._store(tmp_path)
        _write(store / "heartbeat.json", {"data": [
            _hb(802, {"a": {
                "action_type": "build", "object_type": "landmark",
                "object_id": "cairn-1", "materials": {"stone": 5},
                "description": "Stone cairn built to reduce goods overcapacity",
            }}),
        ]})
        result = census_pair(store, 800, 810)
        assert len(result["builds"]) == 1
        assert result["builds"][0]["housekeeping"] is True
        assert result["builds"][0]["heartbeat"] == 802

    def test_records_questions(self, tmp_path):
        store = self._store(tmp_path)
        _write(store / "heartbeat.json", {"data": [
            _hb(797, {"a": {
                "action_type": "ask_human", "urgency": "high",
                "question": "or is there a bug?"}}),
        ]})
        result = census_pair(store, 790, 800)
        assert result["asks"][0]["urgency"] == "high"

    def test_knowledge_growth_counts_first_observed_in_window(self, tmp_path):
        store = self._store(tmp_path)
        _write(store / "known_map_west_eve.json", {
            "agent_id": "x",
            "known_tiles": {
                "t1": {"first_observed_tick": 100},
                "t2": {"first_observed_tick": 805},
                "t3": {"first_observed_tick": 812},
            },
            "myths": {},
        })
        result = census_pair(store, 801, 900)
        info = result["known_tiles"]["west_eve"]
        assert info["total"] == 3
        assert info["new_in_arc"] == 2  # 805 and 812, not 100

    def test_myths_counted(self, tmp_path):
        store = self._store(tmp_path)
        _write(store / "known_map_a.json", {
            "known_tiles": {}, "myths": {"myst_x": {"status": "confirmed"}}})
        result = census_pair(store, 1, 100)
        assert result["known_tiles"]["a"]["myths"] == 1

    def test_holdings_recorded(self, tmp_path):
        store = self._store(tmp_path)
        _write(store / "inventory.json", {"data": {
            "east_adam": {"wild_berries": 1}}})
        result = census_pair(store, 1, 100)
        assert result["agents"]["east_adam"]["food"] == 1

    def test_corrupt_known_map_does_not_crash(self, tmp_path):
        store = self._store(tmp_path)
        (store / "known_map_bad.json").write_text("{not json", encoding="utf-8")
        result = census_pair(store, 1, 100)
        assert isinstance(result["known_tiles"], dict)


class TestRender:
    def test_renders_the_measures_and_totals(self):
        pairs = {"east": {
            "arc_ticks": 100, "tick_now": 900,
            "agents": {"a": {"food": 1, "goods": 0, "holdings": {"wild_berries": 1}}},
            "actions": {"a:gather": 50}, "rejections": {"No wild_berries": 12},
            "builds": [{"heartbeat": 802, "agent": "a", "object_type": "landmark",
                        "object_id": "x", "materials": {"stone": 1},
                        "description": "to reduce goods overcapacity",
                        "housekeeping": True}],
            "asks": [{"heartbeat": 803, "agent": "a", "question": "bug?",
                      "urgency": "high"}],
            "objects": [], "capability_requests": Counter(),
            "known_tiles": {"a": {"total": 12, "new_in_arc": 3, "myths": 0}},
        }}
        text = render_census(801, 900, pairs)
        assert "Arc census HB801-900" in text
        assert "new in arc" in text
        assert "housekeeping" in text
        assert "build attempts: **1**" in text
        assert "housekeeping-stated: **1**" in text
        assert "Read-only export" in text


class TestIndex:
    def test_arc_id_format(self):
        assert arc_id(801, 900) == "arc_0801_0900"
        assert arc_id(1, 2) == "arc_0001_0002"

    def test_index_lists_sorted_arcs(self, tmp_path, monkeypatch):
        import scripts.export_arc_census as mod
        arcs = tmp_path / "arcs"
        arcs.mkdir()
        (arcs / "arc_0801_0900.md").write_text("x", encoding="utf-8")
        (arcs / "arc_0701_0800.md").write_text("x", encoding="utf-8")
        (arcs / "README.md").write_text("x", encoding="utf-8")
        monkeypatch.setattr(mod, "ARCS_DIR", arcs)
        text = build_index()
        assert "arc_0701_0800.md" in text
        assert text.index("arc_0701_0800.md") < text.index("arc_0801_0900.md")
        assert "README.md](README.md)" not in text

    def test_export_writes_lf_only(self, tmp_path, monkeypatch):
        import scripts.export_arc_census as mod
        arcs = tmp_path / "arcs"
        store = tmp_path / "store"
        store.mkdir()
        _write(store / "heartbeat.json", {"data": [_hb(801)]})
        monkeypatch.setattr(mod, "ARCS_DIR", arcs)
        monkeypatch.setattr(mod, "PAIRS", {"east": store})
        result = export(801, 900)
        data = (arcs / "arc_0801_0900.md").read_bytes()
        assert b"\r\n" not in data
        assert result["written"] is True

    def test_export_never_touches_the_store(self, tmp_path, monkeypatch):
        import scripts.export_arc_census as mod
        arcs = tmp_path / "arcs"
        store = tmp_path / "store"
        store.mkdir()
        _write(store / "heartbeat.json", {"data": [
            _hb(801, {"a": {"action_type": "gather"}})]})
        _write(store / "inventory.json", {"data": {"a": {"stone": 3}}})
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in store.iterdir()}
        monkeypatch.setattr(mod, "ARCS_DIR", arcs)
        monkeypatch.setattr(mod, "PAIRS", {"east": store})
        export(801, 900)
        after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in store.iterdir()}
        assert before == after

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        import scripts.export_arc_census as mod
        arcs = tmp_path / "arcs"
        monkeypatch.setattr(mod, "ARCS_DIR", arcs)
        result = export(801, 900, dry_run=True)
        assert result["written"] is False
        assert not arcs.exists()
