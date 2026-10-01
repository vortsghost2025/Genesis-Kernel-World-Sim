"""A completion ping that arrives saying only 'done' is not the result.

The operator asked for an update in 100 heartbeats. I cannot wake to
deliver it. What the monitor CAN do is not merely announce a terminal
state but deliver the VERDICT the run was measuring - did they speak, did
'unresponsive' leave their reasoning, did they come within sight of each
other - the questions the change was testing.

Unit under test: completion_digest, which assembles that verdict from the
store, and the completion message that carries it.
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
    row = {"heartbeat_number": n, "action_taken": acts or None,
           "decision_summaries": {}}
    if pos_adam or pos_eve:
        row["observation"] = {
            "east_adam": {"tile_id": pos_adam}, "east_eve": {"tile_id": pos_eve},
        }
        row["position"] = {"east_adam": pos_adam, "east_eve": pos_eve}
    return row, row


class TestDigestContents:
    def test_zero_messages_is_said_as_zero(self, monkeypatch):
        beats = [(_hb(n, adam="move", eve="gather"))[0]
                 for n in range(1447, 1501)]
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=0: beats)
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (0, 0, 0, ""))
        out = cw.completion_digest("east", 1447, 1546)
        assert "no messages" in out.lower()

    def test_a_message_is_the_verdict_not_a_count(self, monkeypatch):
        beats = [(_hb(n, adam="move", eve="move",
                    pos_adam=f"cont_a_gen_{n}_0",
                    pos_eve=f"cont_a_gen_{46 - n}_-4"))[0]
                 for n in range(1447, 1460)]
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=0: beats)
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (1, 0, 0,
                                             "I am here. Where are you?"))
        out = cw.completion_digest("east", 1447, 1546)
        assert "I am here" in out
        assert "1 message" in out

    def test_unresponsive_in_reasoning_is_reported(self, monkeypatch):
        """The falsifiable row: that framing appearing in their own
        reasoning is the thing the change was supposed to kill - and when
        it is still there the verdict must say so, in plain language,
        without echoing the word back as the verdict itself."""
        row, _ = _hb(1500, adam="move", eve="gather")
        row["decision_summaries"] = {"east_adam": "Eve is unresponsive"}
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=0: [row])
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (0, 0, 0, ""))
        out = cw.completion_digest("east", 1447, 1546)
        assert "still names being unanswered" in out.lower(), out

    def test_absent_unresponsive_is_also_a_verdict(self, monkeypatch):
        row, _ = _hb(1500, adam="move", eve="gather")
        row["decision_summaries"] = {"east_adam": "walking east"}
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=0: [row])
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (0, 0, 0, ""))
        out = cw.completion_digest("east", 1447, 1546)
        assert "unresponsive" not in out.lower()
        assert "no longer names" in out.lower() or "gone" in out.lower(), (
            "absence is itself the verdict and must be stated")

    def test_unreadable_store_is_unknown_not_a_claim(self, monkeypatch):
        monkeypatch.setattr(cw, "load_heartbeats", lambda p, limit=0: [])
        monkeypatch.setattr(cw, "window_counts",
                            lambda p, a, b: (_ for _ in ()).throw(
                                AssertionError("must not be called")))
        out = cw.completion_digest("east", 1447, 1546)
        assert "cannot" in out.lower() or "unreadable" in out.lower()
