"""Comfort physics - epistemic.6: the shelter bonus.

The design question from Sean: shelter was purely damage control
(less cold, no rain) with zero upside in fine weather. Now inside a
shelter the body holds warmth near 45 however cold it is outside, and
rest inside heals twice as fast. Summer days make shelters optional;
winter nights and storms make them the warm dry good place.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival as sv  # noqa: E402


class TestComfortFloor:
    def test_winter_night_inside_is_warm_outside_is_lethal(self):
        """The whole point: same night, two tiles apart, one tile has a
        wall. Inside holds near the floor; outside sinks toward 13."""
        winter_mid = sv.ambient_temperature(sv.SEASON_LENGTH * 3)
        inside, outside = 20.0, 20.0
        for _ in range(10):
            inside = sv.warmth_next(inside, winter_mid, by_fire=False,
                                    in_shelter=True)
            outside = sv.warmth_next(outside, winter_mid, by_fire=False,
                                     in_shelter=False)
        assert inside > 34.0, "shelter insulation must warm toward 45"
        assert outside < 17.0, "outside must keep sinking"
        assert inside - outside > 15.0

    def test_floor_never_exceeds_mild_weather(self):
        """The floor is a floor, not a heater for summer: a warm day
        outside is warmer than the floor, and shelter does not cool
        the day."""
        summer_day = sv.ambient_temperature(sv.SEASON_LENGTH + 36)
        sheltered = sv.warmth_next(80.0, summer_day, by_fire=False,
                                   in_shelter=True)
        assert sheltered >= 70.0, "warm day inside stays warm"

    def test_floor_never_exceeds_100(self):
        v = sv.warmth_next(99.0, 5.0, by_fire=False, in_shelter=True)
        assert v <= 100.0


class TestRest:
    def test_rest_inside_heals_twice_as_fast(self):
        fed, warm = 30.0, 80.0
        gain_in = sv.vitality_next(50.0, fed, warm, False, True) - 50.0
        gain_out = sv.vitality_next(50.0, fed, warm, False, False) - 50.0
        assert gain_in == gain_out * 2

    def test_downed_body_recovers_faster_in_shelter(self):
        gain_in = sv.vitality_next(5.0, 30.0, 80.0, True, True) - 5.0
        gain_out = sv.vitality_next(5.0, 30.0, 80.0, True, False) - 5.0
        assert gain_in > gain_out * 2

    def test_neglect_still_drains_inside(self):
        """Comfort is not a force field: starving still drains, even
        inside. The floor protects warmth, not neglect."""
        v = sv.vitality_next(50.0, 99.0, 80.0, False, in_shelter=True)
        assert v < 50.0


class TestFullArc:
    def test_sheltered_winter_night_is_survivable_and_comfortable(self):
        """An unsheltered body sinks toward freezing; a sheltered one
        settles at the floor. Same storm, two tiles apart."""
        v_out, v_in = sv.initial_vitals(), sv.initial_vitals()
        v_out["warmth"] = 40.0
        v_in["warmth"] = 40.0
        hb = sv.SEASON_LENGTH * 3 + 36  # winter, deep night
        for i in range(30):
            t = hb + i
            v_out = sv.apply_heartbeat(v_out, t, by_fire=False,
                                       in_shelter=False, weather="rain")
            v_in = sv.apply_heartbeat(v_in, t, by_fire=False,
                                      in_shelter=True, weather="rain")
        assert v_out["warmth"] < 26.5, "exposed in rain: sinking to the edge"
        assert v_in["warmth"] >= 40.0, "sheltered in rain: holds"
        assert v_in["wetness"] == 0.0, "shelter blocks the rain"
        assert v_out["wetness"] == 100.0, "exposed: soaked"
