"""Phase 10IS - canonical first-pair habitat contract enforcement.

A pure, deterministic, fail-closed, in-memory, validator-only module that
enforces canonical equality against the 10IJ-declared starting habitat
contract. It performs no write, creates no runtime entity, persists
nothing, writes no memory or ledger, and performs no external work. All
non-authority flags are literal ``False``.

Authorship note (AGENTS.md Rule 3 override): Phase 10IS implementation is
reserved by AGENTS.md Rule 3 for GPT-5.6 Sol/Luna. Sean explicitly
authorized this author to fill Sol's spot for the 10IS implementation.
That override is recorded here so the authorship change is documented,
not silent.

Error-vocabulary mapping decisions (10IS proposal section D):

- ``invalid_habitat`` = "this is not a structurally valid habitat
  declaration" (shape/type/version). Reserved by 10IJ section I for the
  future canonical validator; 10IC today converts habitat validation
  failure into ``habitat_drift`` (it sets ``habitat_valid = False`` and
  emits ``habitat_drift`` when ``habitat_valid`` is not True). 10IS
  intentionally distinguishes structural invalidity from canonical-value
  drift more precisely than 10IC does.
- ``habitat_drift`` = "this is a valid-shaped habitat declaration that has
  drifted from the canonical 10IJ contract" (canonical-value deviation).
  Preserves the existing 10IC/10ID meaning for well-shaped habitat content
  that fails the required contract or validation state.
- ``invalid_observation_radius`` = "the observation boundary is not the
  canonical single-tile self-observation" (10ID already uses this code for
  radius/boundary shape failures).
- ``invalid_rollback_anchor`` = "the rollback anchor does not bind to the
  canonical habitat id" (10ID already uses this code).

Duplicate-key boundary assumption (10IS proposal section C3): the validator
receives an already-constructed ``dict``; Python collapses duplicate
literal keys at construction (last-wins). Duplicate-key detection is a
serialization-layer concern and is out of scope for this validator. The
input is a dict; the validator enforces what the dict observably contains.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_CONTRACT_SCHEMA_VERSION = "10IS.1"
_CONTRACT_TYPE = "first_pair_habitat_contract"
_CONTRACT_SCOPE = "pure_in_memory_canonical_validation_only"
_PAIR_ID = "genesis-first-pair"
_CLAIM_BOUNDARY = "canonical_first_pair_habitat_contract_only"

# Canonical constants fixed from 10IJ section I (10IS proposal section C2).
_HABITAT_SCHEMA_VERSION = "first_habitat.1"
_HABITAT_ID = "genesis-first-habitat"
_ALLOWED_TILE_IDS = ("public-start-adam", "public-start-eve")  # canonical order
_STARTING_TILE_IDS = {
    "east_adam": "public-start-adam",
    "east_eve": "public-start-eve",
}
_OBSERVATION_BOUNDARIES = {
    "east_adam": ("public-start-adam",),
    "east_eve": ("public-start-eve",),
}
_MOVEMENT_ALLOWED = False

_HABITAT_KEYS = frozenset(
    {
        "habitat_schema_version",
        "habitat_id",
        "allowed_tile_ids",
        "starting_tile_ids",
        "observation_boundaries",
        "movement_allowed",
    }
)

_AGENT_REFS = ("east_adam", "east_eve")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _canonical_declaration() -> dict[str, Any]:
    """The fixed 10IJ canonical habitat declaration (fresh copy)."""
    return {
        "habitat_schema_version": _HABITAT_SCHEMA_VERSION,
        "habitat_id": _HABITAT_ID,
        "allowed_tile_ids": list(_ALLOWED_TILE_IDS),
        "starting_tile_ids": dict(_STARTING_TILE_IDS),
        "observation_boundaries": {
            ref: list(tiles) for ref, tiles in _OBSERVATION_BOUNDARIES.items()
        },
        "movement_allowed": _MOVEMENT_ALLOWED,
    }


def _canonical_contract_id() -> str:
    """``"10IS-" + SHA256(canonical_contract_material).hexdigest()``.

    ``canonical_contract_material`` is the fixed 10IJ canonical habitat
    declaration (the section C2 constant object, not any caller input)
    serialized deterministically: UTF-8, canonical JSON, sorted object
    keys, ``,``/``:`` separators with no extra whitespace,
    ``ensure_ascii=False``, no trailing newline. Full 64-char lowercase
    digest, never truncated, independent of caller input, validation
    outcome, rollback-anchor presence/validity, time, entropy, and
    environment. Identical across every validation outcome.
    """
    material = _canonical_json(_canonical_declaration()).encode("utf-8")
    return "10IS-" + hashlib.sha256(material).hexdigest()


def _is_str_list(value: Any, expected_members: tuple[str, ...]) -> bool:
    """True iff value is a list of exactly the expected str members in any
    order, with no extra, no missing, and no duplicates."""
    if type(value) is not list:
        return False
    if len(value) != len(expected_members):
        return False
    if any(type(item) is not str for item in value):
        return False
    return frozenset(value) == frozenset(expected_members)


def _validate_canonical(declaration: Any) -> tuple[bool, set[str]]:
    """Validate the declaration against the canonical 10IJ contract.

    Returns ``(canonical, errors)``. ``canonical`` is True iff the
    declaration exactly satisfies the 10IJ canonical habitat contract
    (independent of any optional rollback anchor). Errors is a set of codes;
    a single deviation yields exactly one code, and when multiple deviations
    coexist all applicable codes are returned (sorted and deduplicated by the
    caller), per 10IS proposal section D.

    Structural gate failures (non-dict input, empty dict, wrong top-level key
    set) are terminal: the field-level checks cannot be trusted to run safely
    on a declaration whose shape is not the canonical envelope, so they return
    immediately with the single structural code. Once the key set is exact,
    every field check is independent and errors accumulate.
    """
    if type(declaration) is not dict:
        return False, {"invalid_habitat"}

    # An empty dict carries none of the required keys and is structurally
    # invalid, not merely drifted.
    if not declaration:
        return False, {"invalid_habitat"}

    # Exact top-level key set: any extra or missing key fails closed. Field
    # values are only trustworthy once the envelope shape is canonical.
    keys = list(declaration.keys())
    if len(keys) != len(_HABITAT_KEYS) or frozenset(keys) != _HABITAT_KEYS:
        return False, {"habitat_drift"}

    errors: set[str] = set()

    # habitat_schema_version: exactly the canonical str.
    if (
        type(declaration["habitat_schema_version"]) is not str
        or declaration["habitat_schema_version"] != _HABITAT_SCHEMA_VERSION
    ):
        errors.add("invalid_habitat")

    # habitat_id: canonical str (drift) or non-str (structural).
    habitat_id = declaration["habitat_id"]
    if type(habitat_id) is not str:
        errors.add("invalid_habitat")
    elif habitat_id != _HABITAT_ID:
        errors.add("habitat_drift")

    # allowed_tile_ids: canonical set in any order; wrong type -> structural,
    # otherwise canonical-value drift.
    allowed = declaration["allowed_tile_ids"]
    if type(allowed) is not list or any(type(item) is not str for item in allowed):
        errors.add("invalid_habitat")
    elif not _is_str_list(allowed, _ALLOWED_TILE_IDS):
        errors.add("habitat_drift")

    # starting_tile_ids: exact two-key dict, str values matching canonical.
    starting = declaration["starting_tile_ids"]
    if type(starting) is not dict:
        errors.add("invalid_habitat")
    elif frozenset(starting.keys()) != frozenset(_AGENT_REFS):
        errors.add("habitat_drift")
    else:
        for ref in _AGENT_REFS:
            if type(starting[ref]) is not str:
                errors.add("invalid_habitat")
            elif starting[ref] != _STARTING_TILE_IDS[ref]:
                errors.add("habitat_drift")

    # observation_boundaries: exact two-key dict; each value a single-element
    # list equal to the canonical observation tile for that reference.
    obs = declaration["observation_boundaries"]
    if type(obs) is not dict:
        errors.add("invalid_observation_radius")
    elif frozenset(obs.keys()) != frozenset(_AGENT_REFS):
        errors.add("invalid_observation_radius")
    else:
        for ref in _AGENT_REFS:
            boundary = obs[ref]
            if type(boundary) is not list:
                errors.add("invalid_observation_radius")
            elif len(boundary) != 1:
                errors.add("invalid_observation_radius")
            elif type(boundary[0]) is not str:
                errors.add("invalid_observation_radius")
            elif boundary[0] != _OBSERVATION_BOUNDARIES[ref][0]:
                errors.add("invalid_observation_radius")

    # movement_allowed: must be the literal Python bool False (identity,
    # not truthiness). 0, 0.0, "false", [] all fail closed.
    if declaration["movement_allowed"] is not False:
        errors.add("habitat_drift")

    return (not errors), errors


def _rollback_binding(rollback_anchor: Any) -> tuple[bool, str | None, set[str]]:
    """Validate the optional rollback anchor's habitat_id binding (10IJ K).

    Returns ``(binding_valid, habitat_id_surface, errors)``. ``None`` skips
    the anchor check (binding valid, surface None). Any supplied anchor whose
    ``habitat_id`` does not equal the canonical habitat id fails closed:
    binding invalid, errors contains ``invalid_rollback_anchor``. A supplied
    anchor that is not a dict, or whose ``habitat_id`` is not a str, is
    malformed and also fails closed.

    The ``habitat_id_surface`` is only ever the canonical habitat id (when the
    binding is valid) or ``None``. Per 10IS proposal section C4 the result
    field ``rollback_anchor_habitat_id`` may contain only
    ``"genesis-first-habitat"`` or ``None``; an untrusted mismatched value is
    never echoed onto the result surface.
    """
    if rollback_anchor is None:
        return True, None, set()
    if type(rollback_anchor) is not dict:
        return False, None, {"invalid_rollback_anchor"}
    habitat_id = rollback_anchor.get("habitat_id")
    if type(habitat_id) is not str:
        return False, None, {"invalid_rollback_anchor"}
    if habitat_id != _HABITAT_ID:
        return False, None, {"invalid_rollback_anchor"}
    return True, habitat_id, set()


def _result(
    *,
    canonical: bool,
    rollback_anchor_binding_valid: bool,
    rollback_anchor_habitat_id: str | None,
    errors: set[str],
) -> dict[str, Any]:
    """Build the deterministic result dict with the exact section C4 key set.

    ``within_bounds == (canonical and rollback_anchor_binding_valid)``;
    ``ok == (within_bounds and errors == [])``. ``canonical`` describes the
    habitat declaration equality only; an invalid optional rollback anchor
    does NOT make a canonical habitat declaration non-canonical. ``status``
    describes the complete request: ``"canonical"`` when ok; else
    ``"non_canonical"`` when canonical is True but not ok; else
    ``"invalid_declaration"``. Errors are returned sorted and deduplicated.
    Returned habitat surfaces are fresh copies of the canonical constants,
    never aliases into the caller's input.
    """
    sorted_errors = sorted(set(errors))
    within_bounds = canonical and rollback_anchor_binding_valid
    ok = within_bounds and not sorted_errors
    if ok:
        status = "canonical"
    elif canonical:
        status = "non_canonical"
    else:
        status = "invalid_declaration"

    if canonical:
        habitat_schema_version: str | None = _HABITAT_SCHEMA_VERSION
        habitat_id: str | None = _HABITAT_ID
        allowed_tile_ids: list[str] | None = list(_ALLOWED_TILE_IDS)
        starting_tile_ids: dict[str, str] | None = dict(_STARTING_TILE_IDS)
        observation_boundaries: dict[str, list[str]] | None = {
            ref: list(tiles) for ref, tiles in _OBSERVATION_BOUNDARIES.items()
        }
    else:
        habitat_schema_version = None
        habitat_id = None
        allowed_tile_ids = None
        starting_tile_ids = None
        observation_boundaries = None

    return {
        "ok": ok,
        "canonical_contract_schema_version": _CONTRACT_SCHEMA_VERSION,
        "canonical_contract_type": _CONTRACT_TYPE,
        "canonical_contract_scope": _CONTRACT_SCOPE,
        "canonical_contract_id": _canonical_contract_id(),
        "status": status,
        "pair_id": _PAIR_ID,
        "habitat_schema_version": habitat_schema_version,
        "habitat_id": habitat_id,
        "allowed_tile_ids": allowed_tile_ids,
        "starting_tile_ids": starting_tile_ids,
        "observation_boundaries": observation_boundaries,
        "movement_allowed": _MOVEMENT_ALLOWED,
        "rollback_anchor_habitat_id": rollback_anchor_habitat_id,
        "canonical": canonical,
        "within_bounds": within_bounds,
        "rollback_anchor_binding_valid": rollback_anchor_binding_valid,
        "executed": False,
        "runtime_entity_created": False,
        "persisted": False,
        "memory_written": False,
        "ledger_written": False,
        "write_attempted": False,
        "model_called": False,
        "provider_called": False,
        "network_called": False,
        "daemon_started": False,
        "scheduler_started": False,
        "container_started": False,
        "docker_started": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": sorted_errors,
    }


def enforce_canonical_first_pair_habitat(
    declaration: dict, *, rollback_anchor: dict | None = None
) -> dict[str, Any]:
    """Enforce canonical equality of a First Pair habitat declaration
    against the 10IJ canonical habitat contract.

    Pure, deterministic, fail-closed, in-memory, validator-only. Does not
    mutate ``declaration`` or ``rollback_anchor``. Does not write, persist,
    create runtime entities, or perform external work.

    ``canonical`` describes the habitat declaration equality only;
    ``within_bounds == (canonical and rollback_anchor_binding_valid)``;
    ``ok == (within_bounds and errors == [])``.
    """
    canonical, errors = _validate_canonical(declaration)
    binding_valid, anchor_surface, anchor_errors = _rollback_binding(
        rollback_anchor
    )
    errors |= anchor_errors
    return _result(
        canonical=canonical,
        rollback_anchor_binding_valid=binding_valid,
        rollback_anchor_habitat_id=anchor_surface,
        errors=errors,
    )
