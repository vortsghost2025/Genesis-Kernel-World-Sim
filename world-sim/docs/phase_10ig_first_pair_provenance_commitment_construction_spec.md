# Phase 10IG — First Pair Provenance Commitment Validation and Agent-ID Binding Spec

Numbered docs-only spec. This file corrects the earlier 10IG document,
which conflated two distinct constructions and overclaimed closure of the
Identity spec §3 deferred gap. The earlier 10IG has been rewritten in
place under this same phase number; no new phase number is created.

The Identity spec §3 explicitly defers "the exact commitment construction
(hash algorithm, input material, encoding, verification path) remains
deferred to an implementation spec with explicit review." That full gap
is **not** closed by this document. What this document closes is the
narrower, evidence-grounded question of how the already-implemented 10IC
module validates a caller-supplied `provenance_commitment` and binds it
into the canonical `agent_id` derivation material.

This spec is grounded in the actual behavior of the pushed 10IC module
`backend/world/local_first_pair_birth_candidate.py` (commit `2e1d189`) and
its test suite `tests/test_phase10ic_first_pair_birth_candidate.py`. It
does not invent new fields, does not modify 10IC, does not authorize
creation, and does not open Gate-7.

**FIRST_PAIR_CREATION_AUTHORIZED = False** (unchanged by this document).

---

## 1. Scope and Out-of-Scope

### In scope (what this spec closes)

- The exact **accepted shape** of the `provenance_commitment` field as
  validated by 10IC.
- The exact **type and lowercase-hex validation** 10IC applies to a
  caller-supplied commitment value.
- The **inclusion** of `provenance_commitment` in the canonical identity
  material used to derive `agent_id`.
- The **canonical `agent_id` derivation** algorithm that consumes the
  validated commitment.
- The **exact-equality and fail-closed identity-drift verification**
  procedure that re-derives `agent_id` from the canonical material.

### Out of scope (what this spec does NOT close)

- **The source material from which the operator constructs the
  `provenance_commitment` value.** The Identity spec §3 defers "the exact
  commitment construction (hash algorithm, input material, encoding,
  verification path)" to an implementation spec with explicit review.
  No such source-envelope spec exists in the repository as of this phase.
  This document does not invent one.
- **Truncation and collision budget for `agent_id`** — deferred to a
  future 10IK review.
- **Rollback anchor format** — deferred to a future 10IH spec.
- **Per-call write allow-list** — deferred to a future 10II spec.
- **Starting habitat tiles declaration** — deferred to a future 10IJ spec.

The `provenance_commitment`'s own source material and construction remain
**unresolved**. This document explicitly does not close the Identity-spec
§3 construction gap.

---

## 2. Grounding: 10IC Implementation Behavior

This spec is grounded in the actual behavior of the pushed 10IC module
(commit `2e1d189`). The behavior below is a normative description of what
10IC already does; discrepancies between this spec and 10IC are resolved
by re-reading the 10IC source. This spec does not modify 10IC.

10IC constants relevant to validation and binding:

- `_IDENTITY_SCHEMA_VERSION = "first_pair_identity.1"`
- `_ID_DERIVATION_VERSION = "sha256-full-v1"`
- `_IDENTITY_DOMAIN_SEPARATOR = "GENESIS_FIRST_PAIR_IDENTITY_V1"`
- `_PAIR_ID = "genesis-first-pair"`

10IC validation of `provenance_commitment` (see `_is_hex64` and
`_derive_identity` in `local_first_pair_birth_candidate.py`):

- Type check: `type(value["provenance_commitment"]) is not str` — rejects
  non-`str` types and string subclasses (exact-type identity).
- Length check: `len(value) != 64` — rejects anything other than exactly
  64 characters.
- Alphabet check: every character must be in `"0123456789abcdef"` —
  lowercase hex only; uppercase hex characters are rejected.
- 10IC does **not** recompute the commitment from any source envelope. It
  accepts the caller-supplied value as-is once it passes the hex64 shape
  check, then includes it in the `agent_id` derivation material.

10IC test fixtures (see `tests/test_phase10ic_first_pair_birth_candidate.py`)
use the literal values `"a" * 64` and `"b" * 64` as Adam's and Eve's
`provenance_commitment` respectively. This is direct evidence that 10IC
treats the commitment as a caller-supplied value, not as a value it
constructs from provenance material.

