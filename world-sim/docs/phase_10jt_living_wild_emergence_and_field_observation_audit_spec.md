# Phase 10JT Specification: Living Wild Autonomous Emergence, World Scale Grounding & Field Observation Audit

> **Phase Chain:** 10JT (spec, L) -> 10JU (metadata sync, L+1) -> 10JV (implementation candidate, L+2, NOT started, NOT authorized)  
> **Constitutional Notice:** Docs-only specification and field audit. Implementation of compound settlement architecture is deferred to candidate Phase 10JV following operator authorization.

---

## 1. Problem Statement & Live Field Audit

Phase 10JR landed the cognitive foundations required for living fauna interaction and resolved the catastrophic goal accumulation bottleneck in `FirstPairRuntime`:
1. **Cognitive Goal Hygiene Verified Live:**
   In West at Heartbeat 7220, `goals.json` holds 186 accumulated goals across 7,200+ heartbeats. Under the pre-10JR runtime, all 186 goals (including 85+ obsolete failed tests from HB 1000-2400) were dumped into `context.goals`, consuming 88,637 characters (~21,990 tokens) every heartbeat cycle. Under the 10JR projection, `context.goals` filters strictly to `status in ("active", "in_progress")` and caps at `MAX_ACTIVE_GOALS_EXPOSED = 8`. In live West data, exactly **7 active/in-progress goals** are projected (~602 tokens), achieving a **97% context window bloat reduction**.
2. **Latent Bug Resolution:**
   The latent bug in `first_pair_runtime.py:851` (`active_goal_ids = {g.goal_id for g in agent_goals if g.status == "active"}`), which evaluated to empty in production because agents use `in_progress`, was resolved to use the shared two-status set.
3. **Telegram Notification Loop Cleared:**
   Throughout Heartbeats 6900-7215, West Adam had asked *"What action should I take next given that I have exhausted all testing and confirmed objects are inert records?"* Because `world_steward.py` polled `agent_questions.json` and repeatedly surfaced the oldest unheard question, Genesis Watch repeatedly broadcast this question to Telegram on every poll. At Heartbeat 7219, an authoritative operator message grounded both pairs on continental scale, auto-resolving all 6 unheard asks in West. A live audit of `world_steward.build_narrative_summary()` confirmed `question: None`, terminating the loop.
4. **Sensory Field Affordance Verbs Live:**
   Nearby and adjacent domesticatable fauna and snakes now present exact distance telemetry and actionable verbs (`move closer`, `offer_food`, `milk_animal`) in `YOUR BODY` prompt lines.

---

## 2. World Scale Grounding Invariant

A fundamental driver of agent stillness and "exhausted testing" beliefs is spatial myopia: agents spawn in a small starting clearing and perceive only tiles within Chebyshev distance <= 6. Without structural awareness of the broader continent, agents mistakenly conclude after exploring ~80-100 tiles that the world is a small, finite, and fully tested space.

### 2.1 Continental Scale Reality
- **World Dimensions:** The continental substrate spans a 200x200 grid (**40,000 tiles**).
- **Current Explored Territory:**
  - East: ~503 explored tiles (~1.2% of the continent).
  - West: ~88 explored tiles (**~0.22% of the continent**).
- Over **98% of the world** remains undiscovered wilderness, including mountain passes, deep river valleys, coastal waters, dense unvisited forests, ore deposits, and living animal habitats.

### 2.2 Cognition Model Grounding Specification (Phase 10JV Candidate)
In `backend/world/first_pair_cognition_model.py`, `build_system_prompt()` will embed permanent continental scale and exploration principles into the world facts section:
```text
Fact: The continent is a vast, continuous landmass spanning 40,000 tiles (200x200). Your explored territory covers only a tiny fraction (<2%) of the world. Beyond your immediate sight lie high mountain ridges, river valleys, unexplored biomes, wild and domestic animals, and unmined resources. The world is never exhausted.
Fact: Part of being an embodied inhabitant is active learning: exploring the frontier, hewing timber, building modular compound shelters, and experimenting with physical materials to survive and thrive.
```

---

## 3. Compound Settlement Architecture & Addons (Phase 10JV Candidate)

Currently, `backend/world/survival.py` and `backend/world/first_pair_runtime.py` treat shelter as a binary 1-tile check (`max(abs(x1-x2), abs(y1-y2)) <= 1`). There is no structural incentive to build multi-room compounds, and separate standalone shacks provide no mechanical synergy. Phase 10JV will introduce **Compound Settlement Architecture**.

### 3.1 Compound Topology & Addon Linking
1. **Structural Connectivity:**
   Structures placed on adjacent tiles sharing an edge/doorway with an existing shelter are recognized as belonging to a single unified **Compound**.
2. **Addon Building Action:**
   The `build` action will accept an optional `addon_to: <object_id>` field. When supplied, the runtime validates spatial adjacency and registers the new structure as an extension of the parent compound.

### 3.2 Mechanical Benefits of Compound Structures

```
           +-------------------------+
           |   Attached Animal Pen   |  <- Domesticates sheltered from wolves;
           |       / Stable          |     prevents wandering; safe milking
           +------------+------------+
                        | (Doorway)
+-----------------------+-----------------------+-----------------------+
|   Attached Enclosed   |  Central Hearth Hall  |   Attached Storage    |
|      Garden Plot      |   (Living Quarters)   |     (Root Cellar)     |
|                       |                       |                       |
| Crops shielded from   | Central fire radiates | Food shielded from    |
| wild deer grazing and | warmth through all    | rain rot, frost, and  |
| weather frost         | connected rooms       | predator scavenging   |
+-----------------------+-----------------------+-----------------------+
```

1. **Shared Compound Hearth (Central Heating):**
   - In separate buildings, each room requires an independent fire, consuming multiple wood units per heartbeat and requiring roofs over every fire tile.
   - In a compound, a single hearth built in the central hall radiates warmth to all connected rooms within Chebyshev distance <= 3. One well-tended fire protects the entire household through freezing winter nights.
2. **Compound Thermal Mass & Insulation:**
   - Isolated lean-to: `cold_decay_factor = 0.45`, comfort floor `45.0`.
   - Connected multi-room compound (>= 3 structural tiles): `cold_decay_factor = 0.20`, comfort floor `60.0`.
   - Vitality regeneration during rest inside a compound is 3x baseline (`REST_REGEN_IN_COMPOUND = 1.5`).
3. **Attached Storage Cache (Pantry / Root Cellar):**
   - Food resources deposited in an attached indoor storage cache do not suffer rain rot or frost decay, and cannot be scavenged by wild wolves or insects.
4. **Attached Animal Stable / Corral:**
   - Tamed cows and horses guided into an attached stable are anchored within the enclosure.
   - Attached walls provide predator immunity: nocturnal wolves cannot path into or attack animals inside a closed compound stable.
   - Milking and feeding can be conducted safely within the home perimeter.
5. **Enclosed Cultivation / Garden Plot:**
   - An enclosed, soil-prepared garden addon allows planting seeds, edible roots, wild grain, and berries.
   - Protected by compound walls, growing crops cannot be grazed or trampled by wild deer, providing a predictable, renewable food supply.

---

## 4. Multi-Stage Physical Construction Progression

Rather than instant one-click creation of finished buildings, construction progresses causally through physical stages:

1. **Felling & Timber Preparation:**
   - Striking mature trees with a knapped or crafted axe (flint knife, stone axe, iron axe) hews structural `timber` logs, while hand foraging yields only branches and fiber.
2. **Post-and-Beam Framing:**
   - Placing `timber` on a cleared tile constructs a `frame` or `foundation`.
3. **Enclosure & Roofing:**
   - Woven `thatch` (`fiber_plants`), `clay`, or split `wood` seals the roof and walls, converting the frame into a weather-tight `shelter`.
4. **Modular Addon Extension:**
   - Expanding the home by attaching specialized extensions (`hearth`, `storage`, `stable`, `garden`).

---

## 5. CI Workflow Maintenance & Test Requirements

### 5.1 CI Workflow Parity
As identified in Phase 10JR review, `.github/workflows/pure-tests.yml` must be updated to include the two new test suites created in 10JR:
- `tests/test_goal_hygiene.py`
- `tests/test_fauna_field_observation.py`

This ensures that cognitive goal hygiene and fauna field affordances are continuously verified in GitHub Actions alongside the pure fauna suites.

### 5.2 Required Test Coverage for Candidate Phase 10JV
Candidate Phase 10JV must implement tests covering:
1. `test_compound_topology_recognition`: Adjacent structures with `addon_to` link into a single compound ID.
2. `test_shared_hearth_radiates_through_connected_rooms`: A fire in the central room provides `by_fire=True` to agents in connected addon rooms.
3. `test_compound_thermal_insulation_bonus`: Multi-room compound applies reduced cold decay factor (0.20).
4. `test_attached_stable_predator_immunity`: Wolves refuse to attack tamed cows/horses inside an attached stable.
5. `test_attached_garden_crop_growth`: Planted seeds in an enclosed garden plot mature over heartbeats into harvestable food.
6. `test_timber_hewing_requires_axe`: Felling trees with an axe yields `timber`; bare-handed gathering yields standard yields.

---

## 6. Phase Chain & Governance

- **Phase Chain:**
  - `10JT`: Specification & Field Observation Audit (this document) -- Docs only.
  - `10JU`: Metadata Sync -- Record 10JT hash in `phase_index.md`, name 10JV candidate.
  - `10JV`: Implementation candidate -- TDD implementation of compound architecture, shared hearths, attached stables/gardens, and CI workflow updates.
- **Constitutional Guardrails:**
  - Docs-only specification.
  - No edits to live stores (`.runtime/`) or daemon scripts.
  - Stage ONLY `world-sim/docs/phase_10jt_living_wild_emergence_and_field_observation_audit_spec.md`. Never `git add -A` or `git add .`.
  - Pure LF line endings (`CRLF=0`).
