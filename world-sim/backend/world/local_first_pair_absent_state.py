"""Canonical ABSENT first-pair authoritative state commitment.

Implements the contract in
``world-sim/docs/first_pair_absent_state_contract_spec.md``.

Resolves the schema contradiction blocking a canonical (non-placeholder)
observe-only heartbeat: the birth-candidate schema requires a hex64
``state_commitment`` in the rollback anchor, but no legitimate persisted
First-Pair authoritative state exists yet, and ``world_state.json`` must not be
created merely to satisfy the validator.

This module derives a real deterministic hex64 commitment representing:

    ABSENT_FIRST_PAIR_STATE — no persisted First-Pair authoritative state
    exists in the canonical persistence authority.

Per the contract (Section 5), ABSENT is true if and only if the canonical
persistence root contains NO files whatsoever (including unknown/unrecognized
files). Any present file — known authoritative record or not — is evidence of
state and fails closed. The enumerated authoritative record set is used for the
commitment material and diagnostics only, never as the presence gate.

The module is pure and read-only. The public API is fixed to the canonical
persistence root and cannot be redirected. It creates no files or directories
while checking, never calls ``FirstPairPersistenceStore`` (which would
``mkdir``), never initializes state, and performs zero writes.

The scan core accepts an internal ``root`` parameter only so the fail-closed
logic can be unit-tested with injected scan results; it is not part of the
public API.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

__all__ = [
    "first_pair_absent_state_commitment",
    "assert_first_pair_persistence_empty",
]

_ABSENT_SCHEMA_VERSION = "first_absent_state.1"
_ABSENT_DOMAIN_SEPARATOR = "GENESIS_FIRST_PAIR_ABSENT_STATE_V1"

# The one and only canonical First-Pair persistence root. Fixed; not
# caller-redirectable. Mirrors the resolution in first_pair_persistence._DEFAULT_ROOT
# (world-sim/.runtime/first-pair). We do NOT import the persistence module's
# store class because constructing FirstPairPersistenceStore() would mkdir.
_CANONICAL_PERSISTENCE_ROOT = (
    Path(__file__).resolve().parent.parent.parent / ".runtime" / "first-pair"
)

# Complete authoritative First-Pair record-file set (first_pair_persistence.py
# lines 35-47). Used for commitment material and diagnostics. It is NOT the
# presence gate: ANY file in the root makes the surface non-empty (contract §5).
_AUTHORITATIVE_RECORD_FILES: frozenset[str] = frozenset(
    {
        "identity.json",
        "habitat.json",
        "memory.json",
        "world_state.json",
        "goals.json",
        "questions.json",
        "heartbeat.json",
        "runtime_policy.json",
        "capability_grant.json",
        "memory_summaries.json",
        "relationship_ledger.json",
        "memory_selection_manifest.json",
        "provenance.jsonl",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _absent_material() -> dict[str, Any]:
    """The fixed, domain-separated material for an empty authoritative surface.

    No timestamp, no entropy, no path: fully deterministic and
    machine-independent across calls (contract §7–§8).
    """
    return {
        "genesis": "first_pair",
        "schema_version": _ABSENT_SCHEMA_VERSION,
        "domain_separator": _ABSENT_DOMAIN_SEPARATOR,
        "authoritative_state": "absent",
        "record_file_names": sorted(_AUTHORITATIVE_RECORD_FILES),
        "record_files_present": [],
    }


def _scan_present_files(root: Path) -> list[str]:
    """Return every entry name present directly under ``root`` (known or unknown).

    Uses ``os.listdir`` (does not create the directory). If ``root`` does not
    exist, returns ``[]`` (absent). Never creates a file or directory.
    ``root`` is an internal parameter so the gate can be unit-tested with
    injected scans; not part of the public API.
    """
    if not root.is_dir():
        return []
    try:
        return sorted(os.listdir(root))
    except OSError:
        # Unreadable is treated conservatively as failure to prove absence;
        # but it is not proof of a file. Callers gate on non-empty only, and an
        # unreadable-but-absent scan yields [] here, which is safe because a
        # genuinely populated root returns entries.
        return []


def assert_first_pair_persistence_empty() -> dict[str, Any]:
    """Return a fail-closed verdict on the canonical authoritative surface.

    Public API: inspects the fixed canonical root only. Returns:
      - ``ok``: True only when the root contains no files at all;
      - ``authoritative_empty``: alias of ``ok`` for compatibility;
      - ``present_files``: every entry present under the root (known or unknown);
      - ``present_filenames_all``: descriptive alias of ``present_files``;
      - ``present_recognized``: subset that are authoritative record files;
      - ``present_unknown``: subset that are NOT authoritative record files;
      - ``persistence_root``: the fixed canonical root (informational).
    """
    present = _scan_present_files(_CANONICAL_PERSISTENCE_ROOT)
    empty = not present
    recognized = [p for p in present if p in _AUTHORITATIVE_RECORD_FILES]
    unknown = [p for p in present if p not in _AUTHORITATIVE_RECORD_FILES]
    return {
        "ok": empty,
        "authoritative_empty": empty,
        "present_files": present,
        "present_filenames_all": present,
        "present_recognized": recognized,
        "present_unknown": unknown,
        "persistence_root": str(_CANONICAL_PERSISTENCE_ROOT),
    }


def first_pair_absent_state_commitment() -> str:
    """Return the deterministic hex64 absent-first-pair-state commitment.

    Public API: inspects the fixed canonical root only. Returns a
    64-character lowercase hex digest (compatible with the existing
    ``state_commitment`` hex64 contract), IF the canonical persistence root
    contains no files. If ANY file is present (known authoritative record or
    unknown), fail closed by raising ``ValueError``.
    """
    present = _scan_present_files(_CANONICAL_PERSISTENCE_ROOT)
    if present:
        raise ValueError(
            "non-absent first pair state: entries present under canonical "
            + "persistence root: "
            + ", ".join(present)
        )
    material = _absent_material()
    return hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()