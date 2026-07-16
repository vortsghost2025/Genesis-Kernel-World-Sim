# First Write-Authority Spec — Bounded Writes Before Creation

Unnumbered docs-only spec. This file defines the write-authority boundary the
first Genesis pair **must** satisfy before creation is ever authorized. It
does **not** implement any entity, does **not** authorize any write, does
**not** open Gate-7, does **not** modify `world-sim/data`, and does **not**
implement 10HD. Creation remains unauthorized; 10HD remains named-only; 10CP
remains the sole writer.

Reference: `world-sim/docs/roadmap_adam_eve_first_pair_preflight.md` lists
this spec as the fifth of six required future specs. It depends on the First
Pair Identity Spec, the First Habitat Boundary Spec, the First Heartbeat
Observation Spec, and the First Memory Boundary Spec.

## 1. Write Authority Is Explicit Authorization, Not Execution

- Write authority is **authorization to write**, not write execution. This
  spec defines the boundary that any future write phase must satisfy; it does
  not perform writes.

## 2. This Spec Does Not Authorize Any Write Yet

- No write of any kind is authorized by this document.
- Every future write still requires its own implementation spec, GPT-5.6
  Sol/Luna per AGENTS.md Rule 3, and explicit Sean approval.

## 3. Adam and Eve Receive No Write Authority From Prior Specs

- Identity (Section 1), habitat (Section 1), heartbeat (Section 1), and
  memory (Section 1) specs do **not** grant the pair write authority.
- The pair are not writers. The pair are bounded identities that may, in a
  future authorized phase, produce provenanced material that a writer
  consumes.

## 4. 10CP Remains the Sole Existing Writer

- 10CP remains the only module authorized to write to the world ledger
  (per `first_pair_identity_spec.md` Section 12). This spec introduces no
  new writer and does not modify the 10CP boundary.

## 5. Any Future Write Must Be Caller-Driven, Explicit, Bounded, Reversible, Provenanced

- **Caller-driven** — writes originate from a caller-supplied input, never
  from model/provider autonomy.
- **Explicit** — each writable surface is enumerated, not implied; anything
  not enumerated is forbidden by default.
- **Bounded** — writes affect only the named surface.
- **Reversible** — every write has a rollback path to a known-good state.
- **Provenanced** — every write carries a provenance chain with the correct
  `claim_scope`.

## 6. No Model/Provider May Choose Writes

- No model, no provider, no agent may select what gets written. Choice of
  writes is operator-authorized and caller-supplied, never model-chosen.

## 7. No Runtime Self-Scheduling May Trigger Writes

- No daemon, scheduler, or self-initiated tick may produce a write. Writes
  happen only when an explicit, externally-driven authorizing call is made.

## 8. No world-sim/data Write Is Authorized Here

- This spec writes nothing to `world-sim/data`. Any `world-sim/data` write
  requires a separate write-authority spec and explicit Sean authorization.

## 9. Allowed Future Write Surfaces (Only If Separately Authorized)

When a future write phase is explicitly authorized, only these surfaces may
be written:

- temp / proof artifact,
- sanitized public evidence reference,
- rollback anchor reference,
- future authorized world-ledger boundary,
- future authorized memory boundary.

Each is a bounded, provenanced reference, not raw hidden content.

## 10. Forbidden Write Surfaces

Excluded by default:

- `world-sim/data`,
- identity immutable fields (per `first_pair_identity_spec.md` Section 3),
- hidden true_map,
- private filesystem paths,
- provider / model config,
- daemon / scheduler / network / container / Docker,
- shared mutable identity store,
- unbounded transcript dump.

## 11. Required Write Preconditions

Before any future write may execute, all of the following must hold:

- valid identity (verified contract, `first_pair_identity_spec.md` Section 6
  drift checks pass),
- valid habitat (verified boundary, `first_habitat_boundary_spec.md` Section 9
  drift checks pass),
- valid observation boundary,
- valid memory boundary (`first_memory_boundary_spec.md` Section 14 drift
  checks pass),
- rollback anchor present,
- explicit write allow-list (enumerated per-call, not blanket),
- provenance chain on every item,
- sanitized output surface (no hidden true_map, private paths, secrets, or
  chain-of-thought).

## 12. Fail-Closed Cases

Any of the following fails closed — the write is rejected and the lane
returns to last known good:

- Missing write allow-list — no explicit enumeration for this write.
- Missing provenance — write item has no provenance chain.
- Identity drift — identity fails re-derivation
  (`first_pair_identity_spec.md` Section 6).
- Habitat drift — habitat fails boundary checks
  (`first_habitat_boundary_spec.md` Section 9).
- Memory boundary violation — write would breach the memory boundary
  (`first_memory_boundary_spec.md` Section 14).
- Attempted hidden true_map write.
- Attempted `world-sim/data` write (Section 8).
- Attempted network / provider / model call (Section 6).
- Attempted daemon / scheduler / container / Docker action (Section 7).
- Missing rollback anchor — no known-good state to revert to.

## 13. Creation Remains Unauthorized

This spec does **not** authorize creating Adam or Eve. Write authority is a
precondition for any future write phase, not for pair creation itself.
Creation still requires GPT-5.6 Sol/Luna per AGENTS.md Rule 3 and explicit
Sean approval (`first_pair_identity_spec.md` Section 10). None are met by
this document.

## 14. 10HD Remains Named-Only and Untouched

10HD is the candidate named by 10HB (`e3042c7`) as a meta-meta-meta-verifier
over 10GX.1 meta-meta-verification output. This spec does **not** implement,
alter, supersede, or recur into 10HD. 10HD stays named-only and untouched.
The recursion spine is a separate branch of the chain from the first-pair
life branch.

## 15. 10CP Remains the Sole Writer

No new writer is introduced. 10CP remains the only module authorized to write
to the world ledger. Any future write phase, when authorized, defines a
consumed surface — not a competing writer. This spec does not modify the 10CP
boundary, does not name any specific ledger adapter as a dependency, and does
not grant write authority to anybody, including the pair themselves.
