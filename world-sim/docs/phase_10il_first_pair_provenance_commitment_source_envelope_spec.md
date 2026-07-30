# Phase 10IL — First Pair Provenance Commitment Source-Envelope Specification

Numbered docs-only spec. This file specifies the caller-supplied source envelope
from which the deterministic `provenance_commitment` is derived. It closes the
docs-level source-envelope design gap identified by 10IG §8 and 10IF. It does
**not** implement a runtime source-envelope validator. It does **not** close
the independent operator-approval binding gap. 10IC still validates only the
presented hex64 `provenance_commitment` shape (64-char lowercase hex); no
runtime source-envelope validator exists anywhere in the repository.

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## A. Title and Status

- **Title**: Phase 10IL — First Pair Provenance Commitment Source-Envelope
  Specification.
- **Status**: Docs-only specification. No runtime implementation.
- **Phase number**: 10IL. No other new phase number is assigned by this
  document.
- **Boundary preservation**: Gate-7 remains closed. 10HD remains named-only.
  10CP remains the sole writer. `world-sim/data` remains forbidden.

---

## B. Purpose and Trust Boundary

### B.1 Purpose

The `provenance_commitment` in the First Pair canonical identity (10IG) is a
deterministic SHA-256 hash of a caller-supplied **Source Envelope**. 10IL
defines that envelope's schema, canonical serialization, hash derivation, and
structural validation rules. This is a **docs-level contract**; no runtime
module implements it.

### B.2 Trust Boundary

- The Source Envelope is **caller-supplied** provenance source material. It is
  deterministically canonicalized and committed. The resulting SHA-256 digest
  **is** the `provenance_commitment` that enters the `agent_id` derivation.
- A structurally valid envelope — one whose fields match the schema, whose
  serialization is canonical, and whose SHA-256 digest matches the presented
  `provenance_commitment` — is **not inherently truthful or authorized**. It
  proves only that the envelope bytes hash to the presented commitment.
- Verification of the envelope's content truthfulness, operator approval,
  source integrity, and authorization are **separate** and are not satisfied
  by this spec.

---

## C. Safe Identifier Grammar (Single Definition)

All identifier fields in this spec (`source_ref`, `source_artifact_id`,
`operator_approval_ref`) use a single exact grammar. This grammar is the same
`_is_safe_identifier` contract implemented by 10IC.

### C.1 Exact Grammar

