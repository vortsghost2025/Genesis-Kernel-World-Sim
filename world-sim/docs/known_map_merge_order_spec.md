# Known-Map Merge Order Spec — Making an Observed Tile Reachable in the Same Heartbeat

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-09-28
**Triggered by:** heartbeat 942 — `east_adam` chose a tile it could see and was
blocked: `Tile cont_a_gen_1_2 not in runtime policy allowed tiles`
**Supersedes:** nothing. Fixes a defect the `build` path was already fixed for.

---

## 0. Two corrections to the initial diagnosis

Both were mine, and both are recorded because a spec that hides its own wrong
turns is not evidence of anything.

**Correction 1 — it is not a stale `runtime_policy.json`.** I first reported
that the move executor read the persisted policy directly. False:
`_execute_move` (`:927`) calls `_get_effective_allowed_tiles()`, which derives
topology from the live known maps. The persisted `runtime_policy.json` (dated
2026-09-15, three habitat tiles) is **not consulted** on the fog path at all.

**Correction 2 — it is not a stale artifact.** I then called it a thirteen-day
old snapshot winning over live state. Also false. Measured across the entire
942-heartbeat record: **exactly one blocked move, ever**, and it is HB942.
There is no backlog of agents trapped by a stale file.

The real defect is narrower and worse, because it is not intermittent.

---

## 1. Measured root cause: the merge lands after the action

Reconstructing the known maps as they stood *mid-tick-942* (entries with
`first_observed_tick == 942` removed, i.e. before the merge):

```
PRE-MERGE allowed count: 17
  1_2 allowed pre-merge: False
```

`cont_a_gen_1_2` carries `first_observed_tick: 942`. Adam learned of it **in the
heartbeat where he tried to walk to it.**

The tick order in `_run_heartbeats` (`:1301-1334`) is:

| step | line | what happens | known state |
|---|---|---|---|
| 1 observe | `:1305` | `_build_context` → observation includes `cont_a_gen_1_2` | tile **not** yet known |
| 2 model | `:1307` | agent reads the prompt, sees the tile, chooses to move | tile **not** yet known |
| 3 act | `:1327` | `_execute_move` → `_get_effective_allowed_tiles()` → **blocked** | tile **not** yet known |
| 4 persist | `:1332` | `_merge_and_persist_known_map` | tile becomes known — one step too late |

**The world advertised a tile in the observation, the agent correctly believed
it, and the reachability rule refused it because the knowledge had not been
committed yet.** The observation is the agent's evidence; the known map is what
the rules consult. This heartbeat, those two disagreed by exactly one tick.

### 1.1 The `build` path was already fixed for this

`first_pair_runtime.py:965-967` carries the scar:

```python
# Placement authority: the tile you stand on is always placeable
# (same seam fix as build — movement, not a stale whitelist,
# governs where an agent may be).
```

The identical defect was found, fixed, and documented **in the build path**.
The move path kept it. That comment is why this is a known bug class in this
codebase rather than a novel one — and it is the strongest argument that the
fix belongs at the ordering, not inside the move rule.

---

## 2. The change

Move the known-map merge to **before** the action executes:

```
observe → merge known map → model → act → persist (memory, goals, record)
```

The merge is already idempotent (`merge_observation` is a known-map upsert) and
already runs for both agents; it is simply relocated within the per-agent loop.

### 2.1 Why this preserves the fail-closed ordering

The runbook's ordering is *observe → model → act → persist* and is described as
fail-closed. That property is about **persistence of world state**, and this
change does not touch it:

- The observation is still built first, and if the fog adapter raises
  `FogAdapterError` the runtime still fails closed into the minimal
  `{tile_id, visible_tiles: [tile_id], objects_here}` shape. No merge occurs
  from a degraded observation, because the merge is inside the same guard.
- The merge writes **only the agent's own known map** — a private epistemic
  artifact. It cannot grant a capability, alter the runtime policy, move an
  agent, or mutate world state.
- World mutation, memory, goals, questions, and the heartbeat record all
  remain strictly after the action.
- An agent that observes and then does nothing still ends the heartbeat with
  the same records as before. The merge is not contingent on acting.

**The one thing that does change:** a tile first seen on tick *N* becomes
reachable on tick *N* rather than tick *N+1*. That is a real, small expansion
of agency and is stated here rather than buried.

### 2.2 Why not fix it inside the move rule

The alternative — teaching `_execute_move` to consult the in-flight observation
— would put a special case in the action path, leave the ordering wrong for
every other rule that reads the known map, and reintroduce exactly the
"stale whitelist" problem the `build` comment warns about. The ordering is the
cause; fixing the cause is smaller and safer than fixing each symptom.

---

## 3. What this phase deliberately does NOT do

- **No change to `_get_effective_allowed_tiles`, `derive_topology`, or the
  adjacency rule.** Reachability semantics are untouched; only the moment at
  which knowledge becomes visible to them changes.
- **No change to the fog, the radius, or `visible_tiles`.** Phase 2's dial is
  not touched.
- **No back-fill of historical records.** HB942 stays blocked in the record.
  It is the honest evidence that the defect existed.
- **No prompt changes, no nudges, no new pressure.** This removes an obstacle;
  it does not add a motive.
- **No write to the canonical store outside a heartbeat.**

---

## 4. Test plan (TDD outline)

Ordering:

- a tile first observed on tick *N* is in the derived allowed set during the
  same tick *N*'s action phase
- after the reorder, `_merge_and_persist_known_map` is called before
  `_execute_action` for the same agent — asserted on a recording double
- the merge still runs for both agents every heartbeat regardless of action
  outcome

Preserved behaviour:

- a fog adapter failure still yields the minimal observation and no merge
- world mutation still occurs strictly after the action
- memory, goals, questions, and the heartbeat record are written after the
  action, exactly as before
- a no-op agent (observe, no action) produces the same records as before
- reachability semantics unchanged: a known-but-non-adjacent tile is still
  refused with the adjacency reason; a non-visible tile is still unreachable

Regression:

- the full existing runtime suite passes unchanged
- the HB942 scenario replays: given a known map where the target is observed
  this tick, the move now succeeds

Compliance:

- no test touches `world-sim/data`, connects to a provider, or runs a daemon
- tempdir stores and fakes only
- `git diff --check` clean, LF-only

---

## 5. Falsification census

| signal | baseline | passes if |
|---|---|---|
| moves blocked by reachability | **1** (HB942) | **stays 0** for a 100-heartbeat arc |
| known_tiles growth per agent | 18 / 17, rising | keeps rising |
| moves per agent-heartbeat | 2 of 2 agents moved at HB942 | does not fall |
| adjacency refusals (non-adjacent) | present and correct | unchanged — the rule still bites |
| East build rate | 8 builds in HB801–840 | does not collapse |
| audit record completeness | 100% | stays 100% |
| world mutation ordering | post-action | **unchanged** |

The decisive row is the first: a reachability block that fires **once** in 942
heartbeats is a defect, not a rule doing its job. Zero is the pass condition.
The adjacency row is the guard on this phase — if *that* starts failing, the
change loosened reachability instead of timing it.

---

## 6. Decision requested

1. Approve the reorder (merge before act) as specified.
2. Confirm the fail-closed argument in §2.1, specifically that merging the
   agent's own known map before acting does not constitute persisting world
   state early.
3. Confirm the same-tick reachability expansion (§2.1, final paragraph) is the
   intended behavior.
4. Confirm HB942 stays in the record as-is: blocked, un-back-filled.
