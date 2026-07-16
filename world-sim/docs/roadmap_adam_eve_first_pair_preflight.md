# Roadmap — Adam/Eve First Pair Preflight

Docs-only preflight planning document. This file does **not** implement any
entity, does **not** open Gate-7, does **not** modify `world-sim/data`, and
does **not** implement 10HD. It maps the road from the current verified
governance spine toward the first living Genesis pair.

## 1. Current Verified Checkpoint

- HEAD = `5f2d47d docs: record 10HC metadata hash`
- 10HB = `e3042c7` (Next Runtime Boundary Candidate Spec) — **closed**
- 10HC = `69b71d0` (Sync 10HB Metadata) — **closed**; 10HC hash-correction
  commit = `5f2d47d`
- 10HD = named-only candidate (meta-meta-meta-verifier over 10GX.1
  meta-meta-verification output) — **not implemented**
- Gate-7 = **closed by absence**
- 10CP = **sole writer**
- Recursion spine reaches 10GX / 10GR / 10GL / 10GF — authorization and
  verification depth is strong; **life depth is zero**.

## 2. What "Adam and Eve" Means in Genesis

Per `README.md` founding-agents section: Adam and Eve are simulation
entities with canonical identities, continuity across cycles, and bounded
perception. They are not religious figures, not real-world authorities, and
not conscious beings.

- **First paired entities** — two bounded identities, not one, not many.
- **First bounded identities** — canonical `agent_id`s, continuity across
  cycles, no identity drift.
- **First habitat-bound actors** — their actions are confined to a defined
  habitat boundary, not the open filesystem or network.
- **Not free agents** — no autonomous goal selection.
- **Not internet agents** — no network egress.
- **Not autonomous runtime yet** — no self-initiated ticks.

## 3. Preconditions Before Creation

Every precondition below must be True before any living runtime pair entity
can be created:

- **Identity schema** — deterministic `agent_id` derivation plus canonical
  identity fields; no identity drift across cycles.
- **Habitat boundary** — a defined, sanitized, bounded space the pair may
  act within.
- **Memory boundary** — what the pair may remember, for how long, with what
  provenance and `claim_scope`.
- **Write authority** — explicit allow-list of fields the pair may write;
  default deny.
- **Rollback rule** — any first-pair action must be reversible to a
  known-good state.
- **Observation-only first heartbeat** — the first tick is `observe`, not
  `move` / `gather` / `whisper`.
- **No provider/model autonomy** — no model may choose actions for the pair.
- **No network** — Gate-7 stays closed for pair creation.
- **No `world-sim/data` write** until explicitly Sean-authorized.

## 4. Required Future Specs

Docs-only, named here but **not created** in this phase:

- **First Pair Identity Spec** — identity schema + canonical Adam/Eve
  `agent_id`s.
- **First Habitat Boundary Spec** — spatial/temporal bounds of the first
  habitat.
- **First Heartbeat Observation Spec** — observation-only tick contract.
- **First Memory Boundary Spec** — what persists, why, with what
  `claim_scope`.
- **First Write-Authority Spec** — allow-list of writable fields; default
  deny.
- **First Rollback / Kill-Switch Spec** — kill-switch + revert-to-last-known-good.

## 5. Explicit Forbidden Actions

While this document is the active phase:

- Do not implement Adam/Eve.
- Do not create runtime entities.
- Do not modify `world-sim/data`.
- Do not open Gate-7.
- Do not touch daemon / scheduler / network / provider / container / Docker.
- Do not implement 10HD.
- No model autonomy, no network, no `world-sim/data` write.

## 6. Recommended Next Phase Name

Suggested docs-only candidate (recorded, **not created**): a **First Pair
Preflight Authorization Spec** that names the boundary for the first living
pair without creating them, without touching the 10HD recursion spine, and
without opening Gate-7.

Per instruction, **no phase number is assigned yet**. This document is an
unnumbered roadmap/preflight artifact only. Numbering is deferred to the
moment the next phase is explicitly authorized.

## 7. Honest Friction

- The recursion spine (10FN → 10GX chain) is **strong** but is **not life** —
  it proves we can verify authorization; it does not create a living entity.
- **Identity without habitat is unsafe** — an agent with an ID and no
  spatial/temporal bound can drift anywhere.
- **Heartbeat without rollback is unsafe** — a tick that cannot be reverted
  is a state-commitment trap.
- **Memory without boundary is unsafe** — unbounded memory plus provenance
  drift is the silent truth-transfer risk (the 10AB observed-world-fact
  failure mode).
- **Pair creation requires GPT-5.6 Sol/Luna + explicit Sean approval** — no
  GLM / free-model implementation, per AGENTS.md Rule 3. This document is
  planning only. It does not authorize implementation.
