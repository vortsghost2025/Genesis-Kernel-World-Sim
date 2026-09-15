# Phase 10HE — First Pair Heartbeat Activation Gate

Numbered docs-only working-tree artifact. Documents the readiness and the
activation protocol for the first observe-only Adam/Eve heartbeat, reconciled
against live source and the current (accepted-candidate) implementation. It
does **not** implement anything, does **not** execute a heartbeat in this
task, does **not** authorize Adam/Eve execution, and does **not** open Gate-7.

**FIRST_PAIR_CREATION_AUTHORIZED = False**
**GATE_7_OPENED = False**
**REAL_HEARTBEAT_EXECUTED (in this task) = False**

---

## 1. Header / Readiness

Reconciled readiness status:

- **10IN** = IMPLEMENTED AND TESTED
- **10IQ** = HELD_AS_SPECIFIED_PENDING_REAL_STATE_ARTIFACT
- **ABSENT_STATE_CONTRACT** = IMPLEMENTED AND TESTED
- **HEARTBEAT** = EXISTING

**10IQ is NOT a blocker for this zero-write null-baseline heartbeat.** 10IQ
need not ship before 10HE.

Model note: the implementation phases underlying the accepted-candidate
modules were exercised under the **explicit operator model-policy override**
already granted to DeepSeek for this bounded First-Pair work. This document
records that override as exercised; it does **not** create a permanent blanket
model-policy change.

---

## 2. Readiness — Now Real

The previously missing inputs now exist.

- **Adam provenance commitment**:
  `691e3c72e1318e7724c2625c03b7b7c2b04ede5f4da9eca9c252732d631238aa`
- **Eve provenance commitment**:
  `3df3c9d905d99a7bc930ad1c61dcab27364d24e581f70a7603da5a9f8a1bef3c`
- **Operator approval ref**:
  `8dc714f3a66975eb2543ca780f59e35d9af02e93`
  (operator-proof docs commit `docs: record first-pair provenance approval`)
- **Provenance source artifact**:
  `world-sim/docs/first_pair_identity_spec.md`
- **Source SHA-256**:
  `360e1c916afa9bc1e1d792e90ebb0b46afe7bec07f7a7db8e80d85aa2fceaac4`
- **Rollback state for THIS zero-write phase**:
  the canonical ABSENT_FIRST_PAIR_STATE commitment mechanism
  (`world-sim/backend/world/local_first_pair_absent_state.py`).
- **10IE**: explicitly **NOT consumed** for this activation.
- **Tick**: `0` is used because it is the existing exercised value. Tick `0`
  is **not** asserted globally canonical unless live source establishes that.

Both envelopes share the same approved source artifact, source SHA-256,
operator approval ref, authorization timestamp, `source_ref` and
`source_artifact_id`; they differ through `canonical_name` (`Adam` vs `Eve`).

---

## 3. 10IN — Actual Semantics

The earlier invented batch API is superseded. Actual 10IN semantics:

- raw UTF-8 JSON input, **one envelope per identity**;
- Adam and Eve independently validated (two separate envelopes);
- duplicate-key rejection at the **raw JSON parsing boundary**
  (`object_pairs_hook`), nested-object-inclusive;
- `provenance_commitment = SHA256(canonical JSON envelope)`
  (`sort_keys=True`, `separators=(",",":")`, `ensure_ascii=False`);
- integrity-of-declared-material only;
- **no** authority, truthfulness, freshness, or operator-authentication
  guarantee.

Actual implementation:
`world-sim/backend/world/local_first_pair_provenance_envelope.py`.

Actual focused tests: **8 passed**.

The earlier ~30–40 test proposal is not preserved.

---

## 4. 10IQ — Held, Not Required Here

**10IQ_HELD_AS_SPECIFIED_PENDING_REAL_STATE_ARTIFACT.**

Reason: current 10IQ only re-attests caller-declared state-artifact integrity
and cannot ground rollback in actual state bytes. For the pre-persistence
zero-write heartbeat, the legitimate state condition is **verified absence**,
not a fabricated state artifact.

10IQ is **not** implemented in this document and is **not** a prerequisite for
this zero-write null-baseline heartbeat.

---

## 5. ABSENT-FIRST-PAIR-STATE — Actual Implementation

- Contract:
  `world-sim/docs/first_pair_absent_state_contract_spec.md`
