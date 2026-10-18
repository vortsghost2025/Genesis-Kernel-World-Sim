"""Weather physics — the sky, epistemic.5.

The core question these tests answer: does weather create *planning*
rather than dice? Deterministic skies, a visible forecast, wet-warmth
interaction, and the one rule that makes shelter structural: rain
snuffs open fires, roofed fires keep burning.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival as sv  # noqa: E402


class TestWeatherMachine:
    def test_pure_and_deterministic(self):
        a = sv.weather_at("east", 4000)
        b = sv.weather_at("east", 4000)
        assert a == b
        assert a[0] in sv.WEATHER_TYPES

    def test_pairs_have_different_skies(self):
        """Two civilizations, different weather — the comparison is the
        show. Not guaranteed to differ at every heartbeat, but the
        seeds must not produce identical roll sequences."""
        rolls_differ = any(
            sv._window_roll(sv._pair_seed("east"), w)
            != sv._window_roll(sv._pair_seed("west"), w)
            for w in range(50)
        )
        assert rolls_differ

    def test_forecast_is_complete_and_honest(self):
        f = sv.weather_forecast("east", 4000)
        assert f["current"] in sv.WEATHER_TYPES
        assert f["next"] in sv.WEATHER_TYPES
        assert f["changes_at_heartbeat"] > 4000
        # the forecast's next matches the weather at that heartbeat
        nxt, _ = sv.weather_at("east", f["changes_at_heartbeat"])
        assert nxt == f["next"]

    def test_all_weather_types_reachable_across_seasons(self):
        """The sky must not be a monoculture: across a year and both
        pairs, every weather type occurs."""
        seen = set()
        for pair in ("east", "west"):
            for hb in range(0, sv.SEASON_LENGTH * 4, 6):
                seen.add(sv.weather_at(pair, hb)[0])
        assert seen == set(sv.WEATHER_TYPES)

    def test_winter_storms_at_least_as_common_as_summer(self):
        """Seasonal pressure gradient: winter punishes the unprepared
        more often than summer does."""
        w_storm = sv.WEATHER_TABLE["winter"][3]
        s_storm = sv.WEATHER_TABLE["summer"][3]
        assert w_storm > s_storm


class TestTemperatureAndWetness:
    def test_storm_is_colder_than_clear(self):
        hb = 4000
        assert (sv.effective_temperature(hb, "storm")
                < sv.effective_temperature(hb, "clear"))

    def test_rain_soaks_exposed_body(self):
        w = sv.wetness_next(0.0, "rain", in_shelter=False, by_fire=False)
        assert w == sv.WETNESS_GAIN_EXPOSED

    def test_shelter_blocks_rain_entirely(self):
        w = sv.wetness_next(20.0, "storm", in_shelter=True, by_fire=False)
        assert w < 20.0, "under a roof the rain cannot touch you"

    def test_fire_dries_fast(self):
        w = sv.wetness_next(60.0, "clear", in_shelter=False, by_fire=True)
        assert w == 60.0 - sv.WETNESS_FIRE_DRY_RATE

    def test_soaked_body_cannot_warm_up(self):
        """The wet-warmth interaction: soaked (>=50), even a fire will
        not raise warmth until the wetness falls — the classic killer,
        and the reason drying matters."""
        cold = sv.ambient_temperature(0)
        soaked_by_fire = sv.warmth_next(10.0, cold, by_fire=True,
                                        in_shelter=False, wet=80.0)
        dry_by_fire = sv.warmth_next(10.0, cold, by_fire=True,
                                     in_shelter=False, wet=0.0)
        assert dry_by_fire > soaked_by_fire
        assert soaked_by_fire < 15.0, "wet body barely gains by a fire"


class TestTheShelterRule:
    def test_rain_snuffs_open_fire(self):
        assert sv.fire_is_snuffed("rain", fire_tile_sheltered=False)
        assert sv.fire_is_snuffed("storm", fire_tile_sheltered=False)

    def test_roofed_fire_survives_the_rain(self):
        assert not sv.fire_is_snuffed("rain", fire_tile_sheltered=True)

    def test_clear_sky_never_snuffs(self):
        assert not sv.fire_is_snuffed("clear", fire_tile_sheltered=False)
        assert not sv.fire_is_snuffed("overcast", fire_tile_sheltered=False)


class TestEmbodimentWithWeather:
    def test_rain_appears_in_vitals(self):
        v = sv.initial_vitals()
        for hb in range(4000, 4012):  # 12 x 9/hb saturates
            v = sv.apply_heartbeat(v, hb, by_fire=False, in_shelter=False,
                                   weather="rain")
        assert v["wetness"] == 100.0

    def test_storm_drains_exposed_vitality(self):
        safe = sv.initial_vitals()
        exposed = sv.initial_vitals()
        for hb in range(4000, 4010):
            safe = sv.apply_heartbeat(safe, hb, by_fire=False,
                                      in_shelter=True, weather="storm")
            exposed = sv.apply_heartbeat(exposed, hb, by_fire=False,
                                         in_shelter=False, weather="storm")
        assert exposed["vitality"] < safe["vitality"]

    def test_migration_wetness_default_is_dry(self):
        v = sv.initial_vitals()
        assert v["wetness"] == 0.0

    def test_legacy_vitals_dict_without_wetness_still_works(self):
        """A store written before the sky: missing wetness key must not
        crash the heartbeat."""
        legacy = {"hunger": 20.0, "warmth": 80.0, "vitality": 100.0,
                  "downed": False}
        v = sv.apply_heartbeat(legacy, 4000, by_fire=False,
                               in_shelter=False, weather="rain")
        assert "wetness" in v
