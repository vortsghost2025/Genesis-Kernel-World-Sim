"""Pure fauna ecology for Phase 10JN.

Animal behavior is separate from wildlife hazards. This module is pure:
(entities, environment, rng) -> entities. Runtime state is applied by
FirstPairRuntime.

Caller contracts: spawn_fauna, move_fauna, and advance_cow_milk all
return new lists rather than mutating the input, so callers must
reassign the result of every call:

    entities = fauna.spawn_fauna(entities, heartbeat_number, ...)
    entities = fauna.move_fauna(entities, ...)
    entities = fauna.advance_cow_milk(entities, heartbeat_number)
"""

from __future__ import annotations

import copy
import random

from backend.world import wildlife

FAUNA_MIN_SPAWN_DISTANCE = 4
FAUNA_MAX_SPAWN_DISTANCE = 14
FAUNA_CANDIDATE_STEP = 2

COW_MAX_ALIVE = 1
HORSE_MAX_ALIVE = 1
SNAKE_MAX_ALIVE = 2

COW_HP = 4
HORSE_HP = 5
SNAKE_HP = 2

COW_TRUST_THRESHOLD = 60
HORSE_TRUST_THRESHOLD = 70
HORSE_FLEE_RADIUS = 2
TAMED_ANCHOR_RADIUS = 3

MILK_READY_HEARTBEATS = 144

SNAKE_BITE_DAMAGE = 5.0
SNAKE_FIRE_SAFETY_RADIUS = 2
SNAKE_ACTIVE_TEMP = 50.0
SNAKE_MEAT_DROP = 1

FAUNA_SPAWN_CHANCE = {
    "cow": 0.35,
    "horse": 0.30,
    "snake": 0.45,
}

FAUNA_MAX_ALIVE = {
    "cow": COW_MAX_ALIVE,
    "horse": HORSE_MAX_ALIVE,
    "snake": SNAKE_MAX_ALIVE,
}

ANIMAL_FOOD_TRUST = {
    "wild_berries": 15,
    "edible_roots": 18,
    "wild_apples": 20,
    "wild_grain": 16,
    "fiber_plants": 8,
}

TAMEABLE_KINDS = ("cow", "horse")


def _dist(a_xy, b_xy) -> int:
    if a_xy is None or b_xy is None:
        return 999
    return max(abs(a_xy[0] - b_xy[0]), abs(a_xy[1] - b_xy[1]))


def _entity_xy(entity: dict) -> tuple[int, int] | None:
    tile = entity.get("tile")
    if isinstance(tile, tuple) and len(tile) == 2:
        return (int(tile[0]), int(tile[1]))
    if isinstance(tile, list) and len(tile) == 2:
        return (int(tile[0]), int(tile[1]))
    return None


def _anchor_xy(entity: dict) -> tuple[int, int] | None:
    tile = entity.get("anchor_tile")
    if isinstance(tile, tuple) and len(tile) == 2:
        return (int(tile[0]), int(tile[1]))
    if isinstance(tile, list) and len(tile) == 2:
        return (int(tile[0]), int(tile[1]))
    return None


def _candidate_tiles(center: tuple[int, int]) -> list[tuple[int, int]]:
    tiles: list[tuple[int, int]] = []
    for dx in range(-FAUNA_MAX_SPAWN_DISTANCE, FAUNA_MAX_SPAWN_DISTANCE + 1, FAUNA_CANDIDATE_STEP):
        for dy in range(-FAUNA_MAX_SPAWN_DISTANCE, FAUNA_MAX_SPAWN_DISTANCE + 1, FAUNA_CANDIDATE_STEP):
            tiles.append((center[0] + dx, center[1] + dy))
    return tiles


def _spawn_tile_allowed(tile: tuple[int, int], agent_xys: list[tuple[int, int]],
                        fire_xys: list[tuple[int, int]],
                        sheltered_tiles: set[tuple[int, int]]) -> bool:
    if tile in sheltered_tiles:
        return False
    for fxy in fire_xys:
        if _dist(fxy, tile) <= wildlife.FIRE_SAFETY_RADIUS:
            return False
    for axy in agent_xys:
        if _dist(axy, tile) < FAUNA_MIN_SPAWN_DISTANCE:
            return False
    return True


def snake_active(weather: str, temperature: float, is_night: bool) -> bool:
    """True when snakes are awake and able to move or bite."""
    if is_night:
        return False
    if weather in ("rain", "storm", "blizzard"):
        return False
    return temperature >= SNAKE_ACTIVE_TEMP


def count_kind(entities: list[dict], kind: str) -> int:
    return sum(1 for entity in entities if entity.get("kind") == kind)


def find_fauna(entities: list[dict], target_id: str) -> dict | None:
    for entity in entities:
        if entity.get("id") == target_id:
            return entity
    return None