- Implementation:
  `world-sim/backend/world/local_first_pair_absent_state.py`

Required invariant:
> ABSENT iff the canonical `world-sim/.runtime/first-pair` authority contains
> ZERO entries.

- Any recognized or unknown entry ⇒ **fail closed** (never silently ignored).
- No state initialization, no directory creation, no write, no caller-selected
  alternate persistence root.
- Domain separator: `GENESIS_FIRST_PAIR_ABSENT_STATE_V1`.
- `state_commitment` remains a deterministic lowercase hex64.

No rollback-restore semantics are invented. `rollback_anchor_id` remains a
caller-supplied safe identifier under 10IH; the absent-state helper does **not**
derive it.

Public API (read-only, unredirectable):
- `first_pair_absent_state_commitment() -> hex64` (raises if any entry present)
- `assert_first_pair_persistence_empty() -> verdict dict`

---

## 6. Activation Protocol

The future controlled activation sequence (rewritten against live source):

**PRE**
1. Verify source artifact SHA-256 still equals the approved SHA
   (`360e1c916afa9bc1e1d792e90ebb0b46afe7bec07f7a7db8e80d85aa2fceaac4`).
2. Verify the operator-proof commit exists
   (`8dc714f3a66975eb2543ca780f59e35d9af02e93`).
3. Revalidate the Adam raw provenance envelope and commitment.
4. Revalidate the Eve raw provenance envelope and commitment.
5. Verify the canonical `.runtime/first-pair` authority has zero entries.
6. Derive/verify the canonical absent-state `state_commitment`
   (`first_pair_absent_state_commitment()`).
7. Construct a 10IC-valid rollback anchor using that commitment and an
   explicitly selected safe `rollback_anchor_id`.
8. Construct the canonical Adam birth candidate/declaration.
9. Construct the canonical Eve birth candidate/declaration.

**RUN**
10. Invoke the existing `verify_first_pair_observation_heartbeat` for Adam,
    tick `0`.
11. Invoke the existing `verify_first_pair_observation_heartbeat` for Eve,
    tick `0`.

**POST**
12. Require both proofs `ok=True` and `verified_observation_only`.
13. Require every inert/write/gate flag remains `False`.
14. Re-enumerate the canonical `.runtime/first-pair` authority.
15. Require zero entries remain.
16. Re-run focused + 10IC regression tests.
17. Confirm `FIRST_PAIR_CREATION_AUTHORIZED=False`.
18. Confirm Gate-7 remains closed.

Explicit non-requirements (do **not** require):
- `derive_first_pair_rollback_state_commitment` (not used);
- 10IQ implementation;
- a new heartbeat wrapper;
- a new decision-log framework;
- a `FIRST_PAIR_HEARTBEAT_ACTIVATED` flag.

Evidence-record convention: the existing durable convention is the
**`operator_proof` claim_scope** — "Git commits, test output, or readback
verification" (`persistent_agent_habitat_principles.md`; `genesis_canon_boundaries.md`).
That existing convention is used for evidence; 10HE does **not** invent a new
durable activation-gate record. Git status is **not** used as persistence
proof — persistence is proven by the zero-entry invariant of the canonical
authority, not by the index state.

---

## 7. Verifier Governance

Replace "permanently dead-stopped" with:

> **VERIFIER_RECURSION = STOPPED_AT_10HD**

No verifier-over-verifier successor unless all three hold:
1. a concrete new trust boundary exists;
2. source evidence shows the underlying input cannot be validated directly;
3. explicit operator approval is given.

---

## 8. Removed Non-Engineering Causal Claims

This document contains engineering history only. It removes memory-loss
explanations, Past-Sean / Present-Sean framing, emotional-ceremony rhetoric,
and speculation about why the operator personally built verifier layers.
Those are out of scope for a source-grounded activation gate.

---

## 9. Status of This Artifact

This is a working-tree docs artifact only. It is **not committed** and **not
pushed** in this task. The five existing untracked blocker implementation/test
files remain uncommitted and untouched.

---

## Verification Summary (in this task)

- 10IN focused tests: 8 passed.
- absent-state focused tests: 10 passed.
- 10IC existing suite: 75 passed.
- Combined: 93 passed.
- `.runtime/first-pair` authority: **ZERO entries**.
- The operator-proof approval commit exists; not pushed (`[ahead 1]`).
- No heartbeat executed; no state initialized; no Gate-7; authorization False.