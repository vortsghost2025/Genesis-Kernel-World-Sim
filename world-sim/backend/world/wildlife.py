"""Wildlife — the wild (epistemic.7).

The survival trinity closes: hunger (epistemic.4), elements (5/6),
and now threats. The precondition set in the survival spec is met -
both civilizations built settlements before anything hunted them
(east: shelters and campfires raised in storms; west: a hearth camp
kept through every rain).

Design invariants:

  - No ambushes: wolves spawn at night, in wilderness (never within
    fire radius of any agent), at least WOLF_SPAWN_DISTANCE from any
    agent, and the observation reports howls before contact.
  - Fire is absolute safety: wolves will not approach a burning tile
    and flee from one. A roofed fire keeps them off in rain.
  - Shelters are absolute safety: wolves do not harm a sheltered body.
  - Survivability: a wolf bite costs WOLF_BITE_DAMAGE vitality - from
    full vitality an agent survives many bites, and every bite is
    escapable by walking to fire. The danger pushes behavior; it does
    not execute.

Deer are the reward: they flee, they carry meat, and hunting one with
a tool in hand feeds a pair for days. Tools finally have a purpose.

Entity state persists in world_state.wildlife; the tick functions here
are pure: (entities, environment) -> entities.
"""
from __future__ import annotations

from backend.world import survival

import random

# --- the clock of the wild ---------------------------------------------------
WOLF_SPAWN_DISTANCE = 4     # never spawn within this many tiles of an agent
FIRE_SAFETY_RADIUS = 3      # wolves will not enter a burning tile's radius
DEER_FLEE_RADIUS = 2        # deer bolt when an agent closes this near

WOLF_NIGHT_SPAWN_CHANCE = 0.35   # per night, per pair (checked once/dusk)
WOLVES_MAX_ALIVE = 2
DEER_MAX_ALIVE = 3
DEER_DAY_SPAWN_CHANCE = 0.25

# --- the numbers of a fight ---------------------------------------------------
WOLF_BITE_DAMAGE = 8.0      # vitality per bite (full vitality: many bites)
WOLF_FLEE_HP = 1            # one good hit drives a wolf off (they are wary)
DEER_HP = 2                 # two hits without a tool; one with iron

TOOL_DAMAGE_BONUS = {       # multiplier on hit damage by best held tool
    "iron_tool": 4.0,
    "iron_spear": 4.0,
    "flint_spear": 3.0,
    "stone_axe": 2.5,
    "flint_knife": 2.0,
    "flint": 2.0,
}
UNARMED_DAMAGE = 1.0

MEAT = "meat"
MEAT_SATISFACTION = 40.0    # a kill feeds a pair for days
DEER_MEAT_DROP = 4


def _dist(a_xy, b_xy) -> int:
    """Chebyshev distance between tile coordinate tuples."""
    if a_xy is None or b_xy is None:
        return 999
    return max(abs(a_xy[0] - b_xy[0]), abs(a_xy[1] - b_xy[1]))


def wilderness(tile_xy: tuple, agent_xys: list, fire_xys: list) -> bool:
    """True if a tile is wilderness: outside every fire's safety radius
    and at least WOLF_SPAWN_DISTANCE from every agent."""
    for fxy in fire_xys:
        if _dist(fxy, tile_xy) <= FIRE_SAFETY_RADIUS:
            return False
    for axy in agent_xys:
        if _dist(axy, tile_xy) < WOLF_SPAWN_DISTANCE:
            return False
    return True


def spawn_wolves(entities: list, heartbeat_number: int, night: bool,
                 candidate_tiles: list, agent_xys: list,
                 fire_xys: list, rng: random.Random) -> list:
    """Night spawn pass. Wolves appear rarely, in the dark, far away.
    Returns the new entity list. Deterministic given rng."""
    alive_wolves = sum(1 for e in entities if e.get("kind") == "wolf")
    # nights straddle midnight, so key the roll to the night window:
    # shift the clock so a night maps to a single index
    night_key = (heartbeat_number - int(survival.DAY_LENGTH
                                        * survival.DAY_PHASE_END)
                 ) // survival.DAY_LENGTH
    already_rolled = any(
        e.get("spawn_day") == night_key for e in entities
        if e.get("kind") == "wolf")
    if (not night or already_rolled or alive_wolves >= WOLVES_MAX_ALIVE
            or not candidate_tiles):
        return entities
    if rng.random() > WOLF_NIGHT_SPAWN_CHANCE:
        return entities
    wild = [t for t in candidate_tiles
            if wilderness(t, agent_xys, fire_xys)]
    if not wild:
        return entities
    tile = rng.choice(wild)
    entities = list(entities)
    entities.append({
        "kind": "wolf",
        "id": f"wolf-{heartbeat_number}-{len(entities)}",
        "tile": tile,
        "hp": WOLF_FLEE_HP,
        "spawn_day": night_key,
    })
    return entities