def trust_after(kind: str, resource_kind: str, current_trust: int) -> int:
    """Trust gained by feeding a tameable animal, clamped at its threshold.

    Fails closed: an unknown animal kind is rejected before
    ``ANIMAL_FOOD_TRUST`` is indexed, so only TAMEABLE_KINDS ever gain
    trust. Cow and horse behavior is unchanged.
    """
    if kind not in TAMEABLE_KINDS:
        raise ValueError(f"fauna:not_tameable:{kind}")
    if resource_kind not in ANIMAL_FOOD_TRUST:
        raise ValueError(f"fauna:not_food:{resource_kind}")
    threshold = COW_TRUST_THRESHOLD if kind == "cow" else HORSE_TRUST_THRESHOLD
    return min(threshold, int(current_trust) + ANIMAL_FOOD_TRUST[resource_kind])


def new_fauna_entity(kind: str, heartbeat_number: int, tile: tuple[int, int],
                      entity_count: int) -> dict:
    base = {
        "kind": kind,
        "id": f"{kind}-{heartbeat_number}-{entity_count}",
        "tile": [int(tile[0]), int(tile[1])],
    }
    if kind == "cow":
        base.update({
            "hp": COW_HP,
            "trust": 0,
            "tamed": False,
            "milk_ready": False,
            "milk_ready_at_hb": 0,
            "anchor_tile": None,
        })
    elif kind == "horse":
        base.update({
            "hp": HORSE_HP,
            "trust": 0,
            "tamed": False,
            "anchor_tile": None,
        })
    else:
        base.update({"hp": SNAKE_HP})
    return base


def spawn_fauna(entities: list[dict], heartbeat_number: int,
                agent_xys: list[tuple[int, int]],
                fire_xys: list[tuple[int, int]],
                sheltered_tiles: set[tuple[int, int]],
                weather: str, temperature: float, is_night: bool,
                rng: random.Random) -> list[dict]:
    """Spawn fauna deterministically, never adjacent or inside protection."""
    updated = list(entities)
    if not agent_xys:
        return updated

    center = agent_xys[0]
    candidates = _candidate_tiles(center)

    for kind in ("cow", "horse", "snake"):
        if count_kind(updated, kind) >= FAUNA_MAX_ALIVE[kind]:
            continue

        if kind == "snake":
            if not snake_active(weather, temperature, is_night):
                continue
        else:
            if is_night or weather in ("rain", "storm", "blizzard"):
                continue

        if rng.random() > FAUNA_SPAWN_CHANCE[kind]:
            continue

        wild = [
            tile for tile in candidates
            if _spawn_tile_allowed(tile, agent_xys, fire_xys, sheltered_tiles)
        ]
        if not wild:
            continue

        tile = rng.choice(wild)
        updated.append(new_fauna_entity(kind, heartbeat_number, tile, len(updated)))

    return updated


def _neighbors(tile: tuple[int, int]) -> list[tuple[int, int]]:
    x, y = tile
    return [
        (x + dx, y + dy)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if not (dx == 0 and dy == 0)
    ]


def _step_toward(tile: tuple[int, int], target: tuple[int, int]) -> tuple[int, int]:
    options = _neighbors(tile)
    return min(options, key=lambda option: _dist(option, target))


def _bounded_anchor_step(entity: dict, tile: tuple[int, int],
                         rng: random.Random) -> tuple[int, int]:
    anchor = _anchor_xy(entity)
    if anchor is None:
        return tile

    if _dist(tile, anchor) > TAMED_ANCHOR_RADIUS:
        return _step_toward(tile, anchor)

    safe = [
        option for option in _neighbors(tile)
        if _dist(option, anchor) <= TAMED_ANCHOR_RADIUS
    ]
    if not safe:
        return tile
    return rng.choice(safe)


def _free_drift_step(entity: dict, tile: tuple[int, int],
                     rng: random.Random) -> tuple[int, int]:
    if entity.get("tamed"):
        return _bounded_anchor_step(entity, tile, rng)
    options = _neighbors(tile)
    return rng.choice(options)


def _horse_step(entity: dict, tile: tuple[int, int],
                agent_xys: list[tuple[int, int]],
                rng: random.Random) -> tuple[int, int]:
    if not entity.get("tamed") and entity.get("trust", 0) == 0:
        nearest = min(
            (_dist(tile, axy) for axy in agent_xys),
            default=999,
        )
        if nearest <= HORSE_FLEE_RADIUS:
            options = _neighbors(tile)
            return max(
                options,
                key=lambda option: min(
                    (_dist(option, axy) for axy in agent_xys),
                    default=999,
                ),
            )
    return _free_drift_step(entity, tile, rng)


