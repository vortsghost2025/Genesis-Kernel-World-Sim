# Phase 10IG — First Pair Provenance Commitment Construction Spec

Numbered docs-only authorization spec. This file closes the first unresolved
preflight gap identified by the 10IF audit: the `provenance_commitment`
construction (hash algorithm, input material, encoding, verification path)
that the Identity spec §3 explicitly deferred to "an implementation spec
with explicit review."

This spec documents the construction **already in use** by the implemented
10IC birth-candidate module. It does not invent a new algorithm, does not
modify 10IC, does not authorize creation, and does not open Gate-7.

**FIRST_PAIR_CREATION_AUTHORIZED = False** (unchanged by this document).

This document records provenance commitment construction only. It does not
authorize Adam/Eve creation, implementation of new boundary modules,
runtime activation, or world-state writes. Gate-7 remains closed. 10HD
remains named-only and untouched. 10CP remains the sole writer.

---

## 1. Scope and Out-of-Scope

### In scope

- The exact construction of the immutable `provenance_commitment` field
  carried by every First Pair identity.
- The exact derivation algorithm for `agent_id` from canonical identity
  material, including the role of `provenance_commitment` in that
  derivation.
- The verification path: how a presented `provenance_commitment` and
  presented `agent_id` are checked against canonical material.

### Out of scope (separate Lane A specs)

- **Truncation and collision budget for `agent_id`** — deferred to 10IK.
  This spec documents the **full-hash** `agent_id` form already produced by
  10IC (no truncation). Any truncation review is a separate explicit spec.
- **Rollback anchor format** — deferred to 10IH. The
  `rollback_anchor.state_commitment` field reuses the hex64 shape defined
  here, but the anchor envelope is a separate spec.
- **Per-call write allow-list** — deferred to 10II.
- **Starting habitat tiles declaration** — deferred to 10IJ.

---

## 2. Grounding: 10IC Implementation Behavior

This spec is grounded in the actual behavior of the pushed 10IC module
`backend/world/local_first_pair_birth_candidate.py` (commit `2e1d189`).
The construction below is a **normative description of what 10IC already
does**, not a new algorithm. Discrepancies between this spec and 10IC are
resolved by re-reading the 10IC source; this spec does not modify 10IC.

10IC constants used by the construction:

- `_IDENTITY_SCHEMA_VERSION = "first_pair_identity.1"`
- `_ID_DERIVATION_VERSION = "sha256-full-v1"`
- `_IDENTITY_DOMAIN_SEPARATOR = "GENESIS_FIRST_PAIR_IDENTITY_V1"`
- `_PAIR_ID = "genesis-first-pair"`

---

## 3. Provenance Commitment Construction

### 3.1 Shape

The `provenance_commitment` is a **64-character lowercase hexadecimal
string** — the sha256 hexdigest of operator-approved creation provenance
material.

- Type: `str` (exact; subclasses rejected by 10IC's `type(value) is not str`
  guards).
- Length: exactly 64 characters.
- Alphabet: `0123456789abcdef` (lowercase only; uppercase hex is rejected).
- Role: an immutable, operator-approved commitment to creation provenance.
  This is **not** a raw secret seed; nothing in this spec or in 10IC
  requires raw secret material to be held at runtime.

### 3.2 Operator Approval of the Commitment Value

The `provenance_commitment` value itself is **operator-approved** before
pair definition. The operator selects the commitment value (a 64-char
lowercase hex string) and supplies it as part of the canonical identity
material at pair definition time.

This spec does **not** define how the operator chooses or stores the
commitment value — only that it must be a 64-char lowercase hex string
when presented at runtime. Selection and secure storage of the commitment
value outside the runtime lane is an operator responsibility, not a
Genesis module responsibility.

### 3.3 Immutability After Definition

Per Identity spec §3, `provenance_commitment` is immutable across cycles
and restarts. Any proposed mutation is rejected fail-closed by 10IC, and
identity is re-derived from the unchanged canonical material on every
restart. There is no field-rename, no commitment rotation, and no
re-derivation under a different commitment value.

---

## 4. agent_id Derivation Algorithm

### 4.1 Canonical Material

The `agent_id` is derived from an **exact, ordered** canonical material
dict containing these eight fields and no others:

| Field | Source | Value |
|---|---|---|
| `domain_separator` | 10IC constant | `"GENESIS_FIRST_PAIR_IDENTITY_V1"` |
| `identity_schema_version` | 10IC constant | `"first_pair_identity.1"` |
| `id_derivation_version` | 10IC constant | `"sha256-full-v1"` |
| `canonical_name` | identity input | `"Adam"` or `"Eve"` |
| `canonical_agent_ref` | identity input | `"east_adam"` or `"east_eve"` |
| `pair_id` | 10IC constant | `"genesis-first-pair"` |
| `founding_role` | 10IC constant | `"founding_agent"` (unified; see §7) |
| `provenance_commitment` | identity input | 64-char lowercase hex per §3 |

### 4.2 Canonical Serialization

Canonical serialization is **deterministic JSON**:

```
json.dumps(
    material,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
```

- `sort_keys=True` — field order is canonical, not insertion order.
- `separators=(",", ":")` — compact, no insignificant whitespace.
- `ensure_ascii=False` — UTF-8 preserved; non-ASCII canonical names (if
  any future pair ever uses them) are not escaped.
- The serialized string is then UTF-8 encoded before hashing.

### 4.3 Hash Algorithm

- Algorithm: `hashlib.sha256` (SHA-2 family, 256-bit output).
- Output encoding: lowercase hexdigest (64 chars).
- The derivation is **pure and deterministic** — no clock, no entropy, no
  environment input, no model output, no file read, no network, no
  `world-sim/data` access.

### 4.4 agent_id Format

The `agent_id` is the string:

```
"genesis-agent-" + sha256_hexdigest(canonical_material)
```

- **No truncation.** The full 64-character sha256 hexdigest is used. 10IC
  line 314: `"genesis-agent-" + _hash_canonical(material)` — no `[:32]`
  slice.
- The full-hash form is the canonical form for this spec. Any truncation
  review (32-char or otherwise) is deferred to 10IK and is not authorized
  by this document.
- Prefix `"genesis-agent-"` is fixed; it namespaces First Pair agents from
  any other identity scheme in the project.

### 4.5 Determinism and Pair Symmetry

- Both Adam and Eve `agent_id`s are derived by the **same algorithm**.
  Only the canonical identity material differs (`canonical_name`,
  `canonical_agent_ref`, and the per-identity `provenance_commitment`
  value).
- Adam and Eve are not granted different identity tiers; they differ only
  in identity material.
- Re-derivation from the same canonical material always produces the same
  `agent_id`. There is no per-tick variation, no per-restart variation, no
  per-process variation.

---

## 5. Verification Path

### 5.1 Re-Derivation, Not Recall

After any restart, identity is verified by **re-derivation**, not by
recalling a stored `agent_id`. Re-derivation either matches the canonical
`agent_id` exactly or the recovery fails closed.

### 5.2 Verification Procedure

To verify a presented First Pair identity:

1. Confirm the presented `provenance_commitment` is a 64-char lowercase
   hex string (§3.1). Reject fail-closed if not.
2. Confirm the presented `canonical_name`, `canonical_agent_ref`, `pair_id`,
   and `founding_role` match their canonical values (§4.1). Reject
   fail-closed on any mismatch.
3. Re-derive `agent_id` from the canonical material (§4.2–§4.4).
4. Confirm the presented `agent_id` equals the re-derived value by exact
   string equality. Reject fail-closed on any mismatch.
5. Confirm no extra identity material is present. The canonical material
   set is exactly the eight fields in §4.1; any extension is drift.

### 5.3 Drift Cases Rejected Fail-Closed

Per Identity spec §6, these drift cases are rejected immediately and
absolutely:

- Immutable field mismatch — any §4.1 field on a presented identity differs
  from its canonical value.
- `agent_id` mismatch — the presented `agent_id` does not equal the
  re-derivation from the declared canonical material.
- Pair mismatch — a presented identity carries a `pair_id` that differs
  from `"genesis-first-pair"`, or Adam and Eve fields are cross-swapped.
- Extra identity material — a presented identity carries fields beyond the
  §4.1 set.
- Missing material — any §4.1 field absent at load time; no defaulting,
  no inference.

Rejection is **immediate and absolute**: no partial identity is accepted,
no degraded identity is accepted, no "best-effort" identity is accepted.
The failing lane returns to the last known good and does not act under a
drifted identity.

