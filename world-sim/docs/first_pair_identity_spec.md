# First Pair Identity Spec — Adam/Eve Canonical Identities

Unnumbered docs-only spec. This file defines the identity contracts the
first Genesis pair **must** satisfy before creation. It does **not**
implement any entity, does **not** authorize creation, does **not** open
Gate-7, does **not** modify `world-sim/data`, and does **not** implement
10HD. Creation remains unauthorized; 10HD remains named-only; 10CP remains
the sole writer.

Reference: `world-sim/docs/roadmap_adam_eve_first_pair_preflight.md` lists
this spec as the first of six required future specs. Per `README.md`
founding-agents section, Adam and Eve are simulation entities with canonical
identities, continuity across cycles, and bounded perception — not religious
figures, not real-world authorities, not conscious beings.

## 1. Adam and Eve as Two Distinct Canonical Simulation Identities

There are exactly two first-pair identities: **Adam** and **Eve**.

- They are **pair members**, not interchangeable instances. Adam is not Eve;
  Eve is not Adam.
- They are a closed pair — no third canonical identity exists in this spec,
  and no third identity may be derived or implied from this document.
- Each identity is a **canonical simulation entity**, not a free agent, not
  an internet agent, not an autonomous runtime actor.
- **Independent identity, paired operations** — Adam and Eve remain
  independently valid canonical identities. Pair-scoped operations may
  require both identities, but the absence, failure, or quarantine of one
  must not erase, mutate, or invalidate the other. One identity going down
  never takes the other's identity with it.

## 2. Deterministic agent_id Derivation

Each identity gets a canonical `agent_id`.

- Derivation is **deterministic and pure** — a function of canonical
  identity material only, with no clock, no entropy, no environment input,
  and no model output.
- The canonical derivation inputs are: `identity_schema_version`,
  `id_derivation_version`, the canonical identity fields (§3) in a
  **canonical field ordering**, a **canonical UTF-8 serialization** of
  those fields, and a **Genesis First Pair domain separator** that
  namespaces this derivation from any other identity scheme in the project.
- Hashing is **deterministic** (a chosen member of the sha2 / sha3
  family), with a **documented output encoding**.
- The derivation does **not** read files, does **not** touch
  `world-sim/data`, does **not** call any provider or model, and does
  **not** require Gate-7.
- Both `agent_id`s are derived by the same algorithm. Only the canonical
  identity material differs. Adam and Eve are not granted different identity
  tiers; they differ only in identity material.
- **Truncation and collision budget deferred** — any truncation length and
  any collision budget must be **explicitly specified and reviewed** before
  implementation. This spec does **not** authorize an unspecified or
  unsafe truncation choice.

This spec **names** the derivation rule and its required canonical inputs.
It does **not** ship it; that requires an implementation phase with TDD
and explicit authorization.

## 3. Immutable Identity Fields

Identity fields are the canonical material from which `agent_id` is
derived. Once set at pair definition, they are **immutable across cycles
and restarts**:

- `canonical_name` — the stable canonical name ("Adam" / "Eve").
- `pair_id` — a stable identifier for the closed pair they belong to
  (the same value for both Adam and Eve).
- `founding_role` — the founding role within the pair
  (e.g. "first_observer" / "first_echo"), assigned at pair definition, not
  renegotiated later.
