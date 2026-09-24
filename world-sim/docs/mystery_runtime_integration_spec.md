# Mystery Runtime Integration — Design Specification

**Status:** DESIGN SPECIFICATION ONLY
**Scope:** wiring `scripts/world_content/mystery_reveal.py` into the living
first-pair runtime
**Implementation authorization:** NOT GRANTED by this document
**Canonical-write authorization:** NONE (this document; deployment of the
content candidate was separately authorized and already completed)
**Companion artifacts:** `world-sim/scripts/world_content/mystery_reveal.py`
(pure, tested: 11 no-leak/reveal tests in
`tests/test_world_content_mystery.py`)

## 0. What exists today

- The canonical true map carries exactly 2 mysteries:
  `mst_east_echo` on `cont_a_east_000` (East Crown summit, threshold 3) and
  `mst_west_light` on `cont_b_west_001` (threshold 3).
- The fog engine never reads the `mysteries` array; no observation contains
  mystery data.
- The pure mechanic (`mystery_reveal.py`) already implements: occupancy-only
  evidence accrual (one unit per tick, only while standing on the mystery
  tile), progressive vague hints at evidence 1–2, threshold conversion at
  evidence 3 into a known landmark, fail-closed behavior for unknown
  kinds, and a contamination-guarded agent-facing projection.
- Known maps are schema 7B.1 and already contain the `myths` list, which is
  where evidence lives (currently empty for both agents).

## 1. Design invariants (non-negotiable)

1. The true map is never written by this mechanic. Mystery revelation is
   agent-side state only.
2. No hidden-map leakage: agent-facing output contains no mystery ids, no
   threshold numbers, no `true_map`/`known_map` vocabulary, no hidden
   landmark names. Mechanism words are forbidden by the projection guard
   (`FORBIDDEN_PROJECTION_SUBSTRINGS`), and contaminated claims are dropped,
   never shown.
3. Evidence accrues from **occupancy only** — never from visibility. This
   preserves the 10IZ rule: "never infer a visit merely from visibility."
4. Per-agent state. Adam's evidence gives Eve nothing.
5. Known-map persistence failure remains a heartbeat failure condition.
   Mystery state lives inside known maps, so it inherits that rule.
6. Additive only: no old heartbeat, memory, message, goal, or object
   record changes shape or meaning.

## 2. Runtime integration points

### 2.1 Where the check happens: the merge seam

`FirstPairRuntime` already calls `_merge_and_persist_known_map(agent_ref,
observation, tick)` after building each agent's fog observation and before
cognition. That is the seam.

Proposed heartbeat order per agent (additions in **bold**):

1. resolve current position tile (`world_state.tile_occupancy`)
2. build fog observation (`cognition_safe_observation(...)`)
3. `merge_observation(known_map, observation, tick)`
4. **mystery accrual:** for each mystery whose `tile_id` equals the
   agent's *current position tile* (post-action occupancy at the observed
   tile), call
   `accrue_mystery_evidence(known_map, mystery, position, tick)`
5. **reveal check:** `apply_reveal(known_map, mystery, tick)` (idempotent;
   no-op below threshold or after reveal)
6. `persist_known_map(...)` (once, after both steps — one write per
   heartbeat per agent, unchanged write cost)
7. cognition prompt built from the *persisted* known map, so hints the
   agent just earned are visible to it in the same heartbeat

The runtime reads the true map's `mysteries` array at this seam **read-only**
— the same read-only posture the adapter already takes toward the true map
during heartbeats.

### 2.2 How hint text reaches the agent

The cognition observation gains one additive key:

```text
unsettled_reports: [ {report: str, certainty: float}, ... ]
```

Produced by `project_unsettled_reports(known_map)` — computed from the
agent's **own** persisted known map, never from the true map directly.

Placement: add the key inside `cognition_safe_observation(...)` output
(optional positional argument `known_map` is already a parameter; the
adapter can append the projection after building `visible_tile_details`).
Existing consumers ignore unknown keys; the key is absent (not empty)
when no evidence exists, so pre-integration states are indistinguishable.

After reveal, the mystery is no longer "unsettled": it exits this channel
and enters the discoveries channel (§2.3).

### 2.3 What the known map looks like after reveal

Concrete shape — Eve has stood on the summit three times:

```json
"myths": [
  {
    "id": "myth_mst_east_echo",
    "created_tick": 400,
    "claim": "The sound again. Patient. Repeating. Steady as a heartbeat. It is not wind. It is in the stone.",
    "basis": "experience on cont_a_east_000",
    "confidence": 0.9,
    "status": "confirmed",
    "evidence": 3,
    "last_evidence_tick": 402
  }
],
"known_landmarks": {
  "lm_mystery_mst_east_echo": {
    "true_landmark_id": "lm_mystery_mst_east_echo",
    "first_observed_tick": 402,
    "last_observed_tick": 402,
    "kind": "singing_rock",
    "confidence": 1.0,
    "description": "The Singing Stone. A slab of summit rock that hums a single repeating note. Warm to the palm..."
  }
}
```

