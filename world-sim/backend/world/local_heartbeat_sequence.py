"""Phase 10AM – Bounded Heartbeat Sequence Runner.

Pure helper that chains a finite number of Phase 10AL heartbeats
deterministically. Each heartbeat consumes the previous heartbeat's
``final_position`` and ``known_map`` and advances ``start_tick`` to the
previous heartbeat ``end_tick + 1``.

No runtime pauses, threads, async calls, network I/O or hidden data leakage.
The ``true_map`` is forwarded untouched to the heartbeat helper and never
mutated, copied wholesale, or returned.
"""

from __future__ import annotations

import copy
from typing import Any

from backend.world.local_heartbeat_harness import run_local_exploration_heartbeat


def run_local_heartbeat_sequence(
    *,
    true_map: dict[str, Any],
    current_position: dict[str, Any],
    known_map: dict[str, Any],
    heartbeat_plan: list[dict[str, Any]],
    start_tick: int = 1,
    sequence_id: str | None = None,
    observation_conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Chain a finite list of heartbeats into one bounded sequence.

    Parameters
    ----------
    true_map:
        Full world map – read-only, forwarded to each heartbeat untouched.
    current_position:
        Agent's current active position (deep-copied before use).
    known_map:
        Caller-owned known map – deep-copied before use and carried forward.
    heartbeat_plan:
        Finite list of plan items, e.g. ``[{"heartbeat_id": "hb-1",
        "directions": ["north"]}]``. Deep-copied before iteration.
    start_tick:
        Tick counter to begin the first heartbeat (default ``1``).
    sequence_id:
        Optional identifier echoed back in the result.
    observation_conditions:
        Optional conditions forwarded to every heartbeat.

    Returns
    -------
    dict
        JSON-serialisable sequence record. The ``true_map`` is deliberately
        omitted. On a heartbeat failure prior successful heartbeats remain in
        ``heartbeats`` and the failing entry is appended too.
    """

    # Defensive copies – contract requires we never mutate caller data.
    position = copy.deepcopy(current_position)
    known = copy.deepcopy(known_map)
    plan = copy.deepcopy(heartbeat_plan)
    conditions = (
        copy.deepcopy(observation_conditions)
        if observation_conditions is not None
        else None
    )

    # Empty plan – return an unchanged safe packet.
    if not plan:
        return {
            "ok": True,
            "sequence_id": sequence_id,
            "start_tick": start_tick,
            "end_tick": start_tick,
            "final_position": copy.deepcopy(position),
            "known_map": copy.deepcopy(known),
            "heartbeats": [],
            "timeline": [],
            "error": None,
            "failed_heartbeat_id": None,
            "failed_heartbeat_index": None,
            "failed_tick": None,
            "failed_direction": None,
        }

    heartbeats: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    running_position = position
    running_known = known
    next_start_tick = start_tick

    for index, item in enumerate(plan):
        heartbeat_id = item.get("heartbeat_id")
        directions = copy.deepcopy(item.get("directions", []))

        heartbeat_result = run_local_exploration_heartbeat(
            true_map=true_map,
            current_position=running_position,
            known_map=running_known,
            directions=directions,
            heartbeat_index=index,
            heartbeat_id=heartbeat_id,
            start_tick=next_start_tick,
            observation_conditions=copy.deepcopy(conditions),
        )

        heartbeats.append(heartbeat_result)
        heartbeat_timeline = heartbeat_result.get("timeline", [])
        timeline.extend(heartbeat_timeline)

        if not heartbeat_result.get("ok"):
            return {
                "ok": False,
                "sequence_id": sequence_id,
                "start_tick": start_tick,
                "end_tick": heartbeat_result.get("end_tick", next_start_tick),
                "final_position": heartbeat_result.get("final_position"),
                "known_map": heartbeat_result.get("known_map"),
                "heartbeats": heartbeats,
                "timeline": timeline,
                "error": heartbeat_result.get("error"),
                "failed_heartbeat_id": heartbeat_id,
                "failed_heartbeat_index": index,
                "failed_tick": heartbeat_result.get("failed_tick"),
                "failed_direction": heartbeat_result.get("failed_direction"),
            }

        # Carry forward for the next heartbeat.
        running_position = copy.deepcopy(heartbeat_result.get("final_position"))
        running_known = copy.deepcopy(heartbeat_result.get("known_map"))
        next_start_tick = heartbeat_result.get("end_tick", next_start_tick) + 1

    return {
        "ok": True,
        "sequence_id": sequence_id,
        "start_tick": start_tick,
        "end_tick": heartbeats[-1].get("end_tick", start_tick),
        "final_position": copy.deepcopy(running_position),
        "known_map": copy.deepcopy(running_known),
        "heartbeats": heartbeats,
        "timeline": timeline,
        "error": None,
        "failed_heartbeat_id": None,
        "failed_heartbeat_index": None,
        "failed_tick": None,
        "failed_direction": None,
    }
