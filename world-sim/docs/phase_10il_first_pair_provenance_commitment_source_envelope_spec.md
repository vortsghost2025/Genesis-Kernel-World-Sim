# Phase 10IL — First Pair Provenance Commitment Source-Envelope Specification

Numbered docs-only spec. This file closes the provenance_commitment source-envelope construction gap identified by 10IG §8 and 10IF. It defines the exact schema, field constraints, and validation behavior for the source envelope whose deterministic SHA-256 commitment forms the `provenance_commitment` field in the First Pair identity.

This spec is **docs-only**: it implements no module, adds no tests, performs no write, authorizes no persistence, creates no Adam/Eve runtime entity, does not modify 10CP, does not open Gate-7, does not implement or alter 10HD, and does not touch `world-sim/data`.

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## A. Title and Status

- **Title**: Phase 10IL — First Pair Provenance Commitment Source-Envelope Specification.
- **Status**: Docs-only specification.
- **Phase number**: 10IL. 
- **Boundary preservation**: Gate-7 remains closed. 10HD remains named-only. 10CP remains the sole writer. `world-sim/data` forbidden.

---

## B. Provenance Commitment Source-Envelope Definition

The `provenance_commitment` in the First Pair canonical identity (see 10IG) is a deterministic SHA-256 hash of a specific **Source Envelope**. This spec defines that Source Envelope.

### B.1 Source-Envelope Purpose and Trust Boundary

- **Purpose**: To provide a deterministic, audit-traceable source-of-truth for the `provenance_commitment` value, bridging the gap between operator-approved source material and the runtime identity commitment.
- **Trust Boundary**: The Source Envelope is operator-supplied and caller-presented. 10IL defines the schema and validation rules, but the content integrity is bounded by the operator's provenance-chain record (the source of the commitment) and not by any First Pair runtime module.

### B.2 Schema Literal and Version

- **Provenance Domain Separator**: `"GENESIS_FIRST_PAIR_PROVENANCE_V1"`
- **Source-Envelope Schema Version**: `"first_provenance_envelope.1"`

---

## C. Source-Envelope Schema

The Source Envelope is an exact built-in Python `dict` containing **exactly** the following fields and no others:

| Key | Type | Constraint |
|---|---|---|
| `source_envelope_schema_version` | `str` | Must equal literal `"first_provenance_envelope.1"` |
| `domain_separator` | `str` | Must equal literal `"GENESIS_FIRST_PAIR_PROVENANCE_V1"` |
| `source_ref` | `str` | Approved safe-identifier (1-128 chars, safe alphabet) |
| `source_timestamp` | `str` | ISO 8601 UTC string (e.g., `YYYY-MM-DDTHH:MM:SSZ`) |
| `provenance_material` | `dict` | Canonical provenance record (see Section D) |

---

## D. Provenance Material

The `provenance_material` is an exact built-in Python `dict` containing **exactly** the following fields:

| Key | Type | Constraint |
|---|---|---|
| `canonical_name` | `str` | `"Adam"` or `"Eve"` |
| `source_artifact_id` | `str` | Approved safe-identifier |
| `source_artifact_integrity_id` | `str` | 64-character lowercase hexadecimal SHA-256 |
| `operator_approval_id` | `str` | Approved safe-identifier |

---

## E. Canonical Serialization and Hashing

### E.1 Canonical Serialization

Deterministic JSON:
```python
json.dumps(
    source_envelope,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
```

### E.2 Hash Algorithm

1. Serialize the envelope using E.1.
2. UTF-8 encode the resulting string.
3. Apply `hashlib.sha256`.
4. Output the full 64-character lowercase hex digest.

This digest **is** the `provenance_commitment` value used in the First Pair `agent_id` derivation (10IG).

---

## F. Validation Rules and Fail-Closed Behavior

The future validator (or an operator auditing a pair) must reject any Source Envelope that:

1. Fails the exact-key-set rule for the envelope or the material.
2. Contains any extra or missing key.
3. Contains any key not of built-in type `str` (or `dict` for the nested material).
4. Fails literal constraints (`version`, `domain_separator`, `claim_scope`).
5. Fails `_is_safe_identifier` for `source_ref`, `source_artifact_id`, or `operator_approval_id`.
6. Fails the 64-char lowercase hex check for `source_artifact_integrity_id`.
7. Fails canonical hashing: the re-computed SHA-256 of the presented envelope does not equal the commitment presented in the `agent_id` material.
8. Contains duplicate keys (resolved during parsing).

Fail-closed: "Invalid provenance envelope; identity commitment rejected."

---

## G. Trust Separation

### G.1 Provenance Commitment vs. State Commitment

The `provenance_commitment` (this envelope) and rollback `state_commitment` (10IH) remain **separate trust domains** unconditionally.
- They must use different domain separators (Section B.2).
- They must use different source-envelope schemas.
- The `state_commitment` is **never** embedded in this provenance envelope, and this provenance envelope is **never** embedded in a `state_commitment` (they are separately required artifacts).

### G.2 Integrity vs. Authority

Provenance validation is **not** an assertion of authority:
- The provenance envelope defines the commitment's **integrity** and **derivation**, not its **authorization**.
- A valid provenance envelope is a prerequisite for candidate material validation; it does not authorize creation, nor does it grant `world-sim/data` write authority.
- The `claim_scope` / `operator_proof` association defines classification, not authorization.

---

## H. Forbidden Actions

Under this spec and all preceding preflight specs:
- No creation of Adam/Eve runtime entities.
- No opening of Gate-7.
- No writing to `world-sim/data`.
- No modification of 10IC/10ID/10IE/10IF/10IG/10IH.
- No runtime self-scheduling.
- No silent replacement/aliasing of provenance material.

---

## I. Phase Index

This phase receives a single `phase_index.md` row marked **Done**. The 10IL row's Commit cell records the merge commit that placed the 10IL specification on master (7-char lowercase hex), and the Notes cell records the document's LF-only SHA-256. Post-push synchronization follows the established W4 workflow (Commit A = content, Commit B = index hash-correction). No tests, no backend/runtime changes.
