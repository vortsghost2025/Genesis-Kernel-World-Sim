# Phase 10IO — First Pair Rollback State-Commitment Source-Envelope Specification

Numbered docs-only spec. This file specifies the caller-supplied source envelope
from which the deterministic `state_commitment` is derived. It closes the
docs-level state-commitment source-envelope construction gap identified by
10IH §1 and §12. It does **not** implement a runtime source-envelope validator.
It does **not** authorize rollback, execution, operator approval, or creation.
10IC still validates only the presented hex64 `state_commitment` shape; no
runtime source-envelope validator exists anywhere in the repository.

This spec is the rollback-state symmetric counterpart to the provenance
source-envelope specification (10IL).

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## A. Title and Status

- **Title**: Phase 10IO — First Pair Rollback State-Commitment Source-Envelope
  Specification.
- **Status**: Docs-only specification. No runtime implementation.
- **Phase number**: 10IO. This phase corrects the provisional 10IN label used
  in PR #17, which conflicted with AGENTS.md Rule 4 (10IN is reserved as the
  10IL implementation-candidate slot; 10IM is the 10IL metadata-sync slot).
  This spec is the **L** of the spec -> sync -> implementation-candidate chain
  governed by AGENTS.md Rule 4. It assigns:
  - **10IP** as the 10IO metadata-sync phase (L+1). 10IP records the 10IO row
    in `phase_index.md` with the real commit that places the final corrected
    10IO document on master and the document's LF-only SHA-256. 10IP is itself
    docs-only metadata sync; it does not implement, test, or touch
    runtime/backend/data.
  - **10IQ** as the named 10IO runtime implementation candidate (L+2). 10IQ is
    **not started and not authorized**. Specifying or implementing 10IQ requires
    GPT-5.6 Sol/Luna, TDD, explicit Sean approval, and all First Pair creation
    gates. The actual state-artifact content binding remains **unresolved**:
    `declared_state_artifact_integrity_id` (§F) is a caller-asserted digest
    string with hex64 shape validation only — it does **not** verify
    correspondence to any actual state-artifact bytes (canonical serialization,
    digest recomputation, storage lookup, and verification path remain
    unresolved and separately governed). No rollback validator or rollback
    executor exists anywhere in the repository. Per AGENTS.md Rule 4 the chain
    10IO -> 10IP -> 10IQ is one spec-sync-implementation-candidate unit; 10IQ
    is the named candidate slot for this unit, not a vacant slot.
  No phase beyond 10IQ is assigned by this document.
- **Boundary preservation**: Gate-7 remains closed. 10HD remains named-only.
  10CP remains the sole writer. `world-sim/data` remains forbidden.
  **FIRST_PAIR_CREATION_AUTHORIZED = False**.

---

## B. Purpose and Trust Boundary

### B.1 Purpose

The `state_commitment` in the First Pair rollback anchor (10IH) is a
deterministic SHA-256 hash of a caller-supplied **State-Envelope**. 10IO
defines that envelope's schema, canonical serialization, hash derivation, and
structural validation rules. This is a **docs-level contract**; no runtime
module implements it.

### B.2 Trust Boundary

- The State-Envelope is **caller-supplied** rollback-state material. It is
  deterministically canonicalized and committed. The resulting SHA-256 digest
  **is** the `state_commitment` that enters the rollback anchor.
- A structurally valid envelope — one whose fields match the schema, whose
  serialization is canonical, and whose SHA-256 digest matches the presented
  `state_commitment` — proves only that the envelope bytes hash to the
  presented commitment. It does **not** prove:
  - rollback execution is authorized or safe;
  - operator approval occurred;
  - the referenced state is the true last-known-good state;
  - any replay, freshness, uniqueness, or consumption guarantee.

---

## C. Safe Identifier Grammar

All identifier fields (`source_ref`, `rollback_anchor_ref`, `habitat_id`,
`state_reference`) use the same exact `_is_safe_identifier` contract as
10IC. This grammar is identical to 10IL §C.

