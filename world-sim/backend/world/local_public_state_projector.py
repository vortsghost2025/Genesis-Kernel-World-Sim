"""Phase 10AP - public state projector.

Project accepted public ledger events into a deterministic current public view.
The projector is pure: it does not mutate caller-owned input and does not write
canonical state.  It only reads files through ``project_ledger_file`` by
delegating to the existing ledger reader.

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_ledger import read_events

_REPLAYABLE_ACTION_TYPES = ("observe", "move_local")


def _empty_projection(errors: list[str]) -> dict[str, Any]:
    return {
        "ok": not errors,
        "agent_id": None,
        "current_tile_id": None,
        "current_territory_ref": None,
        "observed_tile_ids": [],
        "visited_tile_ids": [],
        "movement_count": 0,
        "observation_count": 0,
        "first_tick": None,
        "last_tick": None,
        "last_event_id": None,
        "accepted_event_count": 0,
        "ignored_event_count": 0,
        "errors": errors,
    }


def _coerce_tick(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _parse_tile_ref(ref: Any) -> str | None:
    if not isinstance(ref, str):
        return None
    prefix = "tile:"
    if not ref.startswith(prefix):
        return None
    tile_id = ref[len(prefix):].strip()
    return tile_id or None


def _extract_move_tiles(event: dict[str, Any]) -> tuple[str | None, str | None]:
    from_tile = _parse_tile_ref(event.get("before_ref"))
    to_tile = _parse_tile_ref(event.get("after_ref"))

    evidence_refs = event.get("evidence_refs")
    if (from_tile is None or to_tile is None) and isinstance(evidence_refs, list):
        for evidence in evidence_refs:
            if not isinstance(evidence, dict):
                continue
            if evidence.get("category") != "agent_action":
                continue
            candidate_from = evidence.get("from_tile") or evidence.get("from_tile_id")
            candidate_to = evidence.get("to_tile") or evidence.get("to_tile_id")
            if from_tile is None and isinstance(candidate_from, str) and candidate_from:
                from_tile = candidate_from
            if to_tile is None and isinstance(candidate_to, str) and candidate_to:
                to_tile = candidate_to
            if from_tile and to_tile:
                break

    return from_tile, to_tile


def _extract_observed_tile_ids(event: dict[str, Any]) -> list[str]:
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


def _extract_observed_current_tile_id(event: dict[str, Any]) -> str | None:
    evidence_refs = event.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        return None
    for evidence in evidence_refs:
        if not isinstance(evidence, dict):
            continue
        if evidence.get("category") != "observed_world_fact":
            continue
        detail = evidence.get("observation_detail")
        if isinstance(detail, str) and detail:
            try:
                parsed = json.loads(detail)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                tile_id = parsed.get("tile_id")
                if isinstance(tile_id, str) and tile_id:
                    return tile_id
        tile_id = evidence.get("tile_id")
        if isinstance(tile_id, str) and tile_id:
            return tile_id
    return None


def _event_id(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or "")


def _territory_ref(event: dict[str, Any]) -> str | None:
    territory_ref = event.get("territory_ref")
    if isinstance(territory_ref, str) and territory_ref:
        return territory_ref
    return None


def project_public_state(events: list[dict]) -> dict:
    """Project accepted public ledger events into a deterministic current public state view."""

    if not isinstance(events, list):
        projection = _empty_projection(["events must be a list"])
        projection["ok"] = False
        return projection

    local_events = copy.deepcopy(events)
    accepted_events = [
        event
        for event in local_events
        if isinstance(event, dict) and event.get("verification_status") == "accepted"
    ]
    accepted_event_count = len(accepted_events)
    ignored_event_count = len(local_events) - accepted_event_count

    errors: list[str] = []
    actor_ids = sorted(
        {
            str(event.get("actor_id"))
            for event in accepted_events
            if event.get("actor_id")
        }
    )
    if len(actor_ids) > 1:
        projection = _empty_projection(
            ["multiple actors in accepted events; 10AP is single-agent projection only"]
        )
        projection["accepted_event_count"] = accepted_event_count
        projection["ignored_event_count"] = ignored_event_count
        projection["ok"] = False
        return projection

    projection = _empty_projection(errors)
    projection["agent_id"] = actor_ids[0] if actor_ids else None
    projection["accepted_event_count"] = accepted_event_count
    projection["ignored_event_count"] = ignored_event_count

    replayable = [
        event
        for event in accepted_events
        if event.get("action_type") in _REPLAYABLE_ACTION_TYPES
    ]

    valid_replayable: list[dict[str, Any]] = []
    for event in replayable:
        tick = _coerce_tick(event.get("tick"))
        if tick is None:
            errors.append(
                f"accepted {event.get('action_type')} event "
                f"id={event.get('event_id')!r} has invalid tick"
            )
            continue
        event["tick"] = tick
        valid_replayable.append(event)

    valid_replayable.sort(key=lambda event: (event["tick"], _event_id(event)))

    observed_tile_ids: set[str] = set()
    visited_tile_ids: set[str] = set()
    movement_count = 0
    observation_count = 0
    first_tick: int | None = None
    last_tick: int | None = None
    last_event_id: str | None = None
    latest_move_tile_id: str | None = None
    latest_move_territory_ref: str | None = None
    latest_observe_territory_ref: str | None = None

    for event in valid_replayable:
        tick = event["tick"]
        first_tick = tick if first_tick is None else min(first_tick, tick)
        last_tick = tick
        last_event_id = _event_id(event)

        action_type = event.get("action_type")
        if action_type == "observe":
            tile_ids = _extract_observed_tile_ids(event)
            if not tile_ids:
                errors.append(
                    f"accepted observe event id={event.get('event_id')!r} "
                    "has no observed_world_fact tile_ids"
                )
                continue
            observation_count += 1
            observed_tile_ids.update(tile_ids)
            current_observed_tile_id = _extract_observed_current_tile_id(event)
            if current_observed_tile_id:
                visited_tile_ids.add(current_observed_tile_id)
            territory_ref = _territory_ref(event)
            if territory_ref:
                latest_observe_territory_ref = territory_ref
        elif action_type == "move_local":
            from_tile_id, to_tile_id = _extract_move_tiles(event)
            if not from_tile_id or not to_tile_id:
                errors.append(
                    f"accepted move_local event id={event.get('event_id')!r} "
                    "has no valid from/to tile references"
                )
                continue
            movement_count += 1
            visited_tile_ids.add(from_tile_id)
            visited_tile_ids.add(to_tile_id)
            latest_move_tile_id = to_tile_id
            latest_move_territory_ref = _territory_ref(event)

    projection["current_tile_id"] = latest_move_tile_id
    projection["current_territory_ref"] = (
        latest_move_territory_ref if latest_move_territory_ref is not None else latest_observe_territory_ref
    )
    projection["observed_tile_ids"] = sorted(observed_tile_ids)
    projection["visited_tile_ids"] = sorted(visited_tile_ids)
    projection["movement_count"] = movement_count
    projection["observation_count"] = observation_count
    projection["first_tick"] = first_tick
    projection["last_tick"] = last_tick
    projection["last_event_id"] = last_event_id
    projection["ok"] = len(errors) == 0
    return projection


def project_ledger_file(ledger_path: Path | str) -> dict:
    """Read a ledger file with read_events(...) and project accepted public events."""

    events = read_events(ledger_path)
    return project_public_state(events)
