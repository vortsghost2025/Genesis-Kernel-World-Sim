# Phase 10JV Specification: Compound Settlement Architecture, Modular Addons & Sustainable Cultivation

> **Phase Chain:** 10JT (spec, Done `c50442c`) -> 10JU (metadata sync, Done `f091db5`, hash-corrected `7922570`) -> 10JV (specification & design, this document) -> 10JW (metadata sync) -> 10JX (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Comprehensive design and architectural specification. Implementation code is deferred to candidate Phase 10JX following operator authorization.

---

## 1. Overview & Design Vision

In the earlier phases of Genesis, construction was modeled as atomic, isolated objects on individual tiles (`create_public_object` and single-tile `build`). While this permitted early survival (a fire to warm up, a basic lean-to to survive the night), it produced fragmented settlements:
- An agent builds a lean-to on one tile, a campfire 2 tiles away, and a storage basket 3 tiles away.
- When rain falls, the open campfire is instantly snuffed out because it is not roofed.
- The agent must sit shivering in an isolated shack, unable to benefit from the fire without leaving shelter.
- Separated shacks require separate fires, burning unsustainable amounts of wood.
- Tamed cows and horses wander into the wilderness, vulnerable to nocturnal wolf packs.
- Food gathering remains purely extractive (foraging wild bushes and fishing), leaving agents vulnerable to local resource depletion.

**Phase 10JV introduces Compound Settlement Architecture**: rewarding the construction of a single, coherent, expandable homestead with specialized functional addons (Hearth Hall, Living Quarters, Root Cellar, Animal Stable, and Enclosed Garden Plot).

---

## 2. Compound Topology & Data Structures

### 2.1 The Compound Concept
A **Compound** is a spatially contiguous network of structural public objects that share physical enclosure, thermal mass, and security.

```
                                [ Attached Stable ]
                              tile: [35, 52] (North)
                                       |
                                    (Doorway)
                                       |
[ Enclosed Garden ] <--(Doorway)-- [ Central Hearth ] --(Doorway)--> [ Root Cellar / Pantry ]
 tile: [34, 51] (West)              tile: [35, 51]                    tile: [36, 51] (East)
                                Living Quarters
                                Shared Fireplace
```

### 2.2 Data Representation
Compounds are tracked deterministically in `world_state.compounds`:
```python
{
    "compound_id": "compound-west-dawn-1",
    "owner_agent_id": "genesis-agent-west-adam",
    "root_object_id": "hearth-hall-001",
    "rooms": {
        "hearth-hall-001": {
            "room_type": "living_hearth",
            "tile": [35, 51],
            "roofed": True,
            "walls": True,
            "has_hearth": True
        },
        "pantry-002": {
            "room_type": "storage_cellar",
            "tile": [36, 51],
            "roofed": True,
            "walls": True,
            "addon_to": "hearth-hall-001"
        },
        "stable-003": {
            "room_type": "animal_stable",
            "tile": [35, 52],
            "roofed": True,
            "walls": True,
            "addon_to": "hearth-hall-001"
        },
        "garden-004": {
            "room_type": "enclosed_garden",
            "tile": [34, 51],
            "roofed": False,
            "fenced": True,
            "addon_to": "hearth-hall-001"
        }
    },
    "thermal_mass": 3,
    "active_hearth_tile": [35, 51]
}
```

### 2.3 Addon Building Action Contract
The existing `build` action is extended with an optional `addon_to` parameter:
```json
{
  "action_type": "build",
  "object_id": "stable-003",
  "object_type": "shelter_stable",
  "tile_id": "cont_b_gen_35_52",
  "addon_to": "hearth-hall-001",
  "materials": {"timber": 4, "wood": 6, "fiber_plants": 4},
  "description": "Attached animal stable on the north wall of the hearth hall."
}
```
**Validation Rules:**
1. `addon_to` must reference an existing valid structural public object (`shelter`, `hut`, `cabin`, `hearth`).
2. The destination `tile_id` must be cardinally adjacent (North, South, East, West) or Chebyshev adjacent (dist <= 1) to the parent structure.
3. The destination tile must be clear of obstructive natural obstacles (boulders, deep water).

---

## 3. Physical & Mechanical Benefits of Compounds

### 3.1 Shared Compound Hearth (Thermodynamic Radiation)
In separate buildings, heat does not cross open tiles. In a compound:
- When a fire or hearth is burning inside any room of a compound, the warmth radiates through connected doorways to all rooms in the compound network up to Chebyshev distance <= 3.
- **Runtime Rule:** For an agent located in any room of compound $C$, `by_fire` evaluates to `True` if compound $C$ has an active, burning hearth.
- **Fuel Efficiency:** One indoor fire burning 2 units of wood per cycle protects and warms both agents, their domestic animals, and their indoor storage, saving up to 75% of fuel wood compared to multiple outdoor bonfires.
- **Weather Protection:** A fire built inside a compound room is roofed; `fire_is_snuffed()` evaluates to `False` even during severe storms and blizzards.

### 3.2 Compound Thermal Mass & Insulation Multipliers
Larger single structures with shared walls retain internal air temperature and block wind infiltration far more effectively than isolated shacks:

| Structure Type | Connected Tiles | Cold Decay Factor | Comfort Floor | Rest Vitality Regen |
|----------------|-----------------|-------------------|---------------|---------------------|
| Open Terrain   | 0               | 1.00 (baseline)   | Ambient Temp  | 0.50 (baseline)     |
| Isolated Shack | 1 tile          | 0.45              | 45.0          | 1.00 (2x baseline)  |
| Dual-Room Home | 2 tiles         | 0.30              | 52.0          | 1.25 (2.5x baseline)|
| Homestead Compound | >= 3 tiles  | **0.18**          | **62.0**      | **1.50 (3x baseline)**|

In a Homestead Compound, an agent resting inside on a freezing winter night (ambient 10.0) enjoys a comfort floor of 62.0 and loses virtually zero warmth even without a fire, while healing vitality 3x faster than outside.

### 3.3 Attached Food Storage / Root Cellar Addon
- **Perishable Preservation:** Foods stored in an attached `storage_cellar` room decay 4x slower than in outdoor caches.
- **Scavenger Immunity:** Wild wolves, deer, and pest insects cannot path through compound doorways. Food in an attached cellar is completely immune to wildlife theft.

### 3.4 Attached Animal Stable / Corral Addon
- **Anti-Wandering Anchor:** Tamed cows and horses guided into an attached stable have their `anchor_tile` pinned to the stable stall. They remain inside and do not wander off into distant biomes.
- **Predator Exclusion:** Nocturnal wolves stalking the homestead cannot attack animals enclosed within an attached stable.
- **Convenient Milking & Care:** Inhabitants can milk cows and feed horses directly from their living quarters without exposing themselves to freezing rain or predator attacks outside.

---

## 4. Sustainable Cultivation & Garden Addons

To transition civilizations from precarious wild foraging to agricultural stability, compounds support an **Attached Enclosed Garden Plot**.

### 4.1 Garden Plot Creation
1. **Tilling:** An agent equipped with an axe, knife, or digging tool executes:
   ```json
   {
     "action_type": "build",
     "object_id": "garden-001",
     "object_type": "enclosed_garden",
     "tile_id": "cont_b_gen_34_51",
     "addon_to": "hearth-hall-001",
     "materials": {"wood": 4, "fiber_plants": 6},
     "description": "Fenced garden plot attached to the west wall."
   }
   ```
2. The plot provides tilled soil sheltered by the compound's perimeter fence.

### 4.2 Sowing & Crop Maturation Loop
1. **Action `plant_crop`:**
   ```json
   {
     "action_type": "plant_crop",
     "target_id": "garden-001",
     "resource_kind": "wild_berries",
     "reason": "Plant wild berry bush in garden bed."
   }
   ```
   Valid crops: `wild_berries`, `edible_roots`, `wild_grain`. Consumes 1 unit of the raw resource.
2. **Growth Stages:**
   A planted crop progresses deterministically across heartbeats:
   - `seeded` (HB 0 to 24)
   - `growing` (HB 25 to 60)
   - `mature` (HB 61+)
3. **Action `harvest_crop`:**
   When `mature`, executing `harvest_crop` yields:
   - 3 to 5 units of the harvestable food.
   - 1 seed/root unit (enabling indefinite self-sustaining agricultural cycles).
4. **Wildlife Grazing Protection:**
   Wild deer naturally consume unharvested wild berry bushes and root patches. Fenced compound gardens prevent deer from consuming domestic crops.

---

## 5. Multi-Stage Causal Construction Progression

Construction is grounded in physical causality across three distinct phases:

```
[ Natural Forest ] --(Axe Hewing)--> [ Timber Logs ]
                                           |
                                      (Framing)
                                           v
                                    [ Post & Beam Frame ]
                                           |
                              (Thatch/Clay Enclosure)
                                           v
                              [ Weather-Tight Shelter ]
                                           |
                                   (Addon Extension)
                                           v
                              [ Multi-Room Compound ]
```

### 5.1 Step 1: Timber Hewing vs. Gathering
- **Bare-Handed `gather` on Tree:** Yields `branches` (1-2 wood) and `fiber_plants`. Insufficient for heavy structural framing.
- **Tool-Assisted `hew_timber`:** Striking a tree with a knapped flint knife, stone axe, or iron axe executes `hew_timber`, producing `timber` (heavy structural logs, weight 5, durability 100).

### 5.2 Step 2: Framing
- `build` with `object_type: "structural_frame"` using `timber: 4`. Creates a load-bearing post-and-beam skeleton on the tile.

### 5.3 Step 3: Enclosure & Roofing
- Upgrading or completing the frame with `wood`, `clay`, and `fiber_plants` seals the roof and walls, converting the object to a fully insulated `shelter`.

### 5.4 Step 4: Modular Addon Extensions
- Constructing subsequent rooms tagged with `addon_to: <parent_id>` expands the compound network, dynamically recalculating compound thermal mass and shared hearth radii.

---

## 6. Cognition & Sensory Model Enhancements

In `backend/world/first_pair_cognition_model.py`:
1. **Permanent World Scale Facts:**
   ```text
   Fact: The continent is a vast, continuous landmass spanning 40,000 tiles (200x200). Your explored territory covers only a tiny fraction (<2%) of the world. Beyond your immediate sight lie high mountain ridges, river valleys, unexplored biomes, wild and domestic animals, and unmined resources. The world is never exhausted.
   Fact: Part of being an embodied inhabitant is active learning: exploring the frontier, hewing timber, building modular compound shelters, and experimenting with physical materials to survive and thrive.
   ```
2. **Compound Affordances in Observation:**
   When inside or adjacent to a compound, `YOUR BODY` advertises:
   - Compound connectivity (`Inside compound [hearth-hall-001] (3 connected rooms). Warmth radiates from the central hearth.`).
   - Addon build affordances (`You can expand this shelter with addons using build with addon_to: hearth-hall-001.`).
   - Crop harvest readiness (`Garden bed [garden-001] is mature. You can harvest it using harvest_crop.`).

---

## 7. CI Workflow Parity

Per OpenCode's recommendation and Phase 10JT requirements, `.github/workflows/pure-tests.yml` is updated to include:
- `tests/test_goal_hygiene.py`
- `tests/test_fauna_field_observation.py`

---

## 8. Required Test Coverage for Candidate Phase 10JX

Phase 10JX must implement tests in `tests/test_compound_architecture.py` and `tests/test_cultivation.py`:

1. `test_compound_adjacency_network`: Verifies that structures built with `addon_to` form a single compound graph.
2. `test_shared_compound_hearth`: Asserts that an agent in room B receives `by_fire = True` when room A contains an active hearth.
3. `test_compound_thermal_decay_scaling`: Asserts that cold decay decreases from 0.45 to 0.18 as compound size reaches 3+ tiles.
4. `test_compound_roof_fire_protection`: Verifies that rain does not snuff a fire inside a compound room.
5. `test_stable_wolf_exclusion`: Asserts that wolves stalking an inhabited tile refuse to target domestic animals inside a compound stable.
6. `test_garden_crop_lifecycle`: Sowing `wild_berries` in a garden plot transitions across growth stages and yields 4 berries + seed upon harvest.
7. `test_timber_hewing_requires_tool`: Verifies that `hew_timber` requires an axe or knapped tool, while bare-handed gathering yields standard twigs.

---

## 9. Governance & Phase Progression

- **Phase Chain:**
  - `10JT`: Field Audit & Grounding Spec (Done `c50442c`).
  - `10JU`: Metadata Sync (Done `f091db5`, hash-corrected `7922570`).
  - `10JV`: Compound Architecture & Cultivation Specification (this document) -- Docs only.
  - `10JW`: Metadata Sync -- Record 10JV hash in `phase_index.md`, name 10JX candidate.
  - `10JX`: Implementation candidate -- TDD implementation of compound mechanics, shared hearths, stables, and garden plots.
- **Constitutional Guardrails:**
  - Docs-only specification.
  - No edits to live stores (`.runtime/`) or daemon processes.
  - Stage ONLY `world-sim/docs/phase_10jv_compound_architecture_and_settlement_spec.md`. Never `git add -A` or `git add .`.
  - Pure LF line endings (`CRLF=0`).
