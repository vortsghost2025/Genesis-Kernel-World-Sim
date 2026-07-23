# Phase 10IH — First Pair Rollback Anchor Envelope Format and Validation Spec

Numbered docs-only spec. This file closes the rollback-anchor envelope-format
and validation question identified by the 10IF audit and deferred by the
corrected 10IG. It documents the exact envelope shape, field constraints,
and validation behavior already implemented by 10IC. It does not define the
`state_commitment` source-envelope construction, does not define a
last-known-good state envelope, does not authorize rollback, does not
execute rollback, does not authorize Adam/Eve creation, and does not open
Gate-7.

**FIRST_PAIR_CREATION_AUTHORIZED = False**

This document is ground-truthed to the pushed 10IC implementation
(`backend/world/local_first_pair_birth_candidate.py`, commit `2e1d189`)
and its test suite (`tests/test_phase10ic_first_pair_birth_candidate.py`).
It also reflects the downstream propagation through 10ID
(`backend/world/local_first_pair_habitat_boundary.py`, commit `c5b0656`)
and 10IE (`backend/world/local_first_pair_memory_boundary.py`, commit
`f5bfa21`). Discrepancies between this spec and those modules are resolved
by re-reading the module source; this spec does not modify them.

---

## 1. Scope and Out-of-Scope

### In scope (what this spec closes)

- The exact five-field caller-supplied input envelope for `rollback_anchor`.
- The exact six-field normalized output envelope (adds `rollback_anchor_valid`).
- The exact field types, allowed literal values, and validation rules 10IC
  already enforces.
