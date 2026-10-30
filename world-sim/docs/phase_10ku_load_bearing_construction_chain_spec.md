# Phase 10KU Specification: Load-Bearing Construction Chain

> **Phase Chain:** 10KS (impl, Done `66a070a`) -> 10KT (metadata sync, Done `6ca94e3`, hash-corrected `b45f81b`) -> 10KU (specification, this document) -> 10KV (metadata sync) -> 10KW (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10KW following explicit operator authorization.

---

## 1. Origin & Verified Diagnosis

Sean's field report from the live observatory: agents slide rather than walk, they build five scattered huts rather than one proper structure, no trees come down, and no animal is ever fed. A diagnostic was run against the canonical stores and the source. Four defects were isolated, each independently verified.

### 1.1 The construction chain that should exist

```
craft a tool  →  hew_timber  →  structural frame  →  compound rooms (addon_to)
(on a surface)   (needs blade)   (needs timber)        (cheaper than a 2nd hut)
```

### 1.2 Measured usage across both lanes' complete history

| Mechanic | Implemented | Ever called |
| :--- | :--- | :--- |
| `use_object(operation="craft")` | 10JI | **0** — not once, not rejected, never attempted |
| `hew_timber` | 10JX | **0** |
| `build(addon_to=...)` | 10JX | **0** |
| `offer_food` / `milk_animal` | 10JN/10JR | **0** |
| `plant_crop` / `harvest_crop` | 10JX | **0** |

East: 5,817 moves, 2,400 gathers, 102 builds, 0 crafts. West: 298 builds, 2,376 gathers, 0 crafts.

### 1.3 The four defects

**Defect A — Recipes are undiscoverable (root cause of 0 crafts).**
`FirstPairRuntime._CRAFT_RECIPES` (`first_pair_runtime.py:2617-2627`) is a private table keyed by exact material tuples:
```python
(("flint", 2), ("wood", 1)): "flint_knife",
(("stone", 2), ("wood", 1)): "stone_axe",
```
The cognition prompt advertises only *categories* — `first_pair_cognition_model.py:1155` reads *"craft combines materials into tools (knives, spears, axes, baskets, pots on crafting_surface objects)"*. The string `recipe` appears **0 times** in the entire cognition model. No material, no quantity, no ratio is ever disclosed.

Verified consequence: **West Adam holds 21 `flint` and 5 `wood` and stands 1 tile from his own `adam_clay_forge_35_52_001`**, and has the exact materials for `{"flint": 2, "wood": 1}`. The agent is positioned and equipped to craft and has no way to know the formula. Crafting is guesswork over a combinatorial space.

**Defect B — East has no crafting surface at all.**
East Valley holds 75 public objects: 25 campfires, 23 landmarks, 11 shelters, 11 food_processor, 2 lean-to, 2 storage_box, 1 roof. **Zero** `crafting_surface`, `forge`, `workbench`, or `workshop`. `_execute_use_object` rejects craft on any non-surface object (`first_pair_runtime.py:2524-2526`), so crafting is *impossible* in East, not merely unused.

**Defect C — `build` does not require timber, so `hew_timber` has no purpose.**
`_execute_build` (`first_pair_runtime.py:2230`) accepts **agent-declared** materials — `{"stone": 3}` or `{"wood": 4}` — and shelters are just a `object_type` string. Nothing forces structural timber. Agents build shelters from gathered stone and clay, so tree-felling is never load-bearing and the framing path stays dormant.

**Defect D — `addon_to` offers no advantage over a second freestanding hut.**
`_execute_build`'s `addon_to` path (`2252-2270`) validates adjacency and position and then costs the *same* declared materials as any other build. There is no economy that makes attaching a room cheaper than putting another hut on a neighbouring tile, so compounding never emerges.

---

## 2. Scope

### 2.1 In Scope (Phase 10KW Candidate)

1. **Recipe discoverability.** Publish the craft recipe table into the agent's prompt so an agent holding the materials knows the formula.
2. **Surface availability.** Ensure each lane can reach a crafting surface through ordinary play, without hand-placed worlds.
3. **Load-bearing timber.** Make structural construction require hewn timber so `hew_timber` becomes necessary rather than optional.
4. **Compound economy.** Make `addon_to` materially cheaper than a freestanding equivalent.

### 2.2 Out of Scope

- Viewer/rendering work: walk cycles, scaffolding, tree-felling animation, interiors, agents entering buildings. **Explicitly deferred** — it should follow construction behavior, not animate its absence.
- Any new tool, species, recipe, or resource kind beyond what is already implemented.
- Live store edits, goal surgery, or operator messaging. The 10KN finding stands: operator speech converted epistemic dependence and is exhausted.
- Predator, snake, or combat behavior changes.

---

## 3. Design Invariants

1. **Discoverable, not dictated.** Publishing recipes tells the agent what the world *is* (what materials combine into what). It must never tell the agent what to *make*. The distinction from Standing Rule 7 holds: facts, not strategy.
2. **Fail-closed and unchanged.** Existing rejections (`object_type` mismatch, insufficient holdings, adjacency) remain exactly as they are. New work adds paths, it does not loosen existing validation.
3. **Persistence of history.** Nothing already built is invalidated. Shelters built without timber remain valid; the timber requirement applies to *new* construction only, and 10KW must not retroactively reject or delete existing objects.
4. **No free lunch for the cheap path.** The point is to close the cheap path, so any new affordance must be earned. A surface must be built from held materials; timber must be felled; compounds must cost less than the alternative.
5. **Determinism untouched.** No change to RNG, seeding, or fauna drift.

---

## 4. Architectural Specifications

### 4.1 Recipe Discoverability (`first_pair_cognition_model.py`)

Generate the advertised recipe list from the runtime's own table rather than duplicating it, so the prompt cannot drift from the code:

```python
from backend.world.first_pair_runtime import FirstPairRuntime

_CRAFT_RECIPE_LINE = (
    "- Crafting recipes (use_object with operation 'craft' on a crafting_surface, "
    "forge, workbench, or workshop; declare the materials exactly): "
    + "; ".join(
        f"{dict(m)} -> {out}"
        for m, out in sorted(FirstPairRuntime._CRAFT_RECIPES.items())
    )
    + "."
)
```

Rendering each entry as a literal material dict (`{'flint': 2, 'wood': 1} -> flint_knife`) gives the agent the exact formula and nothing else. Requirements for 10KW:

- The list is emitted inside the existing action-advertisement block, adjacent to the `use_object` line.
- Tool *outputs* remain named so their downstream use (`hew_timber` requires `stone_axe`, `iron_axe`, or `flint_knife`) stays legible.
- `_COOK_RECIPES` is discovered by the same mechanism. Cooking already has 6 working recipes and zero recorded rejections, so it is harmless to disclose and consistent to treat uniformly.
- A regression test asserts the rendered advertisement contains every key of `_CRAFT_RECIPES`, so a future recipe added to the table cannot silently become undiscoverable.

### 4.2 Crafting Surface Availability

East cannot craft. Rather than hand-placing a surface, make the *first* surface an ordinary act of building:

- An agent standing on any tile may `build` a `crafting_surface` from materials already commonly held. East Adam holds 306 `stone` and 151 `clay`; West Adam holds 39 `stone` and 38 `clay`.
- Recipe: `{"stone": 3, "wood": 2} -> crafting_surface` (or `{"clay": 3, "wood": 2}`), treatable as a new `_CRAFT_RECIPES`-adjacent rule or a `build`-recognized structural type. 10KW must pick one and document it.
- Once a surface exists on an agent's tile, `use_object(craft)` is reachable under the *existing* validation at line 2524 — no change to that check.
- Test: build a surface from held materials, then craft a `flint_knife` on it, asserting both succeed.

### 4.3 Load-Bearing Timber (`_execute_build` + `_execute_hew_timber`)

Structural types acquire a timber floor. Current types are advertised at cognition line 1151: `shelter`, `cabin`, `hut`, `roof`, `shelter_stable`, `storage_cellar`, `enclosed_garden`, `campfire`, `hearth`, `crafting_surface`.

- Introduce a `_STRUCTURAL_TIMBER_MIN` map. Structural types (`shelter`, `cabin`, `hut`, `roof`) require a minimum of hewn `timber`, e.g.:
  ```python
  _STRUCTURAL_TIMBER_MIN = {"shelter": 2, "cabin": 3, "hut": 2, "roof": 1}
  ```
- `_execute_build` checks the declared materials for sufficient `timber` before the generic affordability check and rejects with a specific reason: *"A shelter needs at least 2 structural timber; fell trees with hew_timber once you hold an axe or knapped blade."*
- Non-structural types (`campfire`, `crafting_surface`, `enclosed_garden`, `storage`) keep their existing material rules. Campfires must stay cheap — fire is the entry point to warmth and cooking.
- `hew_timber` stays exactly as implemented (`first_pair_runtime.py:2002-2032`): axe yields 2, blade yields 1, tool gate unchanged.
- **Legacy rule (invariant 3):** existing `shelter`/`hut`/`roof` objects are grandfathered. The floor applies only to new builds. 10KW must not purge or reject history.

### 4.4 Compound Economy (`_execute_build` addon_to path)

Make attaching materially cheaper so compounding is the rational choice:

- When `addon_to` references a valid adjacent parent, discount declared material costs — e.g. structural types spend **half** the timber minimum on the addon, rounding up, because shared walls bear load.
- The discount applies *only* to the structural-timber component; stone/clay/fiber costs remain as declared.
- Result: a 3-room compound costs less total timber than three freestanding huts, and the shared-hearth mechanic from 10JX (already implemented in `_nearby_fire` and advertised at cognition line 1151) becomes worth pursuing.
- Test: build two freestanding shelters and one 2-room compound with `addon_to`, assert the compound's total timber cost is strictly lower.

---

## 5. Required Test Coverage for Phase 10JW

In `tests/test_load_bearing_construction.py`:

1. `test_recipe_advertisement_covers_every_recipe`: the rendered prompt contains every `_CRAFT_RECIPES` key, so drift fails the build.
2. `test_crafting_surface_buildable_from_common_materials`: an agent holding only stone/clay/wood can build a surface.
3. `test_craft_flint_knife_on_new_surface`: crafting succeeds on a freshly built surface with `{"flint": 2, "wood": 1}`.
4. `test_shelter_requires_timber`: a `shelter` build declared without `timber` is rejected with the guidance reason.
5. `test_shelter_succeeds_with_timber`: a `shelter` build with sufficient timber succeeds and deducts.
6. `test_addon_costs_less_than_freestanding`: total timber for a 2-room compound is strictly less than two freestanding shelters.
7. `test_existing_shelters_grandfathered`: pre-existing `shelter` objects in a loaded store remain valid and are not rejected.
8. `test_campfire_still_cheap`: a `campfire` build with no timber still succeeds.
9. `test_recipe_advertisement_discloses_no_strategy`: the advertised string contains material formulas and tool names, and contains none of the banned directive phrases.

---

## 6. Governance & Progression

- **Phase Chain:**
  - `10KS`: Multi-Step Trajectory Suite & Horizon Sighting Implementation (Done `66a070a`).
  - `10KT`: Metadata Sync (Done `6ca94e3`, hash-corrected `b45f81b`).
  - `10KU`: Load-Bearing Construction Chain Specification (this document) -- Docs only.
  - `10KV`: Metadata Sync -- Record 10KU hash in `phase_index.md`, name 10KW candidate.
  - `10KW`: Implementation candidate -- TDD implementation of recipe disclosure, surface availability, load-bearing timber, and compound economy.
- **Constitutional Guardrails:**
  - Docs-only specification; no implementation code is authorized under Phase 10KU.
  - Do not edit live stores, canonical world state, or daemon processes.
  - Preserve determinism and all existing fail-closed rejections.
  - Grandfather all existing structures.
  - Stage ONLY `world-sim/docs/phase_10ku_load_bearing_construction_chain_spec.md`. Never `git add -A` or `git add .`.
  - Pure LF line endings (`CRLF=0`).
