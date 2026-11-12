# Phase 10QC - Rung Payoff: A Proper Home Must Outrank the Shacks It Replaces

Specification only. Implementation is the candidate phase 10QE.

Operator statement, 2026-11-11, after watching both lanes:

> "they're actually at level 4 which is progress, but they're not building
> real houses then they only have shelters which is fine but it doesn't make
> sense for level 4 to be the end here."

Phase chain: 10QC (spec) -> 10QD (metadata sync) -> 10QE (implementation
candidate, not started).

---

## 1. What the live lanes actually show (measured, not asserted)

Read from `.runtime/first-pair` and `.runtime/first-pair-west` at heartbeats
12572 / 12741 with the production weight functions:

| measurement | East | West |
|---|---|---|
| public objects | 90 | 153 |
| roofed tiles (weight > 0) | 43 | 41 |
| objects carrying `structure_rung` | 7 | 9 |
| distribution | `{3: 2, 1: 5}` | `{1: 9}` |
| highest dwelling type ever built | `cabin` (rung 3) | `cabin` (rung 3, legacy) |
| `house` / `longhouse` ever built | **0** | **0** |
| Adam's connected footprint | **1** | **46** |
| Eve's connected footprint | 0 | **46** |
| home-network tier reached | tier 1 (the floor) | tier 5 (the cap) |
| in-flight builds | 0 | 3 (two `shelter` foundations, one `lean-to`) |
| last 14 East builds | `roof` x9, `campfire` x2, `storage_box`, ... | `shelter`, `wall`, `lean-to` |

East Adam holds `stone 643, timber 38, clay 84, iron_ore 9`. West Adam holds
`timber 196, stone 42, clay 6`. A `house` costs `timber 4, stone 6, clay 4`.
**The materials are in hand. Nobody has ever tried.**

## 2. Root cause: the ladder pays nothing to climb

The 10PU spec (section 5) promised:

> `_in_shelter` keeps its predicate, but the 10PJ tier lookup uses
> `max(footprint_units, rung_weight)` so a single rung-5 longhouse outranks
> four lean-tos without any change to `_HOME_NETWORK_TIERS`.

That clause was **never implemented**. Measured against `HEAD` (`948a911`):

```
$ rung_weight consumers in backend/world/*.py
first_pair_runtime.py:1534:  weight = here.get("rung_weight")     # read of the field
first_pair_runtime.py:4097:  envelope["rung_weight"] = ...        # the only write
```

`rung_weight` is written into the object envelope at build time and into the
disclosure dict at read time. **Nothing in the tier lookup, the cellar budget,
or any survival parameter consumes it.** The consequence, computed live:

- a `house` (weight 3) and three `lean-to`s (3 x weight 1) are worth the
  **same** 3 footprint units;
- a `longhouse` (weight 4) and four `lean-to`s are worth the **same** 4;
- so the cheapest way up the ladder is always one more shack, which is
  precisely the settlement shape the operator has been rejecting since 10PH.

Second cause: **the tier table is a ceiling.** `_HOME_NETWORK_TIERS` ends at
`(8, 75.0, 0.10, 2.00, 1.10, 0.22)`. West is at footprint 46. There is no row
above 8, so the best home in either lane already receives the final answer
and no amount of building changes anything again. That is the "level 4 is the
end" the operator is describing: the ladder does not continue.

Third cause: **the vocabulary is invisible.** The prompt discloses
`shelter`, `cabin`, `hut`, `roof` as buildable things. `house` and `longhouse`
appear in exactly one place - the rejection string for an unknown type. An
agent cannot build a thing it has never been told exists, and in 12,700
heartbeats across two lanes neither has tried.

Fourth cause: **the rung effects column is prose, not code.** `_STRUCTURE_RUNGS`
promises "walls: predators refuse the tile" (rung 2), "hearth slot: cooking on
the tile" (rung 4) and "campaign build: cellar budget doubled" (rung 5).
- rung 2's promise is already true for *every* roofed kind via `_in_shelter`
  (`first_pair_runtime.py:2665-2667`), so it is not a rung effect at all;
- rung 4's does not exist: cooking still requires a `fire`, `campfire`,
  `hearth`, `cooker` or `oven` object (`first_pair_runtime.py:4354-4358`);
