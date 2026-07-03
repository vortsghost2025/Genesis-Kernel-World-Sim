"""Phase 10AO - local ledger replay verifier.

Replay accepted public ledger events (written by Phase 10AN) into a
deterministic audit summary.  This is audit replay only: it does not
project a known map, does not rebuild true_map, does not export memory,
and does not touch any runtime substrate.

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens network handles, never spawns processes, and never writes
files.  The only I/O happens in :func:`replay_ledger_file`, which
delegates file reading to the existing 10K ledger reader.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from backend.world.world_event_ledger import read_events


# Replayed action types.  Only these accepted public events are replayed
# into the audit summary; other accepted actions (gather / whisper / ...)
# remain accepted in the ledger but are not part of the audit replay.
_REPLAYABLE_ACTION_TYPES = ("observe", "move_local")


def _empty_summary(errors: list[str]) -> dict[str, Any]:
    return {
        "ok": not errors,
        "agent_id": None,
        "final_public_position": None,
        "observed_tile_ids": [],
        "movement_chain": [],
        "first_tick": None,
        "last_tick": None,
        "event_count": 0,
        "accepted_event_count": 0,
        "ignored_event_count": 0,
        "errors": errors,
    }


def _coerce_tick(value: Any) -> int | None:
    """Return *value* as an int when it is a clean integer-like object.

    Booleans are rejected because ``isinstance(True, int)`` is True in
    Python but a boolean is not a meaningful replay tick.
    """

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _parse_tile_ref(ref: Any) -> str | None:
    """Parse a ``"tile:<id>"`` reference into the bare tile id.

    Returns ``None`` when the value is not a string tile reference.
    """

    if not isinstance(ref, str):
        return None
    prefix = "tile:"
    if not ref.startswith(prefix):
        return None
    tile_id = ref[len(prefix):].strip()
    if not tile_id:
        return None
    return tile_id


def _extract_move_tiles(event: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return ``(from_tile_id, to_tile_id)`` for an accepted move event.

    Preference order is ``after_ref`` / ``before_ref`` first (the public
    custody refs), falling back to the ``agent_action`` evidence payload.
    """

    from_tile = _parse_tile_ref(event.get("before_ref"))
    to_tile = _parse_tile_ref(event.get("after_ref"))

    if from_tile is None or to_tile is None:
        evidence_refs = event.get("evidence_refs")
        if isinstance(evidence_refs, list):
            for evidence in evidence_refs:
                if not isinstance(evidence, dict):
                    continue
                if evidence.get("category") != "agent_action":
                    continue
                candidate_from = evidence.get("from_tile")
                candidate_to = evidence.get("to_tile")
                if from_tile is None and isinstance(candidate_from, str) and candidate_from:
                    from_tile = candidate_from
                if to_tile is None and isinstance(candidate_to, str) and candidate_to:
                    to_tile = candidate_to
                if from_tile is not None and to_tile is not None:
                    break

    return from_tile, to_tile


def _extract_observed_tile_ids(event: dict[str, Any]) -> list[str]:
    """Collect observed tile ids from ``observed_world_fact`` evidence."""

    tile_ids: list[str] = []
    evidence_refs = event.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        return tile_ids
    for evidence in evidence_refs:
        if not isinstance(evidence, dict):
            continue
        if evidence.get("category") != "observed_world_fact":
            continue
        raw_tile_ids = evidence.get("tile_ids")
        if not isinstance(raw_tile_ids, list):
            continue
        for item in raw_tile_ids:
            if isinstance(item, str) and item:
                tile_ids.append(item)
    return tile_ids


