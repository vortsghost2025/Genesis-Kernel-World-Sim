# Phase 10QU — Home Quality: the payoff ladder keyed to what a home IS

**Status:** spec (this commit). Implementation is 10QV. Index sync is 10QW.

Operator, 2026-11-14, watching the live viewer:

> "maybe there just isint enough benefits for them to build a single main
> shelter and then just have smaller temp shelter when exploring"

Measured the same hour. **The operator is right**, and the reason is exact.

---

## 1. The measurement

### 1.1 Cold is lethal, but the cheapest roofed tile already defeats it

| quantity | value | source |
|---|---|---|
| winter base temperature | **26** | `survival.SEASON_BASE_TEMP` |
| night swing | ±13 | `survival.DAY_NIGHT_AMPLITUDE` |
| winter midnight ambient | **13** | 26 − 13 |
| vitality begins draining at warmth | **≤ 20** | `survival.FREEZE_THRESHOLD` |
| warmth closes of the gap per heartbeat | **10%** | `survival.WARMTH_APPROACH_RATE` |
| unsheltered, winter night, 100 → 20 | **≈ 17 heartbeats** | drift at 10%/hb |
| a night is | **36 heartbeats** | `DAY_LENGTH` 72, night = half |

So going unsheltered through a winter night drains vitality — shelter really is
life-or-death. But:

| quantity | value | source |
|---|---|---|
| comfort floor inside **any** roofed tile | **45.0** | `survival.SHELTER_COMFORT_FLOOR` |
| the tier-1 row of the warmth table | **(45.0, 0.45, 1.00, 0.40, 0.10)** | `_HOME_NETWORK_TIERS[0]` |

`_home_network_tier(1)` and `SHELTER_COMFORT_FLOOR` are the same 45. **One
lean-to sets the floor 25 points above the freeze line.** Nothing in the rules
dies at a 45 floor, so survival stops being a reason to build anything better.

### 1.2 Everything above rung 1 buys comfort, not survival

From `_HOME_NETWORK_TIERS` (comfort floor, cold decay, rest regen, downed
regen):

| tier row | floor | decay | rest regen | downed regen |
|---|---|---|---|---|
| 1 (a lone lean-to) | 45.0 | 0.45 | 1.00 | 0.40 |
| 2 | 52.0 | 0.30 | 1.25 | 0.55 |
| 3 | 62.0 | 0.18 | 1.50 | 0.70 |
| 5 | 68.0 | 0.14 | 1.75 | 0.90 |
| 8 | 75.0 | 0.10 | 2.00 | 1.10 |
| 12+ | 80.0 | 0.09 | 2.20 | 1.40 |

Every floor in that table is above the freeze threshold of 20. **No row in it
is a survival upgrade over row 1.**

### 1.3 The payoffs that DO gate on rung sit at the top of the ladder

* predator protection: identical for **every** roofed kind — `_in_shelter`
  gives it to all of them, which is why 10QC dropped rung 2's "predators refuse
  the tile" promise (it was already universal);
* cellar food capacity: needs **rung 5** (`_record_rung(rec) >= 5` doubles it);
* cistern water: needs **rung 6**.

So the ladder reads: *rung 1 = you survive winter; rungs 2–5 = comfort; rung 6
= water.* The middle of the ladder has no felt payoff at all.

### 1.4 The ladder is barely registering in the world

Live `structure_rung` across roofed objects:

| pair | roofed objects | rung unset | rung set |
|---|---|---|---|
| west | 154 (shelter 111, cabin 23, lean-to 20) | **140** | 14 (all rung 1) |
| east | 66 (shelter 30, lean-to 29, cabin 7) | **61** | 5 (rung 3 ×2, rung 1 ×3) |

They build the generic, rung-less `shelter`, so the rung bonuses mostly do not
attach to their buildings at all.

### 1.5 And the settlement shapes match the incentive exactly

* **West:** one **34-tile connected compound** plus six outposts of 1–3 tiles.
  That is literally "one main shelter plus small temp shelters when exploring".
* **East:** **31 separate clusters, largest only 5 tiles.** No main home.

The sprawl is rational, because the ladder does not pay.

---

## 2. What this phase changes

Two changes, in the order the operator approved them.

### 2.1 (A) The comfort ladder is keyed to the home's BEST RUNG, not its size

Today `_shelter_params_for` feeds `_home_tier_weight(footprint, best_rung)`
into `_home_network_tier` — so **twelve shacks out-warm one well-built house**,
which is the defect.

New: the warmth lookup is keyed by the network's best **rung**, through a
single shared map onto the existing table (one source of truth, no new table):

```
_THERMAL_TIER_BY_RUNG = {1: 1, 2: 2, 3: 3, 4: 5, 5: 8, 6: 12}
```

