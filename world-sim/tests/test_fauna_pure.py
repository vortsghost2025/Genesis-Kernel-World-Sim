"""Pure fauna tests for Phase 10JN."""

from __future__ import annotations

import random
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

import pytest

from backend.world import fauna
from backend.world import wildlife


def _rng(seed: int = 7) -> random.Random:
    return random.Random(seed)


def test_snake_active_requires_day_warmth_and_dry_sky():
    assert fauna.snake_active("clear", 61.0, is_night=False)
    assert not fauna.snake_active("clear", 49.9, is_night=False)
    assert not fauna.snake_active("rain", 61.0, is_night=False)
    assert not fauna.snake_active("storm", 61.0, is_night=False)
    assert not fauna.snake_active("blizzard", 61.0, is_night=False)
    assert not fauna.snake_active("clear", 61.0, is_night=True)


def test_spawn_fauna_never_spawns_adjacent():
    agents = [(0, 0)]
    existing_fauna: list[dict] = []
    entities = fauna.spawn_fauna(
        entities=existing_fauna,
        heartbeat_number=100,
        agent_xys=agents,
        fire_xys=[(0, 3)],
        sheltered_tiles={(1, 1)},
        weather="clear",
        temperature=62.0,
        is_night=False,
        rng=_rng(),
    )
    assert entities, "spawn did not occur"
    for entity in entities:
        tile = entity["tile"]
        distance = max(abs(tile[0]), abs(tile[1]))
        assert distance >= fauna.FAUNA_MIN_SPAWN_DISTANCE


def _legal_candidate_tiles(agent_xys, fire_xys) -> list[tuple[int, int]]:
    """Step-aligned spawn candidates that pass distance and fire checks."""
    center_x, center_y = agent_xys[0]
    allowed = []
    for dx in range(
        -fauna.FAUNA_MAX_SPAWN_DISTANCE,
        fauna.FAUNA_MAX_SPAWN_DISTANCE + 1,
        fauna.FAUNA_CANDIDATE_STEP,
    ):
        for dy in range(
            -fauna.FAUNA_MAX_SPAWN_DISTANCE,
            fauna.FAUNA_MAX_SPAWN_DISTANCE + 1,
            fauna.FAUNA_CANDIDATE_STEP,
        ):
            tile = (center_x + dx, center_y + dy)
            if any(
                max(abs(tile[0] - ax), abs(tile[1] - ay))
                < fauna.FAUNA_MIN_SPAWN_DISTANCE
                for ax, ay in agent_xys
            ):
                continue
            if any(
                max(abs(tile[0] - fx), abs(tile[1] - fy))
                <= wildlife.FIRE_SAFETY_RADIUS
                for fx, fy in fire_xys
            ):
                continue
            allowed.append(tile)
    return allowed


def _spawn_over_heartbeats(count: int, fire_xys, sheltered_tiles) -> list[dict]:
    """Sample many independent spawns by re-spawning from an empty world.

    Accumulating entities across heartbeats hits ``FAUNA_MAX_ALIVE`` after
    the first few heartbeats, so only a handful of tiles would ever be
    sampled and a blocked tile region could be missed by luck. Spawning
    from a fresh empty entity list each heartbeat keeps every heartbeat
    draw independent and yields many spawn tiles.
    """
    agents = [(0, 0)]
    spawned: list[dict] = []
    for hb in range(100, 100 + count):
        entities = fauna.spawn_fauna(
            [],
            hb,
            agents,
            fire_xys,
            sheltered_tiles,
            "clear",
            62.0,
            False,
            _rng(hb),
        )
        spawned.extend(entities)
    return spawned


def test_spawn_fauna_never_spawns_on_sheltered_tile():
    fire_xys = [(0, 3)]
    # Shelter only otherwise-legal candidates, so shelter is the single
    # remaining reason a tile can be rejected.
    sheltered_tiles = set(_legal_candidate_tiles([(0, 0)], fire_xys)[::5])
    assert sheltered_tiles, "no legal candidates to shelter"

    entities = _spawn_over_heartbeats(200, fire_xys, sheltered_tiles)
    assert entities, "spawn did not occur"
    assert len(entities) >= 100, "too few spawns sampled to prove shelter coverage"

    for entity in entities:
        assert tuple(entity["tile"]) not in sheltered_tiles


