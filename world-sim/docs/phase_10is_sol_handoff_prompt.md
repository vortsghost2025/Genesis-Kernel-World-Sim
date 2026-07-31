# Phase 10IS — GPT-5.6 Sol/Luna Implementation Handoff Prompt

Docs-only handoff package. This file is the **exact implementation
prompt** for GPT-5.6 Sol/Luna to author the Phase 10IS executable
artifacts. It is untracked and uncommitted. It authorizes nothing by
itself; it becomes active only when Sean separately authorizes the 10IS
implementation lifecycle (after Sol/Luna is available, currently
expected after August 5, 2026).

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## Role

You are GPT-5.6 Sol/Luna authoring Phase 10IS — First Pair Canonical
Habitat Contract Enforcement. This is the implementation candidate
(L+2) for Phase 10IJ per AGENTS.md Rule 4. You are the authoritative
implementation author for this phase. No other model has authored any
executable 10IS work.

## Preconditions (verify before writing anything)

1. Recover the authoritative master checkpoint:
   - `git checkout master`
   - `git fetch origin master && git pull --ff-only origin master`
   - `git rev-parse HEAD` must equal the public master head.
   - Working tree must be clean before any new work.
2. Read, in order:
   - `AGENTS.md` (constitutional constraints, Rules 1–4).
   - `world-sim/docs/phase_10ij_first_pair_starting_habitat_tiles_spec.md`
     (the canonical contract this phase enforces).
   - `world-sim/docs/phase_10ir_*` (10IR rows in `phase_index.md`).
   - `world-sim/docs/phase_10is_first_pair_canonical_habitat_contract_impl_proposal.md`
     (approved design: interface, constants, result schema, error
     vocabulary, acceptance matrix).
   - `world-sim/docs/phase_10is_sol_handoff_prompt.md` (this file).
3. Confirm you have read this entire handoff before writing any code.

## Scope of work (nothing more, nothing less)

### Artifact 1 — TDD test file (write FIRST)

- Path: `world-sim/tests/test_phase10is_canonical_first_pair_habitat_contract.py`
- Content must assert, at minimum, the complete §C5 acceptance matrix
  (24 cases) and the additional required assertions from the approved
  proposal (ok/within_bounds/canonical/rollback_anchor_binding_valid
  semantics including the canonical-habitat-plus-invalid-anchor case,
  `canonical_contract_id` identity across all outcomes as the fixed
  10IJ-contract identifier derived from `canonical_contract_material`,
  all flags False, input immutability, sorted-deduplicated errors).
- Module under test: `backend.world.canonical_first_pair_habitat_contract`
  with entry point `enforce_canonical_first_pair_habitat`.
- Follow the strict-TDD header style of the existing 10IC/10ID/10IE test
  files (module name/path constants, schema/type/id constants, clear
  docstring stating this file is written first and must fail RED before
  the module exists).
- **Prove RED**: run the new test file alone against master (no module
  exists) and show that it fails with a collection/module-not-found error
  for the intended missing implementation — i.e. it does not accidentally
  pass.

### Artifact 2 — Validator module (write SECOND)

- Path: `world-sim/backend/world/canonical_first_pair_habitat_contract.py`
- Implement exactly the interface and semantics in the approved proposal:
  - Pure, deterministic, fail-closed, in-memory, validator-only.
  - No writes: no persistence, no ledger, no memory write, no runtime
    entity, no model/provider/network/daemon/scheduler/container/Docker
    activity. All such flags are literal `False`.
  - Exact canonical constants from the proposal (§C2).
  - Exact equality semantics (§C3): strict types, exact key-set, list
    order-insensitive for `allowed_tile_ids` only, `movement_allowed`
    identity-checked as `False`, no input mutation, deterministic
    output, errors as sorted set.
  - Contract identifier (§C3/C4): `canonical_contract_id` MUST be
    `"10IS-" + SHA256(canonical_contract_material).hexdigest()` where
    `canonical_contract_material` is the fixed 10IJ canonical
    declaration serialized deterministically (UTF-8, canonical JSON,
    sorted object keys, `,`/`:` separators with no extra whitespace,
    `ensure_ascii=False`, no trailing newline). The full 64-char
    lowercase digest is never truncated, is independent of caller input,
    validation outcome, and rollback-anchor presence/validity, and is
    identical across every validation outcome. Do NOT add an
    input/declaration digest field.
  - Exact result schema (§C4): same key set, same types.
  - Result semantics (§C4): `canonical` describes the habitat
    **declaration** equality only; `within_bounds == (canonical and
    rollback_anchor_binding_valid)`; `ok == (within_bounds and errors ==
    [])`. An invalid optional rollback anchor must NOT make a canonical
    habitat declaration non-canonical.
  - Error vocabulary (§D): reuse `invalid_habitat`, `habitat_drift`,
    `invalid_observation_radius`, `invalid_rollback_anchor`; do not
    invent new codes.
  - Optional `rollback_anchor` keyword enforcing the 10IJ §K binding.
  - Module docstring must document the invalid_habitat vs habitat_drift
    mapping decisions and the duplicate-key boundary assumption.
- **Prove GREEN**: run the new test file; all 24 acceptance cases and
  additional assertions must pass.

### Artifact 3 — Regression verification

- Run the bounded suite, which must pass entirely:
  - `test_phase10is_canonical_first_pair_habitat_contract.py`
  - `test_phase10ic_first_pair_birth_candidate.py`
  - `test_phase10id_first_pair_habitat_boundary.py`
  - `test_phase10ie_first_pair_memory_boundary.py`
  - `test_phase10ad_public_egress_sanitizer.py`
  - Expected total: 225 existing tests (10IC + 10ID + 10IE + 10AD)
    + all new 10IS tests.
- Do NOT run full `pytest` (legacy canonical/world mutation tests cause
  import-time collection errors).
- Verify `git diff --check` clean and CRLF=0 (LF only) on all touched
  files.

## Boundaries (mandatory)

- Preserve Gate-7 closed (no daemon/scheduler/network/provider/container/
  Docker activity).
- Preserve 10CP as the sole writer. Adam and Eve never become writers.
- Preserve 10HD named-only and untouched.
- Preserve `FIRST_PAIR_CREATION_AUTHORIZED = False`.
- Do NOT modify 10IC, 10ID, 10IE, 10CP, persistence, runtime,
  daemon/scheduler/network/provider/container/Docker, or any
  `world-sim/data` file.
- Do NOT touch the legacy/demo runtime path (`first_pair_runtime.py`,
  `first_pair_persistence.py`, `first_pair_cognition_*`). Its alignment
  is out of scope (10IJ §A).
- Do NOT create a First Pair runtime creation path. 10IS is
  validator-only.
- Do NOT write to `phase_index.md`; the 10IS row and 10IT metadata-sync
  are separate later steps.

## Stop condition

**Stop before commit.** After GREEN and regression verification, leave
the working tree with exactly two new files (test + module), uncommitted,
for Sean's review. Do not stage, commit, push, branch, or open a PR.
Explicit commit/push authorization from Sean is required to proceed with
the lifecycle (AGENTS.md Rule 3).

## Final report to Sean

Report:

- `git status -sb` and `git log --oneline -3`
- exact paths of the two new files
- RED evidence (the initial failing run)
- GREEN evidence (passing run with counts)
- regression totals (225 + new)
- `git diff --check` and CRLF=0 confirmation
- confirmation that no existing module or data file was modified
- confirmation that boundaries (Gate-7, 10CP, 10HD, FIRST_PAIR_CREATION_AUTHORIZED)
  are preserved
