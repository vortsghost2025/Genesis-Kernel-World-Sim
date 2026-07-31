# Phase 10IS — First Pair Canonical Habitat Contract Enforcement
# Implementation-Candidate Proposal (Docs-Only)

Docs-only implementation-candidate proposal. This document designs the
future **10IS** phase — the named-but-not-implemented implementation
candidate (L+2) reserved by Phase 10IJ for **canonical-equality
enforcement** of the 10IJ-declared habitat contract.

This is **documentation only**. It creates no module, writes no code,
adds no tests, executes nothing, performs no write, authorizes no
persistence, creates no Adam/Eve runtime entity, does not modify 10CP,
does not open Gate-7, does not implement or alter 10HD, and does not
touch `world-sim/data`. 10CP remains the sole writer. Adam and Eve never
become writers.

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## A. Title and Status

- **Title**: Phase 10IS — First Pair Canonical Habitat Contract
  Enforcement (Implementation-Candidate Proposal).
- **Status**: **Docs-only proposal. Not approved.**
  - 10IS is **named-but-not-implemented**.
  - 10IS is **not started**.
  - 10IS is **not authorized for executable work** — no Python module,
    no Python test file, no executable scaffold, no RED/GREEN test
    execution. All executable artifacts of 10IS are **planned** and will
    be authored by GPT-5.6 Sol/Luna under AGENTS.md Rule 3.
  - Approval of this proposal authorizes only **freezing the executable
    design** into the record and preparing the GPT-5.6 Sol/Luna handoff.
    It does **not** authorize any executable work, and it does not
    substitute for GPT-5.6 Sol/Luna authorship.
- **Phase number**: 10IS. The next sequenced phase after 10IR (metadata
  sync, L+1, merged at `823fded` / hash-corrected at `32a85a9`). Chain
  per AGENTS.md Rule 4: 10IJ (spec, L) -> 10IR (sync, L+1) -> 10IS
  (implementation candidate, L+2).
- **Authoritative model boundary**: The 10IS implementation (test file +
  module) is authored **exclusively by GPT-5.6 Sol/Luna**. Sean's
  temporary unavailability of Sol/Luna until **August 5, 2026** is
  accommodated by completing the full docs-only design package now and
  handing it to Sol/Luna when available. No other model authors
  executable 10IS work. A later Sol/Luna review of work authored by
  another model does **not** satisfy this boundary.
- **Boundary preservation**: Gate-7 remains closed. 10HD remains
  named-only and untouched. 10CP remains the sole writer.
  `world-sim/data` remains forbidden. `FIRST_PAIR_CREATION_AUTHORIZED =
  False`.

---

## B. Purpose

10IJ declared the canonical starting habitat contract for the First
Pair. 10IS is the future phase that will **enforce canonical equality**
against that contract at runtime — the specific enforcement the 10IJ
spec explicitly deferred to 10IS in §F, §H, §I, and §K:

> "Canonical-identifier equality enforcement against this 10IJ spec is
> **future 10IS implementation work**, not existing 10ID behavior."

Today's 10ID validator
(`backend/world/local_first_pair_habitat_boundary.py`) enforces
**structural self-consistency** of a caller-supplied declaration
(exact key-set, types, reference-key containment, `movement_allowed =
False` literal). It does **not** enforce canonical equality against the
10IJ-declared identifiers. 10IS closes that gap with a future **pure,
deterministic, fail-closed, in-memory, validator-only** module that is
**non-writing** and **non-creating**.

---

## C. Planned Artifacts (future, authored by GPT-5.6 Sol/Luna)

These artifacts are **planned** in this proposal. They do not exist yet.
They will be authored by GPT-5.6 Sol/Luna, TDD-first, after Sean approves
this proposal and Sol/Luna becomes available.

- **Planned module**:
  `world-sim/backend/world/canonical_first_pair_habitat_contract.py`
- **Planned entry point**:
  `enforce_canonical_first_pair_habitat(declaration: dict, *, rollback_anchor: dict | None = None) -> dict[str, Any]`
