# First Rollback / Kill-Switch Spec — Revert and Stop Before Creation

Unnumbered docs-only spec. This file defines the rollback and kill-switch
boundary the first Genesis pair **must** satisfy before creation is ever
authorized. It does **not** implement any entity, does **not** create Adam or
Eve, does **not** authorize any write, does **not** open Gate-7, does **not**
modify `world-sim/data`, and does **not** implement 10HD. Creation remains
unauthorized; 10HD remains named-only; 10CP remains the sole writer.

Reference: `world-sim/docs/roadmap_adam_eve_first_pair_preflight.md` lists
this spec as the sixth and final required preflight future spec. It depends
on the First Pair Identity Spec, First Habitat Boundary Spec, First Heartbeat
Observation Spec, First Memory Boundary Spec, and First Write-Authority Spec.

## 1. Rollback Is Mandatory Before Creation

- No creation phase may start until a verified rollback boundary exists.
- Rollback is a precondition for pair creation, not an afterthought.

## 2. Kill-Switch Is Mandatory Before Creation

- No creation phase may start until a verified kill-switch exists.
- A pair that cannot be stopped immediately is unsafe to start.

## 3. Rollback Means Revert to a Known-Good Pre-Action State

- Rollback reverts to a known-good state that existed **before** the action
  being rolled back.
- Rollback is not "destroy and recreate"; it is revert-to-anchor.

## 4. Kill-Switch Means Stop All Pair Activity Immediately Without Mutating Identity

- Kill-switch halts all pair action at once: no new ticks, no in-flight
  observations, no pending writes, no scheduled callbacks.
- Kill-switch does **not** mutate identity. Identity remains intact and
  re-derivable from canonical material (`first_pair_identity_spec.md`
  Section 3) after kill-switch fires.
- Kill-switch is not deletion; it is immediate cessation of activity.

## 5. Rollback Must Preserve Immutable Identity Fields

- Rollback never mutates the immutable identity fields (canonical_name,
  pair_id, founding_role, provenance_commitment — `first_pair_identity_spec.md`
  Section 3).
- A rollback that would alter identity is itself rejected as drift
  (`first_pair_identity_spec.md` Section 6).

## 6. Rollback Must Not Erase or Merge Adam/Eve Identities

- Rollback never collapses Adam into Eve, Eve into Adam, or either into a
  shared identity.
- The pair relationship (shared `pair_id`, public merge artifacts) survives
  rollback intact; identity separateness survives rollback
  (`first_pair_identity_spec.md` Section 8).

## 7. Rollback Must Preserve Pair Independence

- One identity's failure/quarantine must not invalidate the other identity
  (`first_pair_identity_spec.md` Section 1).
- Rollback can be scoped to one identity without erasing or mutating the
  other. Pair rollback (both at once) is allowed; asymmetric rollback is
  allowed; one-sided rollback never takes the other identity down.

## 8. Rollback Must Cover

Rollback to a known-good state must be able to revert:

- habitat boundary state,
- observation proof artifacts,
- memory boundary references,
- write-authority proof references,
- public evidence / proof artifacts.

## 9. Rollback Must Not Cover

Rollback is **not** responsible for mutating or undoing:

- hidden true_map mutation (hidden substrate is not pair state and must not
  be rolled back by the pair),
- unauthorized `world-sim/data` writes (those are rejected at write time,
  not rolled back by the pair),
- provider / model config,
- network state,
- daemon / scheduler / container / Docker state.

## 10. Kill-Switch Triggers

Kill-switch fires immediately on any of the following:

- identity drift (`first_pair_identity_spec.md` Section 6),
- habitat drift (`first_habitat_boundary_spec.md` Section 9),
- memory boundary violation (`first_memory_boundary_spec.md` Section 14),
- attempted write without allow-list (`first_write_authority_spec.md`
  Section 12),
- attempted `world-sim/data` write,
- hidden true_map leakage,
- private path / secret / config leakage,
- attempted model / provider autonomy,
- attempted daemon / scheduler / network / container / Docker action,
- missing rollback anchor (no known-good state to revert to).

## 11. Rollback Anchor Requirements

A rollback anchor must be:

- explicit (enumerated, not implied),
- caller-supplied or pre-authorized (never model-chosen),
- provenanced (carries a provenance chain with correct `claim_scope`),
- sanitized (no hidden true_map, no private paths, no secrets, no
  chain-of-thought).

An anchor missing any of these is treated as no anchor — and any operation
requiring an anchor fails closed.

## 12. First Creation Remains Unauthorized Until the Roadmap Plus All Six Preflight Specs Are Reviewed Together

- The roadmap is the **planning anchor**:
  - `roadmap_adam_eve_first_pair_preflight.md` (roadmap).
- The six required **preflight specs** are:
  1. `first_pair_identity_spec.md` (First Pair Identity Spec),
  2. `first_habitat_boundary_spec.md` (First Habitat Boundary Spec),
  3. `first_heartbeat_observation_spec.md` (First Heartbeat Observation Spec),
  4. `first_memory_boundary_spec.md` (First Memory Boundary Spec),
  5. `first_write_authority_spec.md` (First Write-Authority Spec),
  6. this `first_rollback_kill_switch_spec.md` (First Rollback / Kill-Switch
     Spec) — the sixth preflight spec.
- Pair creation requires the roadmap **plus** all six preflight specs to
  exist **and** to be reviewed together before any implementation phase
  begins.
- Creation still requires GPT-5.6 Sol/Luna per AGENTS.md Rule 3 and explicit
  Sean approval. None are met by the existence of this document alone.

## 13. This Spec Does Not Implement Rollback

- This document is a boundary definition, not an implementation.
- Implementing rollback requires a separate implementation phase, TDD, and
  explicit Sean authorization.

## 14. This Spec Does Not Implement Kill-Switch

- This document is a boundary definition, not an implementation.
- Implementing kill-switch requires a separate implementation phase, TDD, and
  explicit Sean authorization.

## 15. This Spec Does Not Create Adam/Eve

- No Adam/Eve runtime entity is created or authorized by this document.

## 16. 10HD Remains Named-Only and Untouched

10HD is the candidate named by 10HB (`e3042c7`) as a meta-meta-meta-verifier
over 10GX.1 meta-meta-verification output. This spec does **not** implement,
alter, supersede, or recur into 10HD. 10HD stays named-only and untouched.
The recursion spine is a separate branch of the chain from the first-pair
life branch.

## 17. 10CP Remains the Sole Writer

No new writer is introduced. 10CP remains the only module authorized to write
to the world ledger. Rollback and kill-switch, when eventually implemented,
are **not** writers; they are safety boundaries consumed by a future
authorized world-ledger boundary. This spec does not modify the 10CP
boundary, does not name any specific ledger adapter as a dependency, and does
not grant write authority to anybody, including the pair themselves.

## 18. Gate-7 Remains Closed

Gate-7 stays closed by absence under this spec. No daemon, scheduler,
network, provider, container, or Docker action is authorized or started.
Rollback and kill-switch are safety contracts, not execution surfaces.
