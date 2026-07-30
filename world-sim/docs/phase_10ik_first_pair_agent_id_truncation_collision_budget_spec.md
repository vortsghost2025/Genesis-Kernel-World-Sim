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

### D.1 Intra-Pair Derivation, Not Detection

The First Pair consists of exactly two identities: Adam and Eve. The 10IC
birth-candidate constructor derives Adam's and Eve's `agent_id`s from
distinct canonical identity material (`canonical_name` and
`canonical_agent_ref` differ between the two), so their `agent_id`s are
derived from different material:

- Adam's material: `canonical_name="Adam"`, `canonical_agent_ref="east_adam"`,
  `provenance_commitment=<Adam's commitment>`.
- Eve's material: `canonical_name="Eve"`, `canonical_agent_ref="east_eve"`,
  `provenance_commitment=<Eve's commitment>`.

If Adam and Eve were supplied with identical `provenance_commitment` values,
their `agent_id`s would still differ because `canonical_name` and
`canonical_agent_ref` differ. The 10IC test fixtures use different
placeholder commitments (`"a" * 64` for Adam, `"b" * 64` for Eve), but the
derivation does not depend on commitments being distinct.

### D.2 Actual Implementation Boundary (no 10IC equality check)

The 10IC module (`local_first_pair_birth_candidate.py`, `create_first_pair_birth_candidate`)
does **not** compare Adam's and Eve's `agent_id` strings for equality. A
full-hash collision between Adam and Eve is therefore **not surfaced** by
the existing 10IC fail-closed errors `invalid_birth_candidate` or
`candidate_declaration_drift`; both identities are returned as valid, and
`create_first_pair_birth_candidate()` returns `ok=True` even if Adam's and
Eve's full 64-character digests were identical.

The **first existing duplicate-ID check** is in the 10ID module
(`local_first_pair_habitat_boundary.py`, `create_first_pair_habitat_boundary`):
at `local_first_pair_habitat_boundary.py:161-162` it compares
`adam_ref["agent_id"] == eve_ref["agent_id"]` and, on equality, appends
`duplicate_identity` to the errors list. This check runs against the
already-derived `agent_id` produced by 10IC; it does not re-derive and
does not introduce a new derivation path.

### D.3 Required Future Collision Handling (specification, not implementation)

If identity-layer collision rejection is desired **inside 10IC** (so that
`create_first_pair_birth_candidate()` itself fails closed on a colliding
pair without depending on the downstream 10ID check), it remains an
**unresolved future implementation requirement** and is **not** authorized
or implemented by this docs-only spec. Any such change requires:

- a separate numbered implementation phase,
- GPT-5.6 Sol/Luna per AGENTS.md Rule 3,
- explicit Sean approval,
- TDD tests covering the collision case inside 10IC,
- and backward-compatible handling so the existing 10ID `duplicate_identity`
  check is not duplicated or weakened.

This spec records that requirement; it does not satisfy it.

### D.4 No Duplicate Tolerance (specification)

The First Pair does not tolerate duplicate `agent_id`s. Two identities with
the same `agent_id` is an invalid state, not a valid degenerate pair. This
holds for the full-digest form and would hold for any future truncated form
(see Section B.3). The current implementation enforces this at the 10ID
boundary (D.2); a future 10IC-side enforcement is recorded in D.3 but not
implemented here.

---

## E. Collision Detection and Fail-Closed Behavior

### E.1 Collision Definition

A collision occurs when two distinct canonical identity materials produce
the same `agent_id` string. "Distinct" means the materials differ in at
least one of the eight canonical fields (Section C.1).

### E.2 Fail-Closed Behavior (specification, not 10IC behavior)

The behavior below is the **specification** for how the First Pair lane
must fail closed if and when identity-layer collision detection is ever
implemented inside 10IC (see Section D.3). It is **not** a description of
the current 10IC runtime, which does not detect an Adam-vs-Eve collision
(see Section D.2 for the actual current boundary):

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
- **Error vocabulary** — a future 10IC-side detection must surface the
  collision via the existing 10IC fail-closed errors
  (`invalid_birth_candidate`, `candidate_declaration_drift`) or via a new
  collision-specific error string added through a separate implementation
  phase. 10IK does not add a new error string to the runtime vocabulary.
