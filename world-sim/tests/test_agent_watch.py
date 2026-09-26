"""Agent watch — the operator's early-warning system.

TDD suite for scripts/agent_watch.py. Covers pure scanning (asks, stuck
refusals, starvation, first builds, dead clocks), the dedupe ledger,
rendering, and delivery (durable log always; Telegram additive and
never required). The watcher is READ-ONLY: no test may leave a store
modified, and that property is asserted directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.agent_watch import (
    ALERT_LOG,
    STARVE_TICKS,
    STUCK_MIN_HITS,
    STUCK_WINDOW,
    dedupe,
    load_ledger,
    render,
    run_once,
    scan_all,
    scan_asks,
    scan_dead,
    scan_first_build,
    scan_starving,
    scan_stuck,
    send_telegram,
    split_ledgers,
    telegram_config,
)


def _store(tmp_path: Path, name: str = "first-pair") -> Path:
    store = tmp_path / name
    store.mkdir(parents=True, exist_ok=True)
    return store


def _write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")


def _heartbeat(hb: int, actions=None, outcomes=None) -> dict:
    return {
        "heartbeat_number": hb,
        "action_taken": actions or {},
        "action_outcomes": outcomes or {},
        "world_mutations": [],
    }


# ---------------------------------------------------------------------------
# Ledger math
# ---------------------------------------------------------------------------


class TestSplitLedgers:
    def test_food_vs_goods(self):
        assert split_ledgers({"wild_berries": 3, "stone": 2}) == {"food": 3, "goods": 2}

    def test_malformed_is_zero(self):
        assert split_ledgers({"wild_berries": "x", "stone": True}) == {"food": 0, "goods": 0}
        assert split_ledgers(None) == {"food": 0, "goods": 0}


# ---------------------------------------------------------------------------
# Asks
# ---------------------------------------------------------------------------


class TestScanAsks:
    def test_unheard_ask_fires(self, tmp_path):
        store = _store(tmp_path)
        _write(store / "agent_questions.json", {"data": [{
            "question_id": "q1", "agent_ref": "west_eve", "heartbeat": 723,
            "urgency": "high", "status": "unheard",
            "question": "Why is build refused?",
        }]})
        signals = scan_asks("west", store)
        assert len(signals) == 1
        assert signals[0]["kind"] == "ask"
        assert signals[0]["severity"] == "high"
        assert signals[0]["key"] == "west:ask:q1"
        assert "build refused" in signals[0]["body"]

    def test_heard_ask_does_not_fire(self, tmp_path):
        store = _store(tmp_path)
        _write(store / "agent_questions.json", {"data": [{
            "question_id": "q1", "agent_ref": "west_eve", "heartbeat": 723,
            "urgency": "high", "status": "heard", "question": "x",
        }]})
        assert scan_asks("west", store) == []

    def test_no_file_no_signal(self, tmp_path):
        assert scan_asks("west", _store(tmp_path)) == []


# ---------------------------------------------------------------------------
# Stuck detection
# ---------------------------------------------------------------------------


class TestScanStuck:
    def test_repeated_refusal_fires(self, tmp_path):
        store = _store(tmp_path)
        hbs = [
            _heartbeat(
                100 + i,
                actions={"west_eve": {"action_type": "build"}},
                outcomes={"west_eve": {"status": "rejected",
                                       "reason": "Tile x not in allowed tiles"}},
            )
            for i in range(STUCK_MIN_HITS)
        ]
        _write(store / "heartbeat.json", {"data": hbs})
        signals = scan_stuck("west", store)
        assert len(signals) == 1
        assert signals[0]["kind"] == "stuck"
        assert signals[0]["agent"] == "west_eve"
        assert "not in allowed tiles" in signals[0]["body"]

    def test_scattered_refusals_below_threshold_stay_quiet(self, tmp_path):
        store = _store(tmp_path)
        hbs = [
            _heartbeat(
                100 + i * 2,
                actions={"west_eve": {"action_type": "build"}},
                outcomes={"west_eve": {"status": "rejected", "reason": "nope"}},
            )
            for i in range(3)
        ]
        _write(store / "heartbeat.json", {"data": hbs})
        assert scan_stuck("west", store) == []

    def test_outside_window_ignored(self, tmp_path):
        store = _store(tmp_path)
        # refusals happened long ago; the clock has since moved on
        hbs = [
            _heartbeat(100 + i, actions={"a": {"action_type": "build"}},
                       outcomes={"a": {"status": "rejected", "reason": "old"}})
            for i in range(20)
        ]
        hbs.append(_heartbeat(100 + 20 + STUCK_WINDOW + 5))
        _write(store / "heartbeat.json", {"data": hbs})
        assert scan_stuck("west", store) == []

    def test_successes_do_not_count(self, tmp_path):
        store = _store(tmp_path)
        hbs = [
            _heartbeat(100 + i, actions={"a": {"action_type": "gather"}},
                       outcomes={"a": {"status": "success"}})
            for i in range(20)
        ]
        _write(store / "heartbeat.json", {"data": hbs})
        assert scan_stuck("west", store) == []


# ---------------------------------------------------------------------------
# Starvation
# ---------------------------------------------------------------------------


class TestScanStarving:
    def test_foodless_agent_fires(self, tmp_path):
        store = _store(tmp_path)
        _write(store / "inventory.json", {"data": {
            "west_eve": {"fiber_plants": 51},
            "west_adam": {"stone": 3, "wild_berries": 2},
        }})
        _write(store / "heartbeat.json", {"data": [_heartbeat(700 + i) for i in range(20)]})
        signals = scan_starving("west", store)
        assert len(signals) == 1
        assert signals[0]["agent"] == "west_eve"

    def test_fed_agent_quiet(self, tmp_path):
        store = _store(tmp_path)
        _write(store / "inventory.json", {"data": {"a": {"wild_berries": 1}}})
        _write(store / "heartbeat.json", {"data": [_heartbeat(700 + i) for i in range(20)]})
        assert scan_starving("west", store) == []

    def test_missing_files_quiet(self, tmp_path):
        assert scan_starving("west", _store(tmp_path)) == []


# ---------------------------------------------------------------------------
# First build
# ---------------------------------------------------------------------------


class TestScanFirstBuild:
    def test_material_bearing_object_fires(self, tmp_path):
        store = _store(tmp_path)
        _write(store / "world_state.json", {"data": {"public_objects": {
            "wall-001": {
                "object_id": "wall-001", "object_type": "wall",
                "public_description": "A low wall.", "created_heartbeat": 712,
                "materials": {"stone": 5},
            },
        }}})
        signals = scan_first_build("west", store)
        assert len(signals) == 1
        assert signals[0]["kind"] == "first_build"
        assert "wall" in signals[0]["title"]

    def test_legacy_object_without_materials_ignored(self, tmp_path):
        store = _store(tmp_path)
        _write(store / "world_state.json", {"data": {"public_objects": {
            "meeting-stone-center": {
                "object_id": "meeting-stone-center", "object_type": "landmark",
                "public_description": "founded at heartbeat 7",
            },
        }}})
        assert scan_first_build("east", store) == []


# ---------------------------------------------------------------------------
# Dead clock
# ---------------------------------------------------------------------------


class TestScanDead:
    def test_idle_store_fires(self, tmp_path):
        store = _store(tmp_path)
        _write(store / "world_state.json", {"data": {
            "tick": 758, "updated_at_utc": "2020-01-01T00:00:00+00:00"}})
        signals = scan_dead("west", store, idle_minutes=1)
        assert len(signals) == 1
        assert signals[0]["kind"] == "dead"

    def test_fresh_store_quiet(self, tmp_path):
        from datetime import datetime, timezone
        store = _store(tmp_path)
        _write(store / "world_state.json", {"data": {
            "tick": 800,
            "updated_at_utc": datetime.now(timezone.utc).isoformat()}})
        assert scan_dead("west", store, idle_minutes=8) == []

    def test_unparseable_stamp_quiet(self, tmp_path):
        store = _store(tmp_path)
        _write(store / "world_state.json", {"data": {
            "tick": 1, "updated_at_utc": "not-a-date"}})
        assert scan_dead("west", store, idle_minutes=1) == []


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


class TestDedupe:
    def test_first_sight_fires_once(self):
        sigs = [{"key": "k1", "kind": "ask", "pair": "west", "severity": "high",
                 "agent": "a", "heartbeat": 1, "title": "t", "body": "b"}]
        fresh, fired = dedupe(sigs, {})
        assert len(fresh) == 1
        fresh2, fired2 = dedupe(sigs, fired)
        assert fresh2 == []
        assert fired2["k1"]["kind"] == "ask"

    def test_distinct_keys_all_fire(self):
        sigs = [{"key": f"k{i}", "kind": "ask", "pair": "west", "severity": "low",
                 "agent": "a", "heartbeat": 1, "title": "t", "body": ""}
                for i in range(3)]
        fresh, _ = dedupe(sigs, {})
        assert len(fresh) == 3

    def test_ledger_never_loses_prior_keys(self):
        prior = {"old": {"fired_at_utc": "x", "kind": "ask", "pair": "east"}}
        fresh, fired = dedupe(
            [{"key": "new", "kind": "dead", "pair": "west", "severity": "high",
              "agent": "-", "heartbeat": 1, "title": "t", "body": ""}], prior)
        assert "old" in fired and "new" in fired

    def test_load_ledger_missing_file_is_empty(self, tmp_path):
        assert load_ledger(tmp_path / "nope.json") == {}


# ---------------------------------------------------------------------------
# Render + delivery
# ---------------------------------------------------------------------------


class TestRenderAndDeliver:
    def test_render_contains_the_essentials(self):
        sig = {"severity": "high", "title": "T", "pair": "west",
               "agent": "west_eve", "heartbeat": 723, "body": "B",
               "reply_hint": "H"}
        text = render(sig)
        assert "[HIGH] T" in text
        assert "west_eve" in text and "723" in text
        assert "B" in text and "-> H" in text

    def test_telegram_unconfigured_is_not_an_error(self):
        ok, detail = send_telegram({"severity": "low", "title": "t", "pair": "p",
                                     "agent": "a", "heartbeat": 1},
                                    token="", chat_id="")
        assert ok is False
        assert "not configured" in detail

    def test_telegram_config_reads_env(self):
        token, chat_id = telegram_config(
            {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"})
        assert (token, chat_id) == ("t", "c")

    def test_never_writes_the_store(self, tmp_path):
        """The watcher's core guarantee."""
        from scripts import agent_watch
        store = _store(tmp_path)
        _write(store / "inventory.json", {"data": {"a": {"stone": 1}}})
        _write(store / "heartbeat.json", {"data": [_heartbeat(1)]})
        _write(store / "world_state.json", {"data": {"tick": 1}})
        before = {
            p.name: (p.read_bytes(), p.stat().st_mtime_ns)
            for p in store.iterdir()
        }
        agent_watch.scan_all(pairs={"east": store})
        after = {
            p.name: (p.read_bytes(), p.stat().st_mtime_ns)
            for p in store.iterdir()
        }
        assert before == after
        assert sorted(before) == sorted(after)

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch, capsys):
        from scripts import agent_watch
        store = _store(tmp_path)
        _write(store / "agent_questions.json", {"data": [{
            "question_id": "q", "agent_ref": "a", "heartbeat": 1,
            "urgency": "low", "status": "unheard", "question": "why"}]})
        monkeypatch.setattr(agent_watch, "PAIRS", {"east": store})
        monkeypatch.setattr(agent_watch, "SCRATCH", tmp_path / "scratch")
        monkeypatch.setattr(agent_watch, "STATE_PATH", tmp_path / "scratch" / "l.json")
        monkeypatch.setattr(agent_watch, "ALERT_LOG", tmp_path / "scratch" / "a.log")
        status = agent_watch.run_once(dry_run=True)
        assert "[DRY-RUN]" in capsys.readouterr().out
        assert not (tmp_path / "scratch" / "l.json").exists()
        assert not (tmp_path / "scratch" / "a.log").exists()
        assert status["alerts_logged"] == 0

    def test_alert_is_logged_and_deduped(self, tmp_path, monkeypatch):
        from scripts import agent_watch
        store = _store(tmp_path)
        _write(store / "agent_questions.json", {"data": [{
            "question_id": "q", "agent_ref": "a", "heartbeat": 1,
            "urgency": "high", "status": "unheard", "question": "why not"}]})
        monkeypatch.setattr(agent_watch, "PAIRS", {"east": store})
        monkeypatch.setattr(agent_watch, "SCRATCH", tmp_path / "scratch")
        monkeypatch.setattr(agent_watch, "STATE_PATH", tmp_path / "scratch" / "l.json")
        monkeypatch.setattr(agent_watch, "ALERT_LOG", tmp_path / "scratch" / "a.log")
        monkeypatch.setattr(agent_watch, "STATUS_PATH", tmp_path / "scratch" / "s.json")
        first = agent_watch.run_once()
        assert first["alerts_logged"] == 1
        assert first["telegram_sent"] == 0
        assert first["telegram_configured"] is False
        assert "why not" in (tmp_path / "scratch" / "a.log").read_text(encoding="utf-8")
        second = agent_watch.run_once()
        assert second["alerts_logged"] == 0

    def test_scanner_survives_corrupt_files(self, tmp_path, monkeypatch):
        from scripts import agent_watch
        store = _store(tmp_path)
        (store / "heartbeat.json").write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(agent_watch, "PAIRS", {"east": store})
        signals = agent_watch.scan_all()
        assert any(s["kind"] == "watcher_error" for s in signals)

    def test_empty_heartbeat_list_is_safe(self, tmp_path):
        store = _store(tmp_path)
        _write(store / "heartbeat.json", {"data": []})
        _write(store / "inventory.json", {"data": {}})
        assert scan_stuck("east", store) == []
        assert scan_starving("east", store) == []
