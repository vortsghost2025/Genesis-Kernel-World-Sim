# Phase 10PK — Thirst, Spoilage, and Tool Condition Specification

## Operator request (2026-11-08)

Add missing ordinary survival pressure from the period: thirst, food
spoilage, and tool deterioration. Docs-only; implementation is Phase 10PM.
Phase chain: 10PK (spec) → 10PL (metadata sync) → 10PM (implementation
candidate).

## Measured problem

- The body tracks hunger, warmth, wetness, and vitality, but thirst is
  absent. Drinkable water tiles and a `fresh_water` gather target exist,
  yet nothing makes them matter.
- Inventories and object contents never rot. The claimed
  `storage_cellar` benefit is capacity-only, so indefinite hoarding is
  free.
- Crafted stone_axe, iron_axe, flint_knife, spear, and woven_basket items
  are permanent. Tools that never dull or break remove the maintenance
  loop that makes early woodworking and hunting material.
- Agents have no factual `drink` action, so `fresh_water` can never be
  consumed from holdings or a clay_pot, and carried food has no
  freshness clock.

## Design (implemented in 10PM)

1. **Thirst.** Daily rising thirst (`+0.8/hb`) and severe-dehydration
   vitality drain begin at thirst 88. `drink` is factual and optional:
   immediate drinking from a current drinkable tile reduces thirst by 75;
   one `fresh_water` from belongings or from a clay_pot object on the
   same/adjacent tile reduces thirst by 55. Rain does not quench thirst.
   Existing stores seed the new `thirst` value without retroactive harm.
2. **Spoilage.** Perishable lots age in heartbeats; older lots are eaten
   first and expired servings are removed before the heartbeat's action.
   Cellars apply `4 + connected roofed footprint` as their effective
   lifetime multiplier, so a larger home preserves food longer. Existing
   untracked inventory and contents are grandfathered fresh at the
   migration heartbeat; no backdated rot is invented.
3. **Tool condition.** Crafted tools get remaining-use records. Axes,
   knives, spears, and woven baskets accrue one wear per successful
   gather, hew, attack, or basket forage. A newly crafted item starts
   full; a broken item is removed from belongings only after its full
   uses are spent. Tools in existing stores are grandfathered at full
   condition.
4. **Prompt disclosure.** The cognition model renders thirst, drain,
   direct drink, water sources, spoilage/effective storage status, and
   remaining tool condition as facts only, without survival directives.

## Verification

- TDD: thirst rises and drains; drink works from tile, holdings, and pot;
  spoilage removes aged food; cellar footprint extends preservation;
  tools break after exact use counts; schema accepts `drink`; behavior
  packs are green; `git diff --check` clean; CI green.
- No `world-sim/data` writes, no migration of public objects, no viewer
  work, no taming, no goal injection. Existing inventory quantities and
  public-object placements remain untouched.