---

## 3. Provenance Commitment Accepted Shape

### 3.1 Shape

The `provenance_commitment` accepted by 10IC is a **64-character
lowercase hexadecimal string**.

- Type: exactly `str` (subclasses rejected by 10IC's
  `type(value) is not str` guards).
- Length: exactly 64 characters.
- Alphabet: `0123456789abcdef` (lowercase only; uppercase hex is
  rejected).
- Role per Identity spec §3: an operator-approved immutable commitment to
  creation provenance. This is **not** a raw secret seed; nothing in this
  spec or in 10IC requires raw secret material to be held at runtime.

### 3.2 Operator Approval of the Supplied Value

The `provenance_commitment` value is **operator-approved** before pair
definition and supplied to 10IC by the caller. 10IC validates the shape
only; it does not verify operator approval, does not consult any external
registry of approved commitments, and does not store the value beyond
including it in the in-memory identity dict.

### 3.3 Immutability After Definition

Per Identity spec §3, `provenance_commitment` is immutable across cycles
and restarts. 10IC's drift checks (Section 5 of this spec) reject any
proposed mutation. There is no field-rename, no commitment rotation, and
no re-derivation under a different commitment value.

---

## 4. agent_id Derivation That Consumes the Validated Commitment

### 4.1 Canonical Material

After `provenance_commitment` passes the §3 shape check, 10IC builds an
**exact, ordered** canonical material dict containing these eight fields
and no others:

| Field | Source | Value |
|---|---|---|
| `domain_separator` | 10IC constant | `"GENESIS_FIRST_PAIR_IDENTITY_V1"` |
| `identity_schema_version` | 10IC constant | `"first_pair_identity.1"` |
| `id_derivation_version` | 10IC constant | `"sha256-full-v1"` |
| `canonical_name` | identity input | `"Adam"` or `"Eve"` |
| `canonical_agent_ref` | identity input | `"east_adam"` or `"east_eve"` |
| `pair_id` | 10IC constant | `"genesis-first-pair"` |
| `founding_role` | 10IC constant | `"founding_agent"` (unified; see §7) |
| `provenance_commitment` | identity input | validated 64-char lowercase hex per §3 |

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
  uses `"genesis-agent-" + _hash_canonical(material)` — no `[:32]` slice
  on the `agent_id` form.
- Truncation review (32-char or otherwise) is deferred to a future 10IK
  spec and is not authorized by this document.
- Prefix `"genesis-agent-"` is fixed; it namespaces First Pair agents
  from any other identity scheme in the project.

### 4.5 Determinism and Pair Symmetry

- Both Adam and Eve `agent_id`s are derived by the **same algorithm**.
  Only the canonical identity material differs (`canonical_name`,
  `canonical_agent_ref`, and the per-identity `provenance_commitment`
  value).
- Adam and Eve are not granted different identity tiers; they differ only
  in identity material.
- Re-derivation from the same canonical material always produces the same
  `agent_id`. There is no per-tick variation, no per-restart variation,
  no per-process variation.

---

## 5. Verification Path (Validated by 10IC Drift Checks)

### 5.1 Re-Derivation, Not Recall

After any restart, identity is verified by **re-derivation**, not by
recalling a stored `agent_id`. Re-derivation either matches the canonical
`agent_id` exactly or the recovery fails closed.

### 5.2 Verification Procedure Used by 10IC

To verify a presented First Pair identity:

1. Confirm the presented `provenance_commitment` passes the §3 shape
   check (exact-`str` type, length 64, lowercase hex only). Reject
   fail-closed if not.
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

- `provenance_commitment` shape mismatch — not exact-`str`, not 64 chars,
  or not lowercase hex.
- Immutable field mismatch — any §4.1 field on a presented identity
  differs from its canonical value.
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

The binding to `claim_scope = "identity"` is meaningful only when the
commitment value itself carries operator approval — which 10IC does not
verify and this spec does not specify (see §1, out of scope).

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

## 8. Status of the Identity-spec §3 Construction Gap

The Identity spec §3 says:

> The exact commitment construction (hash algorithm, input material,
> encoding, verification path) remains deferred to an implementation spec
> with explicit review.

