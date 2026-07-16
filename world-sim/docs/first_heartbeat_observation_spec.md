# First Heartbeat Observation Spec — Observation-Only First Tick

Unnumbered docs-only spec. This file defines the first heartbeat as an
observation-only tick the first Genesis pair must satisfy before creation is
ever authorized. It does **not** implement any entity, does **not** create
Adam or Eve, does **not** open Gate-7, does **not** modify `world-sim/data`,
and does **not** implement 10HD. Creation remains unauthorized; 10HD remains
named-only; 10CP remains the sole writer.

Reference: `world-sim/docs/roadmap_adam_eve_first_pair_preflight.md` lists
this spec as the third of six required future specs. It depends on the First
Pair Identity Spec (`first_pair_identity_spec.md`) and the First Habitat
Boundary Spec (`first_habitat_boundary_spec.md`).

## 1. First Heartbeat Is Observation-Only

- The first heartbeat is a single `observe` tick. Nothing else.
- No gather, no whisper, no movement, no route planning, no memory write, no
  world ledger write (see Section 10).
- The first heartbeat proves the identity + habitat contract can produce a
  sanitized observation without side effects. It creates no living entity and
  no state outside the allowed surface.

## 2. First Heartbeat Requires a Valid First-Pair Identity Contract

- A valid identity contract (per `first_pair_identity_spec.md` Section 1,
  Section 3) must be present and verified before the first heartbeat runs.
- Missing or drifted identity fails closed (Section 11).
- Each observing identity remains independently valid; one identity failing
  does not invalidate the other (`first_pair_identity_spec.md` Section 1).

## 3. First Heartbeat Requires a Valid First Habitat Boundary

- A valid habitat boundary (per `first_habitat_boundary_spec.md` Section 3,
  Section 5) must exist before the first heartbeat (habitat precedes first
  tick, per Section 2 of that spec).
- The heartbeat observes only within the habitat's observation boundary.
- Missing or drifted habitat fails closed (Section 11).

## 4. First Heartbeat Must Not Create Adam/Eve Runtime Entities

- The heartbeat is a verification of contract-readiness, not a birth event.
- No Adam/Eve runtime entity is created, scheduled, or persisted by this
  spec.
- Creation remains unauthorized (`first_pair_identity_spec.md` Section 10).

## 5. First Heartbeat Must Not Write world-sim/data

- This spec performs no `world-sim/data` write.
- Any data produced lives only in authorized temp / proof paths, never in
  the world ledger or world data, unless a separate write-authority spec is
  authorized.

## 6. First Heartbeat Must Not Open Gate-7

- Gate-7 stays closed by absence. No daemon, scheduler, network, provider, or
  container is started or contacted.

## 7. First Heartbeat Must Not Use Provider/Model Autonomy

- No model or provider chooses the observation, the tick, or any action.
- The heartbeat is caller-driven: inputs are caller-supplied (Section 8); the
  tick is a caller-supplied value, not model-selected.
- Any attempted model/provider call fails closed (Section 11).

## 8. Allowed Inputs

- Canonical identity references (the two canonical identities from the
  verified identity contract).
- Verified habitat boundary (the allowed surface, observation boundary, and
  rollback anchor).
- Observation boundary (slice of world the pair may observe).
- Rollback anchor (known-good habitat state to revert to).
- Caller-supplied tick number (a deterministic input; not model-chosen).

No other inputs are permitted. Inputs are read-only references, not live
connections.

## 9. Allowed Outputs

- A sanitized observation result (local fog-of-war observation only, never
  hidden true_map).
- A public evidence / proof artifact proving the observation ran under the
  verified identity + habitat contract.
- No hidden true_map in any output.
- No private filesystem paths in any output.
- No secrets / tokens / raw config in any output.

## 10. Forbidden Actions

Excluded by default:

- No gather.
- No whisper.
- No movement.
- No route planning.
- No memory write.
- No world ledger write.
- No daemon / scheduler / network / provider / container / Docker work.

## 11. Fail-Closed Cases

Any of the following fails closed — the heartbeat does not run, and the
affected lane returns to the last known good:

- Missing identity — no valid identity contract present.
- Identity drift — present identity fails re-derivation
  (`first_pair_identity_spec.md` Section 6).
- Missing habitat — no valid habitat boundary present.
- Habitat drift — present habitat fails its boundary checks
  (`first_habitat_boundary_spec.md` Section 9).
- Missing rollback anchor — no known-good state to revert to.
- Missing observation boundary — no defined observation slice.
- Hidden true_map leakage — hidden substrate appears in any output.
- Attempted write — any write to a forbidden surface (Section 10).
- Attempted model / provider call — any autonomous model or provider
  invocation (Section 7).

## 12. Creation Remains Unauthorized

This spec does **not** authorize creating Adam or Eve. The first heartbeat is
an observation-only verification of contract readiness. Creation still
requires all preconditions in `first_pair_identity_spec.md` Section 10 plus a
verified habitat, a memory boundary spec, a write-authority spec, and a
rollback / kill-switch spec, with GPT-5.6 Sol/Luna per AGENTS.md Rule 3 and
explicit Sean approval. None are met by this document.

## 13. 10HD Remains Named-Only and Untouched

10HD is the candidate named by 10HB (`e3042c7`) as a meta-meta-meta-verifier
over 10GX.1 meta-meta-verification output. This spec does **not** implement,
alter, supersede, or recur into 10HD. 10HD stays named-only and untouched.
The recursion spine is a separate branch of the chain from the first-pair
life branch.

## 14. 10CP Remains the Sole Writer

No new writer is introduced. 10CP remains the only module authorized to write
to the world ledger. The first heartbeat, when eventually implemented, is
**not** a writer; it is an observation-only read under the verified identity
+ habitat contract, consumed by a future authorized world-ledger boundary.
This spec does not modify the 10CP boundary, does not name any specific
ledger adapter as a dependency, and does not grant write authority to anybody,
including the pair themselves.
