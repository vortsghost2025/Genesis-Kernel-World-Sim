"""Pure fauna tests for Phase 10JN."""

from __future__ import annotations

import random
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import fauna


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
    fishes: list[dict] = []
    entities = fauna.spawn_fauna(
        entities=fishes,
        heartbeat_number=100,
        agent_xys=agents,
        fire_xys=[(0, 3)],
        sheltered_tiles={(1, 1)},
        weather="clear",
        temperature=62.0,
        is_night=False,
        rng=_rng(),
    )
    for entity in entities:
        tile = entity["tile"]
        distance = max(abs(tile[0]), abs(tile[1]))
        assert distance >= fauna.FAUNA_MIN_SPAWN_DISTANCE


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


def test_advance_cow_milk_respects_interval():
    entities = [{
        "kind": "cow",
        "id": "cow-1",
        "tile": [0, 1],
        "hp": 4,
        "trust": 60,
        "tamed": True,
        "milk_ready": False,
        "milk_ready_at_hb": 0,
        "anchor_tile": [0, 1],
    }]
    fauna.advance_cow_milk(entities, heartbeat_number=100)
    assert entities[0]["milk_ready"] is False
    assert entities[0]["milk_ready_at_hb"] == 100

    fauna.advance_cow_milk(entities, heartbeat_number=243)
    assert entities[0]["milk_ready"] is False
    assert entities[0]["milk_ready_at_hb"] == 100


def test_advance_cow_milk_becomes_ready_after_interval():
    entities = [{
        "kind": "cow",
        "id": "cow-1",
        "tile": [0, 1],
        "hp": 4,
        "trust": 60,
        "tamed": True,
        "milk_ready": False,
        "milk_ready_at_hb": 100,
        "anchor_tile": [0, 1],
    }]
    fauna.advance_cow_milk(entities, heartbeat_number=244)
    assert entities[0]["milk_ready"] is True


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


def test_tool_knife_kills_snake_in_one_strike():
    snake = {"kind": "snake", "id": "snake-1", "tile": [1, 0], "hp": 2}
    updated, damage, killed, meat = fauna.strike_snake(snake, {"flint_knife": 1})
    assert damage == 2.2
    assert updated["hp"] == 0.0
    assert killed is True
    assert meat == 1


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
