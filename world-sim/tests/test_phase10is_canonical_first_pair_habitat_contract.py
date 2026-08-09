"""Phase 10IS - canonical first-pair habitat contract enforcement tests.

This test file is written FIRST under strict TDD (AGENTS.md Rule 3, Phase
10IS handoff). It must fail RED before the implementation module
``backend/world/canonical_first_pair_habitat_contract.py`` exists -- it
exercises an entry point that does not yet resolve, so collection imports
the module by name and pytest surfaces a module-not-found / import error
rather than accidentally passing.

Authorship note: Phase 10IS is reserved for GPT-5.6 Sol/Luna by
AGENTS.md Rule 3. Sean explicitly authorized this author to fill Sol's
spot for the 10IS implementation; that override is recorded here so the
authorship change is documented, not silent.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path

import pytest


MODULE_NAME = "backend.world.canonical_first_pair_habitat_contract"
MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "canonical_first_pair_habitat_contract.py"
)

# Canonical constants fixed from 10IJ section I / 10IS proposal section C2.
HABITAT_SCHEMA_VERSION = "first_habitat.1"
HABITAT_ID = "genesis-first-habitat"
ALLOWED_TILE_IDS = ["public-start-adam", "public-start-eve"]
STARTING_TILE_IDS = {
    "east_adam": "public-start-adam",
    "east_eve": "public-start-eve",
}
OBSERVATION_BOUNDARIES = {
    "east_adam": ["public-start-adam"],
    "east_eve": ["public-start-eve"],
}
MOVEMENT_ALLOWED = False

# Exact key set the habitat declaration must carry (10IS section C3).
HABITAT_KEYS = frozenset(
    {
        "habitat_schema_version",
        "habitat_id",
        "allowed_tile_ids",
        "starting_tile_ids",
        "observation_boundaries",
        "movement_allowed",
    }
)

# Exact result key set (10IS proposal section C4).
RESULT_FIELDS = frozenset(
    {
        "ok",
        "canonical_contract_schema_version",
        "canonical_contract_type",
        "canonical_contract_scope",
        "canonical_contract_id",
        "status",
        "pair_id",
        "habitat_schema_version",
        "habitat_id",
        "allowed_tile_ids",
        "starting_tile_ids",
        "observation_boundaries",
        "movement_allowed",
        "rollback_anchor_habitat_id",
        "canonical",
        "within_bounds",
        "rollback_anchor_binding_valid",
        "executed",
        "runtime_entity_created",
        "persisted",
        "memory_written",
        "ledger_written",
        "write_attempted",
        "model_called",
        "provider_called",
        "network_called",
        "daemon_started",
        "scheduler_started",
        "container_started",
        "docker_started",
        "runtime_allowed",
        "daemon_allowed",
        "scheduler_allowed",
        "network_allowed",
        "world_sim_data_accessed",
        "gate7_activity_allowed",
        "claim_boundary",
        "errors",
    }
)

# Flags that MUST be literal False in every outcome (non-authority).
INERT_FLAGS = frozenset(
    {
        "executed",
        "runtime_entity_created",
        "persisted",
        "memory_written",
        "ledger_written",
        "write_attempted",
        "model_called",
        "provider_called",
        "network_called",
        "daemon_started",
        "scheduler_started",
        "container_started",
        "docker_started",
        "runtime_allowed",
        "daemon_allowed",
        "scheduler_allowed",
        "network_allowed",
        "world_sim_data_accessed",
        "gate7_activity_allowed",
    }
)

# Static result fields fixed across all outcomes.
CONTRACT_SCHEMA_VERSION = "10IS.1"
CONTRACT_TYPE = "first_pair_habitat_contract"
CONTRACT_SCOPE = "pure_in_memory_canonical_validation_only"
PAIR_ID = "genesis-first-pair"
CLAIM_BOUNDARY = "canonical_first_pair_habitat_contract_only"


def _module():
    """Import the module under test lazily for strict-TDD RED behavior."""
    return importlib.import_module(MODULE_NAME)


def _entry():
    return _module().enforce_canonical_first_pair_habitat


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _canonical_declaration() -> dict:
    """Return a fresh canonical habitat declaration (10IJ section I exact)."""
    return {
        "habitat_schema_version": HABITAT_SCHEMA_VERSION,
        "habitat_id": HABITAT_ID,
        "allowed_tile_ids": list(ALLOWED_TILE_IDS),
        "starting_tile_ids": dict(STARTING_TILE_IDS),
        "observation_boundaries": {
            ref: list(tiles) for ref, tiles in OBSERVATION_BOUNDARIES.items()
        },
        "movement_allowed": MOVEMENT_ALLOWED,
    }


def _expected_contract_id() -> str:
    """Derive the fixed canonical_contract_id from the 10IJ canonical
    declaration serialized per 10IS section C3 (independent of any caller
    input and identical across all outcomes)."""
    material = _canonical_json(_canonical_declaration()).encode("utf-8")
    return "10IS-" + hashlib.sha256(material).hexdigest()


def _canonical_anchor() -> dict:
    return {"habitat_id": HABITAT_ID}


# ---------------------------------------------------------------------------
# Module / entry-point existence (RED guard)
# ---------------------------------------------------------------------------


def test_module_exists_and_exposes_entry_point():
    """Strict-TDD RED guard: the implementation module and its entry point
    must exist before any acceptance case can pass."""
    mod = _module()
    assert hasattr(mod, "enforce_canonical_first_pair_habitat"), (
        "entry point enforce_canonical_first_pair_habitat is missing"
    )
    assert callable(mod.enforce_canonical_first_pair_habitat)


def test_canonical_contract_material_file_present():
    """The implementation module file must exist on disk (RED guard)."""
    assert MODULE_PATH.is_file(), f"expected module at {MODULE_PATH}"


# ---------------------------------------------------------------------------
# Result schema invariants (apply to every outcome)
# ---------------------------------------------------------------------------


def _assert_schema(result: dict, *, is_canonical: bool, anchor_supplied: bool):
    """Assert the result carries exactly the required key set and the static
    fixed fields, with the inert flags all literal False."""
    assert type(result) is dict
    assert frozenset(result.keys()) == RESULT_FIELDS, (
        f"result key set mismatch: got {sorted(result.keys())}"
    )

    # Static contract-identity fields (fixed across all outcomes).
    assert result["canonical_contract_schema_version"] == CONTRACT_SCHEMA_VERSION
    assert result["canonical_contract_type"] == CONTRACT_TYPE
    assert result["canonical_contract_scope"] == CONTRACT_SCOPE
    assert result["pair_id"] == PAIR_ID
    assert result["claim_boundary"] == CLAIM_BOUNDARY
    assert result["movement_allowed"] is False

    # Non-authority flags all literal False in every case.
    for flag in INERT_FLAGS:
        assert result[flag] is False, f"inert flag {flag} must be False"

    # Contract identifier: full 64-char lowercase digest, identical for
    # every validation outcome, independent of caller input.
    cid = result["canonical_contract_id"]
    assert type(cid) is str
    assert cid == _expected_contract_id(), (
        "canonical_contract_id must equal the fixed 10IJ-contract digest"
    )
    assert cid.startswith("10IS-")
    assert len(cid) == len("10IS-") + 64
    assert cid[5:].islower() and all(c in "0123456789abcdef" for c in cid[5:])

    # status + canonical/within_bounds/ok/rollback binding consistency.
    assert result["canonical"] is is_canonical
    assert result["within_bounds"] is (
        result["canonical"] and result["rollback_anchor_binding_valid"]
    )
    assert result["ok"] is (
        result["within_bounds"] and result["errors"] == []
    )
    if result["ok"]:
        assert result["status"] == "canonical"
    elif result["canonical"]:
        assert result["status"] == "non_canonical"
    else:
        assert result["status"] == "invalid_declaration"

    # Anchor binding surface.
    if anchor_supplied and result["rollback_anchor_binding_valid"]:
        assert result["rollback_anchor_habitat_id"] == HABITAT_ID
    elif anchor_supplied:
        # Supplied but invalid: binding is invalid; the surface echoes the
        # supplied anchor's habitat_id (a str) or is None when the anchor was
        # malformed (non-dict / missing or non-str habitat_id).
        assert result["rollback_anchor_habitat_id"] is None or (
            type(result["rollback_anchor_habitat_id"]) is str
        )
        assert result["rollback_anchor_binding_valid"] is False
    else:
        assert result["rollback_anchor_habitat_id"] is None
        assert result["rollback_anchor_binding_valid"] is True

    # Errors are a list, sorted and deduplicated.
    assert type(result["errors"]) is list
    assert result["errors"] == sorted(set(result["errors"]))

    # Habitat surface mirrors canonical form only when canonical passes.
    if is_canonical:
        assert result["habitat_schema_version"] == HABITAT_SCHEMA_VERSION
        assert result["habitat_id"] == HABITAT_ID
        assert result["allowed_tile_ids"] == list(ALLOWED_TILE_IDS)
        assert result["starting_tile_ids"] == dict(STARTING_TILE_IDS)
        assert result["observation_boundaries"] == {
            ref: list(tiles) for ref, tiles in OBSERVATION_BOUNDARIES.items()
        }
    else:
        assert result["habitat_schema_version"] is None
        assert result["habitat_id"] is None
        assert result["allowed_tile_ids"] is None
        assert result["starting_tile_ids"] is None
        assert result["observation_boundaries"] is None


def _assert_immutability(snapshot: dict, current: dict, label: str):
    assert snapshot == current, f"{label} was mutated by the call"


# ---------------------------------------------------------------------------
# Case 1 -- canonical pass (10IJ section I exact), no anchor
# ---------------------------------------------------------------------------


def test_case_01_canonical_pass_no_anchor():
    declaration = _canonical_declaration()
    snapshot = copy.deepcopy(declaration)
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=True, anchor_supplied=False)
    assert result["ok"] is True
    assert result["canonical"] is True
    assert result["within_bounds"] is True
    assert result["rollback_anchor_binding_valid"] is True
    assert result["errors"] == []
    _assert_immutability(snapshot, declaration, "declaration")


# ---------------------------------------------------------------------------
# Cases 2-3 -- structural / non-dict invalid habitat
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_input",
    [None, "x", 42, 3.14, [], (), object()],
    ids=["none", "str", "int", "float", "list", "tuple", "object"],
)
def test_case_02_non_dict_input(bad_input):
    result = _entry()(bad_input)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_habitat"]
    assert result["ok"] is False
    assert result["canonical"] is False
    assert result["within_bounds"] is False


def test_case_03_empty_dict():
    result = _entry()({})
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_habitat"]
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# Cases 4-5 -- top-level key-set drift
# ---------------------------------------------------------------------------


def test_case_04_extra_top_level_key():
    declaration = _canonical_declaration()
    declaration["extra"] = 1
    snapshot = copy.deepcopy(declaration)
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]
    _assert_immutability(snapshot, declaration, "declaration")


def test_case_05_missing_top_level_key():
    declaration = _canonical_declaration()
    del declaration["habitat_id"]
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


# ---------------------------------------------------------------------------
# Cases 6-7 -- habitat_schema_version structural/value
# ---------------------------------------------------------------------------


def test_case_06_habitat_schema_version_wrong_value():
    declaration = _canonical_declaration()
    declaration["habitat_schema_version"] = "x"
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_habitat"]


@pytest.mark.parametrize("bad_value", [123, 1.0, True, None, [], {}])
def test_case_07_habitat_schema_version_non_str(bad_value):
    declaration = _canonical_declaration()
    declaration["habitat_schema_version"] = bad_value
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_habitat"]


# ---------------------------------------------------------------------------
# Cases 8-9 -- habitat_id value/type
# ---------------------------------------------------------------------------


def test_case_08_habitat_id_wrong_value():
    declaration = _canonical_declaration()
    declaration["habitat_id"] = "other-habitat"
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


@pytest.mark.parametrize("bad_value", [123, 1.0, True, None, [], {}])
def test_case_09_habitat_id_non_str(bad_value):
    declaration = _canonical_declaration()
    declaration["habitat_id"] = bad_value
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_habitat"]


# ---------------------------------------------------------------------------
# Cases 10-14 -- allowed_tile_ids set/type
# ---------------------------------------------------------------------------


def test_case_10_allowed_tile_ids_order_swapped():
    declaration = _canonical_declaration()
    declaration["allowed_tile_ids"] = ["public-start-eve", "public-start-adam"]
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=True, anchor_supplied=False)
    assert result["errors"] == []
    assert result["ok"] is True


def test_case_11_allowed_tile_ids_missing_element():
    declaration = _canonical_declaration()
    declaration["allowed_tile_ids"] = ["public-start-adam"]
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


def test_case_12_allowed_tile_ids_extra_element():
    declaration = _canonical_declaration()
    declaration["allowed_tile_ids"] = [
        "public-start-adam",
        "public-start-eve",
        "public-start-extra",
    ]
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


@pytest.mark.parametrize("bad_value", ["x", 123, ("public-start-adam",), {}, None])
def test_case_13_allowed_tile_ids_not_a_list(bad_value):
    declaration = _canonical_declaration()
    declaration["allowed_tile_ids"] = bad_value
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_habitat"]


@pytest.mark.parametrize("bad_elem", [123, True, None, ["nested"], 3.14])
def test_case_14_allowed_tile_ids_element_non_str(bad_elem):
    declaration = _canonical_declaration()
    declaration["allowed_tile_ids"] = ["public-start-adam", bad_elem]
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_habitat"]


# ---------------------------------------------------------------------------
# Cases 15-18 -- starting_tile_ids
# ---------------------------------------------------------------------------


def test_case_15_starting_tile_ids_missing_key():
    declaration = _canonical_declaration()
    del declaration["starting_tile_ids"]["east_eve"]
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


def test_case_16_starting_tile_ids_extra_key():
    declaration = _canonical_declaration()
    declaration["starting_tile_ids"]["east_extra"] = "public-start-adam"
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


def test_case_17_starting_tile_ids_wrong_value():
    declaration = _canonical_declaration()
    declaration["starting_tile_ids"]["east_adam"] = "public-start-eve"
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


@pytest.mark.parametrize("bad_value", [123, True, None, ["public-start-adam"], 3.14])
def test_case_18_starting_tile_ids_value_non_str(bad_value):
    declaration = _canonical_declaration()
    declaration["starting_tile_ids"]["east_adam"] = bad_value
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_habitat"]


# ---------------------------------------------------------------------------
# Cases 19-21 -- observation_boundaries
# ---------------------------------------------------------------------------


def test_case_19_observation_boundaries_not_single_element():
    declaration = _canonical_declaration()
    declaration["observation_boundaries"]["east_adam"] = [
        "public-start-adam",
        "public-start-eve",
    ]
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_observation_radius"]


def test_case_20_observation_boundaries_wrong_tile():
    declaration = _canonical_declaration()
    declaration["observation_boundaries"]["east_adam"] = ["public-start-eve"]
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_observation_radius"]


@pytest.mark.parametrize("bad_value", ["public-start-adam", 123, None, {}, ("public-start-adam",)])
def test_case_21_observation_boundaries_value_not_a_list(bad_value):
    declaration = _canonical_declaration()
    declaration["observation_boundaries"]["east_adam"] = bad_value
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_observation_radius"]


# ---------------------------------------------------------------------------
# Cases 22-23 -- movement_allowed literal False
# ---------------------------------------------------------------------------


def test_case_22_movement_allowed_int_zero():
    declaration = _canonical_declaration()
    declaration["movement_allowed"] = 0
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


def test_case_23_movement_allowed_true():
    declaration = _canonical_declaration()
    declaration["movement_allowed"] = True
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


@pytest.mark.parametrize("bad_value", [1, 0.0, "false", [], None])
def test_movement_allowed_other_truthy_falsy_values(bad_value):
    """Supplementary: confirm identity/type (not truthiness) is enforced."""
    declaration = _canonical_declaration()
    declaration["movement_allowed"] = bad_value
    result = _entry()(declaration)
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["habitat_drift"]


# ---------------------------------------------------------------------------
# Case 24 -- rollback anchor habitat_id mismatch
# ---------------------------------------------------------------------------


def test_case_24_rollback_anchor_habitat_id_mismatch():
    declaration = _canonical_declaration()
    declaration_snapshot = copy.deepcopy(declaration)
    anchor = {"habitat_id": "other-habitat"}
    anchor_snapshot = copy.deepcopy(anchor)
    result = _entry()(declaration, rollback_anchor=anchor)
    _assert_schema(result, is_canonical=True, anchor_supplied=True)
    assert result["canonical"] is True
    assert result["rollback_anchor_binding_valid"] is False
    assert result["within_bounds"] is False
    assert result["ok"] is False
    assert result["errors"] == ["invalid_rollback_anchor"]
    _assert_immutability(declaration_snapshot, declaration, "declaration")
    _assert_immutability(anchor_snapshot, anchor, "rollback_anchor")


def test_canonical_with_valid_anchor_passes():
    declaration = _canonical_declaration()
    result = _entry()(declaration, rollback_anchor=_canonical_anchor())
    _assert_schema(result, is_canonical=True, anchor_supplied=True)
    assert result["ok"] is True
    assert result["canonical"] is True
    assert result["within_bounds"] is True
    assert result["rollback_anchor_binding_valid"] is True
    assert result["errors"] == []
    assert result["rollback_anchor_habitat_id"] == HABITAT_ID


# ---------------------------------------------------------------------------
# Additional required assertions (not matrix rows)
# ---------------------------------------------------------------------------


def test_canonical_habitat_invalid_anchor_keeps_canonical_true():
    """An invalid optional rollback anchor must NOT make a canonical habitat
    declaration non-canonical (10IS section C4 semantics)."""
    declaration = _canonical_declaration()
    result = _entry()(declaration, rollback_anchor={"habitat_id": "x"})
    assert result["canonical"] is True
    assert result["within_bounds"] is False
    assert result["ok"] is False
    assert result["errors"] == ["invalid_rollback_anchor"]


def test_non_canonical_habitat_is_not_within_bounds():
    declaration = _canonical_declaration()
    declaration["habitat_id"] = "other"
    result = _entry()(declaration)
    assert result["canonical"] is False
    assert result["within_bounds"] is False
    assert result["ok"] is False


def test_canonical_contract_id_identical_across_all_outcomes():
    """The contract identifier is the fixed 10IJ-contract digest,
    identical across canonical/non-canonical/invalid-anchor/invalid-input
    outcomes and never derived from caller input."""
    canonical = _entry()(_canonical_declaration())
    non_canonical = _entry()({"habitat_id": "other"})
    invalid_anchor = _entry()(
        _canonical_declaration(), rollback_anchor={"habitat_id": "x"}
    )
    invalid_input = _entry()(None)

    expected = _expected_contract_id()
    assert canonical["canonical_contract_id"] == expected
    assert non_canonical["canonical_contract_id"] == expected
    assert invalid_anchor["canonical_contract_id"] == expected
    assert invalid_input["canonical_contract_id"] == expected
    # No input/declaration digest field exists in the schema.
    for r in (canonical, non_canonical, invalid_anchor, invalid_input):
        assert "input_digest" not in r
        assert "declaration_digest" not in r


def test_input_dicts_unchanged_after_call():
    """The validator MUST NOT mutate declaration or rollback_anchor."""
    declaration = _canonical_declaration()
    anchor = {"habitat_id": HABITAT_ID}
    decl_snapshot = copy.deepcopy(declaration)
    anchor_snapshot = copy.deepcopy(anchor)

    _entry()(declaration)  # canonical, no anchor
    _assert_immutability(decl_snapshot, declaration, "declaration (no anchor)")

    _entry()(declaration, rollback_anchor=anchor)  # canonical + valid anchor
    _assert_immutability(decl_snapshot, declaration, "declaration (with anchor)")
    _assert_immutability(anchor_snapshot, anchor, "rollback_anchor")

    bad_anchor = {"habitat_id": "x"}
    bad_anchor_snapshot = copy.deepcopy(bad_anchor)
    _entry()(declaration, rollback_anchor=bad_anchor)
    _assert_immutability(bad_anchor_snapshot, bad_anchor, "bad rollback_anchor")


def test_errors_sorted_and_deduplicated():
    """When multiple deviations coexist, all applicable codes are returned,
    sorted ascending and deduplicated (mirrors 10ID section C3)."""
    # Non-dict input yields a single structural code.
    assert _entry()(None)["errors"] == ["invalid_habitat"]
    # Canonical-declaration-with-invalid-anchor yields exactly one code.
    assert _entry()(
        _canonical_declaration(), rollback_anchor={"habitat_id": "x"}
    )["errors"] == ["invalid_rollback_anchor"]


def test_deterministic_output_identical_inputs():
    """Identical inputs MUST produce byte-identical outputs (no time/entropy/
    environment dependence)."""
    declaration = _canonical_declaration()
    r1 = _entry()(declaration)
    r2 = _entry()(copy.deepcopy(declaration))
    assert r1 == r2

    anchor = {"habitat_id": "x"}
    a1 = _entry()(_canonical_declaration(), rollback_anchor=anchor)
    a2 = _entry()(_canonical_declaration(), rollback_anchor=copy.deepcopy(anchor))
    assert a1 == a2


def test_no_input_digest_field_added():
    """10IS section C3: 'No input/declaration digest field is added in this
    phase.' The result key set must not contain such a field, and the
    canonical_contract_id must not be derived from caller input."""
    result = _entry()(_canonical_declaration())
    assert "input_digest" not in result
    assert "declaration_digest" not in result
    assert "habitat_digest" not in result


def test_returned_canonical_values_are_fresh_copies_not_aliases():
    """Per 10IS section C3: returned values are fresh copies of the
    canonical constants, never aliases into the caller's input."""
    declaration = _canonical_declaration()
    result = _entry()(declaration)
    allowed = result["allowed_tile_ids"]
    starting = result["starting_tile_ids"]
    obs = result["observation_boundaries"]

    # Returned collections must not be the same object as the input
    # collections (no aliasing back into the caller's dict).
    assert allowed is not declaration["allowed_tile_ids"]
    assert starting is not declaration["starting_tile_ids"]
    assert obs is not declaration["observation_boundaries"]

    # Mutating the returned copies must not affect a second call's output.
    allowed.append("public-start-mutant")
    r2 = _entry()(declaration)
    assert r2["allowed_tile_ids"] == ALLOWED_TILE_IDS


def test_strict_type_checking_no_subclasses():
    """type(x) is T (no isinstance). A dict subclass must fail closed as a
    non-dict input per 10IS section C1 ('type(declaration) is dict')."""
    class DictSub(dict):
        pass

    result = _entry()(DictSub())
    _assert_schema(result, is_canonical=False, anchor_supplied=False)
    assert result["errors"] == ["invalid_habitat"]
