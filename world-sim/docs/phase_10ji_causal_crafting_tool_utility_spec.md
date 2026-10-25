# Phase 10JI Specification: Causal Crafting & Neolithic Tool Utility

**Status:** SPECIFICATION & IMPLEMENTATION PLAN
**Date:** 2026-10-25
**Phase Chain:** 10JI (spec, L) -> 10JJ (sync, L+1) -> 10JK (implementation candidate, L+2).
**Origin:** Operator mandate ("I want to give them all the possibilities humanity had to figure out and build and expand").
**Substrate Context:** Resolves the historic stalemate documented in West Adam's charter (HB 1674–4216: *"this world is a record-keeping space, not an interaction space... objects are inert records"*).

---

## 1. Problem & Architectural Diagnosis

1. **Inert Materials & Missing Affordances**:
   - West Adam gathered 21 flint, East Eve gathered 20 fiber plants, East Adam holds 178 clay and 214 stone.
   - The runtime previously recognized only 3 hardcoded craft recipes (`stone_axe`, `fiber_rope`, `stone_hammer`), and flint had zero recipes.
   - More critically, **crafted tools had zero physical causal effect**: holding a `stone_axe` did not improve wood gathering, holding a `fiber_rope` had no function, and weapons did not defend against predators.
2. **Raw Diet in a World with Fire**:
   - In `backend/world/survival.py`, physical constants for `cooked_meal` (75.0 hunger satisfaction) and `COOKED_MULTIPLIER = 2.5` were defined, but no runtime mechanism existed to cook raw food at a campfire.
   - Agents survived strictly on raw wild berries and roots.

---

## 2. The Four Causal Pillars of Phase 10JI

### Pillar A: Flint Knapping & Tool Crafting
Extends `_CRAFT_RECIPES` in `FirstPairRuntime` on crafting surfaces (`crafting_surface`, `forge`, `workshop`, `workbench`):
- `(("flint", 2), ("wood", 1)) -> "flint_knife"`
- `(("fiber_plants", 1), ("flint", 1), ("wood", 2)) -> "flint_spear"`
- `(("fiber_plants", 3),) -> "fiber_rope"` (preserved)
- `(("fiber_plants", 4), ("wood", 2)) -> "woven_basket"`
- `(("clay", 3),) -> "clay_pot"`
- `(("iron", 2), ("wood", 1)) -> "iron_axe"`
- `(("fiber_plants", 1), ("iron", 1), ("wood", 2)) -> "iron_spear"`
- `(("stone", 2), ("wood", 1)) -> "stone_axe"` (preserved)
- `(("stone", 1), ("wood", 2)) -> "stone_hammer"` (preserved)

### Pillar B: Causal Tool Utility
Physical interactions in `first_pair_runtime.py` now check the agent's inventory for relevant tools:
1. **Wood Hewing with Stone/Iron Axe**:
   - Gathering `wood` without an axe yields base fallen wood (1 unit).
   - Gathering `wood` while holding `stone_axe` or `iron_axe` yields hewn timber (5 units) and reports `"(hewn with axe)"`.
2. **Predator Defense with Spear or Axe**:
   - In the nighttime wolf attack resolution:
   - When a wolf attempts to bite an unsheltered agent, holding a `flint_spear`, `iron_spear`, `stone_axe`, or `iron_axe` repels the attacking wolf immediately (`e["hp"] = 0`), preventing bite vitality drain.
   - In `wildlife.strike`: weapon multipliers apply full strike damage to both deer and wolves.
3. **Carry Utility with Woven Basket**:
   - Holding a `woven_basket` increases gathering yield for foraging items (berries, roots, mushrooms) from 1 to 3 units and reports `"(gathered with woven basket)"`.

### Pillar C: Campfire & Hearth Cooking
Enables `operation="cook"` on `use_object` when standing at an active, functional fire object (`campfire`, `hearth`, `fire`, `cooker`, `oven`):
- **Functional Fire Rule**: The fire object must have been constructed with materials (`_is_functional_fire(obj)` is True).
- **Weather Rule**: Open fires snuffed by rain, storm, or blizzard cannot cook unless protected under a shelter or roof.
- **Eligible Recipes**:
  - `{"wild_berries": 2, "edible_roots": 1} -> "cooked_meal"`
  - `{"wild_berries": 3} -> "cooked_meal"`
  - `{"edible_roots": 2} -> "cooked_meal"`
  - `{"fish": 1} -> "cooked_meal"`
  - `{"meat": 1} -> "cooked_meal"`
  - `{"wild_grain": 2} -> "cooked_meal"`
  - `{"honeycomb": 1, "wild_berries": 1} -> "cooked_meal"`
- Consumes raw ingredients from inventory, creates `cooked_meal` (1 unit), and deposits it into the agent's inventory.
- Consuming a `cooked_meal` via `eat` satisfies 75.0 hunger points, lasting nearly two full days.

### Pillar D: Truthful Empirical Feedback & Cognition
- Outcomes explicitly report crafted and cooked transformations.
- The cognition model prompt advertises `cooked_meal` as edible food with 75 satisfaction in its grounded body facts.

---

## 3. Invariants & Boundaries

1. **No Forcing / No Teleportation**: Agents are never forced to craft or cook; the affordances are made available via ordinary perception and prompt schemas.
2. **Preserve All Existing Stores**: Canonical stores (`first-pair`, `first-pair-west`), ledgers, and memories are 100% preserved.
3. **TDD Verification**: All recipes, tool modifiers, and cooking mechanics are validated by strict unit and regression tests before live deployment.
