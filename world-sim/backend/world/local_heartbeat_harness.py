"""Phase 10AL – Tiny Local Heartbeat Harness.

Pure helper that runs a single deterministic multi‑tick exploration loop (Phase 10AK)
and returns a minimal heartbeat record.

No runtime pauses, threads, async calls, network I/O or hidden data leakage.
"""

from __future__ import annotations

import copy
from typing import Any

# Import the pure deterministic exploration helper from Phase 10AK.
from backend.world.local_exploration_loop import run_multi_tick_exploration


def run_local_exploration_heartbeat(
    *,
    true_map: dict[str, Any],
    current_position: dict[str, Any],
    known_map: dict[str, Any],
    directions: list[str],
    heartbeat_index: int | None = None,
    heartbeat_id: str | None = None,
    start_tick: int = 1,
    observation_conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a deterministic heartbeat.

    Parameters
    ----------
    true_map:
        Full world map – read‑only, never copied nor returned.
    current_position:
        Agent's current active position (will be deep‑copied).
    known_map:
        Caller‑owned known map – deep‑copied before use.
    directions:
        List of movement direction strings to feed to the exploration loop.
    heartbeat_index / heartbeat_id:
        Optional identifiers. If both are ``None`` a default ``heartbeat_id``
        is derived from ``start_tick``.
    start_tick:
        Tick counter to begin the exploration (default ``1``).
    observation_conditions:
        Optional conditions forwarded to the underlying observation helper.

    Returns
    -------
    dict
        A JSON‑serialisable record containing the heartbeat outcome. The
        ``true_map`` is deliberately omitted.
    """

    # Defensive copies – contract requires we never mutate caller data.
    position_copy = copy.deepcopy(current_position)
    known_copy = copy.deepcopy(known_map)
    directions_copy = copy.deepcopy(directions)
    conditions_copy = (
        copy.deepcopy(observation_conditions)
        if observation_conditions is not None
        else None
    )

    # Derive identifiers when not supplied.
    if heartbeat_id is None and heartbeat_index is None:
        heartbeat_id = f"heartbeat-{start_tick}"
    hb_index = heartbeat_index

    # Execute the pure exploration loop exactly once, passing true_map directly.
    loop_result = run_multi_tick_exploration(
        true_map=true_map,
        initial_position=position_copy,
        initial_known_map=known_copy,
        directions=directions_copy,
        start_tick=start_tick,
        observation_conditions=conditions_copy,
    )

    # Determine end tick – timeline may be empty in pathological cases.
    timeline = loop_result.get("timeline", [])
    end_tick = timeline[-1]["tick"] if timeline else start_tick

    # Minimal heartbeat record as specified.
    heartbeat_record = {
        "heartbeat_id": heartbeat_id,
        "heartbeat_index": hb_index,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "ok": bool(loop_result.get("ok")),
        "action_count": len(timeline),
        "final_tile_id": (
            loop_result.get("final_position", {}).get("tile_id")
            if loop_result.get("final_position")
            else None
        ),
        "error": loop_result.get("error"),
    }

    # Assemble the public result – intentionally omit ``true_map``.
    result: dict[str, Any] = {
        "ok": bool(loop_result.get("ok")),
        "heartbeat_id": heartbeat_id,
        "heartbeat_index": hb_index,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "final_position": copy.deepcopy(loop_result.get("final_position")),
        "known_map": loop_result.get("known_map"),
        "timeline": timeline,
        "heartbeat_record": heartbeat_record,
        "error": loop_result.get("error"),
        "failed_tick": loop_result.get("failed_tick"),
        "failed_direction": loop_result.get("failed_direction"),
    }
    return result