The revealed landmark is agent-side. It is NOT in the true map's
`landmarks` array, so the existing landmark projection (driven by
`visible_landmarks`) never emits it. A second additive observation key
carries it, sourced only from the agent's confirmed records:

```text
discoveries: [ {kind: str, name_and_description: str, tile_region: str? } ]
```

Projection rule for discoveries: emit `kind` + description text only;
strip the `lm_mystery_` prefix; include the region name only if the tile
is currently in the agent's known tiles — otherwise the description alone
("you discovered this at the summit") stands without coordinates.

### 2.4 Persistence between heartbeats

None needed beyond existing machinery:

- evidence lives in `known_map["myths"]` (schema 7B.1 field, already
  validated by `validate_known_map`, already persisted by
  `persist_known_map`);
- revealed landmarks live in `known_map["known_landmarks"]` (same);
- no new files, no new sidecar state, no caches.

Replayability: myth evidence is derived-but-persisted — it can be
reconstructed from heartbeat positions (occupancy per tick), matching the
same derivation rule 10IZ used for known-map seeding.

## 3. Prompt-safety and contamination gates

1. `project_unsettled_reports` drops any claim containing a forbidden
   substring; add a regression test asserting the canonical mysteries'
   hint ladders never trip the guard (they don't — hints are pure
   second-person prose).
2. Extend the existing prompt contamination checks with:
   `unsettled_reports` entries must not contain tile ids, mystery ids,
   region ids, or coordinates.
3. Observation-size discipline: reports list is at most one entry per
   gathering mystery (≤2 ever, given current content).

## 4. Failure modes

- **Missing/corrupt known map:** heartbeat fails closed (existing rule).
- **Mystery record malformed** (missing kind / unknown kind): accrual
  returns unchanged map, no crash (already tested).
- **Mystery tile never occupied:** nothing happens. This is the expected
  common case and is a valid long-term state.
- **Duplicate accrual attempt within a tick:** rejected by
  `last_evidence_tick` guard (already tested).
- **Replay divergence:** reconstructing myths from heartbeat positions
  must reproduce the persisted myths exactly; a mismatch is evidence of
  ledger corruption and should halt integration tests.

## 5. Runtime-visible behavior (what the agents will experience)

Standing on the East Crown summit:

- Visit 1: *"Sometimes, when the wind drops, you think you hear a tone
  beneath the world. It stops when you listen for it."* (certainty 0.25)
- Visit 2: *"The sound again. Patient. Repeating. Steady as a heartbeat.
  It is not wind. It is in the stone."* (certainty 0.45)
- Visit 3 — reveal: the summit now holds **The Singing Stone** in their
  personal record of the world, a first-class thing they can reference,
  revisit, and tell the other about.

The distant light on the far continent's west cliffs follows the same
ladder with its own authored text, concluding in **The Lantern of the
West** — effectively unreachable until sea travel exists, which makes it
the correct kind of long mystery.

## 6. Test plan for the implementation phase

1. Full-pipeline scratch heartbeat: agent on mystery tile for 3 ticks →
   hint at 1, deeper hint at 2, reveal at 3; observation at tick 2
   contains exactly one `unsettled_reports` entry and zero
   `discoveries`; at tick 3 the reverse.
2. No-leak sweep across the whole pipeline: cognition observation and
   prompt context at every tick contain no `mst_` ids, no threshold
   values, no `mystery` string.
3. Occupancy-only proof: agent adjacent to the mystery tile for N ticks
   accrues zero evidence.
4. Two-agent independence through the shared runtime.
5. Replay test: rebuild myths from recorded positions and assert equality
   with persisted state.
6. Regression: full existing first-pair suite unchanged; observation
   consumers unaffected when keys are absent.
7. Persistence failure simulation: known-map write failure after accrual
   fails the heartbeat, no partial myth persisted.

## 7. Explicit non-goals

- No `true_map.json` writes from this mechanic, ever.
- No new actions (`listen`, `investigate`); if an agent wants to focus a
  mystery, that is a `request_capability` conversation, not this phase.
- No mysteries generated procedurally; authored-only stands.
- No reveal mechanic for the eight wonders — they are ordinary landmarks,
  visible when observed, by design.
- No scheduler/daemon changes; Gate-7 posture unchanged.

## 8. Stop boundary

This document designs only. It authorizes no code change, no canonical
write, no heartbeat, no commit. The implementation phase implementing
this spec must be separately authorized and must preserve every invariant
in §1.