| Property | Rule |
|---|---|---|
| Type | Exact built-in `str` (subclasses rejected; `type(x) is str`) |
| Length | 1–128 characters inclusive |
| Allowed characters | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-` |
| Forbidden sequence | `..` (two consecutive periods) |
| Forbidden markers | Lowercased form must not contain `true_map`, `known_map`, `world-sim/data`, or `[redacted` (the exact `_FORBIDDEN_IDENTIFIER_MARKERS` tuple from 10IC) |
| Hidden-substrate check | Alphanumeric-only lowercased collapsed form must not contain `truemap`, `knownmap`, or `hiddensubstrate` |
| Sanitization round-trip | `sanitize_public_text(value) == value` must hold |
| Normalization | None. Input is accepted as-is after validation — no NFC/NFD/NFKC/NFKD normalization |

### C.2 Rejection Behavior

Any identifier failing any rule in C.1 causes immediate fail-closed rejection.
The validation error is: `"Invalid identifier in provenance envelope"`. No
silent truncation, replacement, defaulting, or normalization.

---

## D. Timestamp Contract (Single Definition)

All `source_timestamp` values use a single exact canonical representation.

### D.1 Canonical Form

```
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
| `Z` | Literal `Z`. Offset forms such as `+00:00`, `+0000`, `-00:00` are invalid |

### D.2 Explicit Forbidden Variants

- Fractional seconds (e.g., `:30.123Z`) — forbidden
- UTC offsets (e.g., `+00:00`, `+0000`, `-05:00`) — forbidden
- Space instead of `T` separator — forbidden
- Omitting seconds (`:HH:MMZ`) — forbidden
- Non-UTC timezone abbreviations (`EST`, `UTC`) — forbidden
- Invalid calendar dates (e.g., `2024-02-30`) — forbidden

### D.3 Validation Rule

A valid `source_timestamp` must:
1. Match the regex: `^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ$`
2. Be parseable by a UTC-only calendar that rejects invalid month-day combinations (e.g., Feb 29 in a non-leap year).
3. Round-trip to the exact same string after parse-and-reformat. Any timestamp whose string representation differs after parse-and-format is non-canonical and rejected.

---

## E. Source-Envelope Schema

The Source Envelope is an exact built-in Python `dict` containing **exactly**
the following fields and no others.

| Key | Type | Constraint |
|---|---|---|
| `source_envelope_schema_version` | `str` | Must equal literal `"first_provenance_envelope.1"` |
| `domain_separator` | `str` | Must equal literal `"GENESIS_FIRST_PAIR_PROVENANCE_V1"` |
| `source_ref` | `str` | Must satisfy the Safe Identifier Grammar (§C) |
| `source_timestamp` | `str` | Must satisfy the Timestamp Contract (§D) |
| `provenance_material` | `dict` | Must satisfy the Provenance Material schema (§F) |

Any extra key, missing key, wrong key type (including `str` subclass), or wrong
nested type causes immediate fail-closed rejection. No silent correction.

---

## F. Provenance Material Schema

The `provenance_material` is an exact built-in Python `dict` containing
**exactly** the following fields and no others.

| Key | Type | Constraint |
|---|---|---|
| `canonical_name` | `str` | Must equal literal `"Adam"` or `"Eve"` |
| `source_artifact_id` | `str` | Must satisfy the Safe Identifier Grammar (§C) |
| `source_artifact_integrity_id` | `str` | Exactly 64 lowercase hex characters (`[0-9a-f]{64}`) |
| `operator_approval_ref` | `str` | Must satisfy the Safe Identifier Grammar (§C) |

### F.1 `operator_approval_ref` — No Authority Conferred

`operator_approval_ref` is a **caller-supplied reference** only. Shape
validation (Safe Identifier Grammar) establishes only that the field contains
a structurally valid identifier. It does **not** prove:

- that operator approval actually occurred;
- that the referenced approval artifact was independently verified;
- that this envelope is authorized for any particular use;
- uniqueness, freshness, or non-replay of the approval.

Operator-approval artifact verification **remains unresolved and separately
governed** (per 10IH §12 unresolved table, 10IF §3/§4, and the First Pair
write-authority spec). 10IL does not close that gap.

---

## G. Canonical Serialization and Commitment Derivation

### G.1 Canonical Serialization

Deterministic JSON, UTF-8 encoded before hashing:

```python
json.dumps(
    source_envelope,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
```

- `sort_keys=True` — canonical field order.
- `separators=(",", ":")` — compact, no insignificant whitespace.
- `ensure_ascii=False` — non-ASCII preserved, not escaped.
- The serialized string is UTF-8 encoded before hashing.

### G.2 Hash Algorithm

1. Serialize the envelope using §G.1.
2. UTF-8 encode the resulting string.
3. Apply `hashlib.sha256`.
4. Output the full 64-character lowercase hex digest (no truncation).

### G.3 Commitment Binding

The digest from §G.2 **is** the `provenance_commitment` value. Identity
verification compares this digest against the separately-supplied
`provenance_commitment` field in the First Pair identity material (10IG §4).
Mismatch fails closed. The commitment is **not** verified against the
`agent_id` directly; it is verified against the commitment value that was used
in `agent_id` derivation.

---

## H. Duplicate-Key Parsing Boundary

### H.1 Two Distinct Inputs

The spec defines two distinct envelope representations:

| Input | Stage | Purpose |
|---|---|---|
| **Raw envelope bytes** | Stage 1 — Parsing boundary | UTF-8 JSON text or bytes before any `dict` materialization |
| **Normalized envelope dict** | Stage 2 — After validation | Exact-key-set built-in `dict` with duplicate keys already rejected |

### H.2 Duplicate-Key Rejection

The envelope must be received as raw UTF-8 JSON at the parsing boundary. The
parser must:

1. Detect duplicate keys before or during `dict` construction.
2. Reject any input containing a duplicate key at **any nesting level**.
3. Return fail-closed: `"Duplicate key in provenance envelope"`.
4. Never apply last-value-wins semantics for duplicate keys.

This requirement applies to both:
- The top-level envelope (schema from §E).
- The nested `provenance_material` dict (schema from §F).

A built-in Python `dict` (§E) cannot prove whether duplicate JSON keys existed
before materialization, because standard JSON parsers collapse duplicates before
the dict reaches validation. Therefore the raw-JSON parsing boundary (§H.1) is
the only stage where duplicate-key detection is enforceable.

---

## I. Validation Rules and Fail-Closed Behavior

A future validator (or an operator auditing a pair) must reject any Source
Envelope that fails one or more of the following checks. The single fail-closed
error is `"Invalid provenance envelope; identity commitment rejected."` Only
the first failing rule need be reported.

### I.1 Envelope-Level Checks

| # | Check | Test |
|---|---|---|
| 1 | Exact-key-set (envelope) | Envelope has exactly 5 keys: `source_envelope_schema_version`, `domain_separator`, `source_ref`, `source_timestamp`, `provenance_material`. Any extra or missing key → reject |
| 2 | Exact-key-set (material) | `provenance_material` has exactly 4 keys: `canonical_name`, `source_artifact_id`, `source_artifact_integrity_id`, `operator_approval_ref`. Any extra or missing key → reject |
| 3 | Key-value type (envelope) | Each key maps to its required type: `source_envelope_schema_version` → built-in `str`, `domain_separator` → built-in `str`, `source_ref` → built-in `str`, `source_timestamp` → built-in `str`, `provenance_material` → built-in `dict`. Subclass or wrong type → reject |
| 4 | Key-value type (material) | Each key maps to its required type: `canonical_name` → built-in `str`, `source_artifact_id` → built-in `str`, `source_artifact_integrity_id` → built-in `str`, `operator_approval_ref` → built-in `str`. Subclass or wrong type → reject |

### I.2 Value Constraint Checks

| # | Check | Test |
|---|---|---|
| 5 | Schema version literal | `source_envelope_schema_version` == `"first_provenance_envelope.1"`. No other value accepted |
| 6 | Domain separator literal | `domain_separator` == `"GENESIS_FIRST_PAIR_PROVENANCE_V1"`. No other value accepted |
| 7 | Safe identifier (source_ref) | `source_ref` satisfies Safe Identifier Grammar (§C) |
| 8 | Safe identifier (source_artifact_id) | `source_artifact_id` satisfies Safe Identifier Grammar (§C) |
| 9 | Safe identifier (operator_approval_ref) | `operator_approval_ref` satisfies Safe Identifier Grammar (§C). Does **not** verify operator approval |
| 10 | Canonical name | `canonical_name` == `"Adam"` or `"Eve"`. Any other value → reject |
| 11 | Timestamp canonical form | `source_timestamp` satisfies Timestamp Contract (§D) |
| 12 | Integrity digest format | `source_artifact_integrity_id` matches `[0-9a-f]{64}` — exactly 64 lowercase hex characters |

### I.3 Serialization and Commitment Checks

| # | Check | Test |
|---|---|---|
| 13 | Deterministic serialization | Re-serializing the envelope with §G.1 and UTF-8 encoding produces the same bytes each time (idempotent round-trip) |
| 14 | Commitment recomputation | Recomputing `sha256(canonical_json(envelope).encode("utf-8")).hexdigest()` produces a 64-character lowercase hex digest. That digest is compared against the separately-supplied `provenance_commitment` value from the identity material. Exact match required. Mismatch → reject |
| 15 | Input immutability | Serialization does not mutate the input dict. The envelope is not consumed or cleared by validation |

### I.4 Structural Integrity Checks

| # | Check | Test |
|---|---|---|
| 16 | Duplicate-key rejection (envelope level) | Raw JSON bytes at the parsing boundary contained no duplicate keys at the top level (§H) |
| 17 | Duplicate-key rejection (nested level) | Raw JSON bytes at the parsing boundary contained no duplicate keys within `provenance_material` (§H) |
| 18 | No self-referential structure | No circular reference or repeated object identity within the envelope. The envelope is a tree of scalar and dict values, not a graph |

### I.5 Trust-Domain Checks

| # | Check | Test |
|---|---|---|
| 19 | Cross-domain non-substitution | The `provenance_commitment` derived from this envelope must **not** be substituted into the rollback `state_commitment` slot. The domain separators (`GENESIS_FIRST_PAIR_PROVENANCE_V1` vs. the rollback envelope's domain) are checked separately by their respective schemas |
| 20 | Provenance/rollback separation | This envelope's domain separator is `GENESIS_FIRST_PAIR_PROVENANCE_V1`. It is never validated against or substituted for the rollback domain |

---

## J. Trust Separation

### J.1 Provenance vs. Rollback State Commitment

The `provenance_commitment` (this envelope) and rollback `state_commitment`
(10IH) are separate trust domains:

- Different domain separators
- Different source-envelope schemas
- Different semantic purposes
- Different commitment hashes (computed over different material)
- Different verification paths
- Different operator-approval bindings (both unresolved)
- Different replay and consumption rules (both unresolved)

Cross-domain substitution must fail closed. The domain separator
`"GENESIS_FIRST_PAIR_PROVENANCE_V1"` distinguishes this envelope from any
other commitment scheme.

### J.2 Integrity vs. Authority

A structurally valid provenance envelope proves **only**:
- The envelope bytes hash to the presented commitment value.
- The envelope fields satisfy the schema constraints in §E–§F.

It does **not** prove:
- Operator approval or authority for any action.
- Uniqueness, freshness, or non-replay.
- That the source material is truthful.
- That creation, write, or any runtime operation is authorized.
- That the operator-approval reference (§F.1) corresponds to a genuine
  approval artifact.

Provenance integrity is a prerequisite for identity validation. It is not a
substitute for independent operator-approval verification.

---

## K. Non-Authority Statements

- This spec authorizes **nothing beyond documenting the provenance source-
  envelope schema and commitment derivation**.
- It does **not** authorize creating Adam or Eve.
- It does **not** implement a runtime source-envelope validator.
- It does **not** modify 10IC, 10ID, 10IE, 10IG, 10IH, or 10II.
  (Reference updates to 10IG and 10IF recording that a docs-level envelope
  design now exist are not boundary-modifying changes to those specs.)
- It does **not** close the independent operator-approval binding gap.
- It does **not** open Gate-7, start a daemon, add a scheduler, open a
  network connection, call a provider, or touch `world-sim/data`.
- It does **not** specify the rollback `state_commitment` source envelope.
- It does **not** enumerate the per-call write allow-list.
- It does **not** review truncation/collision budget (deferred to 10IK).
- It does **not** declare starting habitat tiles (protected 10IJ draft).
- It does **not** invoke GPT-5.6 Sol/Luna.
- It does **not** grant explicit Sean approval for creation.

---

## L. Future Acceptance-Test Matrix (Docs-Level Specification)

The following tests are **specified** for a future source-envelope validator
implementation. They are **not** implemented by this PR. Implementation
requires a separate numbered phase with GPT-5.6 Sol/Luna and TDD. The tests
below are categorized by the validation rule they exercise.

### L.1 Exact Envelope

| # | Test | Validates |
|---|---|---|
| 1 | Envelope with all 5 top-level keys matching §E, all 4 material keys matching §F, valid identifiers, valid timestamp, valid digest → accepted | Full valid envelope |
| 2 | Round-trip canonical serialization matches original | Deterministic serialization (§I.3 #13) |
| 3 | Commitment recomputation matches presented `provenance_commitment` | Commitment integrity (§I.3 #14) |

### L.2 Key-Set Violations

| # | Test | Validates |
|---|---|---|
| 4 | Envelope missing any top-level key → rejected | Exact-key-set (§I.1 #1) |
| 5 | Envelope with extra top-level key → rejected | Exact-key-set (§I.1 #1) |
| 6 | `provenance_material` missing any key → rejected | Exact-key-set (§I.1 #2) |
| 7 | `provenance_material` with extra key → rejected | Exact-key-set (§I.1 #2) |

### L.3 Type Violations

| # | Test | Validates |
|---|---|---|
| 8 | Non-string top-level key value → rejected | Key-value type (§I.1 #3) |
| 9 | Non-dict `provenance_material` → rejected | Key-value type (§I.1 #3) |
| 10 | Non-string material value → rejected | Key-value type (§I.1 #4) |
| 11 | String subclass where `str` required → rejected | Key-value type (§I.1 #3/#4) |

### L.4 Safe Identifier Violations

| # | Test | Validates |
|---|---|---|
| 12 | `source_ref` longer than 128 chars → rejected | Safe identifier (§C) |
| 13 | `source_ref` contains `..` → rejected | Safe identifier (§C) |
| 14 | `source_ref` contains forbidden marker → rejected | Safe identifier (§C) |
| 15 | `source_ref` with leading `.` or trailing `-` accepted (actual `_is_safe_identifier` permits leading/trailing punctuation) | Safe identifier (§C) |
| 16 | `source_artifact_id` empty string → rejected | Safe identifier (§C) |
| 17 | `operator_approval_ref` valid identifier accepted, no operator approval implied | Shape only (§I.2 #9) |

### L.5 Timestamp Violations

| # | Test | Validates |
|---|---|---|
| 18 | Fractional second `2026-07-30T06:25:18.123Z` → rejected | Timestamp (§D) |
| 19 | Offset `2026-07-30T06:25:18+00:00` → rejected | Timestamp (§D) |
| 20 | Invalid date `2024-02-30` → rejected | Timestamp (§D) |
| 21 | Space separator `2026-07-30 06:25:18Z` → rejected | Timestamp (§D) |
| 22 | Missing seconds `2026-07-30T06:25Z` → rejected | Timestamp (§D) |
| 23 | Non-UTC timezone `2026-07-30T06:25:18UTC` → rejected | Timestamp (§D) |
| 24 | Year `0000` timestamp → rejected | Timestamp (§D — year must be 0001–9999) |

### L.6 Duplicate-Key Violations

| # | Test | Validates |
|---|---|---|
| 25 | Raw JSON with duplicate top-level key → rejected | Duplicate-key (§H) |
| 26 | Raw JSON with duplicate key inside `provenance_material` → rejected | Duplicate-key (§H) |
| 27 | Normalized dict with no duplicate keys → accepted when raw JSON also had none | Duplicate-key (§H) |

### L.7 Value Constraint Violations

| # | Test | Validates |
|---|---|---|
| 28 | Wrong schema version `"v2"` → rejected | Schema literal (§I.2 #5) |
| 29 | Wrong domain separator `"PROVENANCE_V2"` → rejected | Domain literal (§I.2 #6) |
| 30 | `canonical_name` is `"Nope"` → rejected | Canonical name (§I.2 #10) |
| 31 | `canonical_name` is `"adam"` (lowercase) → rejected | Canonical name (§I.2 #10) |
| 32 | `source_artifact_integrity_id` has uppercase hex → rejected | Digest format (§I.2 #12) |
| 33 | `source_artifact_integrity_id` is not 64 chars → rejected | Digest format (§I.2 #12) |

### L.8 Commitment and Cross-Domain

| # | Test | Validates |
|---|---|---|
| 34 | Commitment digest matches presented `provenance_commitment` → accepted | Commitment check (§I.3 #14) |
| 35 | Commitment digest does not match presented commitment → rejected | Commitment check (§I.3 #14) |
| 36 | Envelope with correct provenance domain separator but substituted into rollback slot → rejected | Cross-domain (§I.5 #19) |
| 37 | Envelope hash changed after mutation of any field → different commitment | Immutability/collision |

### L.9 Authorization Boundaries

| # | Test | Validates |
|---|---|---|
| 38 | Valid envelope + valid commitment → creation still unauthorized, Gate-7 still closed | Non-authority (§J.2) |
| 39 | `operator_approval_ref` passes shape check → no authority implied | Shape only (§F.1) |
| 40 | `operator_approval_ref` fails shape check → envelope rejected | Shape only (§F.1) |

---

## M. Forbidden Actions

Under this spec and all preceding First Pair preflight specs:

- Creating Adam or Eve runtime entities
- Opening Gate-7 (no network egress/ingress, no daemon, no scheduler, no
  provider, no container, no Docker)
- Writing to `world-sim/data`
- Implementing, altering, or recurring into 10HD (10HD remains named-only;
  recursion spine is separate)
- Granting write authority to Adam, Eve, or any new writer (10CP remains the
  sole writer)
- Model/provider autonomy (no model may choose actions, writes, or ticks)
- Runtime self-scheduling (no self-initiated ticks)
- Any write without an explicit per-call allow-list and provenance chain
- Silent replacement or aliasing of provenance material
- Implementing a runtime source-envelope validator under 10IL
- Claiming that a valid envelope proves operator approval, creation authority,
  or `world-sim/data` write authorization

---

## N. Phase Index

This phase receives a single `phase_index.md` row marked **Done**. The 10IL
row's Commit cell records the merge commit that placed the 10IL specification
on master (7-char lowercase hex). The row's Notes cell records the document's
LF-only SHA-256. Post-push synchronization follows the established W4 workflow:
Commit A = content (this spec + consistency amendments to 10IG/10IF, excluding
`phase_index.md`), Commit B = index hash-correction (add 10IL row with real
merge SHA and document digest). No tests, no backend/runtime changes.
