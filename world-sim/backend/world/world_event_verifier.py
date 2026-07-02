"""Pure event verifier for Phase 10T.

Checks a candidate event against existing ledger events before commitment.
Runs after validate_event passes (reuses it for schema/scope/category checks).
No filesystem I/O — receives existing_events as a pre-loaded list.
"""

from __future__ import annotations

from typing import Any

from backend.world.world_event_ledger import validate_event

# Habitat-approved scopes and their required evidence categories.
# Defined inline — not imported from the ledger — to keep the verifier
# constrained to the habitat model. The ledger's allowlist is broader
# (includes "unknown") and is intentionally not imported.
HABITAT_SCOPE_CATEGORIES: dict[str, set[str]] = {
    "observed": {"observed_world_fact", "agent_action", "artifact_record", "territory_record"},
    "speech": {"agent_speech"},
    "memory": {"agent_memory"},
    "operator_proof": {"operator_proof"},
}

# Scopes that are source-valid but get no consistency rules.
NO_CONSISTENCY_CHECK: frozenset[str] = frozenset({"unknown"})


def _evidence_categories(candidate: dict[str, Any]) -> set[str]:
    """Extract the set of evidence categories from a candidate event."""
    categories: set[str] = set()
    for ref in candidate.get("evidence_refs", []):
        if isinstance(ref, dict) and isinstance(ref.get("category"), str):
            categories.add(ref["category"])
    return categories


def _find_duplicate(
    candidate: dict[str, Any],
    existing_events: list[dict[str, Any]],
) -> str | None:
    """Check for a logical duplicate by tick + actor_id + action_type + territory_ref.

    Includes ``territory_ref`` so that an agent observing two different
    territories in the same tick is not falsely flagged as a duplicate.

    Returns the matching event_id or None.
    """
    tick = candidate.get("tick")
    if tick is None:
        return None
    actor = candidate.get("actor_id")
    action = candidate.get("action_type")
    territory = candidate.get("territory_ref")
    for e in existing_events:
        if (e.get("tick") == tick
                and e.get("actor_id") == actor
                and e.get("action_type") == action
                and e.get("territory_ref") == territory):
            return str(e.get("event_id", "unknown"))
    return None


def _find_contradiction(
    candidate: dict[str, Any],
    existing_events: list[dict[str, Any]],
) -> list[str]:
    """Check for factual contradictions against existing observed events.

    Contradiction = same territory, same entity name, different value
    in the summary "X is Y" pattern.
    """
    if candidate.get("claim_scope") != "observed":
        return []
    territory = candidate.get("territory_ref")
    if not territory:
        return []
    candidate_entity, candidate_value = _parse_is_claim(candidate.get("summary", ""))
    if candidate_entity is None:
        return []

    errors: list[str] = []
    for e in existing_events:
        if (e.get("event_id") == candidate.get("event_id")):
            continue
        if (e.get("territory_ref") != territory):
            continue
        if e.get("claim_scope") != "observed":
            continue
        existing_entity, existing_value = _parse_is_claim(e.get("summary", ""))
        if existing_entity is not None and existing_entity == candidate_entity:
            if existing_value != candidate_value:
                errors.append(
                    f"contradiction: {existing_entity} asserted as "
                    f"'{existing_value}' (event {e['event_id']}) and "
                    f"'{candidate_value}' (candidate)"
                )
    return errors


def _parse_is_claim(summary: str) -> tuple[str | None, str | None]:
    """Extract the first '<entity> is <value>' pattern from a summary string."""
    idx = summary.lower().find(" is ")
    if idx < 0:
        return None, None
    entity = summary[:idx].strip()
    value = summary[idx + 4:].strip().rstrip(".")
    if not entity or not value:
        return None, None
    return entity, value


def verify_candidate_event(
    candidate: dict[str, Any],
    existing_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check a candidate event against existing ledger events.

    Calls validate_event(candidate) first. If the candidate fails schema
    validation, returns immediately with the schema errors.

    Verifier-specific checks (run only after schema passes):
    1. Exact event_id duplicate
    2. Logical duplicate (tick + actor_id + action_type)
    3. Contradiction (observed scope, same territory, same entity, different value)
    4. Claim/evidence consistency (scope requires matching evidence category)

    Returns:
        {"accepted": bool, "errors": list[str], "warnings": list[str]}
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Step 1: Schema validation (reuses 10K validate_event)
    schema_result = validate_event(candidate)
    if not schema_result["ok"]:
        return {
            "accepted": False,
            "errors": schema_result["errors"],
            "warnings": warnings,
        }

    # Step 2: Exact event_id duplicate
    candidate_id = candidate.get("event_id")
    for e in existing_events:
        if e.get("event_id") == candidate_id:
            errors.append(f"duplicate event_id: {candidate_id}")
            break

    # Step 3: Logical duplicate (tick + actor_id + action_type + territory_ref)
    dup_id = _find_duplicate(candidate, existing_events)
    if dup_id is not None:
        errors.append(
            f"duplicate: tick {candidate.get('tick')}, "
            f"actor {candidate.get('actor_id')}, "
            f"action {candidate.get('action_type')}, "
            f"territory {candidate.get('territory_ref')} "
            f"already recorded as event {dup_id}"
        )

    # Step 4: Contradiction (observed only)
    errors.extend(_find_contradiction(candidate, existing_events))

    # Step 5: Claim/evidence consistency
    scope = candidate.get("claim_scope")
    evidence_cats = _evidence_categories(candidate)

    if scope == "hypothesis":
        if "observed_world_fact" in evidence_cats:
            errors.append(
                "consistency: hypothesis claim must not have "
                "observed_world_fact evidence"
            )
    elif scope in HABITAT_SCOPE_CATEGORIES:
        required = HABITAT_SCOPE_CATEGORIES[scope]
        if not required & evidence_cats:
            errors.append(
                f"consistency: {scope} claim requires at least one "
                f"evidence_ref with category in {required}"
            )
    elif scope in NO_CONSISTENCY_CHECK:
        pass  # "unknown" has no consistency rules
    else:
        # Any other scope is not handled by 10T (e.g., "world_event"
        # is a future schema concern). validate_event has already
        # rejected unrecognized scopes, so this branch is defensive only.
        pass

    # Step 6: Echo-specific rules (whisper action_type only)
    if candidate.get("action_type") == "whisper":
        scope = candidate.get("claim_scope")

        # Rule 6a: whisper must not claim observed scope
        if scope == "observed":
            errors.append(
                "echo: whisper action must not claim observed scope"
            )
        # Rule 6b: speech echo requires both agent_speech and world_event
        elif scope == "speech":
            if "agent_speech" not in evidence_cats:
                errors.append(
                    "echo: speech echo requires agent_speech evidence"
                )
            if "world_event" not in evidence_cats:
                errors.append(
                    "echo: speech echo requires world_event provenance "
                    "evidence"
                )
            # Rule 6c: speech echo must not include observed_world_fact
            # as truth transfer
            if "observed_world_fact" in evidence_cats:
                errors.append(
                    "echo: speech echo must not include "
                    "observed_world_fact evidence (truth transfer)"
                )

    return {
        "accepted": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }