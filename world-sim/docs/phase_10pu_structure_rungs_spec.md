# Phase 10PU — Structure Rungs: One Proper House, Not Twelve Shacks

## Operator request (2026-11-10)

Operator, after watching the World Atlas: *"i also really dont like seeing 15
single houses. we need to give them a reason to build a proper house or
shelter. no one builds 12 small houese beside each other would be an insane
waste of time and resources"*

Docs-only; implementation is Phase 10PW. Phase chain: 10PU (spec) → 10PV
(metadata sync) → 10PW (implementation candidate).

## Measured problem (live lanes, 2026-11-10, tick 11,477 east / 11,844 west)

Direct audit of `world_state.public_objects`:

| | east | west |
|---|---|---|
| shelter-like objects | 72 | 142 |
| distinct tiles | 43 | 40 |
| tiles holding >1 shelter | 2 | 16 |
| connected clusters | 31 | 8 |
| single-tile clusters | **25 of 31** | **5 of 8** |
| largest footprint (10PJ units) | 5 | 45 |
| `world_state.compounds` entries | **0** | **0** |

The operator's "15 single houses beside each other" is exactly what the store
records: west's 29-tile / footprint-45 blob is dozens of independent shelter
objects that happen to touch, and east is mostly scattered singles.

## Root cause

The build path decouples *what you build* from *what it costs* and *what it
does*:

1. **`object_type` is a free-form string.** `_execute_build` derives its
   structural requirement by substring-matching `_STRUCTURAL_TIMBER_MIN`
   (`shelter`, `cabin`, `hut`, `roof`). An `object_type` of `house`, `home`,
   `dwelling`, `hut_2`, or `shelters` either misses the table entirely or
   matches a cheaper key. `house` with `{"wood": 1}` is a legal shelter today.
2. **`_in_shelter` is binary.** One lean-to and a 29-tile compound grant the
   identical protection. The only differentiation is the 10PJ footprint tier,
   and reaching the top tier *requires* ~8 adjacent roofed tiles — the physics
   actively rewards the "many singles beside each other" shape the operator
   rejects.
3. **`addon_to` compounds (10JX) exist and have never been used.**
   `world_state.compounds` is empty in both lanes after ~11,800 heartbeats.
   The one mechanic meaning "one house, many rooms" is dead code in practice.
4. **The payoff is invisible.** Warmth floor, cold decay, rest regen, and
   cellar budget are all real (10PJ) but nothing in the observation or the
   viewer HUD surfaces them, so neither the agent nor the operator can see a
   house "level up."

## Design — Phase 10PW

### 1. A closed structure vocabulary with real rungs
`_STRUCTURE_RUNGS` is an ordered table. Each rung names a canonical
`object_type` and a **floor material cost** (validated before placement, the
same seam 10KM already uses) plus **what it unlocks**:

| rung | type | material floor | effect gained |
|---|---|---|---|
| 1 | `lean-to` | 1 timber | shelter from cold (today's baseline) |
| 2 | `hut` | 2 timber, 2 wood | **walls**: predators physically refuse the tile |
| 3 | `cabin` | 3 timber, 4 stone | **door**: interior view; 1 cellar slot |
| 4 | `house` | 4 timber, 6 stone, 4 clay | **hearth slot**: cooking on the tile; footprint weight 3 |
| 5 | `longhouse` | 8 timber, 10 stone, 6 wood | the campaign build: footprint weight 4, cellar budget ×2 |

The floor is a *minimum declared amount*, not a spend list — the agent may
declare more, and 10KM's honest-materials rule (declared vs held, rejected
before any placement) is unchanged. Types outside the table are rejected with
a message that lists the five legal roofed names, which closes the free-string
hole without inventing new agent behaviour.

### 2. Extension is strictly cheaper than duplication

`addon_to` gains a structural **inheritance** rule, on top of the existing
half-timber discount:

- Attaching a room to an existing roofed structure requires only the
  *difference* between the two rungs' floors (a rung-2 room onto a rung-4
  house costs the rung-2 shortfall, nothing more).
- The room **inherits the parent's rung effects** for footprint and comfort.
- A standalone build always pays its own full floor and starts at rung 1.

This is the actual real-world reason nobody builds twelve shacks: the second
room of your house is cheaper per unit of warmth than the twelfth lean-to, and
the shacks do not compound.

### 3. Construction is a visible, staged process

Operator, 2026-11-10: *"i would like to be able to see them build things and
stuff not just see things appear"*.

Today `build` is atomic: one heartbeat in, one finished object on the tile.
Nothing is ever under construction. That is why the atlas reads as a settlement
that was pasted on rather than a place being made.

**A build becomes a multi-heartbeat project with visible stages.**

- `build` on a new object_id **starts** construction. The object appears
  immediately at stage `foundation`, with `progress` 0 and a declared
  `rung`. It is not yet functional: it does not shelter.
- Each later heartbeat the agent issues `build` with the **same** object_id
  (and optionally `addon_to`) to advance it one stage. No new fields, no new
  action — the existing `build` schema already carries what is needed.
- Stages, fixed and world-defined:

  | stage | progress | visible form | functional |
  |---|---|---|---|
  | `foundation` | 0 | stone ring / cleared pad | no |
  | `frame` | 1 | posts + ridge beam | no |
  | `walls` | 2 | log walls part-height | no |
  | `roofed` | 3 | thatch/pitch roof on | shelters |
  | `finished` | 4 | rung props: door, hearth, windows, chimney | full rung effects |

- Materials are spent **per stage**, not up front: the foundation takes the
  rung's stone fraction, the frame its timber fraction, and so on. Each stage
  validates against holdings before it is applied, so a project abandoned
  half-built leaves an honest half-built structure rather than a debt.
- The rung's floors become a **time cost**, not just a material cost. A
  longhouse is a campaign of many heartbeats; a lean-to is an afternoon. That
  is the real-world reason a proper house feels valuable and twelve shacks do
  not.
- The viewer renders the stage: the object group draws a growing partial
  structure (pad → frame → partial walls → roofed → rung props) instead of the
  finished sprite appearing whole. `__GENESIS_PROTO__` exposes each object's
  `construction_stage` and `progress` so the HUD can show
  `BUILDING hut — walls (2/4)`.
- Action FX (`updateAgentActionFx`) already has a scaffolding prop; the staged
  build reuses it as the persistent in-progress visual and keeps the woodchip
  particle burst on each stage advance.

### 4. The payoff becomes visible

`AgentContext` and the observation carry `home_rung`, `home_footprint`, and
`home_effects` for the structure the agent stands in. One factual settlement
line renders it:

```
- Fact: you are inside a house (rung 4) with footprint 9; warmth floor 75,
  rest recovery 2.0/hb, cellar budget 180 units.
```

The same three values are exposed on the viewer's `__GENESIS_PROTO__` so the
orbit HUD and the settlement HUD can display the home's rung and footprint.
No directive phrasing — it states what the world is, never what to build.

### 5. Rung plumbing into existing physics

`_in_shelter` keeps its predicate (any roofed kind shelters), but the
10PJ tier lookup uses `max(footprint_units, rung_weight)` so a single rung-5
longhouse outranks four lean-tos without any change to `_HOME_NETWORK_TIERS`.
`storage_cellar` budget uses the same merged weight.

## Verification — Phase 10PW

New suite `world-sim/tests/test_structure_rungs.py`:

1. `test_free_string_types_are_rejected_and_name_the_legal_set` — `house` free
   builds no longer pass; the rejection lists the five canonical names.
2. `test_rung_floors_enforce_before_placement` — each rung's floor rejects a
   short declaration and accepts an exact one, with nothing spent on rejection.
3. `test_extension_inherits_rung_and_costs_the_shortfall` — a rung-2 room on a
   rung-4 house costs the rung-2 shortfall and inherits footprint weight 3.
4. `test_standalone_build_pays_full_floor` — no parent, no discount, rung 1.
5. `test_rung_weight_outranks_equivalent_lean_tos` — rung 5 alone beats four
   lean-tos in the tier lookup.
6. `test_home_rung_disclosure_is_a_fact_without_directives` — the rendered line
   is bounded, present only inside a structure, and carries no banned phrase.
7. `test_proto_exposes_home_rung_footprint_effects`.
8. `test_load_bearing_construction_still_passes` — 10KM's structural minimum
   and honest-materials regression stay green.
9. `test_addon_to_compounds_still_track` — the 10JX network still records
   inherited rooms, and `compounds` is no longer empty once an addon is built.
10. `test_build_starts_a_staged_project_and_shelters_only_when_roofed` — a new
    build lands at `foundation` with progress 0, grants no shelter, and
    shelters from the `roofed` stage onward.
11. `test_each_stage_spends_its_own_material_fraction` — advancing a stage
    spends only that stage's fraction and rejects before applying anything
    when the holding is short.
12. `test_same_object_id_advances_and_a_new_id_is_a_new_project` — repeating
    the id progresses; changing it starts a separate structure.
13. `test_proto_exposes_construction_stage_and_progress`.
14. `test_abandoned_project_leaves_an_honest_partial_structure` — a half-built
    project costs what it has already spent and leaves the stage standing.

Plus the full CI list, `git diff --check`, and CRLF=0.

## Scope boundaries

- Changes touch `backend/world/first_pair_runtime.py`,
  `first_pair_cognition_interface.py`, `first_pair_cognition_model.py`, the
  `__GENESIS_PROTO__` block, and the new test suite. The viewer HUD readout is
  optional in this phase and may be deferred if the risk is not worth it.
- **No new agent action** and **no schema change**: `build` and `addon_to`
  keep their existing fields. The change is what the world accepts and what it
  pays back.
- No `world-sim/data` writes, no migration of existing public objects. The 72
  and 142 existing shelters stay exactly as they are; their rung is inferred
  from their declared `object_type` on first read (grandfathered, never
  retroactively charged).
- No runtime restart: lockstep spawns fresh subprocesses per heartbeat.
- No taming, no goal injection, no directive phrasing, no banned phrases.

## Why this is the right next step

It answers the operator's complaint directly (one proper house instead of
twelve shacks), it makes the screen legible (a visible rung and footprint to
watch grow), and it revives the 10JX compound mechanic that has never once
been used. 10PT just fixed material flow, without which any rung cost would
have been another wall rather than a goal.
