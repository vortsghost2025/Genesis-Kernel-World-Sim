# First Pair ABSENT State Commitment — Contract Specification

Unnumbered docs-only contract. This document specifies the semantics of the
canonical **ABSENT FIRST-PAIR STATE** commitment that grounds the rollback-anchor
`state_commitment` for the zero-write observe-only heartbeat. It does **not**
implement anything, does **not** authorize creation, does **not** open Gate-7,
does **not** modify `world-sim/data`, and does **not** implement 10IQ or 10HD.

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## 1. Purpose and Non-Purpose

### 1.1 Purpose

The birth-candidate rollback anchor (10IH) requires a `state_commitment` that is
exactly 64 lowercase hex (`_is_hex64`). Before any legitimate persisted
First-Pair authoritative state exists, no real `state_commitment` can be derived
from a state artifact. This contract defines a real, deterministic commitment
for the semantic:

> **ABSENT_FIRST_PAIR_STATE** — no persisted First-Pair authoritative state
> exists in the canonical persistence authority.

### 1.2 Non-Purpose (explicit non-guarantees)

This commitment does **NOT** establish:
- rollback execution or restore capability;
- a last-known-good state, backup, or recovery mechanism;
- operator approval or any authority for creation/write/runtime;
- freshness, uniqueness, non-replay, or expiry;
- that the canonical Persistence root contains any meaningful data beyond the
  absence itself;
- that the heartbeat or runtime is otherwise authorized.

It grounds only the `state_commitment` value for a phase in which the
authoritative First-Pair persistence surface is provably empty.

---

## 2. Logical First-Pair Persistence Authority

The logical authority for persisted First-Pair state is the set of records
managed by `FirstPairPersistenceStore` (`world-sim/backend/world/first_pair_persistence.py`).
This contract concerns only that authority's **presence or absence**, never its
contents.

---

## 3. Canonical Persistence Root Resolution

- `first_pair_persistence.py` `_DEFAULT_ROOT` (line 34) resolves to
  `world-sim/.runtime/first-pair/` as the single canonical persistence root.
- This contract adopts the **same resolution**: the canonical root is derived
  relative to the backend package location
  (`Path(__file__).resolve().parent.parent.parent / ".runtime" / "first-pair"`),
  matching `_DEFAULT_ROOT`.
- The public API accepts **no caller-supplied root** and cannot be redirected.
- The canonical root itself is **not** part of the commitment hash material
  (no machine-specific absolute path enters the committed bytes).

---

## 4. Complete Authoritative Record-File Set

The authoritative First-Pair record-file set is the union of the JSON record
files and the provenance append log written by `FirstPairPersistenceStore`
(`first_pair_persistence.py` lines 35–47):

```
identity.json
habitat.json
memory.json
world_state.json
goals.json
questions.json
heartbeat.json
runtime_policy.json
capability_grant.json
memory_summaries.json
relationship_ledger.json
memory_selection_manifest.json
provenance.jsonl
```

### 4.1 Why `provenance.jsonl` is included

`provenance.jsonl` is the append-only provenance/audit log of the same store and
can describe state-bearing actions. Its presence is authoritative evidence that
the persistence surface is non-empty, so it is included in the record set.

---

## 5. ABSENT_FIRST_PAIR_STATE — Exact Meaning

**ABSENT_FIRST_PAIR_STATE is true if and only if the canonical persistence root
contains no files whatsoever** (including no unrecognized/unknown file). It is
also true if the canonical persistence root does not exist.

This is intentionally conservative: **any file** present inside the canonical
persistence root — whether a known authoritative record or an unrecognized file —
means the surface is not authoritatively empty and the ABSENT commitment must
fail closed. Unknown files are never silently ignored.

The public absence check therefore reports, and treats as fail-closed, *every*
entry present under the root, not merely the enumerated authoritative file set.
The enumerated set (Section 4) is used only for the commitment material and for
clear diagnostics, not as the gate.

---

## 6. Exact Domain Separator

The commitment uses the domain separator:

```
GENESIS_FIRST_PAIR_ABSENT_STATE_V1
```

Rationale for this literal being a contract choice (not merely code-canon):
- It is distinct from the provenance domain
  `GENESIS_FIRST_PAIR_PROVENANCE_V1` (10IL §E, §J.1) and the rollback-state
  domain `GENESIS_FIRST_PAIR_ROLLBACK_V1` (10IO §E, §I.6).
- Distinct domains prevent cross-domain substitution (10IL §I.5, 10IO §I.6).
- Domain literals are chosen by this contract; no code path is treated as
  canonical solely because it hard-codes a value.

---

## 7. Exact Canonical JSON / Material

The commitment hashes exactly this material (a fixed dict, no entropy, no
timestamps, no paths):

```json
{
  "genesis": "first_pair",
  "schema_version": "first_absent_state.1",
  "domain_separator": "GENESIS_FIRST_PAIR_ABSENT_STATE_V1",
  "authoritative_state": "absent",
  "record_file_names": [<the sorted Section 4 record file names>],
  "record_files_present": []
}
```

---

## 8. Exact UTF-8 Bytes Hashed and Hex64 Derivation

1. Serialize the material (Section 7) deterministically:
   `json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
2. UTF-8 encode the resulting string.
3. Apply `hashlib.sha256`.
4. Return the full 64-character lowercase hex digest (no truncation).

The result is exactly 64 lowercase hex and satisfies the existing
`_is_hex64` contract used by the birth-candidate rollback anchor (10IC).

---

## 9. Exact `rollback_anchor_id` Semantics for this Absent-State Anchor

- `rollback_anchor_id` (10IH) is a caller-supplied safe identifier; it does not
  carry a persistence-presence meaning. This contract does **not** redefine it.
- For the zero-write absent-state anchor, a caller may use any structurally
  valid `rollback_anchor_id` that links to the enclosing canonical habitat.
  No uniqueness semantics are implied (10IH §12: uniqueness not enforced).
- The `state_commitment` that binds the anchor is exactly the Section 8 digest.
- This contract does not name a specific binding between `rollback_anchor_id`
  and the absent-state commitment; the value a caller selects for the anchor ID
  is out of this contract's scope.

---

## 10. Zero-Write / No-Initialization Rule

The commitment and absence-check operations:
- perform **zero** writes;
- never create a directory;
- never call `FirstPairPersistenceStore` (whose construction would create the
  root directory);
- never initialize First-Pair state;
- are pure and read-only.

---

## 11. Fail-Closed Behavior When Authoritative State Exists

If the canonical persistence root contains **any file** (authoritative record or
unknown), the ABSENT commitment MUST fail closed (raise an error) and MUST NOT
return a valid commitment.

A conforming chest exposes obligations:
- `assert_first_pair_persistence_empty()` returns a verdict where `ok` is True
  only when the root contains no files; reports any present files (known and
  unknown).
- `first_pair_absent_state_commitment()` raises on non-empty.

---

## 12. Unknown File Handling (explicit)

Any unrecognized file/directory entry inside the canonical persistence root is
treated as evidence that state exists. It is reported in the verdict's present
entries and forces fail-closed. It is never silently ignored.

---

## 13. Conformance Summary

| Obligation | Contract Rule |
|---|---|
| Root | fixed canonical root; no caller redirection |
| Presence gate | ANY file present → non-empty → fail closed |
| Known set | used for material/diagnostics only, not the gate |
| Hash material | no timestamps, no entropy, no machine path |
| Domain | `GENESIS_FIRST_PAIR_ABSENT_STATE_V1` (distinct) |
| Output | full 64 lowercase hex |
| Writes | zero |
| Rollback/restore/IQ/HD | not implemented by this contract |