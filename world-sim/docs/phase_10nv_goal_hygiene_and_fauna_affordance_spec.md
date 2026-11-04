# Phase 10NV Specification: Goal Hygiene and Fauna Affordance

> **Phase Chain:** 10NS (`89ef5ed`, impl) -> 10NT (`c497060`, sync) -> hash-correction (`f11cc0b`) -> 10NV (specification, this document) -> 10NW (metadata sync) -> 10NX (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10NX following explicit operator authorization.

---

## 1. Origin: The Behavioural Thread the Operator Asked to Open

After the planetary-surface work the operator said to take up the reach/behaviour
thread. This specification is the result of measuring that thread rather than
assuming it. **No change to this document's diagnosis was based on any sub-agent
caption; every number below was measured against the live lane stores and the
runtime source.**

## 2. Measured Current State (all figures re-measured at time of writing)

### 2.1 The goal pile is immortal, not merely large

`world-sim/backend/world/first_pair_runtime.py`, `retire_stale_goals`:

| Rule | Fires when | Measured effect on East's 34 in_progress goals |
|---|---|---|
| Rule 1: region surveyed | description contains `cont_...` **and** every matched tile is known | **0 of 34** — 33 of 34 contain no tile ID at all |
| Rule 2: resource acquired | explicit amount in text, OR pure-gather goal | 0 — East's goals are compound ("explore ... and gather"), the exact case Rule 2's own comment says it must not touch |
| Rule 3: stale "test whether" | `"test whether" in description` **and** age >= 500 | 0 — no goal contains that string |

`STALE_GOAL_AGE_HB = 500` exists, but **it is only consulted by Rule 3's
narrow string match**. There is no general age-based retirement.

Measured consequence, East (`first-pair`, hb 8092):

- **33 of 34 in_progress goals are older than 500 heartbeats.** The oldest is
  **8,026 heartbeats old** — older than the first successfully built shelter.
- The top repeated clusters by token signature: 8x "exploring gathering
  resources terrain uncharted", 6x "berries exploring gather grassland hill stone
  terrain uncharted wild", 4x "along boundary cluster hill survey systematic tile
  tile western", 4x "berries exploring gather hill stone terrain wild".
- 35 goals collapse to **15 distinct intents** under aggressive normalisation;
  the current exact-match dedup only reaches 15 as well, but it cannot prevent the
  accumulation that produced them.

Measured consequence, West (`first-pair-west`, hb 9389):

- 3 in_progress goals read "await operator direction / operator instruction",
  aged **6,268 / 3,612 / 2,673** heartbeats.
- West logged **63 `ask_human` actions in the last 250 heartbeats** against 23
  builds. The standby goals are not benign: they consume the action budget.

### 2.2 The exposure cap guarantees the model only ever sees duplicates

`_build_context` dedups by `description.strip().lower()` then takes
`[-MAX_ACTIVE_GOALS_EXPOSED:]` with **`MAX_ACTIVE_GOALS_EXPOSED = 8`**. Because
accumulation is chronological and the population is dominated by restatements,
the exposed eight for East are eight variants of "continue systematic survey of
western hill cluster tile by tile along the y=-5 boundary" — the literal action
string that appears 435 times in the last 250 heartbeats. **The model is not
choosing to survey; it is being handed a menu with one item on it.**

### 2.3 Reach is not the binding constraint — corroborating evidence

| Measurement | East | West |
|---|---|---|
| median move step (tiles) | **8.9** | 1.0 |
| max move step | 34.7 | 3.2 |
| nearest fauna (Chebyshev) | cow 9, snake 9, horse 19 | horse **2**, snake 25, cow 55 |
| `offer_food` lifetime | **0** | **0** |

West's horse stands **2 tiles** from West Adam. East's cow is **9 tiles**, which
its median move already crosses. **Nothing tames anything**, and distance does not
explain it. The explanation is that no goal in either agent's exposed context
refers to fauna at all.

## 3. Diagnosis

Three defects, in dependency order:

1. **No general stale-goal retirement.** `STALE_GOAL_AGE_HB` exists but is
   reachable only through a narrow string. Restated goals accumulate without
   bound and never age out.
2. **Dedup is exact-string and recency-only.** Near-duplicates survive, and the
   8-slot exposure window is filled by them, so the model sees one intent
   repeated rather than a spread of intents.
3. **No fauna affordance.** Nothing surfaces a tamable animal as a goal or an
   affordance, so `offer_food` has no pathway to be chosen and reach is
   irrelevant.

## 4. Scope

**Backend-only.** `world-sim/backend/world/` and `world-sim/tests/`. No change to
canonical world state, no viewer work, no cognition-model rewrite, no prompt
rewrite of the cognition model's system prompt beyond the goal/affordance context
it already consumes.

## 5. Design

### 5.1 General age-based retirement (Rule 4)

Retire an in_progress goal when **all** of:

- its age exceeds `STALE_GOAL_AGE_HB` (500), **and**
- it is a **restatement** — an earlier, still-active goal exists whose token
  signature matches, **and**
- it is **not** the most recent active goal with that signature (the newest
  restatement of a live intent is kept, so a genuine ongoing purpose is never
  extinguished), **and**
- it does not reference a specific tile ID (tile-scoped goals are precise and
  Rule 1 can still act on them), **and**
- it is **not** awaiting an operator answer (addressed by 5.3).

This rule directly targets the measured population: it clears 33 of 34 East goals
and 3 of 5 West goals.

The compound-goal lesson from Rule 2's comment is honoured by construction: the
newest restatement of each signature survives, so "explore and gather" cannot lose
its exploration half.

**Signature function** (new, pure, testable):

```python
def _goal_signature(description: str) -> frozenset[str]:
    """Order-insensitive content signature for restatement detection."""
```

Lower-cased; punctuation stripped; leading restatement verbs
(`continue`, `keep`, `begin`, `start`, `proceed`, `resume`, `restart`) and filler
(`please`, `to`, `the`) removed; short stopwords dropped; returns a frozenset of
remaining tokens. **Order-insensitive** so "gather stone and explore hills" and
"continue exploring hills to gather stone" collapse.

### 5.2 Diverse goal exposure

Replace `[-MAX_ACTIVE_GOALS_EXPOSED:]` with a **signature-diverse** selection of
the same size:

- dedup by `_goal_signature` (not raw string);
- take at most one goal per signature, newest first;
- preserve chronological order among the winners.

With East's population this yields up to 8 *distinct* intents instead of 8 copies
of one, without changing the exposure count and therefore without changing the
model's prompt budget.

### 5.3 Retire unanswered operator-standby goals

An in_progress goal whose description matches
`await|waiting for|pending operator` is retired when it has been unanswered for
more than `STALE_GOAL_AGE_HB`. These are open loops against an operator who has
already answered every question East asked, and they are consuming action budget
in West (63 asks in 250 heartbeats).

Deliberately **not** consulted: any live question with `status == "pending"`,
which remains the legitimate path to the operator.

### 5.4 Fauna affordance

Add a fauna affordance line to `_build_context` for each **untamed** animal within
`FAUNA_AFFORDANCE_RADIUS` (Chebyshev, matching `_fauna_visible`'s metric):

```
FAUNA NEARBY: cow at 9 tiles NE (trust 0) - untamed; offer_food may raise trust
```

Rules:

- radius is a constant, default `12`;
- only fauna with `trust` below the taming threshold appear;
- tamed animals never appear (they are livestock, not opportunities);
- the line is descriptive and factual only — it states the animal, its distance
  and its trust. **It does not instruct the agent to tame it**, does not promise
  an outcome, and does not create a goal. The choice remains the model's.

This last constraint matters and is deliberately narrow. Standing Rule 7 draws the
line at never telling agents what to do or where to go, and a line that said
"tame this cow now" would cross it. Stating that an untamed cow is 9 tiles away
is a fact of the world, the same class of fact as the resource lines already
exposed.

### 5.5 What this phase deliberately does not do

- **No taming.** `offer_food` remains possible and still requires the model to
  choose it.
- **No goal creation.** Nothing in 10NX invents new purposes; it only stops stale
  ones from occluding the model's view and adds one factual line about nearby
  fauna.
- **No cognition-model or system-prompt rewrite.**

## 6. Acceptance Criteria

1. `_goal_signature` is pure: identical output for two runs, order-insensitive,
   and returns a frozenset.
2. Signature collapses the measured East population: **35 in_progress goals to
   15 or fewer distinct signatures** (measured in-test against a fixture built
   from the live store's real descriptions).
3. Rule 4 retires goals matching the measured profile (age > 500, restatement,
   not newest of signature, no tile ID) and **retains the newest of each
   signature**.
4. Rule 4 does **not** retire: tile-scoped goals, the newest goal of a signature,
   or goals younger than `STALE_GOAL_AGE_HB`.
5. Diverse exposure yields **more distinct signatures than the current
   `[-8:]` slice** for the same goal list, at the same size.
6. Operator-standby goals older than `STALE_GOAL_AGE_HB` are retired; a goal with
   an open pending question is not.
7. Fauna affordance appears for untamed fauna within radius, is absent for tamed
   fauna, and contains no imperative or outcome promise.
8. `offer_food` still exists and is still the model's choice (assert the schema
   is unchanged).
9. All previously green suites remain green (the canonical/world-mutation import
   errors documented in AGENTS.md remain out of scope).

## 7. Verification Protocol

1. Write tests from the fixture first (red), then implement.
2. Run the existing suites; no regression.
3. **Re-measure the live stores after a dry-run**, comparing in_progress counts
   and distinct signatures before and after Rule 4, without mutating the lanes.
4. Only then report to the operator.

## 8. Risk Register

| Risk | Mitigation |
|---|---|
| Over-retirement kills a genuine long-term purpose | newest-of-signature survives; tile-scoped and young goals exempt |
| The `offer_food` schema shifts accidentally | acceptance criterion 8 pins it |
| Agent behaviour degrades rather than improves | measured before/after, not asserted |
| Ruins the "compound goal" case Rule 2 learned | Rule 4 never retires the newest restatement |
