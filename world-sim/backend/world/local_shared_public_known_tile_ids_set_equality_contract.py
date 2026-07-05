"""Phase 10BL - shared public known tile IDs set equality contract.

Create a deterministic sanitized shared-public-known-tile-ids set
equality contract artifact from a Phase 10AS two-agent public merge.
10BL formalizes whether two agents' public bundle known-tile-id sets are
identical, without inferring same map knowledge, same exploration
history, same observation event, same place, co-presence, awareness,
route, path, destination, timing, plan, or relationship.

Known tile IDs are read from the 10AS agent bundles only. Missing,
non-list, or empty-after-sanitize lists are treated as empty lists.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in
:func:`contract_known_tile_ids_set_equality_file`, which only reads JSON
from a caller-supplied path.

10BL consumes 10AS only.  It never imports or calls earlier phase
creators; it never writes to a ledger, never calls a projector, route
planner, movement helper, runtime, daemon, provider, Docker, network, or
live data directory.  The only upstream symbol 10BL imports is
``sanitize_public_mapping`` from the public egress sanitizer.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_mapping


_CONTRACT_SCHEMA_VERSION = "10BL.1"
_CONTRACT_TYPE = "shared_public_known_tile_ids_set_equality_contract"
_SOURCE_PHASE = "10AS"
_CLAIM_SCOPE = "shared_public_known_tile_ids_set_equality_only"

_EXPECTED_MERGE_TYPE = "two_agent_public_merge"
_EXPECTED_MERGE_SCHEMA_VERSION = "10AS.1"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_str(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return ""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _hash_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _empty_contract(errors: list[str]) -> dict[str, Any]:
    return {
        "ok": not errors,
        "contract_schema_version": _CONTRACT_SCHEMA_VERSION,
        "contract_type": _CONTRACT_TYPE,
        "contract_id": None,
        "source_phase": _SOURCE_PHASE,
        "source_merge_id": None,
        "source_merge_hash": None,
        "source_merge_schema_version": None,
        "agent_a_id": None,
        "agent_b_id": None,
        "agent_a_known_tile_ids": [],
        "agent_b_known_tile_ids": [],
        "agent_a_known_tile_count": 0,
        "agent_b_known_tile_count": 0,
        "same_known_tile_ids": False,
        "shared_known_tile_ids": [],
        "shared_known_tile_count": 0,
        "agent_a_only_known_tile_ids": [],
        "agent_a_only_known_tile_count": 0,
        "agent_b_only_known_tile_ids": [],
        "agent_b_only_known_tile_count": 0,
        "claim_scope": _CLAIM_SCOPE,
        "errors": errors,
    }


def _sanitize_known_tile_ids(raw: Any) -> list[str]:
    """Sanitize, drop invalid entries, deduplicate, and sort tile IDs."""

    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        sanitized = sanitize_public_mapping(item)
        if not isinstance(sanitized, str) or not sanitized:
            continue
        if "[REDACTED" in sanitized:
            continue
        seen.add(sanitized)
    return sorted(seen)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_shared_known_tile_ids_set_equality_contract(merge: dict) -> dict:
    """Create a deterministic sanitized known-tile-ids set contract.

    Consumes an already-built Phase 10AS two-agent public merge artifact
    and emits a thin set-equality contract recording whether the two
    agents' public bundle known-tile-id sets are mechanically equal.
    Missing, non-list, or empty-after-sanitize values are treated as
    empty lists.  Never infers same map knowledge, same exploration
    history, same observation event, same place, co-presence, awareness,
    route, path, destination, timing, plan, or relationship.  Never
    raises; always returns a dict.
    """

    errors: list[str] = []

    if not isinstance(merge, dict):
        contract = _empty_contract(["merge must be a dict"])
        contract["ok"] = False
        return contract

    # Deep-copy before any read so caller-owned data can never be
    # mutated by validation, sanitization, or hashing.
    local_merge = copy.deepcopy(merge)

    # --- Structural validation of the 10AS merge --------------------------

    if local_merge.get("ok") is not True:
        errors.append("merge ok flag is not True")

    merge_type = local_merge.get("merge_type")
    if merge_type != _EXPECTED_MERGE_TYPE:
        errors.append("merge_type is not " + repr(_EXPECTED_MERGE_TYPE))

    merge_schema_version = local_merge.get("merge_schema_version")
    if merge_schema_version != _EXPECTED_MERGE_SCHEMA_VERSION:
        errors.append(
            "merge_schema_version is not "
            + repr(_EXPECTED_MERGE_SCHEMA_VERSION)
        )

    agent_a_raw = local_merge.get("agent_a")
    agent_b_raw = local_merge.get("agent_b")
    if not isinstance(agent_a_raw, dict):
        errors.append("agent_a must be a dict")
    if not isinstance(agent_b_raw, dict):
        errors.append("agent_b must be a dict")

    # Early bail on structural failure - we cannot trust bundle shape
    # past this point, and reading them would risk KeyError-ing.
    if errors:
        contract = _empty_contract(errors)
        contract["ok"] = False
        source_merge_id = _safe_str(local_merge.get("merge_id"))
        if source_merge_id:
            contract["source_merge_id"] = source_merge_id
        contract["source_merge_schema_version"] = (
            merge_schema_version
            if isinstance(merge_schema_version, str)
            else None
        )
        return contract

    assert isinstance(agent_a_raw, dict)
    assert isinstance(agent_b_raw, dict)

    a_id_raw = _safe_str(agent_a_raw.get("agent_id"))
    b_id_raw = _safe_str(agent_b_raw.get("agent_id"))
    if not a_id_raw:
        errors.append("agent_a_id is missing or empty")
    if not b_id_raw:
        errors.append("agent_b_id is missing or empty")
    if a_id_raw and b_id_raw and a_id_raw == b_id_raw:
        errors.append("agent_a_id and agent_b_id must be distinct")

    if errors:
        contract = _empty_contract(errors)
        contract["ok"] = False
        source_merge_id = _safe_str(local_merge.get("merge_id"))
        if source_merge_id:
            contract["source_merge_id"] = source_merge_id
        contract["source_merge_schema_version"] = (
            merge_schema_version
            if isinstance(merge_schema_version, str)
            else None
        )
        return contract

    # --- Sanitize the whole merge for the provenance hash -----------------

    sanitized_merge = sanitize_public_mapping(local_merge)
    if not isinstance(sanitized_merge, dict):
        contract = _empty_contract(["sanitized merge is not a dict"])
        contract["ok"] = False
        return contract

    source_merge_id = _safe_str(sanitized_merge.get("merge_id"))
    source_merge_hash = _hash_canonical(sanitized_merge)

    sanitized_agent_a = sanitized_merge.get("agent_a")
    sanitized_agent_b = sanitized_merge.get("agent_b")
    if not isinstance(sanitized_agent_a, dict):
        contract = _empty_contract(["sanitized agent_a is not a dict"])
        contract["ok"] = False
        if source_merge_id:
            contract["source_merge_id"] = source_merge_id
        contract["source_merge_hash"] = source_merge_hash
        return contract
    if not isinstance(sanitized_agent_b, dict):
        contract = _empty_contract(["sanitized agent_b is not a dict"])
        contract["ok"] = False
        if source_merge_id:
            contract["source_merge_id"] = source_merge_id
        contract["source_merge_hash"] = source_merge_hash
        return contract

    agent_a_id = _safe_str(sanitized_agent_a.get("agent_id"))
    agent_b_id = _safe_str(sanitized_agent_b.get("agent_id"))

    # Re-sanitize ids so private markers cannot reach output via agent ids.
    agent_a_id = _safe_str(sanitize_public_mapping(agent_a_id)) or agent_a_id
    agent_b_id = _safe_str(sanitize_public_mapping(agent_b_id)) or agent_b_id

    # --- Bundle known tile IDs --------------------------------------------
    # These are read only from the sanitized 10AS agent bundles.  The
    # root merge set-algebra fields are ignored as authority and are
    # recomputed below from these two bundle lists.

    a_known_tile_ids = _sanitize_known_tile_ids(
        sanitized_agent_a.get("known_tile_ids")
    )
    b_known_tile_ids = _sanitize_known_tile_ids(
        sanitized_agent_b.get("known_tile_ids")
    )

    # --- Set operations ---------------------------------------------------
    # Pure set equality and set algebra over opaque public identifiers.

    a_set = set(a_known_tile_ids)
    b_set = set(b_known_tile_ids)

    same_known_tile_ids = bool(a_set == b_set and a_set)
    shared_known_tile_ids = sorted(a_set & b_set)
    agent_a_only_known_tile_ids = sorted(a_set - b_set)
    agent_b_only_known_tile_ids = sorted(b_set - a_set)

    # Build the contract material - only contract-level public fields
    # feed the hash input.  agent_a_id and agent_b_id are preserved in
    # A/B orientation; they are NOT sorted.
    contract_material: dict[str, Any] = {
        "contract_schema_version": _CONTRACT_SCHEMA_VERSION,
        "claim_scope": _CLAIM_SCOPE,
        "source_merge_id": source_merge_id or "",
        "source_merge_hash": source_merge_hash,
        "agent_a_id": agent_a_id,
        "agent_b_id": agent_b_id,
        "agent_a_known_tile_ids": a_known_tile_ids,
        "agent_b_known_tile_ids": b_known_tile_ids,
        "same_known_tile_ids": same_known_tile_ids,
        "shared_known_tile_ids": shared_known_tile_ids,
        "agent_a_only_known_tile_ids": agent_a_only_known_tile_ids,
        "agent_b_only_known_tile_ids": agent_b_only_known_tile_ids,
    }
    contract_id = "10BL-" + _hash_canonical(contract_material)[:32]

    return {
        "ok": True,
        "contract_schema_version": _CONTRACT_SCHEMA_VERSION,
        "contract_type": _CONTRACT_TYPE,
        "contract_id": contract_id,
        "source_phase": _SOURCE_PHASE,
        "source_merge_id": source_merge_id or None,
        "source_merge_hash": source_merge_hash,
        "source_merge_schema_version": (
            merge_schema_version
            if isinstance(merge_schema_version, str)
            else None
        ),
        "agent_a_id": agent_a_id or None,
        "agent_b_id": agent_b_id or None,
        "agent_a_known_tile_ids": a_known_tile_ids,
        "agent_b_known_tile_ids": b_known_tile_ids,
        "agent_a_known_tile_count": len(a_known_tile_ids),
        "agent_b_known_tile_count": len(b_known_tile_ids),
        "same_known_tile_ids": same_known_tile_ids,
        "shared_known_tile_ids": shared_known_tile_ids,
        "shared_known_tile_count": len(shared_known_tile_ids),
        "agent_a_only_known_tile_ids": agent_a_only_known_tile_ids,
        "agent_a_only_known_tile_count": len(agent_a_only_known_tile_ids),
        "agent_b_only_known_tile_ids": agent_b_only_known_tile_ids,
        "agent_b_only_known_tile_count": len(agent_b_only_known_tile_ids),
        "claim_scope": _CLAIM_SCOPE,
        "errors": [],
    }


def export_shared_known_tile_ids_set_equality_contract(contract: dict) -> str:
    """Export a known-tile-ids set-equality contract as stable JSON."""

    sanitized = sanitize_public_mapping(contract)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def contract_known_tile_ids_set_equality_file(
    merge_json_path: Path | str,
) -> dict:
    """Read an exported 10AS merge JSON file and build a 10BL contract."""

    path = Path(merge_json_path)
    text = path.read_text(encoding="utf-8")
    merge = json.loads(text)
    return create_shared_known_tile_ids_set_equality_contract(merge)
