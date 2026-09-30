"""The frozen verdict must reach the operator, in plain language.

`run_health` (test_run_health.py) pins the arithmetic. These pin the
consequence: a run that reached its target with both agents inert is
reported as FROZEN, never as complete, and the message says the
heartbeats are not evidence about the agents.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import chain_watch as cw  # noqa: E402


def _hb(n, adam=None, eve=None):
    acts = {}
    for who, act in (("east_adam", adam), ("east_eve", eve)):
        if act is not None:
            acts[who] = {"action_type": act}
    return {"heartbeat_number": n, "action_taken": acts or None,
            "action_outcomes": {}}


class _StubStore:
    """Minimal heartbeat store stand-in for load_heartbeats."""

    def __init__(self, rows):
        self.rows = rows


class TestCompleteIsNotSuccess:
    def test_inert_tail_overrides_complete(self, monkeypatch):
        rows = [_hb(n) for n in range(1, 9)]
        monkeypatch.setattr(cw, "store_tick", lambda pair: 8)
        monkeypatch.setattr(cw, "pid_alive", lambda pid: False)
        monkeypatch.setattr(cw, "_seconds_since_last_evidence", lambda: 0.0)
        monkeypatch.setattr(cw, "load_heartbeats", lambda pair, limit=60: rows)
        sent = []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        monkeypatch.setattr(cw, "already_sent", lambda k, s: False)
        monkeypatch.setattr(cw, "mark_sent", lambda k, s: None)
        out = cw.monitor_once("east", 1, 8, None)
        assert out["state"] == "frozen"
        assert sent and "stopped acting" in sent[0]

    def test_live_run_still_reports_complete(self, monkeypatch):
        rows = [_hb(n, adam="move", eve="gather") for n in range(1, 9)]
        monkeypatch.setattr(cw, "store_tick", lambda pair: 8)
        monkeypatch.setattr(cw, "pid_alive", lambda pid: False)
        monkeypatch.setattr(cw, "_seconds_since_last_evidence", lambda: 0.0)
        monkeypatch.setattr(cw, "load_heartbeats", lambda pair, limit=60: rows)
        sent = []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        monkeypatch.setattr(cw, "already_sent", lambda k, s: False)
        monkeypatch.setattr(cw, "mark_sent", lambda k, s: None)
        out = cw.monitor_once("east", 1, 8, None)
        assert out["state"] == "complete"
        assert sent and "complete" in sent[0].lower()


class TestMessageIsForSean:
    def test_frozen_message_names_the_failure_not_the_census(self):
        msg = cw.terminal_message("frozen", "east", 1243, 1243, inert_tail=46)
        assert "stopped acting" in msg
        assert "not evidence" in msg.lower()
        assert "46 heartbeats" in msg

    def test_frozen_message_carries_no_telemetry_junk(self):
        """Sean's constraint: no `pair= agent= hb=` soup, no field dumps."""
        msg = cw.terminal_message("frozen", "east", 1243, 1243, inert_tail=46)
        for junk in ("pair=", "agent=", "severity=", "{"):
            assert junk not in msg, f"telemetry leaked into message: {junk}"


class TestHealthIsReported:
    def test_result_carries_the_health_verdict(self, monkeypatch):
        rows = [_hb(n) for n in range(1, 9)]
        monkeypatch.setattr(cw, "store_tick", lambda pair: 5)
        monkeypatch.setattr(cw, "pid_alive", lambda pid: True)
        monkeypatch.setattr(cw, "_seconds_since_last_evidence", lambda: 0.0)
        monkeypatch.setattr(cw, "load_heartbeats", lambda pair, limit=60: rows)
        sent = []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        monkeypatch.setattr(cw, "already_sent", lambda k, s: False)
        monkeypatch.setattr(cw, "mark_sent", lambda k, s: None)
        out = cw.monitor_once("east", 1, 8, 1)
        assert out["health"]["inert_tail"] == 8
        # Mid-run freeze must alert NOW, not at the end of the run. The
        # 46 dead heartbeats cost a night because the only alert came when
        # the paperwork finished.
        assert out["state"] == "frozen"
        assert sent and "HB5" in sent[0]

    def test_unreadable_store_is_not_a_frozen_world(self, monkeypatch):
        """The monitor must never invent death from its own read failure."""
        monkeypatch.setattr(cw, "store_tick", lambda pair: 5)
        monkeypatch.setattr(cw, "pid_alive", lambda pid: True)
        monkeypatch.setattr(cw, "_seconds_since_last_evidence", lambda: 0.0)
        monkeypatch.setattr(cw, "load_heartbeats", lambda pair, limit=60: [])
        monkeypatch.setattr(cw, "send_telegram_text", lambda t: (True, "ok"))
        out = cw.monitor_once("east", 1, 8, 1)
        assert out["state"] == "running"
        assert out["health"]["verdict"] == "unknown"
