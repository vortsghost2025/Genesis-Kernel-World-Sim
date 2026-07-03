"""Phase 10AK — Multi-Tick Exploration Loop.

Pure deterministic helper for local observe -> remember -> move exploration.
No runtime, daemon, scheduler, provider, Docker, live agent, external service,
or canonical data mutation is involved.
"""

from __future__ import annotations

import copy
from typing import Any

from backend.world.fog_of_war import (
    build_local_observation,
    merge_observation_into_known_map,
)
from backend.world.local_movement import resolve_local_move


def _observe_entry(tick: int, observation: dict[str, Any]) -> dict[str, Any]:
    position = observation.get("position", {})
    return {
        "tick": tick,
        "action": "observe",
        "tile_id": position.get("tile_id"),
        "territory_ref": position.get("region_id"),
        "visible_tile_ids": list(observation.get("visible_tile_ids", [])),
    }


def _move_entry(tick: int, direction: str, move_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "tick": tick,
        "action": "move_local",
        "direction": direction,
        "ok": bool(move_result.get("ok")),
        "from_tile_id": move_result.get("previous_tile_id"),
        "to_tile_id": move_result.get("tile_id"),
        "territory_ref": move_result.get("territory_ref"),
        "error": move_result.get("error"),
    }


def run_multi_tick_exploration(
    *,
    true_map: dict[str, Any],
    initial_position: dict[str, Any],
    initial_known_map: dict[str, Any],
    directions: list[str],
    start_tick: int = 1,
    observation_conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a pure deterministic local exploration sequence.

    Tick pattern for ``directions=["north", "southeast"]`` and
    ``start_tick=1`` is:

    - tick 1: observe + merge known_map
    - tick 2: move_local
    - tick 3: observe + merge known_map
    - tick 4: move_local
    - tick 5: observe + merge known_map

    The returned result intentionally excludes ``true_map`` and keeps timeline
    entries minimal so hidden substrate details are not exposed.
    """
    if not isinstance(start_tick, int) or start_tick < 0:
        raise ValueError(f"start_tick must be a non-negative integer, got {start_tick!r}")
    if not isinstance(directions, list):
        raise ValueError("directions must be a list of direction strings")

    position = copy.deepcopy(initial_position)
    known_map = copy.deepcopy(initial_known_map)
    conditions = copy.deepcopy(observation_conditions)

    observations: list[dict[str, Any]] = []
    move_results: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []

    tick = start_tick
    observation = build_local_observation(true_map, position, known_map, conditions)
    merge_observation_into_known_map(known_map, observation, tick)
    observations.append(observation)
    timeline.append(_observe_entry(tick, observation))

    for direction in directions:
        tick += 1
        move_result = resolve_local_move(position, direction, true_map, tick=tick)
        move_results.append(move_result)
        timeline.append(_move_entry(tick, direction, move_result))

        if not move_result.get("ok"):
            return {
                "ok": False,
                "error": move_result.get("error"),
                "failed_tick": tick,
                "failed_direction": direction,
                "final_position": copy.deepcopy(position),
                "known_map": known_map,
                "observations": observations,
                "move_results": move_results,
                "timeline": timeline,
            }

        position = copy.deepcopy(move_result["new_position"])

        tick += 1
        observation = build_local_observation(true_map, position, known_map, conditions)
        merge_observation_into_known_map(known_map, observation, tick)
        observations.append(observation)
        timeline.append(_observe_entry(tick, observation))

    return {
        "ok": True,
        "error": None,
        "failed_tick": None,
        "failed_direction": None,
        "final_position": copy.deepcopy(position),
        "known_map": known_map,
        "observations": observations,
        "move_results": move_results,
        "timeline": timeline,
    }