- **Escalation** — the collision is reported for operator review. No
  automatic resolution exists.

### E.3 Detection Scope

Collision detection applies to:

- **Intra-pair**: Adam vs. Eve within the First Pair. (Currently detected
  at the 10ID boundary as `duplicate_identity` per Section D.2; a 10IC-side
  detection remains unresolved per Section D.3.)
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
derivation from any other identity scheme in the project. The current
enforceable domain separation is limited to this internally injected
constant: in the 10IC `_derive_identity()` function (verified at
`local_first_pair_birth_candidate.py`), the `domain_separator` field is
**not** a member of `_IDENTITY_INPUT_FIELDS` and is **not** a caller-
supplied field. The function rejects any identity input that adds
`domain_separator` as an extra key (`_has_exact_string_keys` against
`_IDENTITY_INPUT_FIELDS`), and it constructs the canonical hashing
material itself by emitting `"domain_separator":
_IDENTITY_DOMAIN_SEPARATOR = "GENESIS_FIRST_PAIR_IDENTITY_V1"` into
the canonical dict (line 298 in `create_first_pair_birth_candidate`).
Consequently no caller can present or substitute a different domain
separator, but neither can a caller *assert* a domain claim — the
domain is fixed by the implementation. No other domain claim is
validated.

### G.2 Provenance Domain — Current Limited Enforcement

The `provenance_commitment` field currently receives **hex64 shape
validation only** in 10IC (`_is_hex64()` at
`local_first_pair_birth_candidate.py:211-214`: 64-char lowercase hex
string). 10IC's `_derive_identity()` consumes the field into the canonical
hash material (C.1, C.2) but does not verify the commitment's source
envelope or source-domain metadata.

Consequences, stated exactly as the implementation behaves:

- The 10IC identity derivation cannot currently determine the source
  domain of a presented `provenance_commitment`. It validates only that
  the string is a 64-character lowercase hex string.
- A valid hex64 `provenance_commitment` produced by another source domain
  (e.g., a non-First-Pair provenance envelope, or any external source
  emitting a 64-char lowercase hex digest) **cannot presently be detected
  or rejected** by the 10IC identity layer, because no source-envelope
  metadata is captured and no source-domain comparison is performed.
- Provenance-domain rejection — i.e., refusing a `provenance_commitment`
  whose source envelope belongs to a different trust domain than the
  First Pair — is **deferred** until the `provenance_commitment` source
  envelope is specified (unresolved per 10IG §8), implemented, and
  verified. This spec does not close that gap and does not claim
  cross-domain rejection is currently enforced.

Cross-domain `provenance_commitment` substitution must fail closed **once
the source envelope is specified and verified**, but not before. This spec
authorizes no such implementation.

### G.3 Separate Trust Domains (unchanged constraint)

The `provenance_commitment` (identity provenance) and rollback
`state_commitment` (rollback provenance) are **separate trust domains**.
They may share a generic canonical-serialization utility only if later
authorized, but they must retain separate domain separators,
source-envelope schemas, semantic purposes, commitment hashes,
verification procedures, operator-approval bindings, and replay and
consumption rules. The `agent_id` derivation consumes
`provenance_commitment` (identity provenance), not `state_commitment`
(rollback provenance). These are not interchangeable. Cross-domain
substitution between them must fail closed. This constraint is
unconditional; it is not contingent on the deferred source-envelope
specification in G.2.

### G.4 Derivation Version Pinning

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
  collision-budget decision already implemented by 10IC**, plus the
  deferred requirements recorded in Sections D.3 and G.2.
