# Memory Synthesis Spec — Replacing Stub Derivation With Model Rollups

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-09-28
**Origin:** Sean's question — "I thought state preservation should make it
closer to 99%… is that not the case?" — and his authorization to fix the 1%.

---

## 0. What was measured before this spec

- **Storage is total:** 1,948 / 2,064 memories banked per agent, hashed,
  manifested. Nothing is lost.
- **Presentation is 0.78%:** HB1043 manifest for Eve — 2,063 raw, 2,047
  omitted, 16 selected (6 recent + 6 relevant, 12,000-char budget,
  `first_pair_persistence.py:85-89`).
- **The summaries layer is a stub.** 16 summaries exist for 2,000+ memories.
  `derivation_method` is `deterministic_extractive`; content is
  `"[derived from heartbeat 1 (reflection)] Previous action move: success"`.
  The allow-list (`_ALLOWED_DERIVATION_METHODS`) admits only
  `deterministic_stub` and `deterministic_extractive` — synthesis is not a
  missing feature, it is a forbidden method.
- **The pipeline around the stub is complete.** `derive_summaries_for_omitted`
  → `append_summary` → `load_summaries` → `derived_memory_summaries` in the
  prompt (`first_pair_cognition_model.py:811-812`). Derive, persist, inject
  all work. Only derivation quality is broken.

This is the narrowest possible fix surface: one rung of an intact ladder.

## 1. What this phase does

Admit one new derivation method, `model_synthesized_v1`, and use it to roll up
omitted memories into compressed understanding — same record shape, same
commitments, same injection path. Nothing else in the memory system changes.

From the NPC's spot, this is the rung that matters. The agent cannot read
2,000 memories and should never be asked to. What it needs is what the
summaries layer was *designed* to be: the past, compressed, truthful, present.

## 2. The load-bearing distinction

A synthesis is a **claim about the past, not the past.** Raw memories are
evidence; a rollup is testimony. The design treats them differently forever:

- A synthesized summary must **never outrank raw memories** in selection.
  Where both cover an event, the raw memory wins the slot. Synthesis fills
  gaps; it does not compete with evidence.
- The `[derived …]` label is retained and strengthened: it must name the
  method (`model_synthesized_v1`), so a future reader — agent or auditor —
  can discount it correctly.
- The existing source commitment (`compute_summary_source_commitment`)
  already binds a summary to its exact covered memories. That binding is what
  makes a hallucination *checkable*: every claim in the rollup resolves to a
  covered ID or it is fabrication.

## 3. Grounding rule (falsifiable content constraint)

The synthesis prompt forbids specifics not present in the covered memories:
tile IDs, resource counts, heartbeat numbers, proper names. Validation
enforces the checkable subset of this:

- every `salient_entity` in the record must appear verbatim in at least one
  covered memory (machine-checkable, no model judgment);
- heartbeat range must exactly span the covered memories (already validated);
- covered IDs must resolve (already validated).

What validation **cannot** check — tone, emphasis, omission — is why §2's
ordering rule exists. The machine-checkable half keeps fabrication out; the
ordering rule keeps the remaining soft error below the evidence.

## 4. Coverage discipline

- Summaries cover **omitted** memories only — never memories already selected
  (that would spend synthesis duplicating the present).
- Coverage is accounted: every omitted memory should eventually fall under at
  least one valid synthesis. Gaps are visible in the manifest, not silent.
- **No mass backfill.** 2,000 memories synthesized at once would be a wall of
  unreviewed testimony. Backfill is phased, oldest first, bounded per run
  (bound chosen at implementation; hitting it is logged, never silent).
- Overlapping coverage is allowed; contradictory coverage is not resolved by
  the runtime — both records persist with their commitments, and selection
  prefers raw over either.

## 5. Cost and provider policy

- Synthesis calls go through the same 5 fail-closed free-only gates as
  heartbeats. No paid lane, no new credentials, no new endpoint.
- Synthesis is **not per-heartbeat.** It runs on a cadence (phased backfill +
  rolling coverage of newly-omitted memories), bounded per run. A heartbeat
  must never wait on a synthesis.

## 6. What this phase does NOT do

- No change to selection budgets, scoring, or the 6+6+12,000-char presentation
  contract. The 0.78% figure is not moved by this phase; what the other 99.22%
  *degrades into* is.
- No new verb, action, object type, or prompt instruction. No agent is told
  summaries exist; the census stays falsifiable.
- No change to charter, anchors, messages, physics, fog, or movement.
- No synthesizing the other agent's memories into anyone's context. Owner
  binding is unchanged.
- No silent replacement of stubs. Existing extractive records persist as-is
  with their method label; synthesis adds alongside, and selection prefers
  raw over either.

## 7. Test plan (TDD outline)

Validation and grounding:

- `model_synthesized_v1` admitted by the allow-list; any other new string
  still rejected.
- salient entities not verbatim in covered memories → record invalid.
- summary without method name in the `[derived …]` label → invalid.
- covered IDs resolving to another agent's memories → invalid (owner binding).

Ordering:

- where a raw memory and a synthesis cover the same event, selection ranks
  the raw memory first (unit test on the ordering rule, fixture data only).

Pipeline invariance:

- selection budgets, caps, and manifest shape unchanged.
- synthesis never runs inside a heartbeat's critical path (cadence/budget
  test with a fake clock, not wall time).

Compliance:

- no test touches `world-sim/data`, connects to a provider, or runs a daemon.
- free-only gates asserted on the synthesis call path, not assumed.
- `git diff --check` clean, LF-only.

## 8. Falsification census

| signal | baseline (HB1043) | passes if | reading |
|---|---|---|---|
| omitted memories under valid synthesis | ~0% (16 stubs / 2,000+) | **rises toward full coverage** | the mechanism runs |
| agent decisions consistent with covered-but-omitted events | unmeasured | **checkable post-hoc** (see below) | the understanding lands |
| raw-memory selection outputs | current mix | **unchanged distribution** | synthesis didn't disturb evidence |
| invalid-synthesis rejections | n/a | **> 0 over the arc** | the grounding rule bites, not decor |
| questions / blocks / moves | 0 / 0 / succeeding | hold | nothing regressed |

The honest prior, stated in advance: coverage rising proves the mechanism
runs, not that it matters. The second row is the real test and the hardest to
measure fairly — "consistent with" is judged against heartbeat records where
the agent acted on knowledge no selected memory contained. A coverage arc with
no behavioral trace is a compression success and a cognitive null, and the
spec will record it as such rather than move the goalposts.

## 9. Decision requested

1. Approve the single-rung form: new derivation method, same record, same
   pipeline, ordering rule raw-over-synthesis.
2. Confirm §6's backfill bound (phased, oldest first, logged) over the
   alternative of full backfill.
3. Confirm the grounding rule's machine-checkable half is sufficient guard
   alongside the ordering rule, rather than requiring pre-persistence human
   review of every rollup (which would not scale to 2,000 memories and would
   reintroduce the operator as the bottleneck the bridge was built to remove).
