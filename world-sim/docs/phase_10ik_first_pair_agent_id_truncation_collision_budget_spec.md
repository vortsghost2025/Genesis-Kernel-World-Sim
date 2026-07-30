# Phase 10IK — First Pair Agent-ID Truncation and Collision Budget Spec

Numbered docs-only spec. This file closes the truncation and collision-budget
question deferred by the First Pair Identity Spec (Section 2), the corrected
10IG spec (Section 1, out of scope; Section 4.4), and the 10II spec (Section
A, "10IJ and 10IK have not started"). It is grounded in the actual behavior of
the pushed 10IC module (`backend/world/local_first_pair_birth_candidate.py`,
commit `2e1d189`).

This spec is **docs-only**: it implements no module, adds no tests, performs no
write, authorizes no persistence, creates no Adam/Eve runtime entity, does not
modify 10CP, does not open Gate-7, does not implement or alter 10HD, and does
not touch `world-sim/data`. 10CP remains the sole writer. Adam and Eve never
become writers.

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## A. Title and Status

- **Title**: Phase 10IK — First Pair Agent-ID Truncation and Collision Budget
  Specification.
- **Status**: Docs-only specification. Repository documentation reserves 10IK
  for the First Pair agent-ID truncation and collision-budget decision. The
  phase is started as docs-only under the preflight authorization recorded in
  10IF.
- **Phase number**: 10IK. No new phase number is assigned by this document.
  10IJ remains the protected starting-habitat-tiles draft and is not modified
  or closed by this spec.
- **Boundary preservation**: Gate-7 remains closed. 10HD remains named-only
  and untouched. 10CP remains the sole writer. `world-sim/data` remains
  forbidden.

---

## B. Decision: Preserve the Full 256-Bit Agent-ID Digest

10IK decides that the canonical First Pair `agent_id` format remains:

```text
genesis-agent-<full 64-character SHA-256 hex digest>
```

No truncation is introduced. The full 64-character lowercase hexadecimal
SHA-256 digest is the current and canonical agent-ID format.

### B.1 Current Behavior (Verified from 10IC)

The pushed 10IC module derives `agent_id` as follows (verified at commit
`2e1d189`, `local_first_pair_birth_candidate.py`):

- `_hash_canonical(material)` returns
  `hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()`
  — the full 64-character lowercase hexadecimal SHA-256 digest.
- `agent_id = "genesis-agent-" + _hash_canonical(material)` — the prefix
  concatenated with the full digest. No `[:32]` slice, no truncation, no
  shortening.
- `_ID_DERIVATION_VERSION = "sha256-full-v1"` explicitly names this as the
  full-hash derivation version.
- The 10IC test suite (`tests/test_phase10ic_first_pair_birth_candidate.py`)
  uses `"a" * 64` and `"b" * 64` as provenance_commitment fixtures and
  verifies identity derivation against this full-digest format.

### B.2 Rationale for Preserving the Full Digest

The full 256-bit SHA-256 digest provides:

- **Collision resistance** — SHA-256 has a 128-bit collision-resistance
  bound. The probability of two distinct canonical identity materials
  producing the same 64-character hex digest is astronomically low for a
  pair of two identities.
- **Deterministic re-derivation** — the full digest is reproducible from
  canonical material alone. No external state, no clock, no entropy, no
  truncation-induced ambiguity.
- **Simplicity and auditability** — a single full-hash form is easier to
  audit, test, and reason about than a truncated form with a separate
  collision-handling layer.
- **No compelling operational requirement for truncation** — no current or
  planned First Pair behavior requires a shorter identifier. The full digest
  is 64 characters plus a 14-character prefix (78 total), which is well
  within reasonable identifier-length limits for all current and planned
  surfaces.

### B.3 Conditions Required Before Truncation Could Ever Be Considered

Truncation of the `agent_id` digest is **not authorized** by this spec. Any
future proposal to truncate must satisfy **all** of the following before it
may be considered:

1. **Compelling operational requirement documented** — a specific,
   concrete operational need (e.g., storage constraints, display limits,
   indexing performance) must be documented with evidence. "Shorter is
   nicer" is not a compelling operational requirement.
2. **Truncation length specified exactly** — the proposed truncated length
   must be stated exactly (e.g., 32 characters, 16 characters), not as a
   range or an open variable.
