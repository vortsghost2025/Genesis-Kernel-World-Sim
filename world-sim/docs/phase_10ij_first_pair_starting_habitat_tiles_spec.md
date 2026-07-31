# Phase 10IJ — First Pair Starting Habitat Tiles Specification

Numbered docs-only spec. This file formally declares the concrete starting
habitat tiles for the First Pair, resolving the audit finding in 10IF
§3 ("Starting habitat tiles not declared in spec"). The tiles currently
exist only in 10IC test fixtures; this spec elevates them to documented,
reviewable ground truth.

It is **docs-only**: it implements no module, adds no tests, performs no
write, authorizes no persistence, creates no Adam/Eve runtime entity, does
not modify 10CP, does not open Gate-7, does not implement or alter 10HD,
and does not touch `world-sim/data`. 10CP remains the sole writer. Adam and
Eve never become writers.

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## A. Title and Status

- **Title**: Phase 10IJ — First Pair Starting Habitat Tiles Specification.
- **Status**: Docs-only specification. Repository documentation reserves
  10IJ for the concrete starting habitat tiles declaration. The phase is
  started as docs-only under the preflight authorization recorded in 10IF.
- **Phase number**: 10IJ. No new phase number is assigned by this
  document; 10IK remains the next named future work and remains
  **not started**.
- **Boundary preservation**: Gate-7 remains closed. 10HD remains
  named-only and untouched. 10CP remains the sole writer.
  `world-sim/data` remains forbidden.
- **Phase-chain** (per AGENTS.md Rule 4, spec L -> sync L+1 ->
  implementation candidate L+2): 10IJ (spec, L) -> 10IR (sync, L+1) ->
  10IS (named implementation candidate, L+2). 10IS is named-but-not-
  implemented; it requires GPT-5.6 Sol/Luna, TDD from the 10IJ spec,
  explicit Sean approval, and all First Pair creation gates. No
  starting-habitat-tiles runtime validator, no runtime habitat
  enforcement module, and no First Pair runtime creation path currently
  exists. 10IS remains named-but-not-implemented.

---

## B. Purpose

10IJ defines the exact starting habitat tiles that a future First Pair
creation phase must bind to. It specifies:

- the concrete habitat identifier;
- the concrete allowed tile IDs;
- the concrete starting tile ID for each agent reference;
- the concrete observation boundaries per agent reference;
- the movement prohibition at creation.

This declaration is a prerequisite for any future First Pair creation
phase. It does not implement the habitat boundary validator (that is
10ID), does not implement the birth candidate constructor (that is 10IC),
and does not authorize creation. It is a **data contract only**.

---

## C. Explicit Non-Authority Statement

- 10IJ is docs-only and performs no write.
- 10IJ defines a data contract for starting habitat tiles only.
- 10IJ does not consume or require a 10CJ decision.
- 10IJ does not modify 10CP.
- Current 10CP accepts only the exact 10CN-authorized 10CJ inert audit
  surface. Current 10CP cannot consume a First Pair habitat declaration.
  No existing ledger path or record schema is inherited.
- 10CP remains the sole writer as a constitutional boundary.
- A later separately authorized First Pair adapter or 10CP-owned extension
  must be designed before any writer may consume First Pair candidate
  material. That future design requires separate docs authorization,
  implementation, TDD, GPT-5.6 Sol/Luna, and explicit Sean approval.
- Adam and Eve never become writers.
- `world-sim/data` remains completely forbidden.
- Gate-7 remains closed: no daemon, scheduler, network, provider,
  model, container or Docker activity is authorized.

---

## D. Habitat Identifier

The single canonical habitat identifier for the First Pair is:

```
genesis-first-habitat
```

This identifier **must** appear as the `habitat_id` field in any First Pair
birth candidate habitat declaration and must be strictly validated for
equality by the 10ID habitat boundary validator.

---

## E. Allowed Tile IDs

The complete, enumerated set of tile IDs permitted within the First Pair
habitat at creation is exactly two tiles:

```
public-start-adam
public-start-eve
```

No other tile IDs are allowed in the habitat's `allowed_tile_ids` array at
creation. Any future habitat expansion requires a separate authorized
phase.

These tile IDs are stable identifiers. They are not coordinates; they are
opaque tile references that the underlying world map resolves. The tiles
are public (not private, not hidden-substrate, not known-map only).

---

## F. Starting Tile Assignments

Each agent reference in the birth candidate is assigned exactly one
starting tile from the allowed set. The mapping is:

| Agent Reference | Starting Tile ID |
|-----------------|------------------|
| `east_adam`     | `public-start-adam` |
| `east_eve`      | `public-start-eve` |

These assignments are deterministic and must be validated for exact
equality by the 10ID habitat boundary validator. The `starting_tile_ids`
object in the habitat declaration must contain exactly these two keys
with exactly these two values. Extra keys, missing keys, or value
mismatches cause the habitat boundary to fail closed.

The starting tile for each agent **must** be a member of the
`allowed_tile_ids` array. The validator enforces this containment.

---

## G. Observation Boundaries

The observation boundary for each agent reference at creation is exactly
one tile — the agent's own starting tile:

| Agent Reference | Observation Boundary |
|-----------------|--------------------|
| `east_adam`     | `["public-start-adam"]` |
| `east_eve`      | `["public-start-eve"]` |

The `observation_boundaries` object in the habitat declaration must
contain exactly these two keys with exactly these single-element array
values. Each array element must be a member of `allowed_tile_ids`.

This enforces the observation-first rule: at creation, each agent observes
only its own starting tile. No cross-agent observation, no habitat-wide
observation, and no true-map observation are permitted.

---

## H. Movement Prohibition

