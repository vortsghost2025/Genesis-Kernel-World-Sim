# Continuity Slot Spec — "What Am I in the Middle Of?"

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-09-28
**Origin:** outsider review §§1, 4, 5 + operator's NPC-spot principle. Folds
four proposals into one slot: recurrence signal (§1), session state (§1),
want-tracking (§4), and the NPC's own answer (§5).

---

## 0. Why one slot and not three

The outsider proposed a recurrence signal, a session-state split, and
want-tracking. I proposed joint-plan state from Eve's spot. Measured against
the live store, three facts fold them:

1. **Goals already carry long-horizon will.** 8 of 10 goals completed, 2 in
   progress (`explore-uncharted-territories` is literally Adam walking west
   right now). Building a parallel want system would duplicate a working slot.
2. **All 10 goals are action-completable.** Explore X, establish contact,
   patrol, test. Zero question-type goals ("why one water tile?"). The gap
   the outsider predicted for HB1500 exists *now*: there is nowhere to put a
   want that cannot be completed by action.
3. **Communication is load-bearing, split evenly.** 238 linkable messages:
   120 echoing / 118 deflecting — flat across all windows (0.55 / 0.49 /
   0.55). Messages steer half the time, so joint state is worth persisting;
   the echo half is sync confirmation, worth compressing differently (a
   synthesis concern, not this spec's).
4. **Message volume collapsed 7x** (79 → 258 → 23 per window) while the echo
   ratio held flat. Coordination isn't turning into grooming — it's going
   quiet as surveys complete. That is the §4 risk's actual early shape, and
   it argues for the slot sooner rather than later.

So: one slot, mid-turn continuity ("step 38 of 40"), distinct from goals
(long-horizon, action-completable) and charter (forever-identity). It absorbs
the recurrence signal (themes surface here, not in a separate feed) and
want-tracking (wants with ages live here, not in a new file).

## 1. What this phase does

A per-agent **continuity record**: written by the agent as metadata on its
existing action (no new verb, no free-action machinery), surfaced verbatim at
the top of every observation. Shape:

```
Current context (your own words, updated by you):
- continuing: <what you are in the middle of> (since hb N)
- paused: <what you set aside, and why> (optional)
- completed: <what just closed> (optional, one entry, then clears)
- open questions: <what you want to know that no action can complete> (max 3)
```

Rules:

- **Written piggyback, never standalone.** The record updates ride on the
  action payload the agent already emits each heartbeat. No heartbeat is ever
  spent "updating context" instead of acting — this is what kills the
  free-`declare_want` composition problem: there is no free action.
- **Aging is automatic.** Every line carries its heartbeat; the runtime
  renders ages ("stated 340 heartbeats ago"). Stale lines (>200 heartbeats
  untouched) drop with a one-heartbeat notice, never silently.
- **Recurrence becomes visible.** When both agents' records (or recent
  messages) repeat a theme ≥5 times, the runtime adds one read-only line:
  "You and Eve have both mentioned X recently." No judgment, no instruction —
  the outsider's falsifiable trigger for charter-writing, delivered as
  information.
- **Open questions are second-class in the best sense.** They persist and
  age, but nothing in the runtime answers them. A question answered by events
  is marked completed by the agent; unanswered ones simply grow old visibly.

## 2. Why this shape and not the alternatives

- **Not a file + free action** (outsider §4 as written): free actions need
  composition rules with the one-action-per-turn economy, a new validation
  surface, and a new census dimension. Piggyback metadata needs none of it.
- **Not a charter reform:** the charter is forever-identity, 0 of 4 written
  in 1,043 heartbeats. Continuity is *this-week* will. Different slot,
  different cadence, no interference.
- **Not goals v2:** goals persist and complete well. The continuity record
  may *reference* a goal ("continuing goal-eve-004, step 38/40") but never
  replaces it.

## 3. What this phase does NOT do

- No new verb or action type. No change to the one-action economy — message
  share (23% of all actions) is therefore undisturbed, and its census rows
  keep meaning.
- No auto-sharing of observations and no free messages (outsider §2, phases
  1 and 3). Those are sequenced *after* this slot with their own baselines:
  tile-discovery Adam 0.060 / Eve 0.085 per heartbeat, message share 23%.
- No durable scratchpad yet (outsider §2, phase 2). If the continuity record
  fills with joint plans, that *is* the evidence the scratchpad is needed —
  this phase is its falsifiable predecessor.
- No prompt instruction to use the slot. The census stays falsifiable: an
  empty slot is a finding about the prompt, as Phase B taught.
- No change to selection, synthesis, charter, anchors, physics, fog, or
  movement.

## 4. Test plan (TDD outline)

Presentation:

- the record renders at the top of observations, verbatim, with ages.
- stale lines drop only with a one-heartbeat notice line; never silently.
- recurrence line appears at ≥5 shared mentions, absent below; it is
  read-only (agent metadata cannot set it).
- empty record renders neutral text, never an error or an empty block.

Metadata path:

- record updates arrive inside the existing action payload; a heartbeat with
  no update leaves the record untouched.
- malformed metadata is ignored with a validation error, never persisted;
  the action itself still executes (context must not be able to veto action).

Invariance:

- action economy untouched: verb mix distributions unchanged on fixture runs.
- goals, charter, anchors, selection outputs byte-identical given same inputs.
- no test touches `world-sim/data`, connects to a provider, or runs a daemon.

## 5. Falsification census — 100 heartbeats

| signal | baseline (HB1043) | passes if | reading |
|---|---|---|---|
| records in use (non-empty) | 0 (feature absent) | **> 0** | decisive row, same as Phase B |
| multi-turn references spanning 5+ HBs | unmeasured (survey/patrol language exists) | **rises** | continuity lands in behavior |
| message volume per 100 HBs | ~10 (HB801-1043 pace, down from ~43) | holds or rises | slot supplements talk, doesn't replace it |
| charters written | 0 of 4 | any | recurrence line tested as trigger |
| open questions stated | 0 (no slot) | **> 0** | question-type wants exist |
| goal churn | 10 goals, 2 in progress | new goals still form | §4 risk not yet crystallized |
| echo/deflect ratio | 0.55 echo | holds ±0.15 | coordination still active |

Honest prior, stated in advance: Phase B's slot went 0-for-100. This slot
differs in one structural way — it rides the action the agent already takes
instead of costing one — but that is a design argument, not evidence. A null
here would say agents don't externalize mid-turn state even for free, which
points at prompt furniture blindness (the slot is seen but never salient),
not at missing needs.

## 6. Decision requested

1. Approve the single-slot fold (continuity record with aging + recurrence
   line + open questions) over separate want-file / free-action / charter-
   reform alternatives.
2. Confirm piggyback-over-free-action (§1): no new verb, no economy change.
3. Confirm sequencing: this slot → scratchpad decision → auto-share with
   baselines → free-messages last or never.
4. Confirm the stale-line notice rule (drop with one heartbeat of notice,
   never silent) — the one place this phase could quietly lose a thought.
