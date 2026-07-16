# First Habitat Boundary Spec — Adam/Eve Habitat Before Creation

Unnumbered docs-only spec. This file defines the habitat boundary the first
Genesis pair **must** satisfy before creation. It does **not** implement
any entity, does **not** authorize creation, does **not** open Gate-7, does
**not** modify `world-sim/data`, and does **not** implement 10HD. Creation
remains unauthorized; 10HD remains named-only; 10CP remains the sole writer.

Reference: `world-sim/docs/roadmap_adam_eve_first_pair_preflight.md` lists
this spec as the second of six required future specs. `world-sim/docs/
first_pair_identity_spec.md` (Section 1, Section 12) defines the identity
contract the habitat must bind to.

## 1. Habitat Is a Bounded Simulation Space, Not Runtime Autonomy

- The habitat is a **bounded simulation space** the first pair may act
  within — a defined, sanitized surface with explicit walls.
- It is **not** runtime autonomy. A habitat does not grant the pair the
  right to self-schedule, to choose their own ticks, or to act outside the
  authorized surface.
- A habitat is a constraint envelope. Inside it, the pair is bounded; outside
  it, the pair does not exist as an acting entity.

## 2. Habitat Must Exist Before First Heartbeat

- No heartbeat (no tick, no observation, no action) may occur before a
  habitat boundary is defined and verified.
- The first heartbeat runs **inside** an already-defined habitat. The habitat
  is a precondition, not a consequence, of the first tick.
- A heartbeat without a habitat is an undefined-action and must fail closed
  (see Section 9).

## 3. Habitat Binds Identities to an Allowed Surface

- The habitat binds the canonical identities from `first_pair_identity_spec.md`
  (Section 1, Section 3) to an allowed spatial / world surface.
- Identity is independent of habitat content, but the pair's acting surface
  is bounded by the habitat. Identity stays valid if the habitat is missing
  or quarantined (Section 8); the pair simply cannot act there.
- Each allowed surface is enumerated, not implied. Anything not enumerated is
  forbidden by default.

## 4. Habitat Must Not Be world-sim/data Yet Unless Separately Authorized

- The habitat boundary definition is a **spec and contract**, not a
  `world-sim/data` write.
- This spec writes nothing to `world-sim/data`. Any habitat persistence
  requires a separate write-authority spec and explicit Sean authorization.
- Until then, habitat state lives only in authorized temp / proof paths, not
  in the world ledger or world data.

## 5. Allowed Surfaces

Defined, enumerated surfaces only:

- **Public starting area / initial tile references** — the canonical starting
  tiles the pair may occupy at first heartbeat (declared, not discovered).
- **Observation boundary** — the slice of world the pair is allowed to observe
  (fog-of-war local observation, not hidden true_map).
- **Movement boundary** — the set of tile transitions the pair may perform,
  frozen to no free movement until separately specified (Section 10).
- **Memory boundary references** — the memory-boundary contract the pair's
  memory must respect (defined by a future First Memory Boundary Spec;
  referenced here, not defined).
- **Rollback anchor** — a known-good habitat state the pair may be reverted to
  (defined by a future First Rollback / Kill-Switch Spec; referenced here,
  required per Section 9).

## 6. Forbidden Surfaces

Excluded by default:

- **Network** — no egress, no ingress, Gate-7 closed.
- **Filesystem outside authorized temp / proof paths** — no arbitrary file,
  no project config, no `world-sim/data`.
- **Provider / model autonomy** — no model may choose habitat actions for the
  pair.
- **Daemon / scheduler self-start** — neither identity may start its own
  daemon, scheduler, or tick loop.
- **`world-sim/data` write** — no world data mutation from this spec or from
  the pair under it.
- **Gate-7** — Gate-7 stays closed by absence under this spec.

## 7. Identities Remain Independently Valid Inside the Habitat

- Adam and Eve remain independently valid canonical identities inside the
  habitat (`first_pair_identity_spec.md` Section 1).
- The habitat does not redefine, merge, or weaken their identity. Identity
  contract from the First Pair Identity Spec holds unchanged within the
  habitat boundary.

## 8. Pair-Scoped Habitat Operations

- Pair-scoped habitat operations (e.g. a shared public starting area) may
  require both identities.
- The absence, failure, or quarantine of one identity must not erase, mutate,
  or invalidate the other identity (per `first_pair_identity_spec.md`
  Section 1).
- One identity losing habitat access never takes the other identity down.
  Failures are scoped to the affected identity; the other remains valid.

## 9. Habitat Drift Detection — Fail Closed

Any of the following is habitat drift and must fail closed:

- **Unknown tile** — the pair references a tile outside the allowed surface.
- **Unauthorized expansion** — the habitat surface grows beyond its declared
  enumeration without a new authorized spec.
- **Missing rollback anchor** — no known-good habitat state is available to
  revert to.
- **Missing observation boundary** — no defined observation slice exists.
- **Hidden true_map leakage** — hidden substrate (true_map) appears in any
  public or pair-visible output.
- **Write attempt outside allowed boundary** — any write to a forbidden
  surface (Section 6).

Rejection is immediate and absolute. On drift, the affected lane returns to
the last known good habitat state and does not act under a drifted habitat.

## 10. First Habitat Is Observation-First

The first habitat admits only observation first:

- **No gather** — no resource gathering.
- **No whisper** — no inter-agent speech events.
- **No autonomous route planning** — no pathfinding, no route intent creation.
- **No free movement** — no movement until a separate movement boundary spec
  authorizes it.

The first heartbeat is `observe` only, inside the observation boundary, with
no side effects outside the allowed surface.

## 11. Creation Remains Unauthorized

This spec **does not authorize creating Adam or Eve**. It defines the habitat
contract that must hold before any creation phase. Creation requires the
preconditions listed in `first_pair_identity_spec.md` Section 10 plus a
verified habitat, a heartbeat observation spec, a memory boundary spec, a
write-authority spec, and a rollback / kill-switch spec, with GPT-5.6 Sol/Luna
per AGENTS.md Rule 3 and explicit Sean approval. None are met by this
document.

## 12. 10HD Remains Named-Only and Untouched

10HD is the candidate named by 10HB (`e3042c7`) as a meta-meta-meta-verifier
over 10GX.1 meta-meta-verification output. This spec does **not** implement,
alter, supersede, or recur into 10HD. 10HD stays named-only and untouched.
The recursion spine is a separate branch of the chain from the first-pair
life branch.

## 13. 10CP Remains the Sole Writer

No new writer is introduced. 10CP remains the only module authorized to write
to the world ledger. Habitat definitions, when eventually implemented, are
**not** writers; they are a boundary contract that may be consumed by a future
authorized world-ledger boundary. This spec does not modify the 10CP boundary,
does not name any specific ledger adapter as a dependency, and does not grant
write authority to anybody, including the pair themselves.
