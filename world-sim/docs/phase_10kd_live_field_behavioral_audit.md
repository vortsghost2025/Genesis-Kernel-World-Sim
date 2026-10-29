# Phase 10KD: Live Field Behavioral Audit — Fauna Engagement, Taming Emergence & Cognition Grounding

## 1. Executive Summary & Purpose

Phase 10KD conducts a read-only empirical behavioral audit across the two continuous live lanes (**East Valley**, tick 5535+; **West Dawn**, tick 7494+) in the Genesis Kernel World Simulation. 

Following the landing of Phase 10JR (Cognitive Bandwidth Hygiene & Prompt Compression) and Phase 10KB (Continuous 3D Observatory Visual Fidelity), the central behavioral question left unmeasured was:
> *Does reduced cognitive overhead (~600 tokens in West vs legacy ~22,000) combined with explicit affordance verbs (`offer_food`, `milk_animal`) naturally produce animal domestication and taming emergence in live agents?*

This audit interrogated the canonical simulation stores (`world-sim/.runtime/first-pair/` and `world-sim/.runtime/first-pair-west/`), analyzing raw world states, agent observation mechanics, action histories, goal registries, and cognition prompts.

**Core Findings:**
1. **The Spatial Observation Blindspot (Chebyshev $\le 6$ vs Spawn Drift):** The lack of animal taming is **not** a cognitive refusal, lack of food, or missing affordance verb. It is a spatial disconnect: `FirstPairRuntime._fauna_visible` enforces a perception radius of Chebyshev distance $\le 6$, while fauna spawn up to 14 tiles away and drift randomly across the $200 \times 200$ continent. In West Dawn, the cow drifted 33 tiles away and the horse 42 tiles away. Across hundreds of ticks, neither West agent ever had a domestic animal enter their observation window (`nearby = []`).
2. **Cognition Prompts are Armed but Dormant:** The cognition model (`first_pair_cognition_model.py`) contains complete, explicit directives prompting agents to move closer or offer food when an animal is within 6 tiles. Because `nearby` remained empty, the model never generated those prompt lines.
3. **Civilization Divergence:**
   - **West Dawn is Paralyzed in an Epistemic Impasse:** West Adam and Eve hold 6 active `in_progress` goals all reading `await operator direction`. Out of 233 recent actions, 148 were `ask_human` existential inquiries asking whether the lack of interaction mechanisms is the intended purpose of the simulation.
   - **East Valley is Actively Thriving:** East has zero `ask_human` actions. Out of 740 recent actions, 645 are `move` (87.2%) and 60 are `gather`. East Adam and Eve are actively surveying the western hills along row $y=-5$, maintaining warmth, health, and campfires.
4. **Compound Settlement Readiness:** Compounds (`world_state.compounds`) remain empty in both lanes because compounds require calling `build(..., addon_to=...)`. West is frozen in standby, while East is currently nomadic/surveying far from base camp.

---

## 2. Spatial Perception & Ecology Forensics

### 2.1 Perception Horizon vs Fauna Movement
In `world-sim/backend/world/first_pair_runtime.py:1405-1430`:
```python
def _fauna_visible(self, agent_ref: str) -> dict:
    position = self._world_state.tile_occupancy.get(agent_ref)
    pos = self._tile_xy(position or "")
    visible = []
    if pos is not None:
        for entity in getattr(self._world_state, "fauna", []) or []:
            tile = self._entity_xy(entity.get("tile"))
            if tile is None:
                continue
            dist = max(abs(tile[0] - pos[0]), abs(tile[1] - pos[1]))
            if dist > 6:
                continue
            ...
    return {"nearby": visible}
```
Observation radius for fauna is strictly capped at **$\text{dist} \le 6$**.

In `world-sim/backend/world/fauna.py`:
- `FAUNA_MIN_SPAWN_DISTANCE = 4`
- `FAUNA_MAX_SPAWN_DISTANCE = 14`
- Untamed cows execute `_free_drift_step` (uniform 2D random walk to 8-neighborhood).
- Untamed horses execute `_horse_step` (fleeing if an agent approaches within `HORSE_FLEE_RADIUS = 2`, otherwise random walk).

### 2.2 Live Coordinate Analysis

| Civilization | Entity | Current Coordinates | Agent Coordinates | Chebyshev Distance | Perception Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **West Dawn** (Tick 7494) | `cow-6864-0` | `[2, 82]` | Adam `[35, 51]` | **33 tiles** | **Invisible** ($33 > 6$) |
| | `horse-6866-1` | `[-7, 17]` | Adam `[35, 51]` | **42 tiles** | **Invisible** ($42 > 6$) |
| | `snake-6930-2` | `[12, 45]` | Adam `[35, 51]` | **23 tiles** | **Invisible** ($23 > 6$) |
| | `snake-6931-3` | `[66, 45]` | Adam `[35, 51]` | **31 tiles** | **Invisible** ($31 > 6$) |
| **East Valley** (Tick 5535) | `cow-5058-0` | `[-5, 1]` | Adam `[-14, 2]`, Eve `[-12, -5]` | **9 tiles** (Adam) / **7 tiles** (Eve) | **Invisible** ($> 6$) |
| | `horse-5063-3` | `[-43, -4]` | Adam `[-14, 2]` | **29 tiles** | **Invisible** ($29 > 6$) |
| | `snake-5058-1` | `[-36, -24]`| Eve `[-12, -5]` | **26 tiles** | **Invisible** ($26 > 6$) |
| | `snake-5061-2` | `[-20, -4]` | Adam `[-14, 2]` | **6 tiles** | **Visible on edge** ($\le 6$) |

In West Dawn, the domestic cow and horse spawned and diffused tens of tiles away into the Great Wilds. The agents at `[35, 51]` have never received an observation containing either animal.