3. **Collision budget specified exactly** — the acceptable collision
   probability for the truncated space must be stated exactly, with the
   mathematical derivation from the truncated bit-length and the expected
   number of identities.
4. **Collision-handling mechanism designed** — the deterministic behavior
   when two distinct identity materials produce the same truncated digest
   must be designed. Options include rejection (fail-closed), length
   extension, or domain-specific disambiguation. Silent replacement or
   aliasing is never permitted (see Section E).
5. **Separate explicit Sean approval** — truncation approval is a separate
   authorization decision from this spec. 10IK does not grant it. Any
   future truncation phase requires explicit Sean approval for the exact
   truncation length, collision budget, and collision-handling mechanism.
6. **Separate phase number** — any future truncation phase must receive its
   own phase number. 10IK does not assign it.
7. **GPT-5.6 Sol/Luna review** — any truncation implementation requires
   GPT-5.6 Sol/Luna per AGENTS.md Rule 3.

Until all seven conditions are satisfied, the full 64-character SHA-256
hex digest remains the sole canonical agent-ID format.

---

## C. Deterministic Identity Re-Derivation

The `agent_id` is derived from canonical identity material and may be
re-derived at any time from the same material. Re-derivation must produce
exact equality with the originally derived `agent_id`.

### C.1 Canonical Material (per 10IG §4.1)

The canonical material dict contains exactly eight string-keyed fields:

| Field | Source |
|---|---|
| `domain_separator` | 10IC constant `"GENESIS_FIRST_PAIR_IDENTITY_V1"` |
| `identity_schema_version` | 10IC constant `"first_pair_identity.1"` |
| `id_derivation_version` | 10IC constant `"sha256-full-v1"` |
| `canonical_name` | identity input (`"Adam"` or `"Eve"`) |
| `canonical_agent_ref` | identity input (`"east_adam"` or `"east_eve"`) |
| `pair_id` | 10IC constant `"genesis-first-pair"` |
| `founding_role` | 10IC constant `"founding_agent"` |
| `provenance_commitment` | identity input (64-char lowercase hex per 10IG §3) |

### C.2 Canonical Serialization (per 10IG §4.2)

```python
json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

UTF-8 encoded before hashing.

### C.3 Hash Algorithm (per 10IG §4.3)

`hashlib.sha256` — full 64-character lowercase hexadecimal hexdigest. No
truncation.

### C.4 Re-Derivation Rule

At any time, identity verification re-derives `agent_id` from the presented
canonical material using the algorithm in C.1–C.3 and requires exact string
equality with the presented `agent_id`. Any mismatch fails closed as identity
drift (per 10IG §5.3 and First Pair Identity Spec Section 6).

---

## D. Duplicate Identity Handling

### D.1 Intra-Pair Duplicate Detection

The First Pair consists of exactly two identities: Adam and Eve. The 10IC
birth-candidate constructor enforces that Adam and Eve have distinct
canonical identity material (`canonical_name` and `canonical_agent_ref` differ
between the two), so their `agent_id`s are derived from different material.

- Adam's material: `canonical_name="Adam"`, `canonical_agent_ref="east_adam"`,
  `provenance_commitment=<Adam's commitment>`.
- Eve's material: `canonical_name="Eve"`, `canonical_agent_ref="east_eve"`,
  `provenance_commitment=<Eve's commitment>`.

If Adam and Eve were supplied with identical provenance_commitment values,
their agent_ids would still differ because `canonical_name` and
`canonical_agent_ref` differ. The 10IC test fixtures use different
placeholder commitments (`"a" * 64` for Adam, `"b" * 64` for Eve), but the
derivation does not depend on commitments being distinct.

### D.2 Deterministic Duplicate Handling

If two distinct canonical identity materials were ever to produce the same
full 64-character SHA-256 hex digest (an astronomically improbable SHA-256
collision), the behavior must be:

1. **Detect** — compare the two full `agent_id` strings for exact equality.
2. **Fail closed** — do not proceed with creation under a colliding
   identity pair. Emit an explicit collision error.
3. **Report honestly** — the collision is reported as an impossible-but-
   detected event. No silent replacement, no aliasing, no fallback.
4. **Require operator decision** — the collision is escalated for explicit
   Sean review before any further work. 10CP does not write, and Gate-7
   does not open, to resolve a collision.