def test_spawn_fauna_never_spawns_inside_fire_safety_radius():
    # The fire sits on otherwise-legal candidate tiles, so only the fire
    # safety radius can exclude them.
    fire_xys = [(4, 4), (6, -4)]
    assert any(
        max(abs(tile[0] - 4), abs(tile[1] - 4))
        <= wildlife.FIRE_SAFETY_RADIUS
        for tile in _legal_candidate_tiles([(0, 0)], [])
    ), "fire is not over a legal candidate tile"

    entities = _spawn_over_heartbeats(200, fire_xys, set())
    assert entities, "spawn did not occur"
    assert len(entities) >= 100, "too few spawns sampled to prove fire coverage"

    for entity in entities:
        tile = tuple(entity["tile"])
        for fxy in fire_xys:
            distance = max(abs(tile[0] - fxy[0]), abs(tile[1] - fxy[1]))
            assert distance > wildlife.FIRE_SAFETY_RADIUS


def test_spawn_fauna_respects_max_counts():
    agents = [(0, 0)]
    entities: list[dict] = []
    for hb in range(100, 180):
        entities = fauna.spawn_fauna(
            entities,
            hb,
            agents,
            [],
            set(),
            "clear",
            62.0,
            False,
            _rng(hb),
        )
    assert sum(1 for e in entities if e["kind"] == "cow") <= fauna.COW_MAX_ALIVE
    assert sum(1 for e in entities if e["kind"] == "horse") <= fauna.HORSE_MAX_ALIVE
    assert sum(1 for e in entities if e["kind"] == "snake") <= fauna.SNAKE_MAX_ALIVE


def test_spawn_fauna_is_deterministic():
    kwargs = {
        "heartbeat_number": 123,
        "agent_xys": [(0, 0)],
        "fire_xys": [],
        "sheltered_tiles": set(),
        "weather": "clear",
        "temperature": 62.0,
        "is_night": False,
    }
    first = fauna.spawn_fauna([], rng=random.Random(7), **kwargs)
    second = fauna.spawn_fauna([], rng=random.Random(7), **kwargs)
    assert first == second


def test_trust_after_clamps_at_threshold():
    assert fauna.trust_after("cow", "wild_apples", 50) == 60
    assert fauna.trust_after("horse", "fiber_plants", 69) == 70


def test_trust_after_rejects_unknown_animal_kinds():
    assert set(fauna.TAMEABLE_KINDS) == {"cow", "horse"}
    for kind in ("snake", "deer", "wolf", "flint"):
        with pytest.raises(ValueError, match="fauna:not_tameable"):
            fauna.trust_after(kind, "wild_apples", 10)


def test_trust_after_rejects_unknown_foods():
    for resource in ("stone", "flint", "meat"):
        with pytest.raises(ValueError, match="fauna:not_food"):
            fauna.trust_after("cow", resource, 10)


def _tamed_cow(**overrides) -> dict:
    cow = {
        "kind": "cow",
        "id": "cow-1",
        "tile": [0, 1],
        "hp": 4,
        "trust": 60,
        "tamed": True,
        "milk_ready": False,
        "milk_ready_at_hb": 0,
        "anchor_tile": [0, 1],
    }
    cow.update(overrides)
    return cow


def test_advance_cow_milk_respects_interval():
    entities = [_tamed_cow()]
    entities = fauna.advance_cow_milk(entities, heartbeat_number=100)
    assert entities[0]["milk_ready"] is False
    assert entities[0]["milk_ready_at_hb"] == 100

    entities = fauna.advance_cow_milk(entities, heartbeat_number=243)
    assert entities[0]["milk_ready"] is False
    assert entities[0]["milk_ready_at_hb"] == 100


def test_advance_cow_milk_becomes_ready_after_interval():
    entities = [_tamed_cow(milk_ready_at_hb=100)]
    entities = fauna.advance_cow_milk(entities, heartbeat_number=244)
    assert entities[0]["milk_ready"] is True


def test_advance_cow_milk_is_pure_and_returns_new_list():
    original = [_tamed_cow()]
    frozen = [dict(original[0])]

    result = fauna.advance_cow_milk(original, heartbeat_number=100)

    assert result is not original
    assert original == frozen
    assert original[0]["milk_ready_at_hb"] == 0
    assert result[0]["milk_ready_at_hb"] == 100
    assert result[0] is not original[0]