def replay_accepted_events(events: list[dict]) -> dict:
    """Replay accepted public ledger events into a deterministic audit summary.

    The input list is never mutated; a deep copy is taken before replay.
    Non-accepted events (``verification_status != "accepted"``) are
    ignored and counted, never replayed.

    The replay is single-agent only: if the accepted events reference
    more than one ``actor_id`` the result marks ``ok=False`` with a safe
    boundary error and performs no further replay.
    """

    if not isinstance(events, list):
        summary = _empty_summary(["events must be a list"])
        summary["ok"] = False
        return summary

    # Deep copy so the caller-owned input can never be mutated by replay.
    local_events = copy.deepcopy(events)

    event_count = len(local_events)
    accepted_events = [
        event
        for event in local_events
        if isinstance(event, dict) and event.get("verification_status") == "accepted"
    ]
    accepted_event_count = len(accepted_events)
    ignored_event_count = event_count - accepted_event_count

    errors: list[str] = []

    # Single-agent boundary: only one actor id may appear among accepted events.
    actor_ids = sorted(
        {
            str(event.get("actor_id"))
            for event in accepted_events
            if event.get("actor_id")
        }
    )
    multi_actor = len(actor_ids) > 1
    if multi_actor:
        errors.append(
            "multiple actors in accepted events; 10AO is single-agent replay only"
        )

    summary = _empty_summary(errors)
    summary["event_count"] = event_count
    summary["accepted_event_count"] = accepted_event_count
    summary["ignored_event_count"] = ignored_event_count

    if multi_actor:
        summary["ok"] = False
        return summary

    summary["agent_id"] = actor_ids[0] if actor_ids else None

    # Deterministic ordering: sort accepted replayable events by (tick, event_id).
    replayable = [
        event
        for event in accepted_events
        if event.get("action_type") in _REPLAYABLE_ACTION_TYPES
    ]

    # Validate ticks up front so the sort key is well defined.
    valid_replayable: list[dict[str, Any]] = []
    for event in replayable:
        event_id = event.get("event_id")
        tick = _coerce_tick(event.get("tick"))
        if tick is None:
            errors.append(
                f"accepted {event.get('action_type')} event "
                f"id={event.get('event_id')!r} has invalid tick"
            )
            continue
        valid_replayable.append(event)

    valid_replayable.sort(key=lambda e: (e["tick"], str(e.get("event_id") or "")))

    observed_tile_ids: list[str] = []
    seen_tile_ids: set[str] = set()
    movement_chain: list[dict[str, Any]] = []
    final_public_position: dict[str, str] | None = None
    first_tick: int | None = None
    last_tick: int | None = None

    for event in valid_replayable:
        tick = event["tick"]
        action_type = event.get("action_type")
        event_id = str(event.get("event_id") or "")

        if first_tick is None or (tick is not None and tick < first_tick):
            first_tick = tick
        if last_tick is None or (tick is not None and tick > last_tick):
            last_tick = tick

        if action_type == "observe":
            tile_ids = _extract_observed_tile_ids(event)
            if not tile_ids:
                errors.append(
                    f"accepted observe event id={event.get('event_id')!r} "
                    "has no observed_world_fact tile_ids"
                )
                continue
            for tile_id in tile_ids:
                if tile_id not in seen_tile_ids:
                    seen_tile_ids.add(tile_id)
                    observed_tile_ids.append(tile_id)
        elif action_type == "move_local":
            from_tile_id, to_tile_id = _extract_move_tiles(event)
            if not from_tile_id or not to_tile_id:
                errors.append(
                    f"accepted move_local event id={event.get('event_id')!r} "
                    "has no valid from/to tile references"
                )
                continue
            territory_ref = event.get("territory_ref", "")
            if not isinstance(territory_ref, str):
                territory_ref = str(territory_ref)
            movement_chain.append(
                {
                    "tick": tick,
                    "from_tile_id": from_tile_id,
                    "to_tile_id": to_tile_id,
                    "territory_ref": territory_ref,
                    "event_id": event_id,
                }
            )
            final_public_position = {
                "tile_id": to_tile_id,
                "territory_ref": territory_ref,
            }

    summary["final_public_position"] = final_public_position
    # Deterministic observed tile id ordering: sort for stability across runs
    # and across any input ordering differences.
    summary["observed_tile_ids"] = sorted(observed_tile_ids)
    summary["movement_chain"] = movement_chain
    summary["first_tick"] = first_tick
    summary["last_tick"] = last_tick
    summary["ok"] = len(errors) == 0

    return summary


def replay_ledger_file(ledger_path: Path | str) -> dict:
    """Read a ledger file with ``read_events(...)`` and replay accepted public events.

    File loading is delegated entirely to
    :func:`backend.world.world_event_ledger.read_events`; this function
    only replays the in-memory events it receives.
    """

    events = read_events(ledger_path)
    return replay_accepted_events(events)