- `provenance_commitment` — an operator-approved immutable commitment to
  creation provenance. This is a **commitment** (a reviewed, approved
  anchor to the identity's creation provenance), not a raw secret seed.
  This spec does **not** require any raw secret seed material to exist in
  runtime memory, and does **not** claim that such raw material is held at
  runtime. The exact commitment construction (hash algorithm, input
  material, encoding, verification path) remains **deferred to an
  implementation spec** with explicit review.

Immutable means: any proposed mutation of these fields is rejected
fail-closed, and identity is re-derived from the unchanged canonical
material on every restart. There is no field-rename, no role-swap, and no
re-derivation under different input.

## 4. Mutable Self-State Fields Kept Separate From Identity

Mutable state exists, but it is **not** part of identity and **cannot**
influence `agent_id`.

- Mutable fields include: current public position, observed tile set,
  movement history, last heartbeat tick, public_state hash, snapshot id,
  route intent id — i.e. live read-model fields produced by existing
  verified public-state contracts (named here only as examples, not as
  normative dependencies; this identity spec does not depend on any
  particular public-phase module).
- Mutable fields live under a separate namespace (e.g. `self_state.*`) and
  are never mixed into canonical identity material.
- Re-deriving identity uses **only** §3 fields. Adding, removing, or
  mutating §4 fields must not change `agent_id`.
- This separation is what makes restart safe: live state can be reset to a
  known-good snapshot without invalidating identity.

## 5. Continuity Across Heartbeats and Restarts

- `agent_id` is stable across heartbeat ticks and across full restarts
  because it is a pure function of immutable material (§3).
- After any restart, identity is recovered by **re-derivation**, not by
  recalling a stored id. Re-derivation either matches the canonical
  `agent_id` exactly or the recovery fails closed.
- Pair membership is stable: Adam is still Adam and Eve is still Eve after
  any tick count, any restart, any rollback to a known-good state.
- Continuity does **not** mean memory persistence. Continuity is identity
  persistence. What the pair remembers is governed by the *First Memory
  Boundary Spec*, not by this identity spec.

## 6. Identity-Drift Detection and Fail-Closed Rejection

Identity drift is any condition in which a presented identity fails to
re-derive to its canonical `agent_id` from its declared immutable material.

Drift cases that must be rejected fail-closed:

- Immutable field mismatch — any §3 field on a presented identity differs
  from its canonical value at definition.
- `agent_id` mismatch — a presented `agent_id` does not equal the
  re-derivation from its declared §3 material.
- Pair mismatch — a presented identity carries a `pair_id` that differs
  from the canonical pair id, or Adam and Eve fields are cross-swapped.
- Extra identity material — a presented identity carries fields beyond the
  canonical §3 set and the loader refuses to derive from an extended
  material set.
- Missing material — any §3 field absent at load time; no defaulting, no
  inference.

Rejection is **immediate and absolute**: no partial identity is accepted,
no degraded identity is accepted, no "best-effort" identity is accepted.
The failing lane returns to the last known good and does not act under a
drifted identity.

## 7. Provenance Requirements for Every Identity Claim

Identity is not asserted; it is provenanced.

- Every claim "this is Adam" or "this is Eve" must carry provenance back to
  the operator-approved `provenance_commitment` (§3). Verification uses the
  commitment, not any raw secret material.
- The provenance chain is recorded with `claim_scope = identity` and may
  not be relabeled as `observed`, `world_event`, `agent_speech`, or
  `hypothesis`.
- An identity claim without provenance is rejected as drift (§6).
- Cross-agent identity claims (Adam claiming something about Eve's
  identity, or vice versa) are treated as **speech**, not as identity
  authority. Identity is established by canonical material plus operator
  provenance, never by another agent's assertion.

## 8. Pair Relationship Without Shared-Memory Collapse

Adam and Eve are distinct; the pair is not a merged identity and not a
shared mind.

- Adam and Eve have **separate `agent_id`s**, separate mutable self-state
  (§4), and separate provenance.
- The pair relationship is carried in the shared `pair_id` (§3) and in
  existing verified public-state merge contracts (referenced here only as
  examples), not in any shared mutable state. The identity spec itself
  does **not** depend on any particular merge / equality module; those are
  examples of where the pair relationship surfaces publicly, not
  prerequisites for the identity contract to hold.
- There is **no shared mutable identity store**. Identity is canonical and
  immutable per agent; any public merge lives only at the public-contract
  layer and never collapses the two identities into one.
- A statement like "Adam and Eve are co-located" or "Adam and Eve share a
  known tile" is a public-contract assertion (comparison of declared
  public surfaces), not an identity assertion and not a memory assertion.

## 9. Explicit Non-Authorities

This spec authorizes **nothing beyond defining identity contracts**. The
following are explicitly non-authoritative under this document:

- **No network** — no egress, no ingress, Gate-7 closed.
- **No provider/model autonomy** — no model may select actions on behalf of
  Adam or Eve.
- **No runtime self-scheduling** — neither identity may initiate its own
  tick.
- **No `world-sim/data` writes** — this spec writes nothing to disk; any
  future write requires a separate write-authority spec and explicit
  Sean authorization.
- **No Gate-7** — Gate-7 stays closed by absence under this spec.

## 10. Creation Remains Unauthorized

This spec **does not authorize creating Adam or Eve**. It defines the
contract that must hold before any creation phase. Creation requires:

- a separate implementation phase,
- a First Heartbeat Observation Spec,
- a First Habitat Boundary Spec,
- a First Memory Boundary Spec,
- a First Write-Authority Spec,
- a First Rollback / Kill-Switch Spec,
- GPT-5.6 Sol/Luna per AGENTS.md Rule 3, and
- explicit Sean approval.

None of those preconditions are met by the existence of this document.

## 11. 10HD Remains Named-Only and Untouched

10HD is the candidate named by 10HB (`e3042c7`) as a meta-meta-meta-verifier
over 10GX.1 meta-meta-verification output. This spec does **not**
implement, alter, supersede, or recur into 10HD. 10HD stays named-only and
untouched. The recursion spine is a separate branch of the chain from the
first-pair life branch.

## 12. 10CP Remains the Sole Writer

No new writer is introduced. 10CP remains the only module authorized to
write to the world ledger. Adam/Eve identity definitions, when eventually
implemented, are **not** writers; they are identities that may be consumed
by a **future authorized world-ledger boundary**. This spec does not
modify the 10CP boundary, does not name any specific ledger adapter as a
dependency, and does not grant write authority to anybody, including the
pair themselves.
