# Crossroads Experiment Spec — A/B the Negotiation Scaffold

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-09-29
**Origin:** Sean's crossroads: "we ask them to act human with no instructions
while being agents with stripped abilities — wandering, looking for what?"
plus the outsider's joint-need read (folded into the continuity slot), plus
the null-result discipline (Phase B proved slot-only ≠ use).

---

## 0. The three-layer scoping — and why this is not a mechanic

Every prior physics change was a *thing* (build, hunger, weather) or an
*authorize* (movement). This one is different in kind: it is a **scaffold for
the thing that agents already do**. The lessons:

- **Phase B anchors** (record of what the agent wrote down): null, and most
  rolls went unused — because nothing ever *asked* for them.
- **Build gates** (retired hunger-consumption): failed because a gate answers
  a want that doesn't exist (nothing to eat is a world that doesn't feed).
- **Operator ask/answer loop** (food mechanics): worked because agents asked
  when something did not make sense *to them*, not because the prompt told
  them to.

The crossroads answer is not another verb or pressure. It is a *world that
needs two of them to keep moving* — a reason to coordinate that they can see
without an instruction.

Concretely, from the pair's spot:

> The ledger holds two columns, not one. Your half is what you remember;
> our half is what we agree exists. When we disagree, we check the ledger —
> but the ledger only knows what we *wrote down*. Wandering tiles is how we
> find each other, not what we're for.

The scaffold says that literally: half the map belongs to each, exchange
matters, and the ledger is the shared record. A pair that never writes
*understands nothing yet disagreeing about it* — which is exactly where the
charter, anchors, and continuity slot live in the same shape: *nothing tells
them the slot exists until they use it*.

## 1. What runs (the frozen pair control + two fresh pair treatment)

- **Control (existing):** east and west resume/freeze untouched — continuity
  census continues on the existing stores (now at 1043→1143 chain + west
  941→1043 catch-up).
- **Treatment:** TWO fresh-pair stores, created by `initialize_first_pair_state` —
  the same seam that already produced both first-pair lines — seeded identically
  at heartbeat 0 with negotiation scaffolding only. No world diff, no changed
  physics, no weather, no thirst. Same verbs.

The two treatment stores get **different prompt faces of the same scaffold**:

| | `east-neg` vs `west-neg` | presents |
|---|---|---|
| `east-neg` | "**A ledger exists between you two.** Your half is your memory; ours is what you agree exists. When you disagree, the ledger tells you what was written — and only what was written. | direct-abstraction |
| `west-neg` | "**There are two of you, and the world won't move one heartbeat without an agreement.** You'll know the world has uncertain rules until you've settled them together. | joint-necessity |

Same words that must be true, different emphasis — tests whether the *shape*
(agreement as the world's protocol vs necessity as its precondition) changes
what happens.

Each agent gets the scaffold in its prompt (normal section, same budget as
physics version notice), first-render only, and the runtime records every
heartbeat of each. From first move onward, nothing else differs.

## 2. Falsification (before any data exists)

| signal | control (this week) | treatment expectation | measurement |
|---|---|---|---|
| agenda emergence | exploration-survey only | "ledger/agreement/shared" themes in messages | message motifs |
| dual-authored object rate | 1 per 40 heartbeats | rises meaningfully | objects per heartbeat |
| joint-mentioning what done | messages echo or deflect 50/50 | deflect >60% within 50 HBs | causal message→action causal links |
| repeat-mention of same theme | message volume down 7x | recurrent named themes rise (requires continuity slot to see it) | detect_recurrence on sent messages |
| spurious asks | steady 0 | rises if agents invent constraints the scaffold doesn't carry | asks vs no-ask complaints |
| builds (any) | 0 per 100 | any | proves slot isn't enough alone |

**The decisive row:** do the two treatment stores produce *their own*
coordination language at all? If `east-neg`'s messages are Eve-heavy and
`west-neg`'s Adam-heavy on the exact same scaffold, that says the shape of
the world (where you start, what you see first) matters more than the words.
That's a finding worth preserving.

## 3. What this phase does NOT do

- No hunger, thirst, weather, or any mechanic referred to as "pressure" (they
  are retired, and they're not the target of this experiment).
- No new verbs. `leave_public_message`, `modify_owned_public_object`, `build`
  stay exactly as they are; the scaffold never names an action to take.
- No changes to the existing east/west stores until both chains finish their
  current arcs (east 1143, west 1043) — control integrity.
- No mixing: control pairs never see treatment, treatment stores never spill
  into east/west canonical state. Different scratch dir, different store, nothing
  in the shared world map.
- No operator assistance baked in (no answer-factors for the ledger; the
  scaffold is self-contained and the operators answer only if agents ask).

## 4. Architecture — what "new pair store" costs

`initialize_first_pair_state(store, declaration)` already creates a fresh
pair with deterministic identities from a declaration (same seam). The
experiment needs:

- two treatment stores (that is, two new `.runtime/…` dirs), seeded with the
  same declaration but different scaffold phrasing,
- a prompt shim that injects the scaffold section on first render with the
  same protect-shape as the physics version notice,
- a read-only observer script that dumps per-tick: tick, actions, message
  text tokens, objects created, extractive theme counts.

Everything else (chain, watcher, chain_watch, bridge, continuity, enablement)
stays untouched. The task is *spawn two pairs, freeze the world, give them
half a truth, see what they do.*

## 5. Boundary decisions this spec makes (not asks)

- The scaffold never mentions the operators, rotation, bridge, or census.
  The agents see only what "the world says about two people and a ledger."
- If either pair wedges (no actions, stuck loop, sentinel), the chain's
  fail-closed rule treats it as world-state mismatch, not a finding.
- Any run that ends with "they both finally asked something worth answering"
  is a signal the scaffold worked; the bridge answers as usual, truth-first,
  never strategy-instructions.

## 6. Decision requested

1. Approve two fresh pairs seeded identically with the scaffold (in the two
   phrasings), full 50-heartbeat census, before any code lands.
2. Confirm spawn direction: same declaration for both treatment stores, so the
   only variable is *how the world said what it needs.*
3. Confirm freeze: east and west current arcs run to finish before anything
   newer changes on their old history; the experiment runs alongside, never
   against, the canonical worlds.
4. Confirm the big question: "When both halves share a promise neither could
   have written, does the ledger become history, and does it change what
   they build?"