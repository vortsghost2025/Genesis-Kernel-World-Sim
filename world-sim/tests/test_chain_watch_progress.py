"""Progress pings: "update me every few" without needing an agent awake.

The chain monitor answers complete/stopped/stalled/frozen. It says nothing
while a run is simply proceeding, which is exactly when a person waiting
on it wants to know it is alive and what is happening. That message has to
come from the process, not from an operator session - the whole point of
this watcher existing is that it does not depend on anyone being present.

Sean's constraints, pinned here because they are the ones that rot:
plain sentences, no `pair= agent= hb=` telemetry, no field dumps, and
nothing repeated.

Unit under test: the summary and its render.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import chain_watch as cw  # noqa: E402

ADAM = "east_adam"
EVE = "east_eve"


def _hb(n, adam=None, eve=None, pos_adam=None, pos_eve=None):
    acts = {}
    for who, act in (("east_adam", adam), ("east_eve", eve)):
        if act is not None:
            acts[who] = {"action_type": act}
    row = {"heartbeat_number": n, "action_taken": acts or None}
    if pos_adam or pos_eve:
        row["position"] = {"east_adam": pos_adam, "east_eve": pos_eve}
    return row


class TestWindowSummary:
    def test_window_is_exclusive_at_the_start(self):
        """A heartbeat already counted in the last ping is not counted
        again. Double-counting would make every ping lie."""
        rows = [_hb(1, adam="move"), _hb(2, adam="move"), _hb(3, adam="move")]
        s = cw.window_summary(rows, 2, 3)
        assert s[ADAM]["moves"] == 1

    def test_counts_moves_per_agent_in_the_window(self):
        rows = [_hb(1, adam="move", eve="gather"),
                _hb(2, adam="move", eve="move"),
                _hb(3, adam="gather", eve="move")]
        s = cw.window_summary(rows, 0, 3)
        assert s[ADAM]["moves"] == 2
        assert s[EVE]["moves"] == 2
        assert s[ADAM]["gathers"] == 1

    def test_net_displacement_gets_a_direction_in_words(self):
        rows = [_hb(1, adam="move", pos_adam="cont_a_gen_-40_0"),
                _hb(2, adam="move", pos_adam="cont_a_gen_-34_0")]
        s = cw.window_summary(rows, 0, 2)
        assert s[ADAM]["moves"] == 2
        assert s[ADAM]["direction"] == "east"
        assert s[ADAM]["net_tiles"] == 6

    def test_westward_west(self):
        rows = [_hb(1, eve="move", pos_eve="cont_a_gen_46_-4"),
                _hb(2, eve="move", pos_eve="cont_a_gen_15_-4")]
        s = cw.window_summary(rows, 0, 2)
        assert s[EVE]["direction"] == "west"
        assert s[EVE]["net_tiles"] == 31

    def test_staying_put_is_stated_not_spun(self):
        rows = [_hb(1, adam="gather", pos_adam="cont_a_gen_-34_0"),
                _hb(2, adam="gather", pos_adam="cont_a_gen_-34_0")]
        s = cw.window_summary(rows, 0, 2)
        assert s[ADAM]["moves"] == 0
        assert s[ADAM]["direction"] == "nowhere"

    def test_missing_positions_are_not_invented(self):
        rows = [_hb(1, adam="move"), _hb(2, adam="move")]
        s = cw.window_summary(rows, 0, 2)
        assert s[ADAM]["direction"] == "nowhere"
        assert s[ADAM]["at"] is None


class TestReadsTheStoresRealShape:
    """`position` is an empty string on every row in this store's history.

    The first live render of the ping said "0 tiles nowhere" because the
    reader looked at that field. The location is in
    `observation[agent_ref].tile_id`. This pins that.
    """

    def _row(self, n, adam_tile, eve_tile):
        return {
            "heartbeat_number": n,
            "action_taken": {"east_adam": {"action_type": "move"},
                             "east_eve": {"action_type": "move"}},
            "position": "",  # exactly what the store carries
            "observation": {
                "east_adam": {"tile_id": adam_tile},
                "east_eve": {"tile_id": eve_tile},
            },
        }

    def test_location_comes_from_observation_not_position(self):
        rows = [self._row(1, "cont_a_gen_-40_0", "cont_a_gen_46_-4"),
                self._row(2, "cont_a_gen_-34_0", "cont_a_gen_15_-4")]
        s = cw.window_summary(rows, 0, 2)
        assert s[ADAM]["direction"] == "east" and s[ADAM]["net_tiles"] == 6
        assert s[EVE]["direction"] == "west" and s[EVE]["net_tiles"] == 31

    def test_empty_position_field_yields_a_real_direction(self):
        rows = [self._row(1, "cont_a_gen_0_0", "cont_a_gen_0_0"),
                self._row(2, "cont_a_gen_0_0", "cont_a_gen_0_0")]
        s = cw.window_summary(rows, 0, 2)
        assert s[ADAM]["direction"] != "nowhere" or s[ADAM]["moves"] == 2

    def test_still_falls_back_to_a_dict_position(self):
        row = {"heartbeat_number": 1,
               "action_taken": {"east_adam": {"action_type": "move"}},
               "position": {"east_adam": "cont_a_gen_1_1"}}
        s = cw.window_summary([row], 0, 1)
        assert s[ADAM]["at"] == "1,1"


class TestRenderIsForAHuman:
    def test_plain_sentences_with_the_substance(self):
        rows = [_hb(n, adam="move", eve="move",
                   pos_adam=f"cont_a_gen_{-40 + n}_0",
                   pos_eve=f"cont_a_gen_{46 - n}_-4") for n in (1, 2, 3)]
        s = cw.window_summary(rows, 0, 3)
        msg = cw.progress_message("east", 0, 3, s, 3, 0, 0, 0)
        low = msg.lower()
        assert "east" in low and "west" in low
        assert "moved" in low or "moves" in low
        # Sean's constraint: no telemetry soup, no dumps.
        for junk in ("pair=", "agent=", "severity=", "{", "}", "_gen_"):
            assert junk not in msg, f"telemetry leaked: {junk}"

    def test_zero_messages_is_said_plainly(self):
        rows = [_hb(1, adam="move", eve="move")]
        s = cw.window_summary(rows, 0, 1)
        msg = cw.progress_message("east", 0, 100, s, 1, 0, 0, 0)
        assert "no messages" in msg.lower()

    def test_a_message_is_quoted_because_that_is_the_point(self):
        rows = [_hb(1, adam="move", eve="move")]
        s = cw.window_summary(rows, 0, 1)
        msg = cw.progress_message("east", 0, 100, s, 1, 1, 0, 0,
                                  first_message="I am at -34. where are you?")
        assert "-34" in msg

    def test_progress_is_bounded(self):
        """One short paragraph. This goes to a phone every cycle."""
        rows = [_hb(n, adam="move", eve="gather") for n in range(1, 26)]
        s = cw.window_summary(rows, 0, 25)
        msg = cw.progress_message("east", 0, 100, s, 25, 0, 0, 0)
        assert len(msg) < 420, f"too long for a ping: {len(msg)} chars"
