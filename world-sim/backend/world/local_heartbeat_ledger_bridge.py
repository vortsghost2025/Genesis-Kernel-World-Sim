"""Phase 10AN - bounded sequence to ledger bridge.

Transforms the public Phase 10AM sequence packet into verified event records
inside a caller supplied temp directory. The hidden true_map is never accepted,
read from disk, returned, exported, or inferred.
"""

from __future__ import annotations

import copy
import json
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.world.world_event_candidate_mapper import (
    candidate_from_move_result,
    candidate_from_observe_result,
)
from backend.world.world_event_exporter import export_events
from backend.world.world_event_ledger import append_event, read_events
from backend.world.world_event_sanitizer import (
    sanitize_public_mapping,
    sanitize_public_text,
)
from backend.world.world_event_verifier import verify_candidate_event


def _safe_temp_dir(path: Path) -> bool:
    try:
        path.resolve().relative_to(Path(tempfile.gettempdir()).resolve())
        return True
    except (OSError, ValueError):
        return False


def _safe_label(value: Any) -> str:
    raw = "sequence" if value in (None, "") else str(value)
    label = re.sub(r"[^A-Za-z0-9_.:-]+", "-", raw).strip("-")
    return label or "sequence"


def _timestamp_for_tick(tick: Any) -> str:
    seconds = int(tick) if isinstance(tick, int) and tick >= 0 else 0
    stamp = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)
    return stamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _actor_id(sequence: dict[str, Any], override: str | None) -> str:
    if override:
        return override
    for key in ("final_position", "known_map"):
        value = sequence.get(key)
        if isinstance(value, dict) and value.get("agent_id"):
            return str(value["agent_id"])
    return "unknown_agent"


def _failure(sequence: dict[str, Any]) -> dict[str, Any] | None:
    if sequence.get("ok"):
        return None
    return {
        "error": sanitize_public_text(str(sequence.get("error", ""))),
        "failed_tick": sequence.get("failed_tick"),
        "failed_direction": sequence.get("failed_direction"),
        "failed_heartbeat_id": sequence.get("failed_heartbeat_id"),
        "failed_heartbeat_index": sequence.get("failed_heartbeat_index"),
    }


def _base_result(
    *,
    ok: bool,
    sequence_ok: bool | None,
    ledger_path: Path | None,
    event_count: int = 0,
    rejected_count: int = 0,
    sanitized_export: str = "",
    errors: list[str] | None = None,
    failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "sequence_ok": sequence_ok,
        "event_count": event_count,
        "rejected_count": rejected_count,
        "ledger_path": str(ledger_path) if ledger_path is not None else None,
        "sanitized_export": sanitized_export,
        "errors": errors or [],
        "failure": failure,
        "failed_tick": failure.get("failed_tick") if failure else None,
        "failed_direction": failure.get("failed_direction") if failure else None,
        "failed_heartbeat_id": failure.get("failed_heartbeat_id") if failure else None,
        "failed_heartbeat_index": failure.get("failed_heartbeat_index") if failure else None,
    }


def _observe_candidate(
    entry: dict[str, Any],
    *,
    actor_id: str,
    sequence_label: str,
    index: int,
) -> dict[str, Any] | None:
    tick = entry.get("tick")
    if not isinstance(tick, int):
        return None

    visible_tile_ids = list(entry.get("visible_tile_ids", []))
    detail = {
        "sequence_id": sequence_label,
        "timeline_index": index,
        "tile_id": entry.get("tile_id"),
        "visible_tile_ids": visible_tile_ids,
    }
    summary = json.dumps(
        {
            "observed_tile": entry.get("tile_id"),
            "territory_ref": entry.get("territory_ref"),
            "visible_tile_count": len(visible_tile_ids),
        },
        sort_keys=True,
    )
    result = {
        "territory_ref": entry.get("territory_ref", ""),
        "evidence_used": [
            {
                "category": "observed_world_fact",
                "tile_ids": visible_tile_ids,
                "observation_detail": json.dumps(detail, sort_keys=True),
            }
        ],
        "claim_scope": "observed",
    }
    return candidate_from_observe_result(
        actor_id=actor_id,
        action_text=summary,
        result=result,
        tick=tick,
        timestamp_utc=_timestamp_for_tick(tick),
    )


def _move_candidate(
    entry: dict[str, Any],
    *,
    actor_id: str,
    sequence_label: str,
    index: int,
) -> dict[str, Any] | None:
    if entry.get("ok") is not True:
        return None

    tick = entry.get("tick")
    from_tile = entry.get("from_tile_id")
    to_tile = entry.get("to_tile_id")
    territory_ref = entry.get("territory_ref")

    if not isinstance(tick, int) or not from_tile or not to_tile or not territory_ref:
        return None

    move_result = {
        "ok": True,
        "error": entry.get("error"),
        "tile_id": to_tile,
        "territory_ref": territory_ref,
        "before_ref": f"tile:{from_tile}",
        "after_ref": f"tile:{to_tile}",
        "previous_tile_id": from_tile,
        "previous_territory_ref": entry.get("previous_territory_ref", ""),
    }
    action_text = json.dumps(
        {
            "sequence_id": sequence_label,
            "timeline_index": index,
            "action": "move_local",
            "direction": entry.get("direction"),
            "from_tile_id": from_tile,
            "to_tile_id": to_tile,
        },
        sort_keys=True,
    )
    return candidate_from_move_result(
        actor_id,
        action_text,
        move_result,
        tick=tick,
        timestamp_utc=_timestamp_for_tick(tick),
    )


def _candidate_from_timeline_entry(
    entry: dict[str, Any],
    *,
    actor_id: str,
    sequence_label: str,
    index: int,
) -> dict[str, Any] | None:
    action = entry.get("action")
    if action == "observe":
        candidate = _observe_candidate(
            entry,
            actor_id=actor_id,
            sequence_label=sequence_label,
            index=index,
        )
    elif action == "move_local":
        candidate = _move_candidate(
            entry,
            actor_id=actor_id,
            sequence_label=sequence_label,
            index=index,
        )
    else:
        return None

    if candidate is None:
        return None

    tick = entry.get("tick")
    candidate["event_id"] = f"10AN-{sequence_label}-{index:04d}-{tick}-{action}"
    candidate["verification_status"] = "candidate"
    return sanitize_public_mapping(candidate)


def bridge_heartbeat_sequence_to_ledger(
    sequence_result: dict[str, Any],
    *,
    ledger_dir: Path | str,
    actor_id: str | None = None,
    ledger_filename: str = "phase10an_ledger.jsonl",
    export_format: str = "json",
) -> dict[str, Any]:
    """Map public 10AM timeline entries into a temp ledger/export proof."""

    ledger_root = Path(ledger_dir)
    if not _safe_temp_dir(ledger_root):
        failure = {
            "error": "unsafe ledger_dir",
            "failed_tick": None,
            "failed_direction": None,
            "failed_heartbeat_id": None,
            "failed_heartbeat_index": None,
        }
        return _base_result(
            ok=False,
            sequence_ok=None,
            ledger_path=None,
            errors=["ledger_dir must be inside the system temp folder"],
            failure=failure,
        )

    sequence = copy.deepcopy(sequence_result)
    sequence_ok = bool(sequence.get("ok"))
    failure = _failure(sequence)
    sequence_label = _safe_label(sequence.get("sequence_id"))
    resolved_actor_id = _actor_id(sequence, actor_id)
    ledger_path = ledger_root / ledger_filename

    timeline = sequence.get("timeline", [])
    if not isinstance(timeline, list):
        return _base_result(
            ok=False,
            sequence_ok=sequence_ok,
            ledger_path=ledger_path,
            errors=["sequence timeline must be a list"],
            failure=failure,
        )

    event_count = 0
    rejected_count = 0

    for index, raw_entry in enumerate(timeline):
        if not isinstance(raw_entry, dict):
            rejected_count += 1
            continue

        entry = copy.deepcopy(raw_entry)
        candidate = _candidate_from_timeline_entry(
            entry,
            actor_id=resolved_actor_id,
            sequence_label=sequence_label,
            index=index,
        )
        if candidate is None:
            rejected_count += 1
            continue

        existing_events = read_events(ledger_path)
        verdict = verify_candidate_event(candidate, existing_events)
        if not verdict.get("accepted"):
            rejected_count += 1
            continue

        candidate["verification_status"] = "accepted"
        append_result = append_event(ledger_path, candidate)
        if not append_result.get("ok"):
            rejected_count += 1
            continue

        event_count += 1

    events = read_events(ledger_path)
    exported = export_events(events, fmt=export_format, strict=True)
    sanitized_export = sanitize_public_text(exported)

    return _base_result(
        ok=sequence_ok,
        sequence_ok=sequence_ok,
        ledger_path=ledger_path,
        event_count=event_count,
        rejected_count=rejected_count,
        sanitized_export=sanitized_export,
        errors=[],
        failure=failure,
    )