### D.3 No Duplicate Tolerance

The First Pair does not tolerate duplicate `agent_id`s. Two identities with
the same `agent_id` is an invalid state, not a valid degenerate pair. This
holds for the full-digest form and would hold for any future truncated form
(see Section B.3).

---

## E. Collision Detection and Fail-Closed Behavior

### E.1 Collision Definition

A collision occurs when two distinct canonical identity materials produce
the same `agent_id` string. "Distinct" means the materials differ in at
least one of the eight canonical fields (Section C.1).

### E.2 Fail-Closed Behavior

On collision detection:

- **Identity validation fails** — both colliding identities are marked
  invalid. Neither is accepted.
- **No partial acceptance** — the pair is rejected as a whole if either
  identity collides with the other.
- **No silent replacement** — the colliding identity is not silently
  replaced with the other, with a derived alternative, or with a fallback
  identifier.
- **No fallback identifier generation** — no secondary, tertiary, or
  fallback `agent_id` is generated. The full SHA-256 digest is the only
  derivation path. If it collides, creation is blocked, not worked around.
- **Error vocabulary** — the existing 10IC fail-closed errors
  (`invalid_birth_candidate`, `candidate_declaration_drift`) surface the
  collision. 10IK does not add a new collision-specific error string to
  the runtime vocabulary without a separate implementation phase.
- **Escalation** — the collision is reported for operator review. No
  automatic resolution exists.

### E.3 Detection Scope

Collision detection applies to:

- **Intra-pair**: Adam vs. Eve within the First Pair.
- **Future expansion**: if any future phase introduces additional
  identities, collision detection must extend to the new set. 10IK does
  not authorize future expansion.

---

## F. Cross-Agent Collision Handling

### F.1 Adam and Eve Are Distinct

Adam and Eve have distinct canonical identity material (Section D.1). Their
`agent_id`s are derived by the same algorithm from different material, so
they produce different `agent_id`s under the full SHA-256 digest.

### F.2 No Cross-Agent Aliasing

- Adam's `agent_id` may never be used as Eve's, and vice versa.
- An identity claim that presents Adam's `agent_id` with Eve's canonical
  material (or vice versa) fails closed as identity drift (per 10IG §5.3,
  pair mismatch).
- No agent may assume another agent's `agent_id`. Identity is established
  by canonical material plus operator provenance, never by another agent's
  assertion (per First Pair Identity Spec Section 7).

### F.3 Pair Independence Under Collision

If an impossible-but-detected collision were to occur between Adam and
Eve:

- Both identities fail closed (Section E.2).
- Neither identity is quarantined while the other proceeds. The pair is
  rejected as a whole.
- Identity independence (First Pair Identity Spec Section 1) is preserved
  in the sense that neither identity is mutated by the other's collision;
  both simply fail validation and return to the last known good.

---

## G. Domain Separation

### G.1 First Pair Domain Separator

The canonical identity material includes a domain separator:
`"GENESIS_FIRST_PAIR_IDENTITY_V1"`. This namespaces the First Pair identity
derivation from any other identity scheme in the project.

### G.2 No Cross-Domain Substitution

- A `provenance_commitment` or `agent_id` from any other domain may not be
  substituted into the First Pair derivation. The domain separator must
  match exactly.
- The `provenance_commitment` and rollback `state_commitment` are separate
  trust domains. They may share a generic canonical-serialization utility
  only if later authorized, but they must retain separate domain
  separators, source-envelope schemas, semantic purposes, commitment
  hashes, verification procedures, operator-approval bindings, and replay
  and consumption rules. Cross-domain substitution must fail closed.
- The `agent_id` derivation consumes `provenance_commitment` (identity
  provenance), not `state_commitment` (rollback provenance). These are not
  interchangeable.

### G.3 Derivation Version Pinning

`id_derivation_version = "sha256-full-v1"` pins the current derivation to
the full SHA-256 digest. Any future change to the derivation (truncation,
algorithm change, material change) must:
- assign a new `id_derivation_version` value,
- re-derive all existing `agent_id`s under the new derivation,
- require explicit Sean approval,
- require GPT-5.6 Sol/Luna per AGENTS.md Rule 3.

10IK does not authorize a derivation version change. The current version
remains `"sha256-full-v1"`.