---

## 6. Provenance Chain and claim_scope

Per Identity spec §7, every claim "this is Adam" or "this is Eve" must
carry provenance back to the operator-approved `provenance_commitment`.

- The provenance chain is recorded with `claim_scope = "identity"` and may
  not be relabeled as `observed`, `world_event`, `agent_speech`, or
  `hypothesis`.
- Verification uses the commitment, not any raw secret material.
- An identity claim without provenance is rejected as drift (§5.3).
- Cross-agent identity claims (Adam claiming something about Eve's
  identity, or vice versa) are treated as **speech**, not as identity
  authority. Identity is established by canonical material plus operator
  provenance, never by another agent's assertion.

---

## 7. Founding Role Unification (Documented Deviation)

The Identity spec §3 uses example `founding_role: "first_observer" /
"first_echo"`. The 10IC implementation uses a single fixed
`"founding_agent"` for both identities. This is an intentional
unification, documented as a deviation in the 10IF audit (Section 3,
"Founding role divergence") and not a blocker.

This spec retains the 10IC unification: `founding_role = "founding_agent"`
for both Adam and Eve. Divergent role names are not required by any
implemented boundary and are not authorized by this document. Any future
spec that introduces per-identity role diversity must do so explicitly
and must re-derive `agent_id` under the new material without breaking
existing 10IC/10ID/10IE test fixtures.

---

## 8. Non-Authority Statements

- This spec authorizes **nothing beyond documenting the provenance
  commitment construction**.
- It does **not** authorize creating Adam or Eve.
- It does **not** modify 10IC, 10ID, 10IE, or any prior phase.
- It does **not** implement a new boundary module.
- It does **not** open Gate-7, start a daemon, add a scheduler, open a
  network connection, call a provider, or touch `world-sim/data`.
- It does **not** review truncation/collision budget (deferred to 10IK).
- It does **not** specify the rollback anchor envelope (deferred to 10IH).
- It does **not** enumerate the per-call write allow-list (deferred to 10II).
- It does **not** declare starting habitat tiles (deferred to 10IJ).

---

## 9. Authorization Gate Conclusion

| Condition | Status |
|---|---|
| `provenance_commitment` shape documented (64-char lowercase hex) | ✅ Yes — by this spec |
| `agent_id` derivation algorithm documented (sha256, canonical JSON, domain separator, full hash) | ✅ Yes — by this spec |
| Verification path documented (re-derive, exact-equality, fail-closed drift) | ✅ Yes — by this spec |
| Truncation/collision budget reviewed | ❌ No — deferred to 10IK |
| Rollback anchor format specified | ❌ No — deferred to 10IH |
| Write allow-list enumerated | ❌ No — deferred to 10II |
| Starting habitat tiles declared | ❌ No — deferred to 10IJ |
| `world-sim/data` write authorized | ❌ No — not granted |
| GPT-5.6 Sol/Luna invoked for creation implementation | ❌ No — creation unauthorized |
| Explicit Sean approval for creation phase | ❌ No — not granted |

**FIRST_PAIR_CREATION_AUTHORIZED = False**

This document closes the "Provenance commitment construction deferred"
audit finding from 10IF Section 3. It does not close any other audit
finding. The remaining unresolved creation prerequisites identified by
10IF remain open and require separate review and explicit authorization.

---

## 10. Forbidden Actions (Repeated for Emphasis)

Under this spec and all six preflight specs, the following are forbidden
and must fail closed:

- Creating Adam or Eve runtime entities
- Opening Gate-7 (no network egress/ingress, no daemon, no scheduler, no
  provider, no container, no Docker)
- Writing to `world-sim/data`
- Implementing, altering, or recurring into 10HD (10HD remains named-only
  and untouched; the recursion spine is separate)
- Granting write authority to Adam, Eve, or any new writer (10CP remains
  the sole writer)
- Model/provider autonomy (no model may choose actions, writes, or ticks)
- Runtime self-scheduling (no self-initiated ticks)
- Any write without an explicit per-call allow-list and provenance chain
- Modifying the 10IC implementation to add truncation without an explicit
  10IK review

---

## 11. Phase Index

This phase receives a single `phase_index.md` row marked **Done**,
commit-only, hash recorded after push. No tests, no backend/runtime
changes.