At creation, movement is explicitly disabled:

```
movement_allowed = False
```

This value **must** appear as a literal `false` boolean in the habitat
declaration. The 10ID habitat boundary validator enforces this exact
value. No movement action is valid at creation.

---

## I. Complete Habitat Declaration Canonical Form

The following is the exact canonical habitat declaration object that a
future First Pair birth candidate must contain in its `habitat` field.
All fields are required. All values are exact literals. The 10ID habitat
boundary validator validates exact key-set equality and exact value
equality.

```json
{
  "habitat_schema_version": "first_habitat.1",
  "habitat_id": "genesis-first-habitat",
  "allowed_tile_ids": [
    "public-start-adam",
    "public-start-eve"
  ],
  "starting_tile_ids": {
    "east_adam": "public-start-adam",
    "east_eve": "public-start-eve"
  },
  "observation_boundaries": {
    "east_adam": ["public-start-adam"],
    "east_eve": ["public-start-eve"]
  },
  "movement_allowed": false
}
```

### Field Rules

| Field | Type | Rule |
|-------|------|------|
| `habitat_schema_version` | string | Must be exactly `"first_habitat.1"` |
| `habitat_id` | string | Must be exactly `"genesis-first-habitat"` |
| `allowed_tile_ids` | array[string] | Must contain exactly the two strings `"public-start-adam"` and `"public-start-eve"` in any order; no other elements |
| `starting_tile_ids` | object | Must have exactly keys `"east_adam"` and `"east_eve"` with values `"public-start-adam"` and `"public-start-eve"` respectively |
| `observation_boundaries` | object | Must have exactly keys `"east_adam"` and `"east_eve"` with array values `["public-start-adam"]` and `["public-start-eve"]` respectively |
| `movement_allowed` | boolean | Must be exactly `false` |

Any deviation from this exact structure causes the 10ID habitat boundary
to fail closed with an appropriate error (e.g., `invalid_habitat`,
`habitat_declaration_drift`, `invalid_observation_radius`, etc.).

---

## J. Identity Reference Binding

The agent references `east_adam` and `east_eve` are the **canonical agent
references** (`canonical_agent_ref`) declared in the birth candidate's
`adam_identity` and `eve_identity` objects. The 10IC birth candidate
constructor and the 10ID habitat boundary validator both require that
these references match exactly.

The mapping is:

- `adam_identity.canonical_agent_ref` → must equal `"east_adam"`
- `eve_identity.canonical_agent_ref` → must equal `"east_eve"`

These references are then used as keys in `starting_tile_ids` and
`observation_boundaries`. This creates a transitive identity-to-tile
binding: the agent's identity commits to its canonical reference, the
habitat commits to that reference's starting tile and observation
boundary, and the validator enforces the chain.

---

## K. Rollback Anchor Habitat Binding

The 10IH rollback anchor specification requires that the anchor's
`habitat_id` field exactly equal the validated habitat's `habitat_id`.
Since 10IJ fixes the habitat identifier as `"genesis-first-habitat"`,
any valid rollback anchor for the First Pair must carry:

```
habitat_id = "genesis-first-habitat"
```

The 10ID validator enforces this equality.

---

## L. Cross-Spec Audit Resolution

This spec closes the following audit finding from 10IF §3:

| 10IF Issue | Resolution |
|------------|------------|
| **Starting habitat tiles not declared in spec** — Concrete tiles (`public-start-adam`, `public-start-eve`) exist only in test fixtures | **Resolved**: This spec formally declares the habitat identifier, allowed tiles, starting tile assignments, observation boundaries, and movement prohibition as canonical ground truth. Test fixtures must align with this spec; the spec is the source of truth. |

No other 10IF audit findings are closed by this document. Specifically:

- Provenance commitment construction remains unresolved (10IF issue #1).
- Rollback `state_commitment` source envelope remains unresolved (10IF issue #2).
- Write allow-list enumeration is addressed by 10II, not this spec.
- `world-sim/data` write authorization remains ungranted.
- Truncation/collision budget for `agent_id` remains unreviewed (10IK).
- GPT-5.6 Sol/Luna invocation and explicit Sean approval remain required
  for any implementation phase.

---

## M. Forbidden Actions (Per 10IF §6)

Under this spec and all First Pair preflight specs, the following are
forbidden and must fail closed:

- Creating Adam or Eve runtime entities.
- Opening Gate-7 (no network egress/ingress, no daemon, no scheduler, no
  provider, no container, no Docker).
- Writing to `world-sim/data`.
- Implementing, altering, or recurring into 10HD (10HD remains
  named-only and untouched; recursion spine is separate).
- Granting write authority to Adam, Eve, or any new writer (10CP remains
  the sole writer).
- Model/provider autonomy (no model may choose actions, writes, or ticks).
- Runtime self-scheduling (no self-initiated ticks).
- Any write without an explicit per-call allow-list and provenance chain.

---

## N. Non-Authority Statements (Per All Six Specs)

- This spec authorizes **nothing beyond declaring the starting habitat
  tiles**.
- Creation remains unauthorized. Any future creation phase requires:
  - A separate implementation phase with TDD.
  - GPT-5.6 Sol/Luna per AGENTS.md Rule 3.
  - Explicit Sean approval.
- 10HD remains named-only and untouched.
- 10CP remains the sole writer.
- Write authorization is not write execution.
- Gate-7 remains closed.
- No backend, tests, runtime, daemon, scheduler, network, provider,
  model, frontend, container, Docker, or `world-sim/data` changes are
  performed by this document.

---

## O. Phase Index

This phase receives a single `phase_index.md` row marked **Done**, commit
only, hash recorded after push. No tests, no backend/runtime changes.

---