---

## H. No Silent Replacement or Aliasing

### H.1 No Silent Replacement

- A `agent_id` that collides with another is never silently replaced with
  a non-colliding alternative.
- No secondary derivation, no suffix increment, no fallback path exists.
- The full SHA-256 digest is the sole derivation path.

### H.2 No Aliasing

- Two identities with the same `agent_id` are never aliased together.
- An `agent_id` is a 1:1 binding to canonical identity material. A many-to-
  one or one-to-many aliasing is an invalid state and fails closed.
- Cross-agent references (e.g., Eve referencing Adam's observation) use
  the referenced agent's `agent_id`. No aliasing occurs.

---

## I. Requirements for Future Tests

Any future implementation phase that introduces truncation (after satisfying
all seven conditions in Section B.3) must provide tests covering:

1. **Truncation length compliance** — the truncated digest is exactly the
   specified length.
2. **Collision budget adherence** — the collision probability for the
   truncated space does not exceed the specified budget.
3. **Collision-handling correctness** — the designed collision-handling
   mechanism (rejection, extension, disambiguation) is exercised and
   deterministic.
4. **No silent replacement** — colliding identities are never silently
   replaced or aliased.
5. **No fallback generation** — no secondary or fallback `agent_id` is
   produced.
6. **Re-derivation stability** — truncated `agent_id` re-derivation from
   identical canonical material produces exact equality.
7. **Cross-agent distinctness** — Adam and Eve truncated `agent_id`s are
   distinct when canonical material differs.
8. **Drift detection** — identity drift with truncated `agent_id` fails
   closed exactly as with full digest.
9. **Domain separation** — truncated `agent_id` derivation rejects
   cross-domain `provenance_commitment` values.
10. **Derivation version handling** — new `id_derivation_version` triggers
    re-derivation and requires explicit approval.
11. **Bounded regression** — all existing 10IC, 10ID, 10IE, 10IG, 10IH, 10II
    tests continue to pass.

Until truncation is authorized (which it is not by this spec), these tests
are not required. The current test suite for 10IC (75 targeted + 107 bounded
regression) validates the full-digest behavior.

---

## J. Non-Authority Statements

- This spec authorizes **nothing beyond documenting the truncation and
  collision-budget decision already implemented by 10IC**.
- It does **not** authorize creating Adam or Eve.
- It does **not** modify 10IC, 10ID, 10IE, 10IF, 10IG, 10IH, or 10II.
- It does **not** implement a new boundary module.
- It does **not** open Gate-7, start a daemon, add a scheduler, open a
  network connection, call a provider, or touch `world-sim/data`.
- It does **not** specify the `provenance_commitment` source envelope
  (unresolved per 10IG §8).
- It does **not** specify the rollback `state_commitment` source envelope
  (unresolved per 10IH §12).
- It does **not** enumerate the per-call write allow-list (specified by 10II).
- It does **not** declare starting habitat tiles (protected 10IJ draft).
- It does **not** grant `world-sim/data` write authorization (not granted).
- It does **not** invoke GPT-5.6 Sol/Luna (creation unauthorized).
- It does **not** grant explicit Sean approval for creation (not granted).

---

## K. Forbidden Actions (Per 10IF §6)

Under this spec and all First Pair preflight specs, the following are
forbidden and must fail closed:

- Creating Adam or Eve runtime entities.
- Opening Gate-7 (no network egress/ingress, no daemon, no scheduler, no
  provider, no container, no Docker).
- Writing to `world-sim/data`.
- Implementing, altering, or recurring into 10HD (10HD remains named-only
  and untouched; recursion spine is separate).
- Granting write authority to Adam, Eve, or any new writer (10CP remains
  the sole writer).
- Model/provider autonomy (no model may choose actions, writes, or ticks).
- Runtime self-scheduling (no self-initiated ticks).
- Any write without an explicit per-call allow-list and provenance chain.
- Silent replacement or aliasing of colliding `agent_id`s.
- Fallback identifier generation for `agent_id`.

---

## L. Phase Index

This phase receives a single `phase_index.md` row marked **Done**, commit
only, hash recorded after push. No tests, no backend/runtime changes.

---

## M. 10IK SHA-256

This document's SHA-256 (LF-only):

`TODO: Compute after commit and record in phase_index.md`