| home | floor | decay | rest regen | downed regen |
|---|---|---|---|---|
| lean-to (rung 1) | 45.0 | 0.45 | 1.00 | 0.40 |
| hut (rung 2) | 52.0 | 0.30 | 1.25 | 0.55 |
| cabin (rung 3) | 62.0 | 0.18 | 1.50 | 0.70 |
| house (rung 4) | 68.0 | 0.14 | 1.75 | 0.90 |
| longhouse (rung 5) | 75.0 | 0.10 | 2.00 | 1.10 |
| cistern tier (rung 6) | 80.0 | 0.09 | 2.20 | 1.25 |

**Footprint no longer warms a home.** It still drives: cellar food capacity
(`_CELLAR_FOOD_BUDGET_PER_FOOTPRINT × tier_weight`), the tier weight used for
settlement scoring, and housing room. Size buys **space**; quality buys
**warmth and recovery**.

Invariants this must preserve:

1. **No new deaths.** The worst case is unchanged: a lone rung-1 or rung-less
   structure reads floor 45.0, exactly as today. Every row is above the freeze
   threshold of 20, so no reachable state newly drains vitality.
2. **Disclosure equals physics.** `_home_rung_for` (the prompt text, line
   ~1821) and `_shelter_params_for` (the physics, line ~2899) must derive the
   tier through the SAME helper, or the agent is told a floor it does not get.
3. **Existing compounds are grandfathered, not nerfed to nothing.** West's
   34-tile compound drops from floor 80 (tier 16 by size) to 62 (its best rung
   is a cabin) — a deliberate consequence, still 42 points above freezing.

### 2.2 (B) A home can bank water, and the ladder says how much

Water is what actually killed them: three of four agents collapsed at thirst
100, and not one object in either lane had ever held a unit of `fresh_water`.

The mechanics already exist and need no new drink logic: `_cistern_on_tile`
was generalised by 10QJ, so **any object on a tile whose `contents` hold
`fresh_water` makes that tile drinkable**, finite, and consumable per unit —
including by a collapsed body. What is missing is (i) a legible capacity for a
dwelling, and (ii) any disclosure that a dwelling can hold water at all, so no
agent has ever formed that plan.

New: a water store, keyed to the home's best rung, mirroring
`_CELLAR_FOOD_BUDGET_PER_FOOTPRINT` and enforced at deposit exactly as the
cellar budget is:

```
_WATER_STORE_BY_RUNG = {1: 3, 2: 6, 3: 10, 4: 14, 5: 18, 6: 20}
```

The cistern keeps its own `_CISTERN_WATER_CAPACITY = 20`, so the rung-6
cistern remains the best store in the world and its documented behaviour is
untouched. A lean-to holds 3 — small, but not zero, so this **removes no
capability**: a dwelling that holds water was already drinkable at its tile.

Disclosure: the home section states the store and its capacity, so "carry water
home and bank it" becomes a plan an agent can form.

---

## 3. Why this should change the behaviour

Under (A) + (B), a lone lean-to is: floor 45, rest regen 1.00, downed regen
0.40, water store 3. A house is: floor 68, rest regen 1.75, downed regen 0.90,
water store 14. The upgrade now changes **how fast they heal**, **how fast they
stand up after collapsing**, and **how much water they can keep** — three
things the agents already feel and already talk about, and one of which (water)
is what has actually been killing them.

Expected, watchable consequences: fewer stage-1 lean-tos in the wild, at least
one rung-3+ structure per pair, and water appearing in a home's contents for
the first time in the world's history.

---

## 4. Out of scope (deliberately)

* **Deepening winter.** Not doing it: at winter midnight ambient 13 an
  unsheltered body freezes in ~17 of 36 night heartbeats, and making that worse
  kills agents rather than directing them.
* **Making predator immunity rung-scaled.** `_in_shelter` is universal; that is
  10QC's documented decision and is not re-opened here.
* **Any change to `_FOOTPRINT_SATURATION`, `_RUNG_TIER_BONUS`, or
  `_HOME_NETWORK_TIERS`' numbers.** The 10PJ rows and the 10QC tier rows are
  pinned verbatim by tests and are not touched by this phase.

---

## 5. Test plan (10QV)

Pure tests, no provider, no network, tempdir stores only:

1. a lone rung-1 structure reads floor 45.0 — **the invariant that no new
   deaths are possible**;
2. a network whose best structure is rung 4 out-warms a 12-tile network of
   rung-1 shacks, in floor AND in rest regen AND in downed regen (the defect
   stated directly);
3. footprint alone no longer raises the floor (add roofed tiles, floor stays);
4. adding one higher-rung structure to the shanty town raises it;
5. `_home_rung_for`'s disclosed `comfort_floor`/`cold_decay`/`rest_regen`
   equals `_shelter_params_for`'s physics for the same tile — disclosure equals
   physics;
6. cellar food capacity still scales with footprint (space is not nerfed);
7. a dwelling's water store equals `_WATER_STORE_BY_RUNG[rung]`;
8. depositing water into a dwelling is accepted up to its store and **rejected
   past it**, and the rejection names the capacity;
9. the cistern's 20 is unchanged and still the largest store;
10. a home holding water makes its own tile drinkable, and a collapsed body on
    that tile can drink (the case that killed three agents).