- **Planned test file**:
  `world-sim/tests/test_phase10is_canonical_first_pair_habitat_contract.py`

No existing module is modified. No new dependencies.

### C1. Input contract

`declaration` is the habitat declaration object defined by 10IJ §I — the
same object that would appear as the `habitat` field of a future First
Pair birth candidate. Accepted Python type: **exactly a `dict`**
(`type(declaration) is dict`). Subclasses and non-dict inputs fail
closed.

Optional keyword `rollback_anchor: dict | None` carries the rollback
anchor envelope (10IH) whose `habitat_id` must equal the canonical
habitat id per 10IJ §K. `None` skips the anchor check.

### C2. Canonical constants (fixed from 10IJ §I)

```python
HABITAT_SCHEMA_VERSION = "first_habitat.1"
HABITAT_ID = "genesis-first-habitat"
ALLOWED_TILE_IDS = ("public-start-adam", "public-start-eve")   # canonical order
STARTING_TILE_IDS = {"east_adam": "public-start-adam", "east_eve": "public-start-eve"}
OBSERVATION_BOUNDARIES = {"east_adam": ("public-start-adam",), "east_eve": ("public-start-eve",)}
MOVEMENT_ALLOWED = False
CANONICAL_AGENT_REFS = ("east_adam", "east_eve")
```

### C3. Equality semantics

- **Top-level key-set**: the declaration must have exactly the six keys
  `habitat_schema_version`, `habitat_id`, `allowed_tile_ids`,
  `starting_tile_ids`, `observation_boundaries`, `movement_allowed`. Any
  extra or missing top-level key fails closed.
- **Type sensitivity**: every value is type-checked strictly
  (`type(x) is T`). `bool` is a distinct type from `int`.
- **`habitat_schema_version`**: exactly the string `"first_habitat.1"`.
- **`habitat_id`**: exactly the string `"genesis-first-habitat"`.
- **`allowed_tile_ids`**: a `list` of exactly two `str` elements equal to
  the canonical set **in any order** (10IJ §I: "in any order"). No
  extra, no missing, no duplicates.
- **`starting_tile_ids`**: a `dict` with exactly the two keys
  `east_adam` and `east_eve`; each value is the canonical `str` starting
  tile for that reference, and each starting tile is a member of the
  canonical allowed set.
- **`observation_boundaries`**: a `dict` with exactly the two keys
  `east_adam` and `east_eve`; each value is a single-element `list` equal
  to the canonical observation tile for that reference.
- **`movement_allowed`**: must be the literal Python `bool` `False`
  (`movement_allowed is False`). `0`, `0.0`, `"false"`, and `[]` all fail
  closed. Bool-versus-int is enforced by identity/type, not truthiness.
- **Duplicate keys**: the validator receives an already-constructed
  `dict`; Python collapses duplicate literal keys at construction
  (last-wins). Duplicate-key detection is a serialization-layer concern
  and is out of scope for this validator. The input is a dict; the
  validator enforces what the dict observably contains.
- **Input immutability**: the validator MUST NOT mutate `declaration` or
  `rollback_anchor`. It reads only. Returned values are fresh copies of
  the canonical constants, never aliases into the caller's input.
- **Deterministic output**: identical inputs MUST produce byte-identical
  outputs (same key order, same serialized values). No time, entropy,
  or environment dependence.
- **Full-digest identifier (single derivation algorithm)**:
  `canonical_contract_id` identifies the **fixed authoritative 10IJ
  canonical habitat contract**, not the submitted declaration. It is
  ALWAYS derived from the exact 10IJ canonical declaration:

  ```
  canonical_contract_id = "10IS-" + SHA256(canonical_contract_material).hexdigest()
  ```

  where `canonical_contract_material` is the exact 10IJ canonical
  habitat declaration (the §C2 constant object, not any caller input)
  serialized deterministically as:
  - UTF-8
  - canonical JSON
  - sorted object keys
  - separators equivalent to `,` and `:` with no extra whitespace
  - `ensure_ascii=False`
  - no trailing newline in the hashed byte sequence

  The digest MUST be:
  - exactly 64 lowercase hexadecimal characters (untruncated, per 10IK
    full-digest no-truncation convention)
  - independent of caller input
  - independent of validation outcome
  - independent of rollback-anchor presence or validity
  - independent of time, entropy, environment, provider, runtime,
    filesystem, or network state

  Therefore `canonical_contract_id` is **identical** for a canonical
  habitat input, a non-canonical habitat input, a canonical habitat with
  an invalid rollback anchor, and an invalid declaration input: it
  identifies the contract being enforced, not the submitted declaration.
  No input/declaration digest field is added in this phase.