---

## 3. Cognition & Prompt Delivery Analysis

### 3.1 Prompt Synthesis Integrity
In `world-sim/backend/world/first_pair_cognition_model.py:420-490`, the cognition prompt builder inspects `context.observation["fauna"]["nearby"]`:
- If `dist <= 1`:
  > *"A cow is nearby (adjacent); it is untamed [id: {animal_id}]. You can offer animal foods (wild_berries, edible_roots, wild_apples, wild_grain, fiber_plants) using offer_food to build trust."*
- If `dist > 1`:
  > *"A cow is nearby ({dist} tiles away); it is untamed [id: {animal_id}]. You can move closer to interact."*

The prompt architecture is completely implemented, syntactically verified, and capable of driving action. However, because `nearby` is empty, **these lines are completely omitted from the generated prompt**. The LLM never sees a cow or horse mentioned in its active context.

### 3.2 Hazard Recognition vs Domestication
The only fauna entity that demonstrably came within perception distance was a snake in West Dawn at HB 6934. When Eve observed the snake within range, she immediately responded rationally:
- **HB 6934 Action:** `move` to `cont_b_gen_37_54`
- **Reason:** `"move to safer tile away from snake and gather resources"`
This proves that when fauna enters the observation window, the agents **do perceive it and act upon it**.

---

## 4. Civilization Behavioral Profiles: East vs West

### 4.1 Action Distribution Comparison

| Metric | East Valley (HB 5058–5535) | West Dawn (HB 6864–7494) |
| :--- | :--- | :--- |
| **Total Recorded Actions** | **740** | **233** |
| `move` | 645 (87.2%) | 5 (2.1%) |
| `gather` | 60 (8.1%) | 38 (16.3%) |
| `eat` | 22 (3.0%) | 31 (13.3%) |
| `build` | 13 (1.8%) | 2 (0.9%) |
| `ask_human` | **0 (0.0%)** | **148 (63.5%)** |
| `leave_public_message` | 0 (0.0%) | 8 (3.4%) |
| `use_object` | 0 (0.0%) | 1 (0.4%) |

### 4.2 The West Dawn Epistemic Loop
West Dawn suffered from an epistemic dead-end. The agents concluded during earlier tool/container testing that objects are inert records. This triggered a recursive loop of operator inquiries:
- **Active in_progress goals in West:**
  1. `listen_for_operator_direction : await operator instruction`
  2. `stand_by : awaiting operator direction`
  3. `standing_by : awaiting operator direction`
  4. `await_operator_direction : await operator direction`
  5. `await_operator_instruction : await operator direction`
  6. `6716 : await operator direction`
- **Typical West Adam Prompting Output (HB 7493):**
  > *"Is the impasse itself the intended outcome of this exercise, i.e., that this world is a record-keeping space with no hidden function or missing action?"*

Because the agents entered `standby` waiting for human guidance, they ceased exploring outward into the terrain where the animals drifted.

### 4.3 The East Valley Exploration Momentum
East Valley avoided the epistemic trap. Adam and Eve maintained active exploration goals:
- `explore-new-tiles`: *"Continue exploring uncharted tiles and gathering resources"*
- `explore-uncharted-territories`: *"Continue exploring uncharted hill terrain"*
They have mapped dozens of contiguous tiles along row $y=-5$, gathering clay and stone, foraging wild berries, building campfires during cold rain, and maintaining high vitals.

---

## 5. Compound Settlement Topology Status

1. `world_state.compounds` is initialized as `{}` in both simulation instances.
2. Under Phase 10JX, compounds are registered only when an agent executes:
   `build(..., addon_to="<existing_root_object_id>")`
3. Neither civilization has executed an `addon_to` build action:
   - In West, construction stopped due to the operator standby loop.
   - In East, Adam and Eve are mobile surveyors traveling far west of their initial base, building isolated lean-tos and campfires at their survey camps (`cont_a_gen_-13_-5`, `cont_a_gen_-8_-2`, `cont_a_gen_-15_1`) rather than expanding a clustered compound homestead.

---

## 6. Recommendations & Next Steps

1. **Reconnection of West Dawn (Operator Delegation):**
   - Per Standing Rule 7 (`operator_say.py`), issue a factual operator statement to West Dawn confirming:
     > *"The world is an active physical environment, not an inert record. Crafting, taming, agriculture, and construction exist and respond to physical action. Animals and resources inhabit the continent."*
   - This breaks the 148-turn `ask_human` deadlock without directing strategy or destinations.
2. **Fauna Attraction / Pastoral Mechanics (Candidate Phase 10KE):**
   - A 6-tile observation window on a $200 \times 200$ continent makes accidental animal discovery an $O(1/\text{area})$ low-probability event once animals drift.
   - Introduce pastoral affordances:
     - **Campfire / Hearth Warmth & Salt Lick Attraction:** Domestic grazers (cows/horses) gently bias their random walk toward active settlement smoke or salt/food storage within Chebyshev $\le 15$.
     - **Fodder Trough / Enclosure bait:** Depositing animal food in an attached stable or compound tile attracts nearby fauna.
     - **Expanded Horizon Sighting:** Distant pastoral sighting (`"You see grazing animals on the eastern horizon ~12 tiles away"` in environmental awareness).
3. **Regression Test Hardening:**
   - Enhance `world-sim/tests/test_viewer_fidelity.py` beyond string matching by testing Three.js object graph generation and DOM tag attachment under mock headless conditions.

---

## 7. Phase Governance Chain
- **Phase 10KD:** Live Field Behavioral Audit (docs-only audit complete).
- **Phase 10KE:** Metadata Sync for 10KD $\rightarrow$ names candidate Phase 10KF.
