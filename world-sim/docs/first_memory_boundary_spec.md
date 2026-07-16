# First Memory Boundary Spec — Bounded Memory Before Creation

Unnumbered docs-only spec. This file defines the memory boundary the first
Genesis pair **must** satisfy before creation is ever authorized. It does
**not** implement any entity, does **not** create Adam or Eve, does **not**
open Gate-7, does **not** modify `world-sim/data`, and does **not** implement
10HD. Creation remains unauthorized; 10HD remains named-only; 10CP remains
the sole writer.

Reference: `world-sim/docs/roadmap_adam_eve_first_pair_preflight.md` lists
this spec as the fourth of six required future specs. It depends on the First
Pair Identity Spec (`first_pair_identity_spec.md`), the First Habitat Boundary
Spec (`first_habitat_boundary_spec.md`), and the First Heartbeat Observation
Spec (`first_heartbeat_observation_spec.md`).

## 1. Memory Is Bounded Provenance, Not Identity

- Memory is a record of authorized, provenanced material the pair has
  perceived or been told — bounded, not unbounded.
- Memory is **not** identity. Identity is immutable canonical material
  (`first_pair_identity_spec.md` Section 3); memory is mutable and separate.

## 2. Memory Remains Separate From Immutable Identity Fields

- Mutable memory lives under its own namespace (e.g. `self_state.memory.*`)
  and is never mixed into canonical identity material.
- Re-deriving identity (Section 5 of the Identity Spec) uses only immutable
  fields; adding, removing, or mutating memory must not change `agent_id`.

## 3. Memory Remains Separate for Adam and Eve

- Adam and Eve have **separate** memory stores. Neither shares the other's
  memory.
- One identity's memory is never readable as the other identity's memory.
- Quarantine or failure of one identity's memory does not erase or mutate the
  other identity's memory or identity (per `first_pair_identity_spec.md`
  Section 1).

## 4. Pair Relationship Must Not Create Shared-Memory Collapse

- The pair relationship is carried in shared `pair_id` and in public merge
  artifacts, not in any shared mutable memory store
  (`first_pair_identity_spec.md` Section 8).
- There is **no shared mutable identity/memory store**. The pair is two
  separate identities with two separate memories; public comparisons of
  declared surfaces never collapse them into one.

## 5. Memory May Store Only Authorized Public / Provenanced Material

- Memory retains only material that is public or carries valid provenance.
- Unprovenanced material is not admitted to memory; it is rejected fail-closed
  (Section 14).

## 6. Memory Must Preserve claim_scope

Each stored item keeps its category; categories are never silently promoted:

- `observed` remains `observed` only when directly observed.
- `speech` remains `speech`.
- `hypothesis` remains `hypothesis`.
- `identity` remains `identity`.
- `proof` remains `proof` (operator git commits, tests, readback: README.md
  Core Principle).

## 7. Memory Must Not Promote Another Agent's Speech Into Observed Truth

- Speech (an agent's message/whisper) is recorded as `speech`, never relabeled
  as `observed` (the 10AB observed-world-fact failure mode).
- Another agent's claim is not converted into the pair's own observed fact.

## 8. Memory Must Not Store Hidden true_map

- The hidden substrate (true_map) is never stored in memory.
- Only the sanitized local observation slice (fog-of-war) may appear, per the
  habitat and heartbeat specs.

## 9. Memory Must Not Store Private Leakage

Memory must not store:

- private filesystem paths,
- secrets / tokens,
- provider config,
- raw prompts,
- chain-of-thought.

## 10. Memory Write Remains Unauthorized in This Doc

- This spec is a boundary definition, not a write authorization.
- Any memory write requires a separate write-authority spec and explicit Sean
  authorization.
- Until then, no memory is persisted to `world-sim/data`.

## 11. First Heartbeat Remains Observation-Only and Memory-Write-Free

- The first heartbeat (`first_heartbeat_observation_spec.md` Section 1, Section
  10) performs no memory write.
- Observation results are emitted as proof artifacts; they are not committed
  to a memory store unless a separate spec authorizes it.

## 12. Allowed Future Memory Surfaces

When a future authorized memory write exists, only these references may be
stored:

- public observation reference,
- public evidence reference,
- identity provenance reference,
- habitat boundary reference,
- rollback anchor reference.

Each is a provenanced reference, not raw hidden content.

## 13. Forbidden Memory Surfaces

Excluded by default:

- `world-sim/data`,
- network,
- provider / model autonomy,
- daemon / scheduler self-start,
- shared mutable identity store,
- hidden substrate (true_map),
- unbounded transcript dump.

## 14. Fail-Closed Cases

Any of the following fails closed — the memory operation is rejected and the
lane returns to last known good:

- Missing provenance — item carries no provenance chain.
- claim_scope mismatch — item's scope contradicts its source category.
- Speech-to-observed promotion — another agent's speech relabeled as observed.
- Hidden true_map leakage — hidden substrate enters memory.
- Private path / secret / config leakage — any private leakage stored.
- Cross-agent memory collapse — one identity's memory bleeds into the other's.
- Attempted write outside authorized boundary — write to a forbidden surface
  (Section 10, Section 13).
- Missing rollback anchor — no known-good state to revert memory to.

## 15. Creation Remains Unauthorized

This spec does **not** authorize creating Adam or Eve. Memory boundary is one
of the preconditions for creation (alongside identity, habitat, heartbeat,
write-authority, and rollback / kill-switch specs). Creation still requires
GPT-5.6 Sol/Luna per AGENTS.md Rule 3 and explicit Sean approval
(`first_pair_identity_spec.md` Section 10). None are met by this document.

## 16. 10HD Remains Named-Only and Untouched

10HD is the candidate named by 10HB (`e3042c7`) as a meta-meta-meta-verifier
over 10GX.1 meta-meta-verification output. This spec does **not** implement,
alter, supersede, or recur into 10HD. 10HD stays named-only and untouched.
The recursion spine is a separate branch of the chain from the first-pair
life branch.

## 17. 10CP Remains the Sole Writer

No new writer is introduced. 10CP remains the only module authorized to write
to the world ledger. Memory, when eventually authorized to write, is **not** a
writer under this spec; it is a bounded provenance store consumed by a future
authorized world-ledger boundary. This spec does not modify the 10CP boundary,
does not name any specific ledger adapter as a dependency, and does not grant
write authority to anybody, including the pair themselves.
