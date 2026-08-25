"""Phase 10IN - pure first-pair provenance source-envelope validation.

Implements the minimum runtime behavior specified by 10IL
(``phase_10il_first_pair_provenance_commitment_source_envelope_spec.md``).

The ``provenance_commitment`` in the First Pair canonical identity is the
deterministic SHA-256 commitment of a canonical disclosed provenance source
envelope. This module validates one caller-supplied envelope (raw UTF-8 JSON
bytes) and verifies that its canonical serialization hashes to the presented
``provenance_commitment``.

This establishes:
- deterministic binding of the commitment to the disclosed envelope material;
- integrity of the declared material (any mutation changes the commitment);
- tamper detection of the disclosed envelope.

This does NOT establish:
- truthfulness of the declared material;
- operator authentication;
- authorization of any creation/write;
- freshness, uniqueness, or non-replay;
- resistance to a caller fabricating a self-consistent envelope.

Robustness note (10IL §H): duplicate JSON keys collapse in a standard dict
before validation, so duplicate-key evidence is only preserved at a raw JSON
parsing boundary. This module therefore accepts ``raw bytes/str`` (never a
pre-parsed dict) and rejects any duplicate key at any nesting level.

The module is pure and read-only. It performs no filesystem, world, ledger,
provider, model, or network activity. Imports are limited to stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

__all__ = [
    "validate_provenance_source_envelope",
    "derive_provenance_commitment",
]

_PROVENANCE_SCHEMA_VERSION = "first_provenance_envelope.1"
_PROVENANCE_DOMAIN_SEPARATOR = "GENESIS_FIRST_PAIR_PROVENANCE_V1"

_ENVELOPE_FIELDS = frozenset(
    {
        "source_envelope_schema_version",
        "domain_separator",
        "source_ref",
        "source_timestamp",
        "provenance_material",
    }
)
_MATERIAL_FIELDS = frozenset(
    {
        "canonical_name",
        "source_artifact_id",
        "source_artifact_integrity_id",
        "operator_approval_ref",
    }
)

_SAFE_IDENTIFIER_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-"
)
_FORBIDDEN_IDENTIFIER_MARKERS = ("true_map", "known_map", "world-sim/data", "[redacted")
_HIDDEN_MARKERS = ("truemap", "knownmap", "hiddensubstrate")

_TIMESTAMP_RE = (
    r"^\d{4}-(?:0[1-9]|1[0-2])-"
    r"(?:0[1-9]|[12]\d|3[01])T"
    r"(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ$"
)

_VALID_NAME = frozenset({"Adam", "Eve"})


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _is_hex64(value: Any) -> bool:
    if type(value) is not str or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _is_safe_identifier(value: Any) -> bool:
    if type(value) is not str or not 1 <= len(value) <= 128:
        return False
    if not all(character in _SAFE_IDENTIFIER_CHARACTERS for character in value):
        return False
    lowered = value.lower()
    collapsed = "".join(character for character in lowered if character.isalnum())
    if ".." in value or any(marker in lowered for marker in _FORBIDDEN_IDENTIFIER_MARKERS):
        return False
    return not any(marker in collapsed for marker in _HIDDEN_MARKERS)


def _is_canonical_timestamp(value: Any) -> bool:
    if type(value) is not str or re.fullmatch(_TIMESTAMP_RE, value) is None:
        return False
    year_s, month_s, day_s = value[0:4], value[5:7], value[8:10]
    year, month, day = int(year_s), int(month_s), int(day_s)
    if year < 1 or year > 9999:
        return False
    month_days = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
                  else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return 1 <= day <= month_days[month - 1]


def _has_exact_string_keys(value: Any, expected: frozenset[str]) -> bool:
    if type(value) is not dict:
        return False
    keys = list(value.keys())
    return all(type(key) is str for key in keys) and frozenset(keys) == expected


def _parse_json_no_duplicate_keys(raw: str | bytes) -> dict:
    """Parse raw JSON text, rejecting any duplicate key at any nesting level.

    Standard ``json.loads`` collapses duplicate keys without a trace, so a
    pre-parsed dict cannot prove duplicates were absent (10IL §H). We walk the
    raw text with a strict duplicate-key object hook and reject on the first
    duplicate at any level.
    """
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    if type(text) is not str:
        raise ValueError("invalid provenance envelope; expected UTF-8 JSON text")

    def object_hook(pairs: list[tuple[str, Any]]) -> dict:
        seen: set[str] = set()
        for key, _value in pairs:
            if key in seen:
                raise ValueError("duplicate key in provenance envelope")
            seen.add(key)
        return dict(pairs)

    try:
        return json.loads(text, object_pairs_hook=object_hook, parse_constant=_reject_constant)
    except UnicodeDecodeError:
        raise ValueError("invalid provenance envelope; expected UTF-8 JSON text")


def _reject_constant(name: str) -> None:
    raise ValueError("invalid provenance envelope; non-finite constant rejected")


def _validate_envelope(envelope: dict) -> list[str]:
    """Return the list of failed-check error codes (empty if valid)."""
    if not _has_exact_string_keys(envelope, _ENVELOPE_FIELDS):
        return ["invalid_envelope"]
    if envelope["source_envelope_schema_version"] != _PROVENANCE_SCHEMA_VERSION:
        return ["invalid_schema_version"]
    if envelope["domain_separator"] != _PROVENANCE_DOMAIN_SEPARATOR:
        return ["invalid_domain_separator"]
    if not _is_safe_identifier(envelope["source_ref"]):
        return ["invalid_source_ref"]
    if not _is_canonical_timestamp(envelope["source_timestamp"]):
        return ["invalid_timestamp"]

    material = envelope["provenance_material"]
    if not _has_exact_string_keys(material, _MATERIAL_FIELDS):
        return ["invalid_material"]
    if material["canonical_name"] not in _VALID_NAME:
        return ["invalid_canonical_name"]
    if not _is_safe_identifier(material["source_artifact_id"]):
        return ["invalid_source_artifact_id"]
    if not _is_safe_identifier(material["operator_approval_ref"]):
        return ["invalid_operator_approval_ref"]
    if not _is_hex64(material["source_artifact_integrity_id"]):
        return ["invalid_source_artifact_integrity_id"]
    return []


def derive_provenance_commitment(source_envelope: dict) -> str:
    """Return the deterministic SHA-256 commitment of the disclosed envelope."""
    return hashlib.sha256(
        _canonical_json(source_envelope).encode("utf-8")
    ).hexdigest()


def validate_provenance_source_envelope(
    raw_json: str | bytes,
    proposed_commitment: str,
) -> dict[str, Any]:
    """Validate one provenance source envelope against a proposed commitment.

    Accepts raw UTF-8 JSON text or bytes (never a pre-parsed dict), per 10IL
    §H duplicate-key parsing boundary. Pure, read-only, fail-closed. Returns a
    safe dictionary with determinant, status, and validated material; never
    mutates input and never touches filesystem/world/ledger/provider/model.
    """
    try:
        envelope = _parse_json_no_duplicate_keys(raw_json)
    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "envelope_valid": False,
            "commitment_matches": False,
            "canonical_name": None,
            "material": None,
            "derived_commitment": None,
        }

    errors = _validate_envelope(envelope)
    if errors:
        return {
            "ok": False,
            "error": "invalid provenance envelope; identity commitment rejected.",
            "envelope_valid": False,
            "commitment_matches": False,
            "canonical_name": envelope.get("provenance_material", {}).get("canonical_name"),
            "material": None,
            "derived_commitment": None,
        }

    derived = derive_provenance_commitment(envelope)
    matches = type(proposed_commitment) is str and derived == proposed_commitment
    return {
        "ok": matches,
        "error": "" if matches else "identity commitment rejected.",
        "envelope_valid": True,
        "commitment_matches": matches,
        "canonical_name": envelope["provenance_material"]["canonical_name"],
        "material": dict(envelope["provenance_material"]),
        "derived_commitment": derived,
    }