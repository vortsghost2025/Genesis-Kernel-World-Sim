"""Survival physics arithmetic — the body, epistemic.4.

The design invariant that matters most: SLACK. The retired pressure
model pinned east_adam at zero food for 100+ heartbeats and he
correctly called it a bug. These tests pin the guarantee that the new
pressure creates purpose (expeditions, stockpiles, camps) and never
famine: from full hunger, a gather trip must net more than it costs.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival as sv  # noqa: E402


class TestTheClock:
    def test_day_night_cycle_shape(self):
        assert sv.is_night(0) is True          # phase 0.0 = deep night
        assert sv.is_night(sv.DAY_LENGTH // 2) is False  # noon
        assert sv.is_night(int(sv.DAY_LENGTH * 0.9)) is True
        assert sv.is_night(int(sv.DAY_LENGTH * 0.5)) is False

    def test_noon_is_warmest_and_midnight_coldest(self):
        noon = sv.ambient_temperature(sv.DAY_LENGTH // 2)
        midnight = sv.ambient_temperature(0)
        assert noon > midnight

    def test_seasons_rotate(self):
        assert sv.season(0) == "spring"
        assert sv.season(sv.SEASON_LENGTH) == "summer"
        assert sv.season(sv.SEASON_LENGTH * 4) == "spring"
        assert sv.season(sv.SEASON_LENGTH * 3) == "winter"

    def test_winter_days_are_colder_than_summer_nights(self):
        # the season must dominate the day/night swing, or winter is
        # survivable by napping through noon
        winter_noon = sv.ambient_temperature(
            sv.SEASON_LENGTH * 3 + sv.DAY_LENGTH // 2)
        summer_midnight = sv.ambient_temperature(sv.SEASON_LENGTH + 0)
        assert summer_midnight > winter_noon


class TestSlackInvariant:
    def test_hunger_leaves_expedition_slack(self):
        """From fed, a gather trip (walk 4 + gather 3 = ~12 heartbeats)
        must not reach the weakening line. The v1 model pinned agents
        at zero; this one leaves room to work."""
        hunger = 18.0
        for hb in range(12):
            hunger = sv.hunger_next(hunger, hb)
        assert hunger < sv.HUNGER_WEAKEN

    def test_a_gather_trip_nets_more_than_it_costs(self):
        """3 gathers on a healthy tile (audit: net 1-6 per tile) vs the
        hunger cost of the trip. Food income must exceed time cost."""
        trip_cost = sv.HUNGER_RATE * 12
        trip_income = sv.eat_satisfaction("wild_berries") * 3
        assert trip_income > trip_cost * 1.5

    def test_cooked_food_is_worth_the_fire(self):
        raw = sv.eat_satisfaction("wild_berries")
        cooked = sv.eat_satisfaction("wild_berries", cooked=True)
        assert cooked >= raw * sv.COOKED_MULTIPLIER * 0.99


class TestWarmth:
    def test_night_drains_warmth(self):
        cold_night = sv.ambient_temperature(0)  # midnight, spring
        w = 82.0
        for _ in range(10):
            w = sv.warmth_next(w, cold_night, by_fire=False, in_shelter=False)
        assert w < 82.0

    def test_fire_restores_warmth_fast_even_in_winter(self):
        w = 15.0
        winter_midnight = sv.ambient_temperature(
            sv.SEASON_LENGTH * 3 + 0)
        for _ in range(6):
            w = sv.warmth_next(w, winter_midnight, by_fire=True,
                               in_shelter=False)
        assert w > 60.0, "fire must dominate even the coldest night"

    def test_shelter_slows_the_drain_but_does_not_heat(self):
        cold_night = sv.ambient_temperature(0)
        sheltered, exposed = 82.0, 82.0
        for _ in range(10):
            sheltered = sv.warmth_next(sheltered, cold_night,
                                       by_fire=False, in_shelter=True)
            exposed = sv.warmth_next(exposed, cold_night,
                                     by_fire=False, in_shelter=False)
        assert sheltered > exposed
        assert sheltered < 82.0, "shelter slows, it does not heat"


class TestVitalityAndCollapse:
    def test_starving_drains_vitality(self):
        v = 100.0
        for _ in range(10):
            v = sv.vitality_next(v, hunger=95.0, warmth=80.0, downed=False)
        assert v < 100.0

    def test_freezing_drains_vitality_faster(self):
        starving = sv.vitality_next(100.0, hunger=95.0, warmth=80.0,
                                    downed=False)
        freezing = sv.vitality_next(100.0, hunger=20.0, warmth=10.0,
                                    downed=False)
        assert freezing < starving, "cold must bite harder than hunger"

    def test_care_regenerates(self):
        v = 60.0
        for _ in range(20):
            v = sv.vitality_next(v, hunger=30.0, warmth=70.0, downed=False)
        assert v > 60.0

    def test_collapse_at_zero_and_stand_at_recovery(self):
        v = 3.0
        for _ in range(4):  # 1.4 drain per heartbeat reaches zero fast
            v = sv.vitality_next(v, hunger=95.0, warmth=5.0, downed=False)
        assert v == 0.0
        # down: slow passive recovery, capped below the stand threshold
        for _ in range(50):
            v = sv.vitality_next(v, hunger=95.0, warmth=5.0, downed=True)
            assert v <= sv.RECOVERY_STAND_AT
        # rescue: food + fire bring the body back above the line
        v = sv.vitality_next(0.0, hunger=10.0, warmth=80.0, downed=False)
        assert v > 0.0

    def test_apply_heartbeat_full_lifecycle(self):
        # neglected body collapses
        vitals = sv.initial_vitals()
        vitals["hunger"] = 99.0
        vitals["warmth"] = 0.0
        for hb in range(400):
            vitals = sv.apply_heartbeat(vitals, hb, by_fire=False,
                                        in_shelter=False)
        assert vitals["downed"] is True
        # rescued: partner's fire + brought food
        for hb in range(400, 800):
            vitals = sv.apply_heartbeat(vitals, hb, by_fire=True,
                                        in_shelter=True,
                                        ate_satisfaction=30.0)
        assert vitals["downed"] is False
        assert vitals["vitality"] > sv.RECOVERY_STAND_AT


class TestLabels:
    def test_labels_read_like_a_body(self):
        assert sv.vitals_state_label(
            {"downed": True, "hunger": 0, "warmth": 100,
             "vitality": 5}) == "collapsed"
        assert sv.vitals_state_label(
            {"downed": False, "hunger": 95, "warmth": 80,
             "vitality": 90}) == "starving"
        assert sv.vitals_state_label(
            {"downed": False, "hunger": 10, "warmth": 10,
             "vitality": 90}) == "freezing"
        assert sv.vitals_state_label(
            {"downed": False, "hunger": 20, "warmth": 80,
             "vitality": 100}) == "well"


class TestMigrationDefaults:
    def test_initial_vitals_are_healthy(self):
        """No retroactive famine for existing agents: they wake up fed
        and warm, and learn the new terms from the changelog, not from
        a starting crisis."""
        v = sv.initial_vitals()
        assert v["hunger"] < 30 and v["warmth"] > 70
        assert v["vitality"] == 100.0 and v["downed"] is False