- **Error ordering and deduplication**: errors are collected, deduplicated
  as a set, and returned sorted ascending (`sorted(set(errors))`),
  mirroring 10ID's `_boundary_result`.

### C4. Result schema (exact output key set and types)

The entry returns a `dict` with **exactly** this key set:

| Key | Type | Value |
|-----|------|-------|
| `ok` | bool | True iff `within_bounds` is True and `errors == []` |
| `canonical_contract_schema_version` | str | `"10IS.1"` |
| `canonical_contract_type` | str | `"first_pair_habitat_contract"` |
| `canonical_contract_scope` | str | `"pure_in_memory_canonical_validation_only"` |
| `canonical_contract_id` | str | `"10IS-" + <full 64-char lowercase SHA-256 of canonical_contract_material>` (fixed contract identifier; independent of caller input and validation outcome; see §C3 full-digest rule) |
| `status` | str | `"canonical"` when `ok`; else `"non_canonical"` when `canonical` is True but not `ok`; else `"invalid_declaration"` |
| `pair_id` | str | `"genesis-first-pair"` |
| `habitat_schema_version` | str\|None | `"first_habitat.1"` or None |
| `habitat_id` | str\|None | `"genesis-first-habitat"` or None |
| `allowed_tile_ids` | list[str]\|None | canonical list or None |
| `starting_tile_ids` | dict\|None | canonical dict or None |
| `observation_boundaries` | dict\|None | canonical dict or None |
| `movement_allowed` | bool | `False` |
| `rollback_anchor_habitat_id` | str\|None | `"genesis-first-habitat"` or None |
| `canonical` | bool | True iff the habitat **declaration** exactly satisfies the 10IJ canonical habitat contract (independent of any optional rollback anchor) |
| `within_bounds` | bool | `canonical AND rollback_anchor_binding_valid` (complete request passes all boundaries) |
| `rollback_anchor_binding_valid` | bool | True iff no anchor supplied, or supplied anchor's `habitat_id == "genesis-first-habitat"` |
| `executed` | bool | `False` |
| `runtime_entity_created` | bool | `False` |
| `persisted` | bool | `False` |
| `memory_written` | bool | `False` |
| `ledger_written` | bool | `False` |
| `write_attempted` | bool | `False` |
| `model_called` | bool | `False` |
| `provider_called` | bool | `False` |
| `network_called` | bool | `False` |
| `daemon_started` | bool | `False` |
| `scheduler_started` | bool | `False` |
| `container_started` | bool | `False` |
| `docker_started` | bool | `False` |
| `runtime_allowed` | bool | `False` |
| `daemon_allowed` | bool | `False` |
| `scheduler_allowed` | bool | `False` |
| `network_allowed` | bool | `False` |
| `world_sim_data_accessed` | bool | `False` |
| `gate7_activity_allowed` | bool | `False` |
| `claim_boundary` | str | `"canonical_first_pair_habitat_contract_only"` |
| `errors` | list[str] | empty when canonical, else sorted set of codes |

### C5. Fail-closed acceptance matrix (docs, 24 cases)

The future TDD scaffold must assert these behaviors:

| # | Input deviation from canonical form | Expected `errors` |
|---|-------------------------------------|-------------------|
| 1 | Canonical pass (10IJ §I exact) | `[]` |
| 2 | Non-dict input (e.g. `None`, `"x"`, `42`, `[]`) | `["invalid_habitat"]` |
| 3 | Empty dict `{}` | `["invalid_habitat"]` |
| 4 | Extra top-level key (`"extra": 1`) | `["habitat_drift"]` |
| 5 | Missing top-level key (drop `habitat_id`) | `["habitat_drift"]` |
| 6 | `habitat_schema_version` wrong value (`"x"`) | `["invalid_habitat"]` |
| 7 | `habitat_schema_version` non-str (`123`) | `["invalid_habitat"]` |
| 8 | `habitat_id` wrong value (`"other-habitat"`) | `["habitat_drift"]` |
| 9 | `habitat_id` non-str (`123`) | `["invalid_habitat"]` |
| 10 | `allowed_tile_ids` order swapped (adam/eve) | `[]` (order-insensitive per 10IJ §I) |
| 11 | `allowed_tile_ids` missing one element | `["habitat_drift"]` |
| 12 | `allowed_tile_ids` extra element | `["habitat_drift"]` |
| 13 | `allowed_tile_ids` not a list | `["invalid_habitat"]` |
| 14 | `allowed_tile_ids` element non-str | `["invalid_habitat"]` |
| 15 | `starting_tile_ids` missing key | `["habitat_drift"]` |
| 16 | `starting_tile_ids` extra key | `["habitat_drift"]` |
| 17 | `starting_tile_ids` wrong value | `["habitat_drift"]` |
| 18 | `starting_tile_ids` value non-str | `["invalid_habitat"]` |
| 19 | `observation_boundaries` not single-element | `["invalid_observation_radius"]` |
| 20 | `observation_boundaries` wrong tile | `["invalid_observation_radius"]` |
| 21 | `observation_boundaries` value not a list | `["invalid_observation_radius"]` |
| 22 | `movement_allowed` is `0` (int) | `["habitat_drift"]` |
| 23 | `movement_allowed` is `True` | `["habitat_drift"]` |
| 24 | `rollback_anchor` provided with `habitat_id != "genesis-first-habitat"` | `["invalid_rollback_anchor"]` |

Additional required assertions (not matrix rows):

- `ok == (within_bounds and errors == [])` in every case.
- `canonical` reflects **habitat-declaration equality only**: an invalid
  optional rollback anchor does NOT make a canonical habitat declaration
  non-canonical.