- rung 5's does not exist: `_cellar_food_capacity` is
  `20 x max(1, footprint)` with no rung term (`first_pair_runtime.py:2539-2543`).

## 3. What this phase changes

### 3.1 A home's tier comes from its best structure, and shacks stop paying

Two numbers, both disclosed:

- `footprint` - roofed structures connected by Chebyshev adjacency, counted as
  today (unchanged; `test_home_network_scaling.py` keeps asserting 1 + 1 + 2).
- `tier_weight` - what the comfort physics actually reads:

  ```
  tier_weight = min(footprint, FOOTPRINT_SATURATION) + rung_bonus
  ```

  where `rung_bonus` is 0/2/4/7/11 for the network's highest rung
  (lean-to/hut/cabin/house/longhouse) and `FOOTPRINT_SATURATION` = 12.

Consequences, all computable and testable:

| settlement | footprint | tier_weight | comfort floor |
|---|---|---|---|
| one lean-to | 1 | 1 | 45 |
| three lean-tos | 3 | 3 | 52 |
| one hut | 1 | 3 | 52 |
| one cabin | 2 | 6 | 62 |
| **one house** | 3 | **10** | **75** |
| one longhouse | 4 | 15 | 80 |
| West today (46 roofed, best rung 3) | 46 | 16 | 80 |
| West if they raise one longhouse | 46 | 23 | 84 |

One proper house outranks seven shacks. A 46-tile settlement of cabins earns
the same tier bonus as one longhouse would, which is the point: what a home
*is* has always mattered more than how many tiles it covers, and this makes
the physics say so.

Saturation is the deliberate half of the change. Past 12 roofed tiles,
additional shacks stop adding warmth. That is the mechanic the operator has
asked for since 10PH and it is the one place in this phase that reduces an
existing payoff; it is called out here so the implementation phase cannot
ship it as a silent edit.

### 3.2 The tier table keeps going

`_HOME_NETWORK_TIERS` gains three rows so a large or high-rung home continues
to matter, and no row changes:

```
(1,  45.0, 0.45, 1.00, 0.40, 0.10)   # unchanged, 10PJ
(2,  52.0, 0.30, 1.25, 0.55, 0.12)   # unchanged, 10PJ
(3,  62.0, 0.18, 1.50, 0.70, 0.15)   # unchanged, 10PJ
(5,  68.0, 0.14, 1.75, 0.90, 0.18)   # unchanged, 10PJ
(8,  75.0, 0.10, 2.00, 1.10, 0.22)   # unchanged, 10PJ (was the cap)
(12, 80.0, 0.09, 2.20, 1.25, 0.24)   # new
(18, 84.0, 0.08, 2.40, 1.40, 0.26)   # new
(26, 88.0, 0.07, 2.60, 1.55, 0.28)   # new
(36, 92.0, 0.06, 2.80, 1.70, 0.30)   # new
```

Every row is a strict improvement on the row above it on all five axes, and
the implementation suite asserts that monotonicity directly, so a future edit
cannot add a row that pays less.

### 3.3 The three promised rung effects become real

- **rung 4 `house` = hearth slot.** Cooking (`use_object`, operation `cook`)
  succeeds against a finished `house` or `longhouse` without a separate fire
  object, because a proper home has a hearth built in. A rung-3 cabin still
  needs one. This is the first rung in the table with an effect no smaller
  structure has.
- **rung 5 `longhouse` = cellar budget doubled.** `storage_cellar` capacity in
  a connected network containing a finished longhouse is
  `2 x 20 x tier_weight`. A longhouse is the campaign build 10PU called it.
- **rung 2's "predators refuse the tile"** is dropped from the effects column,
  because it was never a rung effect - every roofed kind is already absolute
  safety (`first_pair_runtime.py:2665-2667`). Leaving it would keep advertising
  a rung-2 reward that a lean-to already provides.

### 3.4 The ladder is disclosed, so the next step is visible

A new factual settlement line renders the whole ladder the way
`_craft_recipe_advertisement` renders recipes:

