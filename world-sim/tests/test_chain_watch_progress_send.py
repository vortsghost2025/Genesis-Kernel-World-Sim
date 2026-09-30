"""The ping must be sent by the process, exactly once per window.

A progress ping that repeats is worse than none: it trains the reader to
ignore the channel, and the terminal alerts share that channel. These pin
the dedup and the not-due rules, and pin that a real window renders
substance rather than a placeholder.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import chain_watch as cw  # noqa: E402


def _hb(n, adam=None, eve=None, pos_adam=None, pos_eve=None):
    acts = {}
    for who, act in (("east_adam", adam), ("east_eve", eve)):
        if act is not None:
            acts[who] = {"action_type": act}
    row = {"heartbeat_number": n, "action_taken": acts or None}
    if pos_adam or pos_eve:
        row["position"] = {"east_adam": pos_adam, "east_eve": pos_eve}
    return row


class TestDueLogic:
    def test_nothing_is_due_before_the_first_boundary(self, monkeypatch):
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=60: [])
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (0, 0, 0, ""))
        sent = []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        monkeypatch.setattr(cw, "mark_sent", lambda k, s: None)
        out = cw.maybe_send_progress("east", 100, 200, 110, every=25)
        assert out["sent"] is False
        assert sent == []

    def test_due_at_the_boundary(self, monkeypatch):
        beats = [_hb(n, adam="move", pos_adam=f"cont_a_gen_{n}_0")
                 for n in range(101, 126)]
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=60: beats)
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (2, 0, 0, "I am here."))
        sent = []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        monkeypatch.setattr(cw, "already_sent", lambda k, s: False)
        monkeypatch.setattr(cw, "mark_sent", lambda k, s: None)
        out = cw.maybe_send_progress("east", 100, 200, 125, every=25)
        assert out["sent"] is True
        assert len(sent) == 1
        assert "I am here." in sent[0]

    def test_same_window_is_never_sent_twice(self, monkeypatch):
        beats = [_hb(n, adam="move") for n in range(101, 126)]
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=60: beats)
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (0, 0, 0, ""))
        sent = []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        # Already delivered for window 1.
        monkeypatch.setattr(cw, "already_sent",
                            lambda k, s: s == "progress:1")
        monkeypatch.setattr(cw, "mark_sent", lambda k, s: None)
        out = cw.maybe_send_progress("east", 100, 200, 130, every=25)
        assert out["sent"] is False
        assert sent == []

    def test_a_failed_send_is_retried_not_lost(self, monkeypatch):
        """A message that did not go out must not be marked as sent. The
        operator is relying on this channel; silently dropping a ping
        would be the same class of failure as the frozen run."""
        beats = [_hb(n, adam="move") for n in range(101, 126)]
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=60: beats)
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (0, 0, 0, ""))
        marked = []
        monkeypatch.setattr(cw, "send_telegram_text", lambda t: (False, "boom"))
        monkeypatch.setattr(cw, "already_sent", lambda k, s: False)
        monkeypatch.setattr(cw, "mark_sent", lambda k, s: marked.append(s))
        out = cw.maybe_send_progress("east", 100, 200, 125, every=25)
        assert out["sent"] is False
        assert marked == [], "an undelivered ping must stay due"

    def test_zero_disables_pings_entirely(self, monkeypatch):
        beats = [_hb(n, adam="move") for n in range(101, 126)]
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=60: beats)
        sent = []
        monkeypatch.setattr(cw, "send_telegram_text",
                            lambda t: (sent.append(t), (True, "ok"))[1])
        out = cw.maybe_send_progress("east", 100, 200, 125, every=0)
        assert out["sent"] is False
        assert sent == []


class TestWindowCounts:
    def test_reads_the_world_state_not_a_guess(self, tmp_path, monkeypatch):
        (tmp_path / "world_state.json").write_text(
            '{"data": {"public_messages": ['
            '{"heartbeat": 110, "message": "hello"},'
            '{"heartbeat": 115, "message": "anyone?"}],'
            '"public_objects": {"a": {"created_heartbeat": 112},'
            '"b": {"created_heartbeat": 90}},'
            '"questions_raised": [{"heartbeat": 120}]}}',
            encoding="utf-8")
        monkeypatch.setitem(cw.STORES, "east", tmp_path)
        n_msgs, n_objs, n_asks, first = cw.window_counts("east", 100, 125)
        assert (n_msgs, n_objs, n_asks) == (2, 1, 1)
        assert first == "hello"

    def test_unreadable_store_is_zero_not_an_exception(self, tmp_path,
                                                       monkeypatch):
        monkeypatch.setitem(cw.STORES, "east", tmp_path)
        assert cw.window_counts("east", 100, 125) == (0, 0, 0, "")
