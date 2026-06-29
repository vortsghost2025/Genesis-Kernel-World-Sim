"""Pure append-only world event ledger helpers for Phase 10K.

This module validates and appends JSONL world-event records. It is deliberately
not wired into daemon or live action execution yet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_CLAIM_SCOPES = {
    "observed",
    "memory",
    "speech",
    "hypothesis",
    "operator_proof",
    "unknown",
}

ALLOWED_EVIDENCE_CATEGORIES = {
    "observed_world_fact",
    "agent_memory",
    "agent_speech",
    "agent_action",
    "artifact_record",
    "territory_record",
    "relationship_record",
    "operator_proof",
    "world_event",
}

REQUIRED_FIELDS = {
    "event_id",
    "schema_version",
    "actor_id",
    "lens",
    "territory_ref",
    "action_type",
    "summary",
    "evidence_refs",
    "claim_scope",
    "before_ref",
    "after_ref",
    "affected_agents",
    "artifacts_created_or_changed",
    "relationship_delta",
    "consequence",
    "verification_status",
}

MUTATING_ACTION_TYPES = {
    "gather",
    "move",
    "move_local",
    "create_artifact",
    "modify_artifact",
    "claim_territory",
    "repair",
    "conflict",
    "rollback",
}

PRIVATE_RUNTIME_MARKERS = (
    "kilo.jsonc",
    ".kilo/state/accepted-state-ledger.md",
    "world-sim/data",
    "active_state.md",
)


def _result(errors: list[str]) -> dict[str, Any]:
    return {"ok": not errors, "errors": errors}


def _normalized_path_text(value: str) -> str:
    return value.replace("\\", "/").strip().lower()


def _contains_private_runtime_path(value: str) -> bool:
    text = _normalized_path_text(value)
    return any(marker in text for marker in PRIVATE_RUNTIME_MARKERS)


def _event_text(event: dict[str, Any]) -> str:
    parts: list[str] = [str(event.get("summary", ""))]
    for evidence in event.get("evidence_refs", []) if isinstance(event.get("evidence_refs"), list) else []:
        if isinstance(evidence, dict):
            parts.extend(str(value) for value in evidence.values() if isinstance(value, str))
    return "\n".join(parts).lower()


def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    """Validate a 10K world event without mutating any files."""

    errors: list[str] = []
    if not isinstance(event, dict):
        return _result(["event must be an object"])

    for field in sorted(REQUIRED_FIELDS):
        if field not in event:
            errors.append(f"missing required field: {field}")

    if not (event.get("tick") is not None or event.get("timestamp_utc")):
        errors.append("event requires tick or timestamp_utc")

    if event.get("claim_scope") not in ALLOWED_CLAIM_SCOPES:
        errors.append(f"invalid claim_scope: {event.get('claim_scope')}")

    evidence_refs = event.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append("evidence_refs must be a list")
    else:
        for index, evidence in enumerate(evidence_refs):
            if not isinstance(evidence, dict):
                errors.append(f"evidence_refs[{index}] must be an object")
                continue
            category = evidence.get("category")
            if category not in ALLOWED_EVIDENCE_CATEGORIES:
                errors.append(f"invalid evidence category: {category}")
            for value in evidence.values():
                if isinstance(value, str) and _contains_private_runtime_path(value):
                    errors.append("private/runtime path is not valid in-world evidence")

    if not isinstance(event.get("affected_agents", []), list):
        errors.append("affected_agents must be a list")
    if not isinstance(event.get("artifacts_created_or_changed", []), list):
        errors.append("artifacts_created_or_changed must be a list")

    action_type = event.get("action_type")
    if action_type in MUTATING_ACTION_TYPES and not (event.get("before_ref") and event.get("after_ref")):
        errors.append("mutation event requires before_ref and after_ref")

    text = _event_text(event)
    if event.get("claim_scope") == "observed":
        if "hidden water source" in text or "water source location" in text:
            errors.append("hidden water claims must remain hypothesis unless directly evidenced")
        animal_terms = ("dove", "lamb", "animal")
        movement_terms = ("movement", "movements", "guiding", "leading", "guide", "lead")
        if any(animal in text for animal in animal_terms) and any(term in text for term in movement_terms):
            errors.append("animal movement/guidance claims must remain hypothesis unless directly evidenced")

    return _result(errors)


def read_events(ledger_path: Path | str) -> list[dict[str, Any]]:
    """Read JSONL events from a ledger path in file order."""

    path = Path(ledger_path)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def append_event(ledger_path: Path | str, event: dict[str, Any]) -> dict[str, Any]:
    """Append one valid event as JSONL, preserving existing lines unchanged."""

    validation = validate_event(event)
    if not validation["ok"]:
        return {"ok": False, "errors": validation["errors"], "appended": False}

    path = Path(ledger_path)
    existing_events = read_events(path)
    event_id = event.get("event_id")
    if any(existing.get("event_id") == event_id for existing in existing_events):
        return {"ok": False, "errors": [f"duplicate event_id: {event_id}"], "appended": False}

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    return {"ok": True, "errors": [], "appended": True}
