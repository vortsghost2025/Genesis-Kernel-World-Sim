# Phase 10QF - The Cistern Rung: Water Becomes a Home-Scale Resource

Specification. Implementation is the candidate phase 10QG.

Operator, 2026-11-12, after watching the agents collapse for the twelfth
hour: *"what should come past a longhouse?"*

Phase chain: 10QF (spec) -> 10QG (implementation candidate).

---

## 1. Why the ladder stopped where it did

The five canonical rungs (`lean-to`, `hut`, `cabin`, `house`, `longhouse`)
are a ladder of QUANTITY: each is more materials and slightly better
numbers. Measured across the live lanes on 2026-11-12:

| observation | measurement |
|---|---|
| houses or longhouses ever built, both lanes | **0** |
| heartbeats of agent reasoning mentioning a house, rung, ladder or tier | **0** of 408 |
| agents that collapsed with thirst at 100 | **3 of 4** |
| weather readings colder than "clear/overcast/rain" in 400 heartbeats | **0%** |
| objects anywhere in either lane holding fresh_water | **0** |
| West lane objects of type `well` / `container` / `storage` | 3 / 40 / 44 |
| West lane containers actually holding water | **0** |

The last three rows are the finding. The lanes have forty containers and
three wells and **not one of them has ever held a unit of water**, while
three of four agents died of thirst. Water is not a home-scale resource: it
must be carried by hand from a river tile, and a collapsed body cannot move.
The rungs above `lean-to` cost MORE of the one thing that was killing
everyone, and none of them did anything about it.

Meanwhile the warmth half of the ladder - comfort floor, cold decay, rest
recovery - is inert, because it never gets cold: 0% of readings were cold
and warmth sat at 88-100 throughout. The 550B model started walking 35
tiles to deliver water to a collapsed partner because the world gave it no
other way to help.

## 2. The change: the ladder turns from bigger to more capable

### 2.1 Rung 6 - `cistern`

| rung | type | material floor | effect gained |
|---|---|---|---|
| 6 | `cistern` | timber 2, stone 8, clay 6 | holds fresh water for the home; a filled cistern makes its tile drinkable |

A cistern is a lined pit, not a building: it needs almost no timber and a
lot of stone and clay. Its value is NOT a bigger tier number - it is that
**water can live at home**.

Mechanics:

- A cistern is a runged dwelling: it is built through the existing staged
  construction path (foundation -> frame -> walls -> roofed -> finished),
  spends the rung floor exactly, and counts toward the roofed footprint.
- It holds `fresh_water` in `contents`, filled by the existing `deposit`
  action, up to a capacity of **20 units**. A cistern is the first object
  in the world whose capacity is about water rather than food.
- While it holds at least one unit, **its tile is drinkable**. The
  environment fact reports `drinkable_water: true` with
  `drinkable_source: "cistern"` and the unit count, so the agent can see
  that the supply is finite rather than a river.
- Drinking from a cistern tile **consumes exactly one unit** and satisfies
  55 thirst points - the same satisfaction as carried water, because it IS
  carried water after storage. A river still satisfies 75 and is
  unlimited; the two sources are never confused.
- Because the `drink` action is permitted for a collapsed body, **a
  collapsed agent beside a filled cistern can drink** and recover. This is
  the case that killed three agents in twelve hours.

### 2.2 The tier numbers

`_RUNG_TIER_BONUS` gains rung 6:

| rung | type | bonus | tier weight alone | comfort floor |
|---|---|---|---|---|
| 5 | longhouse | 11 | 15 | 80 |
| 6 | cistern | 13 | 15 | 80 |

A cistern alone does NOT out-tier a longhouse. That is deliberate: the
ladder stops being a pure tier race and starts having effects worth more
than numbers. If it out-tiered everything, the cistern would be built for
its bonus rather than for its water.

### 2.3 Named, specified, not built

Two further rungs are named here and deliberately NOT implemented, so that
the ladder's shape is visible without inventing mechanics nobody has
measured:

| rung | type | floor | effect | status |
|---|---|---|---|---|
| 7 | `hall` | timber 6, stone 8, clay 4 | the home's tier applies to BOTH agents wherever they are | **named only** |
| 8 | `stead` | timber 8, stone 10, clay 6, **and a second creator** | the summit is gated on shared authorship | **named only** |

A `stead` cannot be built by one agent at any wealth: both agents must have
contributed materials to the same structure. That is the terminus the
operator asked for - the top of the ladder is the pair, not a bigger pile.

## 3. Scope boundaries

- Touches `backend/world/first_pair_runtime.py` (the rung table, the bonus
  table, the drinkable-tile logic, the drink action, the deposit capacity,
  the environment facts) and `world-sim/viewer/prototype/index.html` (the
  cistern's visual and the rung table the HUD reads).
- **No change to the existing rungs.** Their floors, weights, bonuses and
  effects are untouched; the 10PJ and 10QC numbers keep holding.
- **No new agent action.** `build`, `deposit` and `drink` keep their
  existing fields. A cistern is built with `build`; it is filled with
  `deposit`; it is drunk from with `drink`.
- **No schema change and no migration.** Existing objects are unaffected.
  The existing 44 `storage` objects and 3 `well` objects in West stay
  exactly what they are; a `well` remains a plain container, and only a
  `cistern` is a rung.
- No `world-sim/data` writes. No goal injection, no directive phrasing, no
  banned phrases in any new disclosure line.
- The viewer change is a visual and a HUD row only; it must not alter
  agent behaviour.

## 4. Verification - Phase 10QG

New suite `world-sim/tests/test_cistern_rung.py`:

1. `test_cistern_is_rung_six_with_its_floor_and_bonus` - the rung exists,
   costs timber 2 / stone 8 / clay 6, weighs 2, and its bonus is 13.
2. `test_a_cistern_is_built_through_the_staged_path` - it is a staged
   project, spends the floor exactly, and shelters only when roofed.
3. `test_a_cistern_counts_toward_the_home_tier` - a finished cistern gives
   tier weight footprint + 13, so a lone cistern matches a lone longhouse.
4. `test_a_cistern_holds_water_up_to_its_capacity` - deposits fill it to 20
   units and the 21st is refused.
5. `test_a_filled_cistern_makes_its_tile_drinkable` - the environment fact
   says drinkable, with source `cistern` and the unit count; an empty
   cistern says not drinkable.
6. `test_drinking_from_a_cistern_consumes_exactly_one_unit` - one drink,
   one unit, 55 thirst points; the supply is finite.
7. `test_a_cistern_is_not_an_infinite_river` - a canonical river tile still
   satisfies 75 and consumes nothing; a cistern tile satisfies 55 and
   consumes one.
8. `test_a_collapsed_body_can_drink_from_a_cistern_beside_it` - the case
   that killed three agents: collapsed, thirsty, on a filled cistern's tile,
   and able to drink.
9. `test_the_ladder_disclosure_lists_the_cistern` - the prompt names the
   cistern with its floor and effect, and no banned phrase appears.

Plus the full suite, `git diff --check`, and CRLF=0.

## 5. Why this is the right next step

The operator's question - what comes past a longhouse - has an answer that
the twelve-hour measurement supports and that a bigger building does not:
the ladder's next rung should do something the previous five cannot. Water
at home is that thing, because water at home is the difference between a
collapsed body that recovers and a collapsed body that dies. The `hall` and
the `stead` stay named and unbuilt until the cistern has been watched for
long enough to know whether it changes what the agents do.
