"""Pure event exporter for Phase 10V.

Serializes a list of event dicts to JSON / JSONL / CSV for offline audit
trails. No filesystem I/O — the caller receives a string back and writes
(or pipes, or transmits) it themselves.

This module performs pure transformation only. It does not enforce the
egress sanitization rules defined in 10W: callers are responsible for
choosing a field-allowlist that strips any data the audit boundary
must not expose. The default ``EXPORT_FIELDS`` allowlist is intentionally
narrow — it covers the schema's surface fields plus tick / timestamp but
omits any fields that an operator might use to carry private runtime
hints (e.g. ``verification_notes``, ``private_payload``, etc.).

Imports from the Python standard library exclusively.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterable

# Default allowlist of fields emitted by the exporter. Auditors see only
# these fields unless they explicitly opt in to more. Adding a field here
# is a deliberate change to the audit contract — review with 10W.
EXPORT_FIELDS: tuple[str, ...] = (
    "event_id",
    "schema_version",
    "tick",
    "timestamp_utc",
    "actor_id",
    "lens",
    "territory_ref",
    "action_type",
    "summary",
    "claim_scope",
    "verification_status",
    "before_ref",
    "after_ref",
    "affected_agents",
    "artifacts_created_or_changed",
    "relationship_delta",
    "consequence",
)

# Fields emitted as JSON-encoded strings inside CSV cells because they
# hold list-of-object structures that have no flat CSV representation.
_NESTED_FIELDS: frozenset[str] = frozenset({
    "evidence_refs",
    "affected_agents",
    "artifacts_created_or_changed",
    "relationship_delta",
})

SUPPORTED_FORMATS: frozenset[str] = frozenset({"json", "jsonl", "csv"})


class ExporterError(ValueError):
    """Raised when the exporter receives invalid input or configuration."""


def _pick(event: dict[str, Any], field: str) -> Any:
    """Return ``event[field]`` if present, otherwise ``None``.

    Missing fields are not an error at this stage — the caller decides
    whether missing values should be omitted or surfaced as empty.
    """
    return event.get(field)


def _csv_cell(value: Any, field: str) -> str:
    """Render a single event value as a CSV cell string.

    Nested list/dict values are JSON-stringified (using ``json.dumps``)
    which produces a stable, parseable cell. Primitive values are
    ``str()``-coerced. ``None`` becomes the empty string.
    """
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if isinstance(value, str):
        # Newlines inside CSV cells are sanitized to a single space
        # so a downstream ``csv.reader`` cannot be tricked into an
        # extra row. The original value is recoverable from JSON / JSONL.
        return value.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return str(value)


def _project(events: Iterable[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    """Filter each event down to only ``fields``. Missing fields become ``None``."""
    projected: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            raise ExporterError(f"event must be a dict, got {type(event).__name__}")
        projected.append({f: _pick(event, f) for f in fields})
    return projected


def _reorder_fields_for_csv(fields: tuple[str, ...]) -> list[str]:
    """Ensure CSV uses a stable scalar-first, nested-last field ordering."""
    scalars = [f for f in fields if f not in _NESTED_FIELDS]
    nested = [f for f in fields if f in _NESTED_FIELDS]
    return scalars + nested


def export_events(
    events: list[dict[str, Any]],
    *,
    fmt: str = "json",
    fields: tuple[str, ...] | list[str] = EXPORT_FIELDS,
    strict: bool = False,
) -> str:
    """Serialize ``events`` to a string in the chosen format.

    Parameters
    ----------
    events:
        In-memory list of event dicts. Each must be a ``dict``; nested
        dicts/lists in fields are JSON-stringified for CSV output.
    fmt:
        One of ``"json"`` (returns a JSON array), ``"jsonl"`` (one
        event per line, no surrounding brackets), ``"csv"`` (one row
        per event with a header row).
    fields:
        Allowlist of event fields to emit. Defaults to :data:`EXPORT_FIELDS`.
        Order is preserved for JSON and ; for CSV, scalars come first
        then nested fields so a reader can scan the column order
        predictably.
    strict:
        If ``True``, missing fields within an event cause an
        :class:`ExporterError` instead of producing ``null``. ``False``
        treats missing fields as ``None`` (renders as ``null`` in JSON /
        JSONL, empty cell in CSV).

    Returns
    -------
    ``str`` containing the serialized payload. The exporter performs no
    filesystem I/O; the caller writes or transmits the string.

    Raises
    ------
    ExporterError
        If ``fmt`` is not in :data:`SUPPORTED_FORMATS`, ``fields`` is
        empty, the input contains non-dict entries, or ``strict`` is
        set and an event is missing a requested field.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ExporterError(f"unsupported format: {fmt!r}")
    fields_tuple = tuple(fields)
    if not fields_tuple:
        raise ExporterError("fields must contain at least one field")

    if strict:
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                raise ExporterError(f"events[{index}] must be a dict")
            missing = [f for f in fields_tuple if f not in event]
            if missing:
                raise ExporterError(
                    f"events[{index}] is missing required fields: {missing}"
                )

    projected = _project(events, fields_tuple)

    if fmt == "json":
        return json.dumps(projected, ensure_ascii=False, sort_keys=False, indent=2)

    if fmt == "jsonl":
        lines = [json.dumps(event, ensure_ascii=False, sort_keys=False) for event in projected]
        # Trailing newline keeps unix-style tools happy. Empty input
        # yields an empty string (no spurious blank line).
        if not lines:
            return ""
        return "\n".join(lines) + "\n"

    # fmt == "csv"
    ordered = _reorder_fields_for_csv(fields_tuple)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ordered)
    for event in projected:
        row = [_csv_cell(event.get(f), f) for f in ordered]
        writer.writerow(row)
    return buffer.getvalue()