def test_advance_cow_milk_does_not_share_nested_values():
    original = [_tamed_cow(anchor_tile=[3, 4])]
    result = fauna.advance_cow_milk(original, heartbeat_number=100)

    assert result[0]["anchor_tile"] == [3, 4]
    assert result[0]["anchor_tile"] is not original[0]["anchor_tile"]

    result[0]["anchor_tile"].append(99)
    assert original[0]["anchor_tile"] == [3, 4]


def test_advance_cow_milk_ignores_untamed_cows_ready_cows_and_snakes():
    wild_cow = _tamed_cow(id="cow-wild", tamed=False)
    ready_cow = _tamed_cow(id="cow-ready", milk_ready=True, milk_ready_at_hb=50)
    snake = {"kind": "snake", "id": "snake-1", "tile": [3, 3], "hp": 2}
    entities = [wild_cow, ready_cow, snake]

    result = fauna.advance_cow_milk(entities, heartbeat_number=100)

    assert result[0] == wild_cow
    assert result[1] == ready_cow
    assert result[2] == snake
    assert entities == [wild_cow, ready_cow, snake]


def test_cows_and_horses_only_spawn_in_daytime_clear_weather():
    bad_skies = (("rain", False), ("storm", False), ("blizzard", False), ("clear", True))
    for weather, is_night in bad_skies:
        entities: list[dict] = []
        for hb in range(100, 260):
            entities = fauna.spawn_fauna(
                entities,
                hb,
                [(0, 0)],
                [],
                set(),
                weather,
                62.0,
                is_night,
                _rng(hb),
            )
        assert fauna.count_kind(entities, "cow") == 0
        assert fauna.count_kind(entities, "horse") == 0


def test_cows_and_horses_spawn_in_daytime_clear_weather():
    entities: list[dict] = []
    for hb in range(100, 300):
        entities = fauna.spawn_fauna(
            entities,
            hb,
            [(0, 0)],
            [],
            set(),
            "clear",
            62.0,
            False,
            _rng(hb),
        )
    spawned = fauna.count_kind(entities, "cow") + fauna.count_kind(entities, "horse")
    assert entities, "spawn did not occur"
    assert spawned >= 1


def test_untamed_horse_flees_from_nearby_agent():
    horse = {
        "kind": "horse",
        "id": "horse-1",
        "tile": [0, 0],
        "hp": 5,
        "trust": 0,
        "tamed": False,
        "anchor_tile": None,
    }
    agent_xys = [(1, 0)]
    before = max(abs(0 - 1), abs(0 - 0))
    assert before <= fauna.HORSE_FLEE_RADIUS

    for hb in range(100, 140):
        moved = fauna.move_fauna(
            [dict(horse)],
            agent_xys=agent_xys,
            fire_xys=[],
            sheltered_tiles=set(),
            weather="clear",
            temperature=62.0,
            is_night=False,
            rng=_rng(hb),
        )
        tile = moved[0]["tile"]
        after = max(abs(tile[0] - 1), abs(tile[1] - 0))
        assert after > before
        horse["tile"] = tile


def test_untamed_horse_does_not_flee_when_agent_is_far():
    horse = {
        "kind": "horse",
        "id": "horse-1",
        "tile": [0, 0],
        "hp": 5,
        "trust": 0,
        "tamed": False,
        "anchor_tile": None,
    }
    moved = fauna.move_fauna(
        [horse],
        agent_xys=[(0, 12)],
        fire_xys=[],
        sheltered_tiles=set(),
        weather="clear",
        temperature=62.0,
        is_night=False,
        rng=_rng(7),
    )
    tile = moved[0]["tile"]
    assert max(abs(tile[0]), abs(tile[1])) <= 1


def test_untamed_horse_with_trust_does_not_flee_from_nearby_agent():
    horse = {
        "kind": "horse",
        "id": "horse-1",
        "tile": [0, 0],
        "hp": 5,
        "trust": 1,
        "tamed": False,
        "anchor_tile": None,
    }
    agent_xys = [(1, 0)]
    assert max(abs(0 - 1), abs(0 - 0)) <= fauna.HORSE_FLEE_RADIUS

    # The fixture re-seeds the horse each heartbeat: this samples drift
    # behavior per heartbeat, not a multi-heartbeat trajectory, so the
    # flee branch is either taken or skipped on every independent draw.
    #
    # A fleeing horse always takes the maximum-distance neighbor, which is
    # exactly HORSE_FLEE_RADIUS from the agent here. Asserting an interior
    # distance therefore proves the flee branch was skipped, instead of
    # merely accepting the radius the bug itself would produce.
    distances = []
    for hb in range(100, 160):
        moved = fauna.move_fauna(
            [dict(horse)],
            agent_xys=agent_xys,
            fire_xys=[],
            sheltered_tiles=set(),
            weather="clear",
            temperature=62.0,
            is_night=False,
            rng=_rng(hb),
        )
        tile = moved[0]["tile"]
        assert max(abs(tile[0]), abs(tile[1])) <= 1, "moved more than one step"
        distances.append(max(abs(tile[0] - 1), abs(tile[1] - 0)))

    assert distances, "no horse movement sampled"
    assert all(distance in (0, 1, 2) for distance in distances)
    assert any(distance < fauna.HORSE_FLEE_RADIUS for distance in distances), (
        "trusted horse stayed at the flee radius instead of drifting"
    )


def test_snake_movement_avoids_shelter_and_firelight():
    fire_xys = [(2, 2)]
    sheltered = {(1, 0)}
    for hb in range(100, 260):
        moved = fauna.move_fauna(
            [{"kind": "snake", "id": "snake-1", "tile": [0, 0], "hp": 2}],
            agent_xys=[(0, 0)],
            fire_xys=fire_xys,
            sheltered_tiles=sheltered,
            weather="clear",
            temperature=62.0,
            is_night=False,
            rng=_rng(hb),
        )
        tile = moved[0]["tile"]
        assert tuple(tile) not in sheltered
        assert max(abs(tile[0] - 2), abs(tile[1] - 2)) > fauna.SNAKE_FIRE_SAFETY_RADIUS


def test_snake_holds_still_when_all_neighbors_are_blocked():
    blocked = {(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)}
    moved = fauna.move_fauna(
        [{"kind": "snake", "id": "snake-1", "tile": [0, 0], "hp": 2}],
        agent_xys=[(0, 0)],
        fire_xys=[],
        sheltered_tiles=blocked,
        weather="clear",
        temperature=62.0,
        is_night=False,
        rng=_rng(11),
    )
    assert moved[0]["tile"] == [0, 0]


def test_tamed_cow_stays_within_anchor_radius():
    cow = {
        "kind": "cow",
        "id": "cow-1",
        "tile": [0, 0],
        "hp": 4,
        "trust": 60,
        "tamed": True,
        "milk_ready": False,
        "milk_ready_at_hb": 0,
        "anchor_tile": [0, 0],
    }
    for hb in range(100, 240):
        moved = fauna.move_fauna(
            [dict(cow)],
            agent_xys=[(0, 20)],
            fire_xys=[],
            sheltered_tiles=set(),
            weather="clear",
            temperature=62.0,
            is_night=False,
            rng=_rng(hb),
        )
        tile = moved[0]["tile"]
        assert max(abs(tile[0] - 0), abs(tile[1] - 0)) <= fauna.TAMED_ANCHOR_RADIUS
        cow["tile"] = tile


def test_find_fauna_returns_exact_id():
    entities = [{"kind": "cow", "id": "cow-1", "tile": [0, 1]}]
    assert fauna.find_fauna(entities, "cow-1")["kind"] == "cow"
    assert fauna.find_fauna(entities, "missing") is None


def test_snake_bite_events_only_for_adjacent_unsheltered_agents():
    entities = [{
        "kind": "snake",
        "id": "snake-1",
        "tile": [1, 0],
        "hp": fauna.SNAKE_HP,
    }]
    bites = fauna.snake_bite_events(
        entities=entities,
        agent_positions={"east_adam": (0, 0), "east_eve": (8, 8)},
        fire_xys=[],
        sheltered_tiles=set(),
    )
    assert bites == [("east_adam", "snake-1", fauna.SNAKE_BITE_DAMAGE)]