The earlier 10IG document (pushed as `70ec3ca`) overclaimed closure of
this gap by asserting that the commitment "is the sha256 hexdigest of
operator-approved creation provenance material." That assertion was
unsupported: no spec in the repository defines the operator-approved
creation provenance material, no implementation in the repository
computes the commitment from such material, and the 10IC tests supply
placeholder values (`"a" * 64`, `"b" * 64`) directly.

This corrected 10IG document does **not** close the Identity-spec §3
construction gap. It closes only:

- the accepted shape of a caller-supplied `provenance_commitment` (§3);
- the exact type and lowercase-hex validation 10IC applies (§3);
- the inclusion of `provenance_commitment` in the canonical `agent_id`
  material (§4.1);
- the canonical `agent_id` derivation algorithm (§4);
- the exact-equality and fail-closed identity-drift verification
  procedure 10IC implements (§5).

The construction of `provenance_commitment` itself — the source-envelope
fields, the source-envelope hash algorithm, the source-envelope canonical
ordering and JSON settings, the source-envelope UTF-8 encoding, the
source-envelope output encoding, the source-envelope verification
procedure, the unknown/missing-field handling for the source envelope,
the list ordering and duplicate handling for source-envelope fields, the
source-envelope input immutability, and the operator-approval binding to
a specific source-envelope artifact — **remains unresolved**.

A future phase (numbered, not this one) must specify the
`provenance_commitment` source envelope exactly before the Identity-spec
§3 gap can be closed. That future phase requires an already-approved
exact source envelope to exist; if none exists, it must design one with
explicit operator review. This document does neither.

---

## 9. Non-Authority Statements

- This spec authorizes **nothing beyond documenting the validation and
  agent-id binding behavior already implemented by 10IC**.
- It does **not** authorize creating Adam or Eve.
- It does **not** modify 10IC, 10ID, 10IE, or any prior phase.
- It does **not** implement a new boundary module.
- It does **not** open Gate-7, start a daemon, add a scheduler, open a
  network connection, call a provider, or touch `world-sim/data`.
- It does **not** specify the `provenance_commitment` source envelope.
- It does **not** review truncation/collision budget (deferred to a
  future 10IK).
- It does **not** specify the rollback anchor envelope (deferred to a
  future 10IH).
- It does **not** enumerate the per-call write allow-list (deferred to a
  future 10II).
- It does **not** declare starting habitat tiles (deferred to a future
  10IJ).

---

## 10. Authorization Gate Conclusion

| Condition | Status |
|---|---|
| `provenance_commitment` accepted shape documented (64-char lowercase hex) | ✅ Yes — by this spec |
| Exact type and lowercase-hex validation documented | ✅ Yes — by this spec |
| Inclusion of `provenance_commitment` in `agent_id` material documented | ✅ Yes — by this spec |
| Canonical `agent_id` derivation documented (sha256, canonical JSON, domain separator, full hash) | ✅ Yes — by this spec |
| Exact-equality fail-closed identity-drift verification documented | ✅ Yes — by this spec |
| `provenance_commitment` source-envelope construction specified | ❌ No — unresolved (see §8) |
| Operator-approval binding to a specific source-envelope artifact specified | ❌ No — unresolved (see §8) |
| Truncation/collision budget reviewed | ❌ No — deferred to a future 10IK |
| Rollback anchor format specified | ❌ No — deferred to a future 10IH |
| Write allow-list enumerated | ❌ No — deferred to a future 10II |
| Starting habitat tiles declared | ❌ No — deferred to a future 10IJ |
| `world-sim/data` write authorized | ❌ No — not granted |
| GPT-5.6 Sol/Luna invoked for creation implementation | ❌ No — creation unauthorized |
| Explicit Sean approval for creation phase | ❌ No — not granted |

**FIRST_PAIR_CREATION_AUTHORIZED = False**

This document does not close the 10IF audit finding "Provenance commitment
construction deferred." That finding remains open. This document closes
only the narrower question of how 10IC validates and binds a
caller-supplied commitment value, which is a prerequisite for, but not a
substitute for, the future construction spec.

---

## 11. Forbidden Actions (Repeated for Emphasis)

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
- Modifying the 10IC implementation, 10ID, or 10IE
- Inventing a `provenance_commitment` source envelope without an
  explicit, reviewed, operator-approved design

---

## 12. Phase Index

This phase receives a single `phase_index.md` row marked **Done**,
commit-only, hash recorded after push. No tests, no backend/runtime
changes.