- `within_bounds == (canonical and rollback_anchor_binding_valid)`.
- `rollback_anchor_binding_valid` is True when no anchor is supplied,
  and True iff the supplied anchor's `habitat_id ==
  "genesis-first-habitat"` otherwise.
- Canonical habitat + invalid optional rollback anchor:
  `canonical = True`, `within_bounds = False`, `ok = False`,
  `errors = ["invalid_rollback_anchor"]`.
- Canonical habitat + no rollback anchor:
  `canonical = True`, `within_bounds = True`, `ok = True`,
  `errors = []`.
- Non-canonical habitat: `canonical = False`, `within_bounds = False`,
  `ok = False`.
- `canonical_contract_id` is `"10IS-" + <64 lowercase hex>` (full
  digest, no truncation) of `canonical_contract_material` — the fixed
  10IJ canonical declaration serialized per §C3. It is **identical for
  every validation outcome** (canonical input, non-canonical input,
  invalid anchor, invalid declaration) and is **never** derived from
  caller-supplied input. No input/declaration digest field is added.
- Output flags `runtime_entity_created`, `persisted`, `memory_written`,
  `ledger_written`, `write_attempted`, `model_called`, `provider_called`,
  `network_called`, `daemon_started`, `scheduler_started`,
  `container_started`, `docker_started`, and all `*_allowed` flags are
  `False` in every case.
- Input dicts are unchanged (byte-identical) after the call.
- Error list is sorted and deduplicated.

---

## D. Error Vocabulary (finalized — reuse existing codes)

Reuse the existing repository vocabulary. No new codes are invented.

| Code | Used for | Rationale |
|------|----------|-----------|
| `invalid_habitat` | non-dict input; wrong-typed or non-str values; wrong `habitat_schema_version` | Structural/type failures of the habitat declaration. Reserved by 10IJ §I as an allowed illustrative error for the future canonical validator. NOTE: 10IC does not emit this code today — `local_first_pair_birth_candidate.py` sets `habitat_valid = False` for an invalid habitat structure and `create_first_pair_birth_candidate` then emits `habitat_drift` when `habitat_valid` is not True. |
| `habitat_drift` | extra/missing top-level key; wrong `habitat_id`; wrong allowed/starting tile content; `movement_allowed` not literal `False` | Well-typed but non-canonical declaration content; 10ID uses `habitat_drift` for `habitat_valid is not True` and `movement_allowed is not False` |
| `invalid_observation_radius` | observation boundary not single-element / wrong tile / not a list | 10ID already uses `invalid_observation_radius` for radius/boundary shape failures |
| `invalid_rollback_anchor` | rollback anchor `habitat_id` mismatch | 10ID already uses `invalid_rollback_anchor` |

Mapping decisions worth documenting in the module docstring:

- `invalid_habitat` = "this is not a structurally valid habitat
  declaration" (shape/type/version). Reserved by 10IJ §I for the future
  canonical validator; not currently emitted by 10IC (10IC converts
  habitat validation failure into `habitat_drift`).
- `habitat_drift` = "this is a valid-shaped habitat declaration that has
  drifted from the canonical 10IJ contract" (canonical-value deviation).
  Preserves the existing 10IC/10ID meaning for well-shaped habitat
  content that fails the required contract or validation state.
- 10IS intentionally distinguishes **structural invalidity**
  (`invalid_habitat`) from **canonical-value drift** (`habitat_drift`)
  more precisely than 10IC currently does.
- `invalid_observation_radius` = "the observation boundary is not the
  canonical single-tile self-observation".
- `invalid_rollback_anchor` = "the rollback anchor does not bind to the
  canonical habitat id".
- A single deviation yields exactly one error code; when multiple
  deviations coexist, all applicable codes are returned (sorted,
  deduplicated).

---

## E. Relationship to Existing Phases (non-modification)

- **10ID** (`local_first_pair_habitat_boundary.py`): NOT modified. Its
  structural self-consistency role is unchanged. 10IS is the canonical
  layer; 10ID's `boundary_tile_ids` remain `sorted(allowed_tile_ids)`.
- **10IC** (`local_first_pair_birth_candidate.py`): NOT modified. The
  10IJ §J identity-to-tile binding (`east_adam`/`east_eve`) is validated
  by 10IC today; 10IS re-verifies the canonical `starting_tile_ids` and
  `observation_boundaries` key-set against those same canonical refs.
- **10IE** (`local_first_pair_memory_boundary.py`): NOT modified. 10IS
  writes no memory; it only verifies a declaration.
- **10IH** (rollback anchor envelope): NOT modified. 10IS enforces the
  10IJ §K binding — a rollback anchor's `habitat_id` must equal the
  canonical `"genesis-first-habitat"` — by validating the optional
  `rollback_anchor` input against that canonical id.
- **10CP**: NOT modified. 10IS performs no write and consumes no ledger
  path. The 10CJ inert audit surface is unchanged.
- **Legacy/demo runtime path** (`first_pair_runtime.py`,
  `first_pair_persistence.py`, `first_pair_cognition_*`): **out of
  scope**. 10IS neither aligns with, modifies, replaces, nor deprecates
  the legacy path. Per 10IJ §A, that relationship is deferred to a
  future audit phase.
- **10II / 10IG / 10IL / 10IO / 10IK**: NOT modified. 10IS reuses their
  declared identifiers (`genesis-first-habitat`, pair/anchor ids, schema
  version strings) as canonical constants only.

---

## F. Non-Authority Statement

- 10IS is an implementation **proposal**; it performs no write and
  authorizes no creation.
- **Passing canonical validation grants no creation or write
  authority.** A canonical-passing declaration creates nothing,
  persists nothing, and grants no write. 10IS is validation only.
- Adam and Eve never become writers. 10CP remains the sole writer.
- Gate-7 remains closed: no daemon, scheduler, network, provider, model,
  container or Docker activity.
- `world-sim/data` remains completely forbidden.
- 10HD remains named-only and untouched.
- No self-scheduling, no model/provider autonomy.

---

## G. Authoritative Model Boundary and Correct Workaround

**Sean did not waive the GPT-5.6 Sol/Luna authorship requirement.** The
temporary unavailability of Sol/Luna (until August 5, 2026) is handled
by doing the maximum **docs-only** preparation now, and by having
Sol/Luna author all executable 10IS work when it becomes available.

### Allowed now (before Aug 5)

- This docs-only proposal and its refinement.
- Architecture and interface design (done here).
- Exact canonical constants, equality semantics, result schema, error
  vocabulary (done here).
- Acceptance matrix as documentation (done here).
- Pseudocode that is clearly non-executable.
- Integration-boundary analysis (done here).
- A complete GPT-5.6 Sol/Luna implementation handoff prompt.
- Repository consistency audits that make no code or test changes.

### Not allowed now (must wait for GPT-5.6 Sol/Luna)

- Creating or editing Python test files.
- Creating or editing Python modules.
- Executable scaffolding.
- RED/GREEN test execution for 10IS.
- Backend/runtime/data implementation.
- Modifying 10IC, 10ID, 10IE, 10CP, persistence, or runtime modules.
- Claiming that a later Sol/Luna review substitutes for Sol/Luna
  authorship.
- Starting 10IS implementation.

### Correct workaround sequence

1. Refine and approve this docs-only proposal.
2. Freeze the executable design into the record (this document + the
   Sol/Luna handoff prompt).
3. Hand the exact package to GPT-5.6 Sol/Luna when available (Aug 5+).
4. GPT-5.6 Sol/Luna writes the RED test file first.
5. GPT-5.6 Sol/Luna then implements the bounded pure validator module.
6. Normal explicit commit/push authorization applies at the end
   (AGENTS.md Rule 3).

---

## H. GPT-5.6 Sol/Luna Handoff

The complete implementation handoff prompt for GPT-5.6 Sol/Luna is
provided in the separate docs-only file:

`world-sim/docs/phase_10is_sol_handoff_prompt.md`

That file is untracked and uncommitted. It instructs Sol/Luna to:

- recover the authoritative master checkpoint;
- read 10IJ, 10IR, and the approved 10IS proposal;
- write the test file first and prove RED for the intended missing
  implementation;
- implement only the bounded pure validator module;
- prove GREEN;
- run the 225 regression tests plus the new 10IS tests;
- preserve Gate-7, 10CP sole-writer, 10HD named-only, and
  `FIRST_PAIR_CREATION_AUTHORIZED = False`;
- stop before commit unless Sean explicitly authorizes the lifecycle.

---

## I. Verification Plan (docs-only)

- `git diff --check` on every proposed change.
- LF/CRLF verification (CRLF=0; LF only).
- Review: diff inspection, Kilo Code Review, GitGuardian, bounded tests,
  active-thread review. GitHub Codex review remains unavailable until
  Aug 5 and is not polled.
- No full `pytest`; no `git add -A` / `git add .`; explicit staging
  paths only; no squash/rebase/force/amend/reset.

---

## J. Deliverables & Completion (future)

Upon completion of the authorized executable phase (after Aug 5), 10IS
will have:

- A TDD-scaffolded, reviewed canonical habitat contract validator module
  authored by GPT-5.6 Sol/Luna, enforcing the full 10IJ §I canonical
  form.
- A green bounded test set proving canonical pass and fail-closed
  behavior for the §C5 acceptance matrix.
- A `phase_index.md` row marked **Done** (post-push hash recording), and
  a 10IT metadata-sync phase (L+3) planned only after 10IS is pushed —
  per AGENTS.md Rule 4 and the 10IJ/10IR precedent.

No runtime First Pair creation path is implemented by 10IS. 10IS is
**validator-only**. Any future First Pair runtime creation path remains
a separate, separately-authorized phase with GPT-5.6 Sol/Luna, TDD, and
explicit Sean approval.