- The exact-key-set invariant (no extra, no missing keys).
- The single allowed `claim_scope` literal: `"operator_proof"`.
- The habitat binding rule (anchor's `habitat_id` must equal the validated
  habitat stem's `habitat_id`).
- Identity binding: **contextual association through the enclosing
  validated birth-candidate/habitat-boundary chain**; no direct
  `pair_id` / `agent_id` / `provenance_commitment` fields in the anchor.
- Authorization-vs-execution separation: shape validation is not rollback
  authorization; rollback authorization is not rollback execution; anchor
  acceptance performs no rollback; 10IH names no executor.
- Operator-approval boundary: the anchor is caller-supplied, not model-chosen; `claim_scope = "operator_proof"` is a claim classification, not proof of operator approval.
- Existing fail-closed error vocabulary (`invalid_rollback_anchor`,
  `missing_rollback_anchor`, enclosing candidate/boundary drift errors).
- Replay/uniqueness/expiry/tamper status: honestly documented as absent
  today.
- Immutability expectations: normalized output is a detached reconstructed
  dictionary of scalar values; downstream mutation or drift must fail
  revalidation.
- 10CP sole-writer preservation: the anchor validates; it does not write;
  any future executor must use 10CP as the only writer.
- Gate-7 and 10HD boundaries: no import of recursion-spine verifier chain,
  no daemon/scheduler/network/provider/container/Docker activity,
  no `world-sim/data` read/write.

### Out of scope (what this spec does NOT close)

- **The `state_commitment` source-envelope construction** — 10IC validates
  only hex64 shape; no source fields, ordering, hash algorithm, canonical
  serialization, encoding, or verification path is defined anywhere in the
  repository. This remains the symmetric gap to `provenance_commitment`
  (10IG §8).
- **The last-known-good state material envelope** — what the rollback
  executor would actually revert to.
- **Replay / uniqueness / expiry / tamper mechanism** — no sequence number,
  no `previous_anchor_id`, no HMAC, no signature, no expiry field, no
  clock read.
- **Per-agent asymmetric-rollback scope** — the rollback specification
  permits Adam-only, Eve-only, or pair rollback; the anchor envelope
  itself is scope-neutral and contains no `rollback_scope` field. Target
  selection belongs to a future explicitly reviewed authorization or
  execution artifact.
- **Operator-approval artifact verification** — the anchor is
  caller-supplied; the literal `claim_scope = "operator_proof"` is a claim
  classification, not independent proof of operator approval.
- **Rollback executor or kill-switch implementation** — separately named
  and authorized phases; would require GPT-5.6 Sol/Luna + Sean approval.
- **`provenance_commitment` source-envelope construction** — remains
  unresolved per 10IG.

---

## 2. Historical Note on `10IH`

The literal `10IH` once appeared in the 10FX naming paragraph
(`phase_index.md` row 151) as a candidate number for what was eventually
implemented as **10FZ — Minimal Inert Model Routing Approval Authorization
Reporter** (commit `86add55`, phase_index.md row 153). That was a
model-routing governance artifact, unrelated to First Pair rollback. The
slot is vacant for First Pair; no committed `10IH` spec file, module, or
test exists. This note is informational only and is not part of the
normative anchor contract.

---

## 3. Exact Input Envelope

The caller-supplied `rollback_anchor` input is a Python `dict` containing
**exactly** the following five string-keyed fields and no others:

| Key | Type | Constraint | Implementation Reference |
|---|---|---|---|
| `rollback_anchor_schema_version` | exact `str` | Must equal literal `"first_rollback_anchor.1"` | L30, L399-400 |
| `rollback_anchor_id` | exact `str` | Caller-supplied; must satisfy `_is_safe_identifier` (see §4) | L403 |
| `habitat_id` | exact `str` | Must satisfy `_is_safe_identifier`; must equal the already-validated habitat's `habitat_id` | L405-407 |
| `claim_scope` | exact `str` | Must equal literal `"operator_proof"` | L409 |
| `state_commitment` | exact `str` | Must satisfy `_is_hex64`: exactly 64 lowercase hex characters | L211-214, L411 |

Any deviation — missing key, extra key, wrong type (including string
subclasses), wrong literal, non-hex64 `state_commitment`, unsafe
`rollback_anchor_id` or `habitat_id`, mismatched `habitat_id`, or
`claim_scope` not equal to `"operator_proof"` — causes the anchor to be
rejected with `rollback_anchor_valid = False` (see §5).

---

## 4. Safe Identifier Validator (`_is_safe_identifier`)

This is the single source of truth for identifier shape across 10IC/10ID/10IE.
It validates that a value is:

- Exact built-in `str` type (subclasses rejected via `type(value) is str`).
- Length 1–128 characters.
- Every character in the alphabet:
  `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-`
- Does not contain `..`.
- Lowercased form does not contain any forbidden marker from the module's
  `_FORBIDDEN_IDENTIFIER_MARKERS` list.
- Collapsed alphanumeric form (lowercased with non-alphanumeric characters removed) does not contain
  `truemap`, `knownmap`, or `hiddensubstrate`.
- Survives `sanitize_public_text(value) == value` (idempotent
  sanitization).

`rollback_anchor_id` and `habitat_id` are each passed through this
validator individually. The validator does **not** enforce uniqueness across
callers or across time; it is a shape check only.

---

## 5. Exact Normalized Output Envelope

The boundary function `_validate_rollback_anchor` returns a reconstructed
dictionary with exactly six fields:

| Key | Type | Valid Case | Invalid Case |
|---|---|---|---|
| `rollback_anchor_valid` | exact `bool` | `True` | `False` |
| `rollback_anchor_schema_version` | exact `str` | `"first_rollback_anchor.1"` | `None` |
| `rollback_anchor_id` | exact `str` | accepted value | `None` |
| `habitat_id` | exact `str` | accepted value | `None` |
| `claim_scope` | exact `str` | `"operator_proof"` | `None` |
| `state_commitment` | exact `str` | accepted hex64 value | `None` |

On invalid path: all five payload fields are `None`; `rollback_anchor_valid`
is exact `bool` `False`. The module uses `is True` / `is False` checks
(downstream 10ID/10IE enforce the same strictness).

The returned dictionary is a **detached reconstructed dictionary of scalar
values** — not a reference to the input, not technically immutable, and
not a frozen object. Downstream propagation carries the envelope through
each boundary without re-validation: 10ID carries the anchor from the birth
candidate; 10IE carries the anchor from the verified 10ID habitat boundary;
the heartbeat verifier checks only `rollback_anchor_id` equality. No
downstream module calls `_validate_rollback_anchor`. Drift or tampering of
the envelope between stages is detected by the enclosing boundary's
integrity checks and surfaces through existing layer-specific errors
(`invalid_birth_candidate`, `invalid_habitat_boundary`,
`candidate_declaration_drift`, `missing_rollback_anchor`).

---

## 6. Structural Accuracy

- **Exact-key-set enforcement:** 10IC uses `_has_exact_string_keys(input,
  _ROLLBACK_INPUT_FIELDS)` which returns `False` on missing keys, extra
  keys, or any key that is not an exact built-in `str`. It does **not**
  detect duplicate keys that may have already been collapsed by an upstream
  JSON parser before the material reached the boundary.
- **No duplicate-key detection:** Once input is a Python `dict`, any
  duplicate keys in the original serialized representation (JSON, etc.) are
  already resolved by the parser. 10IH does not claim to detect
  pre-materialization duplicates.
- **No Python immutability guarantee:** The normalized output is a plain
  `dict`. Immutability is an operational expectation (downstream
  revalidation detects drift), not a language-level guarantee.

---

## 7. Binding Boundaries

### Habitat Binding

Direct strict equality: the anchor's `habitat_id` must equal the validated
habitat stem's `habitat_id` (10IC L407). The anchor cannot be accepted
without an already-validated habitat.

### Identity Binding

**No direct identity fields exist in the anchor.** The anchor carries no
`pair_id`, no `agent_id`, no canonical identity fields, and no
`provenance_commitment`. Identity association is **contextual/transitive**
through the enclosing validated chain:

```
birth_candidate (10IC) → habitat_boundary (10ID) → memory_boundary (10IE)
       ↓                    ↓                    ↓
  identity fields      same identity       same identity
  (canonical)          fields carried      fields carried
```

The anchor is embedded beside the identity fields within the wider
birth-candidate declaration envelope. Do not claim that `habitat_id`
derives `pair_id` or that the anchor itself binds identity.

### Provenance

The `claim_scope` field is exactly the literal `"operator_proof"`. This
is a **claim classification** used by the provenance taxonomy (see
`first_memory_boundary_spec.md` §6 for the public taxonomy:
`observed`, `speech`, `hypothesis`, `identity`, `proof`). Its presence in
a validated anchor does **not** prove that operator approval occurred.
The anchor is caller-supplied; 10IC does not verify an approval
signature, authorization artifact, or registry.

### Last-Known-Good State

Remains **unresolved**. The `state_commitment` field is a hex64 value
supplied by the caller. The source-envelope construction (what state this
commitment commits to, its fields, ordering, hash algorithm, canonical
serialization, encoding, and verification path) is **not defined** by this
spec, not defined by 10IC, and not defined by any spec in the repository.
It is the symmetric gap to `provenance_commitment` (see 10IG §8).

---

## 8. Authorization and Execution Separation

Use these exact distinctions. They are not optional:

- **Shape validation** (what 10IC does) is not rollback authorization.
- **Rollback authorization** (a future operator-approved decision) is not
  rollback execution.
- **Anchor acceptance** performs no rollback. It returns a normalized
  envelope or a failure.
- **10IH names no executor.** Any future rollback executor phase is
  explicitly out of scope.
- **Any future execution that writes state must preserve 10CP as the sole
  authorized writer** (per 10CN/10CP gate-6 envelope and every First Pair
  spec's §12/§17/equivalent).
- **Adam and Eve receive no write capability.** They are inputs to 10IC's
  identity/habitat/memory boundaries; nowhere in the anchor module are they
  granted a writer capability. The anchor is a **proof** structure, not a
  write surface.

---

## 9. Asymmetric Rollback

The rollback specification (`first_rollback_kill_switch_spec.md` §7)
explicitly permits:

- Adam-only rollback;
- Eve-only rollback;
- Pair rollback (both at once).

The current anchor envelope is **scope-neutral** — it contains no
`rollback_scope` field. Target selection (which identity or identities
are rolled back) belongs to a future explicitly reviewed authorization or
execution artifact. Do not add a `rollback_scope` field in this spec.

---

## 10. Replay, Uniqueness, Expiry, and Tamper Status

Current 10IC behavior, documented honestly:

| Property | Status |
|---|---|
| `rollback_anchor_id` uniqueness | Not enforced. Two anchors with the same id both validate. |
| Replay of identical anchor | Accepted identically (no replay detection). |
| Sequence / previous-anchor linkage | None. |
| Expiry field | None. |
| Clock read | None (10IC uses no clock). |
| Signature / HMAC | None. |
| Anchor-envelope fingerprint (e.g. `sha256(canonical(5-field))`) | Not computed. |
| Tamper detection beyond shape validation | None (shape validation is the only gate). |

10IH does **not** introduce or recommend one mechanism as normative. It
does **not** reserve or name another phase number (e.g. `10IL`) for these
decisions. Those are operator decisions required before any future phase.

---

## 11. Existing Fail-Closed Error Vocabulary

10IH documents only the existing behavior; it does not invent new runtime
error strings:

| Error String | Origin | Condition |
|---|---|---|
| `invalid_rollback_anchor` | 10IC `_validate_rollback_anchor` returns a six-field invalid dict with `rollback_anchor_valid=False`; `create_first_pair_birth_candidate` adds `invalid_rollback_anchor` when `rollback_anchor_valid` is `False` (L474-475) | Any input envelope failing the five-field rules (missing key, extra key, wrong type, wrong literal, unsafe identifier, hex64 violation, habitat_id mismatch, claim_scope mismatch) |
| `missing_rollback_anchor` | Heartbeat verifier L766, L799, L805-806 | Observation's `rollback_anchor_id` absent or mismatched against the birth candidate's anchor id |
| `candidate_declaration_drift` | 10ID / 10IE / 10IC cross-boundary drift detection | Enclosing candidate/habitat/memory boundary fields mutated between stages |

`rollback_anchor_drift` is **not** a separate error string in the current
implementation; drift surfaces through existing layer-specific errors
(`invalid_birth_candidate`, `invalid_habitat_boundary`,
`candidate_declaration_drift`, `missing_rollback_anchor`).
10IH does not add a new string without operator decision.

---

## 12. Explicit Unresolved Findings

This spec leaves open the following questions. They are not silently closed.

| Unresolved Question | Resolution Path |
|---|---|
| `state_commitment` source-envelope construction | Future phase (operator decision required on fields, ordering, algorithm, serialization, encoding, verification, operator-approval binding) |
| Last-known-good state material envelope | Future phase (executor must have a defined state to revert to) |
| Replay / uniqueness / tamper / expiry mechanism | Operator decision (sequence number, HMAC, signature, `previous_anchor_id`, none) |
| Per-agent asymmetric-rollback scope | Future authorization/execution artifact (anchor remains scope-neutral) |
| Operator-approval artifact verification | Operator decision (signature, sign-off record, decision ID, or asserted-only) |
| Rollback executor / kill-switch implementation | Separate named phase (requires GPT-5.6 Sol/Luna + Sean approval) |

---

## 13. Non-Authority Statements

This spec authorizes **nothing beyond documenting the envelope format and
validation rules already implemented by 10IC**.

- `FIRST_PAIR_CREATION_AUTHORIZED = False`
- Gate-7 remains closed (no daemon, scheduler, network, provider, container, Docker, model call, file I/O, or `world-sim/data` read/write).
- 10CP remains the sole writer.
- 10HD remains named-only and untouched.
- No Adam/Eve entity is created.
- No backend or tests change.
- No runtime, persistence, memory write, ledger write, network, provider,
  model, daemon, scheduler, container, Docker, frontend, or `world-sim/data`
  activity occurs.
- This spec does not modify 10IC, 10ID, 10IE, 10IF, or 10IG.
- This spec does not invent fields, does not truncate `agent_id`, does not
  specify the `state_commitment` construction, does not enumerate the write
  allow-list, does not declare starting habitat tiles.

---

## 14. Phase Index

This phase receives a single `phase_index.md` row marked **Done**,
commit-only, hash recorded after push. No tests, no backend/runtime changes.