def test_snake_bite_events_ignore_fire_and_shelter():
    entities = [{
        "kind": "snake",
        "id": "snake-1",
        "tile": [1, 0],
        "hp": fauna.SNAKE_HP,
    }]
    assert fauna.snake_bite_events(
        entities,
        {"east_adam": (0, 0)},
        fire_xys=[(0, 0)],
        sheltered_tiles=set(),
    ) == []
    assert fauna.snake_bite_events(
        entities,
        {"east_adam": (0, 0)},
        fire_xys=[],
        sheltered_tiles={(0, 0)},
    ) == []


def test_snake_bite_events_skip_entities_without_a_valid_id():
    malformed = [
        {"kind": "snake", "tile": [1, 0]},
        {"kind": "snake", "id": None, "tile": [1, 0]},
        {"kind": "snake", "id": "", "tile": [1, 0]},
        {"kind": "snake", "id": 17, "tile": [1, 0]},
        {"kind": "snake", "id": "snake-ok", "tile": "nowhere"},
    ]
    bites = fauna.snake_bite_events(
        malformed,
        {"east_adam": (0, 0)},
        fire_xys=[],
        sheltered_tiles=set(),
    )
    assert bites == []


def test_snake_bite_events_does_not_check_snake_active():
    cold_night = fauna.snake_active("clear", 61.0, is_night=True)
    assert cold_night is False

    entities = [{
        "kind": "snake",
        "id": "snake-1",
        "tile": [1, 0],
        "hp": fauna.SNAKE_HP,
    }]
    bites = fauna.snake_bite_events(
        entities=entities,
        agent_positions={"east_adam": (0, 0)},
        fire_xys=[],
        sheltered_tiles=set(),
    )
    assert bites == [("east_adam", "snake-1", fauna.SNAKE_BITE_DAMAGE)]


def test_tool_knife_kills_snake_in_one_strike():
    snake = {"kind": "snake", "id": "snake-1", "tile": [1, 0], "hp": 2}
    updated, damage, killed, meat = fauna.strike_snake(snake, {"flint_knife": 1})
    assert damage == 2.2
    assert updated["hp"] == 0.0
    assert killed is True
    assert meat == 1


def test_raw_flint_kills_fresh_snake_in_one_strike():
    assert wildlife.TOOL_DAMAGE_BONUS["flint"] == 2.0
    snake = {"kind": "snake", "id": "snake-1", "tile": [1, 0], "hp": fauna.SNAKE_HP}
    updated, damage, killed, meat = fauna.strike_snake(snake, {"flint": 1})
    assert damage == 2.0
    assert updated["hp"] == 0.0
    assert killed is True
    assert meat == fauna.SNAKE_MEAT_DROP


def test_strike_snake_rejects_non_snake_entities():
    for entity in (
        {"kind": "cow", "id": "cow-1", "tile": [0, 1], "hp": 4},
        {"kind": "horse", "id": "horse-1", "tile": [0, 1], "hp": 5},
        {"kind": "deer", "id": "deer-1", "tile": [0, 1], "hp": 2},
    ):
        with pytest.raises(ValueError, match="fauna:not_a_snake"):
            fauna.strike_snake(entity, {"flint_knife": 1})
        assert entity["hp"] in (4, 5, 2)


def test_unarmed_requires_two_snake_strikes():
    snake = {"kind": "snake", "id": "snake-1", "tile": [1, 0], "hp": 2}
    first, damage, killed, meat = fauna.strike_snake(snake, {})
    assert damage == 1.0
    assert first["hp"] == 1.0
    assert killed is False
    assert meat == 0

    second, damage, killed, meat = fauna.strike_snake(first, {})
    assert damage == 1.0
    assert second["hp"] == 0.0
    assert killed is True
    assert meat == 1


def test_tamed_fauna_stays_within_anchor_radius():
    horse = {
        "kind": "horse",
        "id": "horse-1",
        "tile": [0, 0],
        "hp": 5,
        "trust": 70,
        "tamed": True,
        "anchor_tile": [0, 0],
    }
    for hb in range(100, 180):
        moved = fauna.move_fauna(
            [dict(horse)],
            agent_xys=[(0, 0)],
            fire_xys=[],
            sheltered_tiles=set(),
            weather="clear",
            temperature=62.0,
            is_night=False,
            rng=random.Random(hb),
        )
        tile = moved[0]["tile"]
        assert max(abs(tile[0]), abs(tile[1])) <= fauna.TAMED_ANCHOR_RADIUS
        horse["tile"] = tile
