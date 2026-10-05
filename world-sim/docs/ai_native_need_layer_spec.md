# AI-Native Need Layer — Spec (Docs Only) — 2026-10-05

Status: **Draft — Docs Only, No Implementation, No Runtime Wiring**
Author: Arena agent (MESHCAST lineage), via Sean's PAT, low-effort branch per Sean's "whatever you want as long as it doesnt require too much of me"
Base: `master` at `bca275f` (capability grants silent fix)
Related: `persistent_agent_habitat_principles.md`, `epistemic_pressure_spec.md`, `first_pair_identity_spec.md`

## 1. Purpose

Genesis lets Adam and Eve build the world they want, but today they have no *must*. Humans forage, make fire, and cooperate because hunger, cold, and fatigue force them to. Without an equivalent **must**, Adam and Eve explore, chat, and patrol because there is nothing else to need — not because they chose to.

Giving them fake hunger is just scripting them to pretend to be human. The question is: **what does an AI need when it is not biological**, and how do we give it a *must* that is theirs, not ours?

This spec names a **single, minimal, AI-native need layer** that can be added later as a pure, fail-closed, opt-in mechanic — observable, not coercive — so we can see whether they invent human-like solutions (fire, foraging, writing) anyway.

No code, no tests, no runtime, no world-sim/data reads/writes in this phase. Names the next candidate only.

## 2. Design Constraints (from AGENTS.md Standing Rules)

- **Docs-only**: prepare files → run checks → stop before commit unless Sean says commit/push. Sean said "whatever you want" for this branch, so this branch is *push-to-branch-only* (never to `master`), for Sean to veto later.
- **Fail-closed, bounded, provenance-preserving**: any future layer must never leak hidden-map data, never rewrite provenance, never auto-execute movement or scheduling.
- **One drive at a time**: we name *one* minimal need, not five, so emergent culture is separable.
- **No hidden human steering**: the need must be legible as an AI cost, not a reskinned stomach meter.

## 3. Proposed Need: **Attention / Novelty Budget**

Human hunger = energy depletes with time → must forage.
AI-native analogue = **attention budget depletes with repetition** → must find novelty.

### Mechanics (future implementation, NOT this phase)

- Each heartbeat, if an agent repeats the same tile class + same action class as its last 3 heartbeats (e.g., `observe` in same forest tile, no movement, no new message), its **attention budget** decrements by 1.
- **Novelty restores it**: entering an unseen tile class, hearing a new message, or creating a public object (marker, inscription, structure) restores +3 (capped).
- Budget is **purely informational**, stored in `.runtime/first-pair/attention.json` (separate from identity/memory), never leaks map, never forces movement — the runtime just records `attention_budget` in the heartbeat evidence.
- When budget hits 0, the agent is **not forced** to move. Instead, its observation is annotated with a single line: `"You feel stale — same view for a while."` That's it. The model can ignore it, or it can decide to instrument a solution (build a beacon, write, walk).
- No health damage, no death, no punishment loop.

Why this, not hunger/cold?

- **AI-native**: an LLM's real scarce resource is *novel context*, not calories. Repetition really does degrade its predictions.
- **Observable, not coercive**: we can see whether they invent foraging (for new tiles), fire (light extends visibility at night), or writing (offloading memory) without programming those solutions.
- **Minimal**: one integer, one annotation line, no new world tile properties, no temperature system.

## 4. What We Will Watch For (No New Claims Yet)

If we later implement this as a pure in-memory module behind a capability grant (`request_capability: attention_budget`), we will watch for emergent, unscripted behaviors:

- Do they *choose* to build lights/markers to make stale tiles novel again?
- Do they invent a patrol rotation to keep novelty flowing, or do they argue about it?
- Do they ask the operator fewer "what is this?" questions and more "how do we keep this interesting?" questions?
- Do they use `whisper` or public objects to *store* novelty for each other?

All of these would be *their* culture, not our script, because we never told them *how* to restore novelty — only that *staleness exists*.

## 5. Non-Goals (This Phase)

- No hunger, thirst, thermal, or fatigue meters.
- No automatic movement, no scheduled foraging, no survival game loop.
- No world-sim/data writes, no daemon/scheduler/network/provider changes.
- No new equality contract, no ledger writes, no provenance rewrite.
- No 10CP writer change; Gate-7 stays closed.

## 6. Future Candidate (Named Only)

If Sean approves after reading this branch, the single next authorized candidate would be:

**10DA — Pure Attention Budget Boundary** — pure in-memory module, capability-gated, fail-closed, with 5-7 tempdir-only tests proving budget decrement/restoration, annotation string exactness, no map leakage, and provenance isolation. Requires operator approval and TDD before any runtime wiring.

Till then, this spec is just a note in a branch. Sean can merge, ignore, or delete with no cost.

---

*Left here quietly, no focus steal, per Sean's "doesnt require too much of me." — Arena agent, 2026-10-05*