| Property | Rule |
|---|---|
| Type | Exact built-in `str` (subclasses rejected; `type(x) is str`) |
| Length | 1–128 characters inclusive |
| Allowed characters | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-` |
| Forbidden sequence | `..` (two consecutive periods) |
| Forbidden markers | Lowercased form must not contain `true_map`, `known_map`, `world-sim/data`, or `[redacted` (the exact `_FORBIDDEN_IDENTIFIER_MARKERS` tuple from 10IC) |
| Hidden-substrate check | Alphanumeric-only lowercased collapsed form must not contain `truemap`, `knownmap`, or `hiddensubstrate` |
| Sanitization round-trip | `sanitize_public_text(value) == value` must hold |
| Normalization | None. Input is accepted as-is after validation — no NFC/NFD/NFKC/NFKD normalization |

### Rejection Behavior

Any identifier failing any rule causes immediate fail-closed rejection:
`"Invalid identifier in state envelope"`. No silent truncation, replacement,
defaulting, or normalization.

---

## D. Timestamp Contract

All `state_timestamp` values use the same exact canonical representation as
10IL §D.

### D.1 Canonical Form

```text
YYYY-MM-DDTHH:MM:SSZ
```

| Component | Constraint |
|---|---|
| Year | Four decimal digits. `0001`–`9999` inclusive. Year `0000` is rejected |
| Month | Two decimal digits, `01`–`12` |
| Day | Two decimal digits, valid for the given month and year (leap years observed) |
| `T` | Literal `T` separator |
| Hour | Two decimal digits, `00`–`23` |
| Minute | Two decimal digits, `00`–`59` |
| Second | Two decimal digits, `00`–`59` (leap seconds treated as `59`) |
| `Z` | Literal `Z`. Offset forms such as `+00:00` are invalid |

### D.2 Explicit Forbidden Variants

- Fractional seconds — forbidden
- UTC offsets (`+00:00`, `+0000`, `-05:00`) — forbidden
- Space instead of `T` — forbidden
- Omitting seconds — forbidden
- Non-UTC timezone abbreviations — forbidden
- Invalid calendar dates — forbidden

### D.3 Validation Rule

A valid `state_timestamp` must match the exact canonical form, be parseable
by a UTC-only calendar, and round-trip to the exact same string after
parse-and-reformat.

---

## E. State-Envelope Schema

The State-Envelope is an exact built-in Python `dict` containing **exactly**
the following fields and no others.

| Key | Type | Constraint |
|---|---|---|
| `source_envelope_schema_version` | `str` | Must equal literal `"first_rollback_state_envelope.1"` |
| `domain_separator` | `str` | Must equal literal `"GENESIS_FIRST_PAIR_ROLLBACK_V1"` |
| `source_ref` | `str` | Must satisfy the Safe Identifier Grammar (§C) |
| `state_timestamp` | `str` | Must satisfy the Timestamp Contract (§D) |
| `state_material` | `dict` | Must satisfy the State Material schema (§F) |

Any extra key, missing key, wrong key type (including `str` subclass), or
wrong nested type causes immediate fail-closed rejection.

---

## F. State Material Schema

The `state_material` is an exact built-in Python `dict` containing **exactly**
the following fields and no others.

| Key | Type | Constraint |
|---|---|---|
| `rollback_anchor_ref` | `str` | Must satisfy the Safe Identifier Grammar (§C). Must equal the enclosing anchor's `rollback_anchor_id` when validated together |
| `habitat_id` | `str` | Must satisfy the Safe Identifier Grammar (§C). Must equal the enclosing anchor's `habitat_id` when validated together |
| `state_reference` | `str` | Must satisfy the Safe Identifier Grammar (§C) |
| `declared_state_artifact_integrity_id` | `str` | Exactly 64 lowercase hex characters (`[0-9a-f]{64}`). **Caller-asserted** digest string — shape validation only. Does not verify that the digest corresponds to any actual state artifact bytes. Actual state-artifact content, canonical serialization, digest recomputation, storage lookup, and verification path remain unresolved (see 10IH §7 last-known-good state)|

### F.1 No Authority Conferred

All four fields are caller-supplied values. Shape validation establishes only
that the fields contain structurally valid values. It does **not** prove:

- that rollback execution is authorized or safe;
- that operator approval occurred;
- that `declared_state_artifact_integrity_id` corresponds to any actual
  state artifact bytes — it is a caller assertion with hex64 shape only;
- that the referenced state is the true last-known-good state (the
  last-known-good state material envelope remains unresolved per 10IH §7);
- uniqueness, freshness, or non-replay of the commitment.

Operator-approval artifact verification, replay prevention, freshness, and
rollback authorization remain unresolved and separately governed.

---

## G. Canonical Serialization and Commitment Derivation

### G.1 Canonical Serialization

Deterministic JSON, UTF-8 encoded before hashing:

```python
json.dumps(
    state_envelope,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
```

- `sort_keys=True` — canonical field order.
- `separators=(",", ":")` — compact, no insignificant whitespace.
- `ensure_ascii=False` — non-ASCII preserved, not escaped.

### G.2 Hash Algorithm

1. Serialize the envelope using §G.1.
2. UTF-8 encode the resulting string.
3. Apply `hashlib.sha256`.
4. Output the full 64-character lowercase hex digest (no truncation).

### G.3 Commitment Binding

The digest from §G.2 **is** the `state_commitment` value. Rollback-anchor
verification compares this digest against the separately-supplied
`state_commitment` field in the rollback anchor (10IH §3). Mismatch fails
closed.

---

## H. Duplicate-Key Parsing Boundary

### H.1 Two Distinct Inputs

| Input | Stage | Purpose |
|---|---|---|
| **Raw envelope bytes** | Stage 1 — Parsing boundary | UTF-8 JSON text or bytes before any `dict` materialization |
| **Normalized envelope dict** | Stage 2 — After validation | Exact-key-set built-in `dict` with duplicate keys already rejected |

### H.2 Duplicate-Key Rejection

The envelope must be received as raw UTF-8 JSON at the parsing boundary. The
parser must:

1. Detect duplicate keys before or during `dict` construction.
2. Reject any input containing a duplicate key at **any nesting level**.
3. Return fail-closed: `"Duplicate key in state envelope"`.
4. Never apply last-value-wins semantics for duplicate keys.

This applies to both the top-level envelope (§E) and the nested `state_material`
dict (§F).

---

## I. Validation Rules and Fail-Closed Behavior

A future validator (or an operator auditing a rollback anchor) must reject any
State-Envelope that fails one or more of the following checks. The single
fail-closed error is `"Invalid state envelope; rollback commitment rejected."`

### I.1 Envelope-Level Checks

| # | Check | Test |
|---|---|---|
| 1 | Exact-key-set (envelope) | Envelope has exactly 5 keys: `source_envelope_schema_version`, `domain_separator`, `source_ref`, `state_timestamp`, `state_material`. Any extra or missing key → reject |
| 2 | Exact-key-set (material) | `state_material` has exactly 4 keys: `rollback_anchor_ref`, `habitat_id`, `state_reference`, `declared_state_artifact_integrity_id`. Any extra or missing key → reject |
| 3 | Key-value type (envelope) | Each key maps to its required type: `source_envelope_schema_version` → built-in `str`, `domain_separator` → built-in `str`, `source_ref` → built-in `str`, `state_timestamp` → built-in `str`, `state_material` → built-in `dict`. Subclass or wrong type → reject |
| 4 | Key-value type (material) | Each key maps to its required type: `rollback_anchor_ref` → built-in `str`, `habitat_id` → built-in `str`, `state_reference` → built-in `str`, `declared_state_artifact_integrity_id` → built-in `str`. Subclass or wrong type → reject |

### I.2 Value Constraint Checks

| # | Check | Test |
|---|---|---|
| 5 | Schema version literal | `source_envelope_schema_version` == `"first_rollback_state_envelope.1"` |
| 6 | Domain separator literal | `domain_separator` == `"GENESIS_FIRST_PAIR_ROLLBACK_V1"` |
| 7 | Safe identifier (source_ref) | §C |
| 8 | Safe identifier (rollback_anchor_ref) | §C |
| 9 | Safe identifier (habitat_id) | §C |
| 10 | Safe identifier (state_reference) | §C |
| 11 | Digest format | `declared_state_artifact_integrity_id` matches `[0-9a-f]{64}` — exactly 64 lowercase hex characters |
| 12 | Timestamp canonical form | §D |

### I.3 Cross-Validation Checks

| # | Check | Test |
|---|---|---|
| 13 | Anchor ref binding | `state_material.rollback_anchor_ref` must exactly equal the enclosing rollback anchor's `rollback_anchor_id`. Mismatch → reject |
| 14 | Habitat id binding | `state_material.habitat_id` must exactly equal the enclosing rollback anchor's `habitat_id`. Mismatch → reject |

### I.4 Serialization and Commitment Checks

| # | Check | Test |
|---|---|---|
| 15 | Deterministic serialization | Re-serializing with §G.1 produces the same bytes each time |
| 16 | Commitment recomputation | `sha256(canonical_json(envelope).encode("utf-8")).hexdigest()` compared against the separately-supplied `state_commitment` value from the rollback anchor. Exact match required |
| 17 | Input immutability | Serialization does not mutate the input dict |

### I.5 Structural Integrity Checks

| # | Check | Test |
|---|---|---|
| 18 | Duplicate-key rejection (envelope level) | Raw JSON bytes had no duplicate top-level keys (§H) |
| 19 | Duplicate-key rejection (nested level) | Raw JSON bytes had no duplicate keys within `state_material` (§H) |
| 20 | No self-referential structure | No circular reference or repeated object identity |

### I.6 Trust-Domain Checks

| # | Check | Test |
|---|---|---|
| 21 | Cross-domain non-substitution | The `state_commitment` derived from this envelope must **not** be substituted into the `provenance_commitment` slot. Domain separators (`GENESIS_FIRST_PAIR_ROLLBACK_V1` vs. provenance domain) are checked separately |
| 22 | Provenance/rollback separation | This envelope's domain separator is `GENESIS_FIRST_PAIR_ROLLBACK_V1`. Never validated against or substituted for the provenance domain |

---

## J. Trust Separation

### J.1 Rollback State vs. Provenance Commitment

The `state_commitment` (this envelope) and `provenance_commitment` (10IL) are
**separate trust domains** unconditionally:

- Different domain separators
- Different source-envelope schemas
- Different source material and semantic purposes
- Different commitment digests (computed over different material)
- Different verification paths
- Different operator-approval requirements
- Different replay and consumption rules

Cross-domain substitution must fail closed. The domain separator
`"GENESIS_FIRST_PAIR_ROLLBACK_V1"` distinguishes this envelope from the
provenance envelope (`"GENESIS_FIRST_PAIR_PROVENANCE_V1"`).

### J.2 Integrity vs. Authority

A structurally valid state-envelope proves **only**:
- The envelope bytes hash to the presented commitment value.
- The envelope fields satisfy the schema constraints in §E–§F.

It does **not** prove:
- Rollback execution is authorized or safe.
- Operator approval occurred.
- `declared_state_artifact_integrity_id` matches any actual state artifact bytes.
- The referenced state is the true last-known-good state (that envelope remains
  unresolved per 10IH §7).
- Replay safety, freshness, uniqueness, or one-time consumption.
- That creation, write, or any runtime operation is authorized.

---

## K. Acceptance-Test Matrix (Docs-Level Specification)

The following tests are **specified** for a future state-envelope validator
implementation. They are **not** implemented by this PR. Implementation
requires a separate numbered phase with GPT-5.6 Sol/Luna and TDD.

### K.1 Exact Envelope

| # | Test | Validates |
|---|---|---|
| 1 | Envelope with all 5 top-level keys matching §E, all 4 material keys matching §F, valid identifiers, valid timestamp, valid digest → accepted | Full valid envelope |
| 2 | Round-trip canonical serialization matches original | Deterministic serialization (§I.4 #15) |
| 3 | Commitment recomputation matches presented `state_commitment` | Commitment integrity (§I.4 #16) |

### K.2 Key-Set Violations

| # | Test | Validates |
|---|---|---|
| 4 | Envelope missing any top-level key → rejected | Exact-key-set (§I.1 #1) |
| 5 | Envelope with extra top-level key → rejected | Exact-key-set (§I.1 #1) |
| 6 | `state_material` missing any key → rejected | Exact-key-set (§I.1 #2) |
| 7 | `state_material` with extra key → rejected | Exact-key-set (§I.1 #2) |

### K.3 Type Violations

| # | Test | Validates |
|---|---|---|
| 8 | Non-string top-level key value → rejected | Key-value type (§I.1 #3) |
| 9 | Non-dict `state_material` → rejected | Key-value type (§I.1 #3) |
| 10 | Non-string material value → rejected | Key-value type (§I.1 #4) |
| 11 | String subclass where `str` required → rejected | Key-value type (§I.1 #3/#4) |

### K.4 Safe Identifier Violations

| # | Test | Validates |
|---|---|---|
| 12 | `source_ref` longer than 128 chars → rejected | Safe identifier (§C) |
| 13 | `source_ref` contains `..` → rejected | Safe identifier (§C) |
| 14 | `source_ref` contains forbidden marker → rejected | Safe identifier (§C) |
| 15 | `source_ref` or `rollback_anchor_ref` with leading `.` or trailing `-` accepted | Safe identifier (§C) |
| 16 | `habitat_id` empty string → rejected | Safe identifier (§C) |
| 17 | `state_reference` valid identifier accepted | Safe identifier (§C) |

### K.5 Timestamp Violations

| # | Test | Validates |
|---|---|---|
| 18 | Fractional second → rejected | Timestamp (§D) |
| 19 | Offset → rejected | Timestamp (§D) |
| 20 | Invalid calendar date → rejected | Timestamp (§D) |
| 21 | Space separator → rejected | Timestamp (§D) |
| 22 | Missing seconds → rejected | Timestamp (§D) |
| 23 | Non-UTC timezone → rejected | Timestamp (§D) |
| 24 | Year `0000` → rejected | Timestamp (§D) |

### K.6 Duplicate-Key Violations

| # | Test | Validates |
|---|---|---|
| 25 | Raw JSON with duplicate top-level key → rejected | Duplicate-key (§H) |
| 26 | Raw JSON with duplicate key inside `state_material` → rejected | Duplicate-key (§H) |
| 27 | Normalized dict accepted when raw JSON had no duplicates | Duplicate-key (§H) |

### K.7 Value Constraint and Cross-Validation Violations

| # | Test | Validates |
|---|---|---|
| 28 | Wrong schema version → rejected | Schema literal (§I.2 #5) |
| 29 | Wrong domain separator → rejected | Domain literal (§I.2 #6) |
| 30 | Timestamp not canonical → rejected | Timestamp (§I.2 #12) |
| 31 | Declared digest not 64-char lowercase hex → rejected | Declared digest format (§I.2 #11) |
| 32 | Declared digest is 64-char lowercase hex → accepted for shape, does NOT verify artifact bytes | Shape only (§F.1) |
| 33 | `rollback_anchor_ref` does not match enclosing anchor's `rollback_anchor_id` → rejected | Anchor ref binding (§I.3 #13) |
| 34 | `habitat_id` does not match enclosing anchor's `habitat_id` → rejected | Habitat id binding (§I.3 #14) |

### K.8 Commitment and Cross-Domain

| # | Test | Validates |
|---|---|---|
| 35 | Commitment digest matches presented `state_commitment` → accepted | Commitment check (§I.4 #16) |
| 36 | Commitment digest does not match → rejected | Commitment check (§I.4 #16) |
| 37 | Envelope with rollback domain separator substituted into provenance slot → rejected | Cross-domain (§I.6 #21) |
| 38 | Envelope hash changed after mutation → different commitment | Immutability |

### K.9 Authorization Boundaries

| # | Test | Validates |
|---|---|---|
| 39 | Valid envelope + valid commitment → rollback still unauthorized, Gate-7 still closed | Non-authority (§J.2) |
| 40 | Valid declared digest shape → does NOT prove matching artifact bytes | Shape only (§F.1) |

---

## L. Non-Authority Statements

- This spec authorizes **nothing beyond documenting the state-commitment
  source-envelope schema and commitment derivation**.
- It does **not** authorize creating Adam or Eve.
- It does **not** implement a runtime state-envelope validator.
- It does **not** modify 10IC, 10ID, 10IE, 10IG, 10IH, 10II, 10IL, or any
  prior phase.
- It does **not** prove that `declared_state_artifact_integrity_id` corresponds
  to any actual state artifact bytes (caller assertion with hex64 shape only).
- It does **not** authorize rollback execution.
- It does **not** close the independent operator-approval binding gap.
- It does **not** prove that the referenced state is the true last-known-good
  state.
- It does **not** open Gate-7, start a daemon, add a scheduler, open a
  network connection, call a provider, or touch `world-sim/data`.
- It does **not** specify the provenance commitment source envelope (10IL).
- It does **not** enumerate the per-call write allow-list (10II).
- It does **not** review truncation/collision budget (10IK).
- It does **not** declare starting habitat tiles (10IJ).
- It does **not** invoke GPT-5.6 Sol/Luna.
- It does **not** grant explicit Sean approval for creation.

---

## M. Forbidden Actions

Under this spec and all preceding First Pair preflight specs:

- Creating Adam or Eve runtime entities
- Opening Gate-7
- Writing to `world-sim/data`
- Implementing, altering, or recurring into 10HD
- Granting write authority to Adam, Eve, or any new writer
- Model/provider autonomy
- Runtime self-scheduling
- Any write without an explicit per-call allow-list and provenance chain
- Silent replacement or aliasing of state material
- Implementing a runtime state-envelope validator under 10IO
- Claiming that a valid envelope proves operator approval, rollback authority,
  or creation authorization

---

## N. Phase Index

This phase receives a single `phase_index.md` row marked **Done**. The 10IO
row's Commit cell records the merge commit that placed the 10IO specification
on master (7-char lowercase hex). The row's Notes cell records the document's
LF-only SHA-256. Post-push synchronization follows the established W4 workflow:
Commit A = content (this spec + consistency amendments to 10IH/10IF, excluding
`phase_index.md`), Commit B = index hash-correction. No tests, no backend/
runtime changes.
