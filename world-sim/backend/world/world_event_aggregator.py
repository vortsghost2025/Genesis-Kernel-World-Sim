"""Pure event aggregator for Phase 10U.

Produces derived summaries and counts from an in-memory list of committed
event dicts.  No filesystem I/O — receives events as ``list[dict]`` only.

Imports from the Python standard library exclusively.
"""

from __future__ import annotations

from typing import Any


def _parse_is_claim(summary: str) -> tuple[str | None, str | None]:
    """Extract the first '<entity> is <value>' pattern (case-insensitive)."""
    idx = summary.lower().find(" is ")
    if idx < 0:
        return None, None
    entity = summary[:idx].strip()
    value = summary[idx + 4 :].strip().rstrip(".")
    if not entity or not value:
        return None, None
    return entity, value


def _tick_sort_key(event: dict[str, Any]) -> tuple[int, int]:
    """Sort key: numeric tick descending, ``None`` sorts after all ints."""
    t = event.get("tick")
    if isinstance(t, int):
        return (0, -t)
    return (1, 0)


def _apply_filters(
    events: list[dict[str, Any]],
    *,
    scope_filter: str | None = None,
    actor_filter: str | None = None,
    territory_filter: str | None = None,
    tick_start: int | None = None,
    tick_end: int | None = None,
) -> list[dict[str, Any]]:
    """Return only events that match all supplied filters."""
    result = events
    if scope_filter is not None:
        result = [e for e in result if e.get("claim_scope") == scope_filter]
    if actor_filter is not None:
        result = [e for e in result if e.get("actor_id") == actor_filter]
    if territory_filter is not None:
        result = [e for e in result if e.get("territory_ref") == territory_filter]
    if tick_start is not None:
        result = [e for e in result if isinstance(e.get("tick"), int) and e["tick"] >= tick_start]
    if tick_end is not None:
        result = [e for e in result if isinstance(e.get("tick"), int) and e["tick"] <= tick_end]
    return result


def summarize_events(
    events: list[dict[str, Any]],
    *,
    scope_filter: str | None = None,
    actor_filter: str | None = None,
    territory_filter: str | None = None,
    tick_start: int | None = None,
    tick_end: int | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Produce a deterministic summary of a list of world-event dictionaries.

    Parameters
    ----------
    events:
        In-memory list of committed event dicts (same shape as ledger output).
    scope_filter:
        If set, only include events whose ``claim_scope`` equals this value.
    actor_filter:
        If set, only include events whose ``actor_id`` equals this value.
    territory_filter:
        If set, only include events whose ``territory_ref`` equals this value.
    tick_start:
        Inclusive lower tick bound (filters out ``None``-tick events).
    tick_end:
        Inclusive upper tick bound (filters out ``None``-tick events).
    top_n:
        Maximum number of events in ``recent_events``.

    Returns
    -------
    dict with keys:
        ``total_events``, ``by_claim_scope``, ``by_action_type``, ``by_actor``,
        ``by_territory``, ``by_evidence_category``, ``recent_events``,
        ``tick_range``, ``mutation_count``, ``world_state_deltas``.
    """
    filtered = _apply_filters(
        events,
        scope_filter=scope_filter,
        actor_filter=actor_filter,
        territory_filter=territory_filter,
        tick_start=tick_start,
        tick_end=tick_end,
    )

    # total_events
    total_events = len(filtered)

    # by_claim_scope
    by_claim_scope: dict[str, int] = {}
    for e in filtered:
        scope = e.get("claim_scope", "unknown")
        by_claim_scope[scope] = by_claim_scope.get(scope, 0) + 1

    # by_action_type
    by_action_type: dict[str, int] = {}
    for e in filtered:
        at = e.get("action_type", "unknown")
        by_action_type[at] = by_action_type.get(at, 0) + 1

    # by_actor
    by_actor: dict[str, int] = {}
    for e in filtered:
        actor = e.get("actor_id", "unknown")
        by_actor[actor] = by_actor.get(actor, 0) + 1

    # by_territory
    by_territory: dict[str, int] = {}
    for e in filtered:
        terr = e.get("territory_ref", "") or ""
        by_territory[terr] = by_territory.get(terr, 0) + 1

    # by_evidence_category (flatten all evidence_refs across all filtered events)
    by_evidence_category: dict[str, int] = {}
    for e in filtered:
        for ref in e.get("evidence_refs", []):
            if isinstance(ref, dict):
                cat = ref.get("category", "unknown")
                by_evidence_category[cat] = by_evidence_category.get(cat, 0) + 1

    # recent_events (sorted by tick descending, None last)
    sorted_events = sorted(filtered, key=_tick_sort_key)
    recent_events = sorted_events[:top_n]

    # tick_range
    ticked = [e["tick"] for e in filtered if isinstance(e.get("tick"), int)]
    tick_range: dict[str, int | None] = {"min_tick": None, "max_tick": None}
    if ticked:
        tick_range["min_tick"] = min(ticked)
        tick_range["max_tick"] = max(ticked)

    # mutation_count (both before_ref AND after_ref truthy)
    mutation_count = sum(
        1 for e in filtered if e.get("before_ref") and e.get("after_ref")
    )

    # world_state_deltas (observed scope only, "X is Y" pattern)
    world_state_deltas: list[dict[str, Any]] = []
    for e in filtered:
        if e.get("claim_scope") != "observed":
            continue
        entity, value = _parse_is_claim(e.get("summary", ""))
        if entity is None:
            continue
        world_state_deltas.append({
            "entity": entity,
            "value": value,
            "territory_ref": e.get("territory_ref", ""),
            "tick": e.get("tick"),
            "actor_id": e.get("actor_id"),
            "event_id": e.get("event_id"),
        })

    return {
        "total_events": total_events,
        "by_claim_scope": by_claim_scope,
        "by_action_type": by_action_type,
        "by_actor": by_actor,
        "by_territory": by_territory,
        "by_evidence_category": by_evidence_category,
        "recent_events": recent_events,
        "tick_range": tick_range,
        "mutation_count": mutation_count,
        "world_state_deltas": world_state_deltas,
    }