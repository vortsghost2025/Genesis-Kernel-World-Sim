"""Durable cross-domain faunal interactions.

A fauna interaction changes both inventory and world state. Inventory is
authoritative immediately; world state is explicitly flushed inside the
transaction. A JSONL intent journal lets recovery finish interrupted
interactions idempotently.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    WorldStateRecord,
    load_inventory,
    save_world_state,
)

_FAUNA_INTERACTION_FILE = "fauna_interactions.jsonl"

#: Journal control fields owned by this module, never by caller intent. An
#: intent that could rewrite them could forge a stage (claiming a mutation
#: that never happened) or a timestamp, so they are rejected wholesale.
_FAUNA_JOURNAL_CONTROL_KEYS = frozenset({
    "event_id",
    "stage",
    "created_at_utc",
    "schema_version",
})

_STAGE_RANK = {
    "intent": 0,
    "inventory_applied": 1,
    "fauna_applied": 2,
    "recovered_noop": 3,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_path(store: FirstPairPersistenceStore) -> Path:
    return store._path(_FAUNA_INTERACTION_FILE)


def load_fauna_events(store: FirstPairPersistenceStore) -> list[dict[str, Any]]:
    """Read all fauna interaction events in append order."""
    path = _event_path(store)
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def append_fauna_event(store: FirstPairPersistenceStore, event: dict[str, Any]) -> None:
    """Append and fsync one fauna interaction journal record."""
    path = _event_path(store)
    record = dict(event)
    record.setdefault("schema_version", "fauna_interaction.1")
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def new_event_id(prefix: str, heartbeat_number: int,
                 agent_ref: str, target_id: str) -> str:
    return f"{prefix}-{heartbeat_number}-{agent_ref}-{target_id}-{uuid.uuid4().hex[:12]}"


def begin_animal_interaction(store: FirstPairPersistenceStore,
                             event_id: str, intent: dict[str, Any]) -> None:
    """Durably declare an intended interaction before any mutation.

    Caller intent supplies payload only. Journal control fields are set
    here and are never overridable: a caller that could write its own
    `stage` could certify a mutation that never happened.
    """
    reserved = sorted(_FAUNA_JOURNAL_CONTROL_KEYS & set(intent))
    if reserved:
        raise ValueError(
            "fauna_interaction:reserved_key:" + ",".join(reserved)
        )
    event = {
        "event_id": event_id,
        "stage": "intent",
        "created_at_utc": _utc_now(),
    }
    event.update(intent)
    append_fauna_event(store, event)


def mark_inventory_applied(store: FirstPairPersistenceStore,
                           event_id: str) -> None:
    """Durably record that inventory was successfully mutated."""
    append_fauna_event(store, {
        "event_id": event_id,
        "stage": "inventory_applied",
        "created_at_utc": _utc_now(),
    })


def mark_fauna_applied(store: FirstPairPersistenceStore,
                       event_id: str) -> None:
    """Durably record that fauna/world state was successfully flushed."""
    append_fauna_event(store, {
        "event_id": event_id,
        "stage": "fauna_applied",
        "created_at_utc": _utc_now(),
    })


def _latest_stage(events: list[dict[str, Any]]) -> str:
    return max(events, key=lambda event: _STAGE_RANK.get(event["stage"], -1))["stage"]


def _intent_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in events:
        if event.get("stage") == "intent":
            return event
    raise ValueError("fauna_interaction:missing_intent")


def _find_fauna_by_id(state: WorldStateRecord, target_id: str) -> dict[str, Any]:
    for entity in getattr(state, "fauna", []) or []:
        if entity.get("id") == target_id:
            return entity
    return {}


def _apply_offer_food(target: dict[str, Any], intent: dict[str, Any]) -> None:
    trust_after = int(intent["trust_after"])
    current = int(target.get("trust", 0))
    if current == trust_after:
        return
    if current != int(intent["trust_before"]):
        raise ValueError(
            f"fauna_interaction:unexpected_trust_state {current}"
        )
    target["trust"] = trust_after
    target["tamed"] = bool(intent["tamed_after"])
    if intent["tamed_after"]:
        target["anchor_tile"] = intent.get("anchor_tile_after")


def _apply_milk(target: dict[str, Any], intent: dict[str, Any]) -> None:
    milk_after = bool(intent["milk_ready_after"])
    current = bool(target.get("milk_ready", False))
    if current == milk_after:
        return
    if current != bool(intent["milk_ready_before"]):
        raise ValueError(
            f"fauna_interaction:unexpected_milk_state {current}"
        )
    target["milk_ready"] = milk_after
    if not milk_after:
        target["milk_ready_at_hb"] = int(intent["milk_ready_at_hb_after"])


def _inventory_matches(store: FirstPairPersistenceStore,
                       intent: dict[str, Any], snapshot_key: str) -> bool:
    """True when current inventory matches the intent's before/after snapshot.

    An agent with no inventory entry never matches a snapshot: a row that
    was never written and a row whose holdings were consumed both read as
    zero, so absence is not evidence that the inventory mutation happened.
    Refusing the match here keeps recovery on the fail-closed path instead
    of granting fauna trust for an interaction that never touched
    inventory.
    """
    expected = intent.get(snapshot_key)
    if not isinstance(expected, dict):
        return False

    agent_ref = intent["agent_ref"]
    inventory = load_inventory(store)
    if agent_ref not in inventory:
        return False

    agent_holdings = inventory[agent_ref]
    actual = {
        kind: int(agent_holdings.get(kind, 0))
        for kind in expected
    }
    desired = {kind: int(value) for kind, value in expected.items()}
    return actual == desired


def recover_fauna_interactions(store: FirstPairPersistenceStore,
                               state: WorldStateRecord) -> dict[str, int]:
    """Recover interrupted offer_food/milk_animal interactions.

    Inventory snapshots in the intent journal close the crash window between
    inventory mutation and journal marker. If inventory matches the "after"
    snapshot but the marker was not written, recovery completes the fauna
    change. If inventory still matches the "before" snapshot, the interaction
    is a noop. Any other state fails closed.

    Ordering is load-bearing: the fauna mutation is persisted through
    save_world_state BEFORE the fauna_applied marker is appended, so the
    marker is never written for state that is not on disk. A crash between
    the two re-runs recovery, which finds the fauna change already applied
    and is a noop.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in load_fauna_events(store):
        event_id = event.get("event_id")
        if event_id:
            grouped.setdefault(event_id, []).append(event)

    recovered = 0
    for event_id, events in grouped.items():
        stage = _latest_stage(events)
        if stage in ("fauna_applied", "recovered_noop"):
            continue

        intent = _intent_event(events)

        # The journal marker is authoritative: an explicit inventory_applied
        # stage already proves inventory was mutated, so its snapshot must not
        # be re-readjudicated (an untouched store legitimately still matches
        # the "before" snapshot — that is the milk case, not a noop). Snapshots
        # exist solely to close the crash window while the marker is absent.
        if stage == "intent":
            if "inventory_before" in intent or "inventory_after" in intent:
                if _inventory_matches(store, intent, "inventory_after"):
                    mark_inventory_applied(store, event_id)
                elif _inventory_matches(store, intent, "inventory_before"):
                    append_fauna_event(store, {
                        "event_id": event_id,
                        "stage": "recovered_noop",
                        "created_at_utc": _utc_now(),
                    })
                    continue
                else:
                    raise ValueError(
                        f"fauna_interaction:unexpected_inventory_state {event_id}"
                    )
            else:
                append_fauna_event(store, {
                    "event_id": event_id,
                    "stage": "recovered_noop",
                    "created_at_utc": _utc_now(),
                })
                continue

        target = _find_fauna_by_id(state, intent["target_id"])
        if not target:
            raise ValueError(
                f"fauna_interaction:missing_fauna {intent['target_id']}"
            )

        if intent["action"] == "offer_food":
            _apply_offer_food(target, intent)
        elif intent["action"] == "milk_animal":
            _apply_milk(target, intent)
        else:
            raise ValueError(f"fauna_interaction:unknown_action {intent['action']}")

        save_world_state(store, state)
        mark_fauna_applied(store, event_id)
        recovered += 1

    return {"recovered": recovered}
