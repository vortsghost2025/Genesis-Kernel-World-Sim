"""Completion wakes the operator session, not just the phone.

Sean described the working pattern directly: a scheduled turn fires, the
agent is brought back with information, and reports. The watch_bridge
already does this for ask/stuck signals - `opencode run -c <brief>`
resumes this session with the full context attached.

What was missing: a completed census told nobody but Telegram. The verdict
- did they speak, did the record's silence finally register - arrived as
a line on a phone with no operator turn behind it. This change makes a
completed run resume the session with the verdict, so the answer to "how
did it go" is a turn that already knows, not a message that waits.

Hard properties: the wake fires ONCE per completed run (the run ledger,
not another counter), is attached to the existing notification path so
a run that fails to notify doesn't wake anyone about nothing, and the
brief carries the digest so the resumed turn reports substance instead of
re-reading the whole store to find out what happened.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import chain_watch as cw  # noqa: E402


class TestWakeOnComplete:
    def test_complete_wakes_the_session_with_the_verdict(self, monkeypatch):
        monkeypatch.setattr(cw, "store_tick", lambda p: 1546)
        monkeypatch.setattr(cw, "pid_alive", lambda pid: False)
        monkeypatch.setattr(cw, "_seconds_since_last_evidence", lambda: 0.0)
        beats = [{"heartbeat_number": n,
                  "action_taken": {"east_adam": {"action_type": "move"}}}
                 for n in range(1400, 1600)]
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=60: beats)
        monkeypatch.setattr(cw, "run_health",
                            lambda r, *a, **k: {"verdict": "healthy",
                                                "inert_tail": 0,
                                                "last_active_heartbeat": 1599})
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (2, 0, 0, "where are you"))
        sent, wakes = [], []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        monkeypatch.setattr(cw, "already_sent", lambda k, s: False)
        monkeypatch.setattr(cw, "wake_operator", lambda b, run: (wakes.append(b), {'woken': True})[1])
        monkeypatch.setattr(cw, "mark_sent", lambda k, s: None)

        out = cw.monitor_once("east", 1447, 1546, None)
        assert out["state"] == "complete"
        assert len(wakes) == 1, "one wake per completion, not a stream"
        assert "where are you" in wakes[0]

    def test_running_never_wakes(self, monkeypatch):
        monkeypatch.setattr(cw, "store_tick", lambda p: 50)
        monkeypatch.setattr(cw, "pid_alive", lambda pid: True)
        monkeypatch.setattr(cw, "_seconds_since_last_evidence", lambda: 0.0)
        monkeypatch.setattr(cw, "load_heartbeats",
                            lambda p, limit=60: [{"heartbeat_number": 50,}])
        monkeypatch.setattr(cw, "run_health",
                            lambda r, *a, **k: {"verdict": "healthy",
                                                "inert_tail": 0,
                                                "last_active_heartbeat": 50})
        wakes = []
        monkeypatch.setattr(cw, "wake_operator", lambda b, run: (wakes.append(b), {'woken': True})[1])
        cw.monitor_once("east", 1, 200, 1)
        assert wakes == []

    def test_frozen_wakes_too_because_solution_lives_here(self, monkeypatch):
        """A frozen run is the one case where the verdict is 'come back and
        look'. Telegram alone leaves that to a phone while the work for it
        is mechanical diagnosis, which belongs in a turned session."""
        monkeypatch.setattr(cw, "store_tick", lambda p: 900)
        monkeypatch.setattr(cw, "pid_alive", lambda pid: False)
        monkeypatch.setattr(cw, "_seconds_since_last_evidence", lambda: 0.0)
        beats = [{"heartbeat_number": n, "action_taken": None}
                 for n in range(801, 901)]
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=60: beats)
        monkeypatch.setattr(cw, "run_health",
                            lambda r, *a, **k: {"verdict": "frozen",
                                                "inert_tail": 7,
                                                "last_active_heartbeat": 840})
        monkeypatch.setattr(cw, "last_stop_reason", lambda: "")
        sent, wakes = [], []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        monkeypatch.setattr(cw, "already_sent", lambda k, s: False)
        monkeypatch.setattr(cw, "wake_operator", lambda b, run: (wakes.append(b), {'woken': True})[1])
        monkeypatch.setattr(cw, "mark_sent", lambda k, s: None)
        out = cw.monitor_once("east", 800, 900, None)
        assert out["state"] == "frozen"
        assert len(wakes) == 1


class TestWakeIsIdempotent:
    def test_same_run_never_wakes_twice(self, monkeypatch):
        monkeypatch.setattr(cw, "store_tick", lambda p: 1546)
        monkeypatch.setattr(cw, "pid_alive", lambda pid: False)
        monkeypatch.setattr(cw, "_seconds_since_last_evidence", lambda: 0.0)
        beats = [{"heartbeat_number": n,
                  "action_taken": {"east_adam": {"action_type": "move"}}}
                 for n in range(1400, 1600)]
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=60: beats)
        monkeypatch.setattr(cw, "run_health",
                            lambda r, *a, **k: {"verdict": "healthy",
                                                "inert_tail": 0,
                                                "last_active_heartbeat": 1599})
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (0, 0, 0, ""))
        sent, wakes = [], []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        # The ledger already records the completion: the whole reason a
        # second poll must not wake again.
        monkeypatch.setattr(cw, "already_sent",
                            lambda k, s: s == "complete")
        monkeypatch.setattr(cw, "wake_operator", lambda b, run: (wakes.append(b), {'woken': True})[1])
        cw.monitor_once("east", 1447, 1546, None)
        assert wakes == []
