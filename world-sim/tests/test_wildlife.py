"""Wildlife - the wild (epistemic.7). The invariants that matter:

  - no ambushes: spawns are distant, nightly, rare
  - fire is absolute safety: wolves never enter its radius
  - shelters are absolute safety: wolves never harm the sheltered
  - survivability: bites are costly but escapable; nothing executes
  - deer flee and feed: hunting rewards tools and pursuit
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import wildlife as wl


def _rng():
    return random.Random(42)


class TestSpawning:
    def test_wolves_spawn_only_at_night(self):
        ents = wl.spawn_wolves([], 1000, night=False,
                               candidate_tiles=[(10, 10)],
                               agent_xys=[(0, 0)], fire_xys=[],
                               rng=_rng())
        assert ents == [], "daylight spawns are an ambush"

    def test_wolves_never_spawn_near_agents(self):
        near = (wl.WOLF_SPAWN_DISTANCE - 1, 0)
        far = (wl.WOLF_SPAWN_DISTANCE + 5, 0)
        for i in range(20):
            ents = wl.spawn_wolves([], 1000, night=True,
                                   candidate_tiles=[near, far],
                                   agent_xys=[(0, 0)], fire_xys=[],
                                   rng=random.Random(7))
            for e in ents:
                d = max(abs(e["tile"][0]), abs(e["tile"][1]))
                assert d >= wl.WOLF_SPAWN_DISTANCE

    def test_wolves_never_spawn_in_fire_safety(self):
        ents = wl.spawn_wolves([], 1000, night=True,
                               candidate_tiles=[(1, 0), (50, 50)],
                               agent_xys=[(50, 50)], fire_xys=[(0, 0)],
                               rng=_rng())
        for e in ents:
            assert e["tile"] != (1, 0), "no wolf spawns beside a fire"

    def test_spawn_cap(self):
        ents = [{"kind": "wolf", "id": "a", "tile": (50, 50), "hp": 1,
                 "spawn_day": 1}]
        for _ in range(30):
            ents = wl.spawn_wolves(ents, 1000, night=True,
                                   candidate_tiles=[(90, 90)],
                                   agent_xys=[(0, 0)], fire_xys=[],
                                   rng=_rng())
        wolves = [e for e in ents if e["kind"] == "wolf"]
        assert len(wolves) <= wl.WOLVES_MAX_ALIVE

    def test_one_spawn_roll_per_day(self):
        rng = _rng()
        ents = []
        for hb in range(1000, 1026):  # exactly one night (36 hb)
            ents = wl.spawn_wolves(ents, hb, night=True,
                                   candidate_tiles=[(30, 30)],
                                   agent_xys=[(0, 0)], fire_xys=[],
                                   rng=rng)
        wolves = [e for e in ents if e["kind"] == "wolf"]
        assert len(wolves) <= 1


class TestFireSafety:
    def test_wolves_never_step_into_fire_radius(self):
        wolf = {"kind": "wolf", "id": "w", "tile": (5, 0), "hp": 1}
        for _ in range(30):
            wolf = wl.move_wolf(wolf, [(0, 0)], {"e": (0, 0)},
                                [(0, 0)], set(), _rng())
            t = wolf["tile"]
            assert max(abs(t[0]), abs(t[1])) > wl.FIRE_SAFETY_RADIUS - 1

    def test_wolf_holds_at_edge_of_light(self):
        wolf = {"kind": "wolf", "id": "w", "tile": (5, 0), "hp": 1}
        for _ in range(20):
            wolf = wl.move_wolf(wolf, [(0, 0)], {"e": (0, 0)},
                                [(0, 0)], set(), _rng())
        d = max(abs(wolf["tile"][0]), abs(wolf["tile"][1]))
        assert wl.FIRE_SAFETY_RADIUS <= d <= wl.FIRE_SAFETY_RADIUS + 3


class TestDeer:
    def test_deer_flee_when_approached(self):
        deer = {"kind": "deer", "id": "d", "tile": (2, 0), "hp": 2}
        deer = wl.move_deer(deer, [(0, 0)], _rng())
        assert deer["tile"][0] >= 3, "deer bolts away from the hunter"

    def test_distant_deer_drifts_at_most_one_tile(self):
        deer = {"kind": "deer", "id": "d", "tile": (50, 50), "hp": 2}
        after = wl.move_deer(deer, [(0, 0)], _rng())
        assert max(abs(after["tile"][0] - 50),
                   abs(after["tile"][1] - 50)) <= 1


class TestStriking:
    def test_iron_kills_a_deer_in_one_strike(self):
        deer = {"kind": "deer", "id": "d", "tile": (1, 0), "hp": 2}
        _, dmg, killed, meat = wl.strike(deer, {"iron_tool": 1})
        assert killed and meat == wl.DEER_MEAT_DROP

    def test_unarmed_takes_two_strikes(self):
        deer = {"kind": "deer", "id": "d", "tile": (1, 0), "hp": 2}
        deer, _, killed, _ = wl.strike(deer, {})
        assert not killed
        deer, _, killed, _ = wl.strike(deer, {})
        assert killed

    def test_a_wolf_flees_after_one_hit(self):
        wolf = {"kind": "wolf", "id": "w", "tile": (2, 0), "hp": 1}
        wolf, _, killed, meat = wl.strike(wolf, {})
        assert killed and meat == 2, "a driven-off wolf leaves meat"

    def test_tool_bonus_ordering(self):
        assert wl.best_tool_multiplier({}) == 1.0
        assert wl.best_tool_multiplier({"flint": 2}) == 2.0
        assert wl.best_tool_multiplier({"iron_tool": 1, "flint": 2}) == 4.0


class TestSurvivability:
    def test_bites_are_survivable(self):
        bites_to_collapse = 100.0 / wl.WOLF_BITE_DAMAGE
        assert bites_to_collapse >= 10, (
            "a wolf must never be a fast executioner")


class TestWilderness:
    def test_wilderness_excludes_fire_and_agents(self):
        assert not wl.wilderness((0, 1), [(0, 0)], [(0, 0)])
        assert not wl.wilderness((0, 3), [(0, 0)], [])
        assert wl.wilderness((0, 9), [(0, 0)], [(0, 0)])