- It does **not** authorize creating Adam or Eve.
- It does **not** modify 10IC, 10ID, 10IE, 10IG, 10IH, or 10II.
- A stale truncation record inside the 10IF document (10IF §3 and §5,
  previously asserting 10IC used a 32-character truncation) is
  corrected by direct amendment to the 10IF document in the same
  forward-fix commit that amends this document. This is a documentation
  correction to 10IF, not a 10IF phase restart; the 10IF phase number,
  scope, status, and Commit cell are unchanged. The correction is
  necessary because 10IF's stale claim was mutually exclusive with
  10IK's full-digest decision. This 10IK spec records the necessity;
  the actual amendment is owned by the 10IF document.
- It does **not** implement a new boundary module.
- It does **not** implement identity-layer collision detection inside
  10IC. The 10IC-vs-Eve `agent_id` equality comparison remains
  unimplemented; the existing duplicate check at the 10ID boundary
  (`local_first_pair_habitat_boundary.py:161-162`, returning
  `duplicate_identity`) is the current duplicate-ID enforcement
  boundary. A 10IC-side check is recorded as an unresolved future
  implementation requirement (Section D.3), not implemented here.
- It does **not** enforce cross-domain rejection of a
  `provenance_commitment` produced by a non-First-Pair source envelope.
  10IC validates hex64 shape only and captures no source-envelope
  metadata; provenance-domain rejection is deferred (Section G.2) until
  the source envelope is specified and verified.
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

This phase receives a single `phase_index.md` row marked **Done**. The 10IK
row's Commit cell records the merge commit that placed the 10IK
specification on master (7-char lowercase hex); the row's Notes cell
records the document's LF-only SHA-256 (Section M).

**Synchronization flow** (post-push of this forward-fix merge to master):

1. **Commit A** (this spec + the 10IF amendment — `phase_index.md` is
   **excluded** per W4) is pushed and the forward-fix PR is merged to
   master. The merge commit SHA is the 10IK row's authoritative Commit
   cell value.

2. **Commit B** (phase-index hash-correction commit) does a direct,
   hand-edited replacement of the 10IK row's `PENDING` placeholder with
   the real 7-char merge SHA, and inserts this document's LF-only SHA-256
   (computed over the file's bytes as pushed by Commit A) into the 10IK
   row's Notes cell. Commit B stages only `phase_index.md`. **No
   destructive Git operations** (no reset, revert, rebase, squash,
   amend, stash, clean, force-push, or destructive deletion).

3. **Verification after Commit B**: `sync_phase_index_sha.ps1` is run
   as a **dry-run sanity check** (`-PhaseId 10IK -OldShortSha <the-new-SHA>
   -NewFullSha <the-new-SHA>`). Because OldShortSha already equals the
   initial 7 chars of NewFullSha on master, `sync_phase_index_sha.ps1`
   returns `APPLIED: false` (a no-op) on a clean aligned tree. This
   confirms the SHA is recorded in the row the script's regex accepts
   (7-char lowercase hex in backticks). The dry-run does **not** perform
   a byte-level apply; it reads the file in place and reports.

   The `PENDING` placeholder **cannot** be processed by
   `sync_phase_index_sha.ps1` (its apply-path regex requires an existing
   7-char lowercase-hex SHA in backticks, not a token). The authorized
   transition from `PENDING` to a real SHA is therefore the manual
   Commit B edit above, **followed** by the dry-run check. This spec
   does not claim `sync_phase_index_sha.ps1` bootstraps the `PENDING` →
   SHA transition; that transition is owned by the manual Commit B.

No tests, no backend/runtime changes.

---

## M. 10IK SHA-256

This document's LF-only SHA-256 is recorded in the `phase_index.md` 10IK
row's Notes cell during the post-push synchronization flow (Section L),
**not** embedded inside this document. Embedding a file's own SHA-256
inside the file would be self-referential and unverifiable; the design
keeps the digest in the separate-tracked `phase_index.md` so the 10IK
file's bytes are hashed solely by their content and the recorded digest
can be independently verified against the pushed file's bytes.

If the `phase_index.md` Notes cell is ambiguous, the authoritative
LF-only SHA-256 is the SHA-256 of the pushed file's bytes at the merge
commit on master (computed by the authorized synchronization flow after
Commit A is pushed).