```
- Structure ladder (each rung is a buildable type; a roofed structure shelters
  only from the roofed stage): lean-to (rung 1: timber x1; shelter from cold;
  counts 1 roofed unit) | hut (rung 2: timber x2, wood x2; ...) | cabin
  (rung 3: ...) | house (rung 4: ...) | longhouse (rung 5: ...).
- Home tier: connected roofed footprint 46 (saturates at 12), best rung in the
  network cabin, tier weight 16; comfort floor 80, cold decay 0.09, rest
  recovery 2.2/hb, downed recovery 1.25/hb, cellar food budget 320 units.
```

Facts about what the world is. No directive phrasing, no banned phrase, and
the existing `test_home_rung_disclosure_is_a_fact_without_directives` guard
still applies to the disclosure. The point is that an agent holding
`timber 38, clay 84` can see that `house` is a type, what it costs, and what
it pays - which is the only thing that has been missing.

### 3.5 The viewer can show the ladder

`__GENESIS_PROTO__.getHomeRungReport()` gains `tier_weight`, `tier_index`,
`best_rung`, and `next_threshold` (the footprint/rung combination that would
raise the tier, or `null` at the cap), so the HUD can render
`HOME tier 5/8 - next at 26` instead of a bare footprint. Viewer-only; agent
behaviour is untouched.

## 4. Verification - Phase 10QE

New suite `world-sim/tests/test_rung_payoff.py`:

1. `test_one_house_outranks_the_shacks_it_replaces` - a single finished
   `house` yields a strictly better tier weight than N `lean-to`s, where N is
   the number whose combined footprint matches.
2. `test_a_rung_five_home_reaches_the_old_cap_on_its_own` - one finished
   longhouse, no other structures, reaches tier weight >= 12.
3. `test_footprint_saturates_but_rung_does_not` - past 12 roofed tiles,
   additional shacks add 0; a rung upgrade still adds its full bonus.
4. `test_tier_table_rows_are_strictly_ordered` - every added row beats the row
   below it on all five axes, and no 10PJ row was modified.
5. `test_west_live_settlement_keeps_its_tier` - footprint 46 with best rung
   cabin gives tier weight 16, strictly above today's cap of 8.
6. `test_house_grants_a_hearth_slot` - `cook` against a roofed `house`
   succeeds; the same cook against a roofed `cabin` is still rejected.
7. `test_longhouse_doubles_the_cellar_budget` - capacity with a finished
   longhouse in the network is exactly twice the same network without one.
8. `test_ladder_is_disclosed_with_floors_effects_and_no_directives` - all five
   rung names, floors and effects appear in the prompt; no banned phrase.
9. `test_disclosure_states_the_saturating_footprint` - the home-tier line
   names both the raw footprint and the tier weight.
10. `test_existing_footprint_arithmetic_is_unchanged` -
    `test_home_network_scaling.py`'s 1 + 1 + 2 == 4 still holds, proving
    saturation happens in the tier lookup and not in the census.

Plus the existing suites that must stay green: `test_structure_rungs.py`,
`test_home_network_scaling.py`, `test_thirst_spoilage_tool_condition.py`,
`test_construction_staging_visual.py`, `test_load_bearing_construction.py`,
`test_drink_action_phrasing.py`, `git diff --check`, CRLF=0.

## 5. Scope boundaries

- Touches `backend/world/first_pair_runtime.py`,
  `backend/world/first_pair_cognition_model.py`, the `__GENESIS_PROTO__` block,
  and the new suite. No schema change, no migration of the 90 and 153 existing
  public objects, no new agent action, no goal injection.
- **No `world-sim/data` writes.** No runtime restart - lockstep spawns fresh
  subprocesses per heartbeat, so both lanes pick this up on the next one.
- Viewer changes are HUD-only and must not alter agent behaviour.
- One thing this phase deliberately does **not** decide: whether a rung-5
  home should eventually pay more than a 36-tile network. The table now ends
  at 36 with the best parameters either lane has ever had, and the honest
  answer to "what is past a longhouse" belongs to the operator, not to a
  silent row appended by an implementation agent.

## 6. Why this is the right next step

The operator's complaint is that the ladder stops, and the measurement says it
stops four times over: the weight column nobody reads, a tier table with a
ceiling, two rung effects that are only prose, and a vocabulary the agents
have never been shown. All four are small, mechanical, and independently
testable, and together they change the only thing that matters - whether
raising one proper home is better than raising the next shack.