def _snake_step(tile: tuple[int, int],
                fire_xys: list[tuple[int, int]],
                sheltered_tiles: set[tuple[int, int]],
                rng: random.Random) -> tuple[int, int]:
    options = [
        option for option in _neighbors(tile)
        if option not in sheltered_tiles
        and all(_dist(option, fxy) > SNAKE_FIRE_SAFETY_RADIUS for fxy in fire_xys)
    ]
    if not options:
        return tile
    return rng.choice(options)


def move_fauna(entities: list[dict], agent_xys: list[tuple[int, int]],
               fire_xys: list[tuple[int, int]],
               sheltered_tiles: set[tuple[int, int]],
               weather: str, temperature: float, is_night: bool,
               rng: random.Random) -> list[dict]:
    """Move every fauna entity one heartbeat step."""
    moved: list[dict] = []
    active_snakes = snake_active(weather, temperature, is_night)

    for entity in entities:
        kind = entity.get("kind")
        if kind not in ("cow", "horse", "snake"):
            moved.append(dict(entity))
            continue

        tile = _entity_xy(entity)
        if tile is None:
            moved.append(dict(entity))
            continue

        updated = dict(entity)
        if kind == "snake":
            if active_snakes:
                new_tile = _snake_step(tile, fire_xys, sheltered_tiles, rng)
            else:
                new_tile = tile
        elif kind == "horse":
            new_tile = _horse_step(entity, tile, agent_xys, rng)
        else:
            new_tile = _free_drift_step(entity, tile, rng)

        updated["tile"] = [int(new_tile[0]), int(new_tile[1])]
        moved.append(updated)

    return moved


def advance_cow_milk(entities: list[dict], heartbeat_number: int) -> list[dict]:
    """Advance tamed cow milk readiness after the specified interval.

    Pure: the input list and its entity dicts are never mutated. A new list
    holding new entity dicts is returned, so callers must reassign:

        entities = fauna.advance_cow_milk(entities, heartbeat_number)

    Returned entities are independent of the input, including their nested
    mutable values (notably ``anchor_tile``), so mutating a result cannot
    reach back into the caller's entities.
    """
    updated: list[dict] = []
    for entity in entities:
        candidate = copy.deepcopy(entity)
        if (
            candidate.get("kind") == "cow"
            and candidate.get("tamed")
            and not candidate.get("milk_ready")
        ):
            ready_at = int(candidate.get("milk_ready_at_hb") or 0)
            if ready_at == 0:
                candidate["milk_ready_at_hb"] = heartbeat_number
            elif heartbeat_number - ready_at >= MILK_READY_HEARTBEATS:
                candidate["milk_ready"] = True
        updated.append(candidate)
    return updated


def _snake_id(entity: dict) -> str | None:
    """Return a usable snake id, or None when the id is missing/malformed."""
    entity_id = entity.get("id")
    if isinstance(entity_id, str) and entity_id:
        return entity_id
    return None


def snake_bite_events(entities: list[dict],
                      agent_positions: dict[str, tuple[int, int]],
                      fire_xys: list[tuple[int, int]],
                      sheltered_tiles: set[tuple[int, int]]) -> list[tuple[str, str, float]]:
    """Return adjacent snake bite events. Bites never cross shelter or firelight.

    This is a pure function over the entities it is handed; it does NOT
    check ``snake_active``. The runtime must gate every call with
    ``fauna.snake_active(weather, temperature, is_night)`` so sleeping
    (night, wet, or cold) snakes never produce bite events.

    Entities with a missing or malformed id are skipped rather than
    raising, so one bad record cannot break the whole heartbeat.
    """
    events: list[tuple[str, str, float]] = []
    for entity in entities:
        if entity.get("kind") != "snake":
            continue
        snake_id = _snake_id(entity)
        if snake_id is None:
            continue
        snake_tile = _entity_xy(entity)
        if snake_tile is None:
            continue

        for agent_ref, tile in agent_positions.items():
            if tile in sheltered_tiles:
                continue
            if any(_dist(tile, fxy) <= SNAKE_FIRE_SAFETY_RADIUS for fxy in fire_xys):
                continue
            if _dist(snake_tile, tile) <= 1:
                events.append((agent_ref, snake_id, SNAKE_BITE_DAMAGE))
    return events


def strike_snake(entity: dict, inventory: dict) -> tuple[dict, float, bool, int]:
    """Strike a fauna snake. Reuses the existing wildlife tool balance.

    Raises ``ValueError("fauna:not_a_snake")`` before any damage is dealt
    when the entity is not a snake, so cows and horses can never be hit
    by a snake-strike action.
    """
    if entity.get("kind") != "snake":
        raise ValueError("fauna:not_a_snake")
    multiplier = wildlife.best_tool_multiplier(inventory)
    damage = wildlife.UNARMED_DAMAGE * multiplier
    hp = max(0, entity.get("hp", SNAKE_HP) - damage)
    updated = dict(entity)
    updated["hp"] = hp
    killed = hp <= 0
    return updated, damage, killed, (SNAKE_MEAT_DROP if killed else 0)