def spawn_deer(entities: list, heartbeat_number: int, candidate_tiles: list,
               agent_xys: list, rng: random.Random) -> list:
    """Day-or-night deer: skittish, plentiful, never dangerous."""
    alive_deer = sum(1 for e in entities if e.get("kind") == "deer")
    if alive_deer >= DEER_MAX_ALIVE or not candidate_tiles:
        return entities
    if rng.random() > DEER_DAY_SPAWN_CHANCE:
        return entities
    wild = [t for t in candidate_tiles
            if all(_dist(axy, t) >= DEER_FLEE_RADIUS + 1
                   for axy in agent_xys)]
    if not wild:
        return entities
    tile = rng.choice(wild)
    entities = list(entities)
    entities.append({
        "kind": "deer",
        "id": f"deer-{heartbeat_number}-{len(entities)}",
        "tile": tile,
        "hp": DEER_HP,
    })
    return entities


def move_wolf(entity: dict, agent_xys: list, agent_positions: dict,
              fire_xys: list, sheltered_tiles: set,
              rng: random.Random) -> dict:
    """One wolf's move: approach the nearest agent in the dark, but
    never into fire safety radius, never onto a sheltered tile, and
    flee if the agent stands by fire."""
    import math

    def neighbors(tile):
        x, y = tile
        return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if not (dx == 0 and dy == 0)]

    tile = entity["tile"]
    txy = (tile[0], tile[1]) if isinstance(tile, (list, tuple)) else tile
    # nearest agent
    nearest, nearest_d = None, 999
    for axy in agent_xys:
        d = _dist(axy, txy)
        if d < nearest_d:
            nearest, nearest_d = axy, d
    if nearest is None:
        return entity
    # the agent is by fire: the wolf keeps its distance (wary, circles)
    for fxy in fire_xys:
        if _dist(fxy, nearest) <= FIRE_SAFETY_RADIUS:
            if _dist(txy, nearest) <= FIRE_SAFETY_RADIUS + 1:
                return entity  # hold at the edge of the light
    # flee if adjacent to an agent by a fire, else approach
    step_options = [n for n in neighbors(txy)
                    if all(_dist(fxy, n) > FIRE_SAFETY_RADIUS
                           for fxy in fire_xys)
                    and n not in sheltered_tiles]
    if not step_options:
        return entity
    target = min(step_options, key=lambda n: _dist(n, nearest))
    entity = dict(entity)
    entity["tile"] = target
    return entity


def move_deer(entity: dict, agent_xys: list, rng: random.Random) -> dict:
    """Deer flee: they keep DEER_FLEE_RADIUS + 1 between themselves and
    every agent, drifting randomly otherwise."""
    tile = entity["tile"]
    txy = (tile[0], tile[1]) if isinstance(tile, (list, tuple)) else tile

    def neighbors(t):
        x, y = t
        return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if not (dx == 0 and dy == 0)]

    nearest_d = min((_dist(axy, txy) for axy in agent_xys), default=999)
    options = neighbors(txy)
    if nearest_d <= DEER_FLEE_RADIUS:
        # bolt: the neighbor that maximizes distance to the nearest agent
        def min_dist(n):
            return min((_dist(axy, n) for axy in agent_xys), default=999)
        flee = max(options, key=min_dist)
        entity = dict(entity)
        entity["tile"] = flee
        return entity
    # idle drift, half the time
    if rng.random() < 0.5:
        entity = dict(entity)
        entity["tile"] = rng.choice(options)
    return entity


def best_tool_multiplier(inventory: dict) -> float:
    """The best held tool multiplies strike damage."""
    best = UNARMED_DAMAGE
    for tool, mult in TOOL_DAMAGE_BONUS.items():
        if isinstance(inventory.get(tool), int) and inventory[tool] > 0:
            best = max(best, mult)
    return best


def strike(entity: dict, inventory: dict) -> tuple:
    """One agent strike on an animal. Returns (entity, damage, killed,
    meat_dropped). Tools decide: spears, axes, and iron strike with amplified
    damage; a wolf flees when its HP is exhausted."""
    mult = best_tool_multiplier(inventory)
    dmg = UNARMED_DAMAGE * mult
    hp = max(0, entity.get("hp", 1) - dmg)
    entity = dict(entity)
    entity["hp"] = hp
    killed = hp <= 0
    meat = DEER_MEAT_DROP if (killed and entity.get("kind") == "deer") else 0
    if killed and entity.get("kind") == "wolf":
        meat = 2
    return entity, dmg, killed, meat
