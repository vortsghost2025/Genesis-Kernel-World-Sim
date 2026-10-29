# Phase 10JZ Specification: 3D Continuous World Observatory Visual Fidelity, Dynamic Weather Atmospherics, Fauna, Architectural Rescaling & Living Interior Dollhouse Cutaway

> **Phase Chain:** 10JX (impl, Done `f26b137`) -> 10JY (metadata sync, Done `7b34639`, hash-corrected `72172f3`) -> 10JZ (specification & design, this document) -> 10KA (metadata sync) -> 10KB (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Comprehensive design and architectural specification. Implementation code is deferred to candidate Phase 10KB following operator authorization.

---

## 1. Overview & Empirical Motivation

On 2026-10-28, operator Sean inspected the live Genesis 3D Continuous World Observatory running at `http://localhost:8090/` and identified six critical immersion, architectural, and visual fidelity breakdowns:
1. **Animals absent from view:** Domestic cows, horses, snakes, and wild deer/wolves exist in the backend simulation state but are completely invisible in the 3D world.
2. **Abnormal sliding movements:** Agents slide linearly across tiles like flat cardboard cutouts on ice, lacking walk cycles, footfall physics, or directional facing.
3. **Weather absent from 3D scene:** The weather is only a static text string in the header (`Spring (17°C) // Clear`); there are no 3D rain streaks, storm darkening, or atmospheric particle systems.
4. **Distorted architectural scale:** Agent figures (`1.44m`) are disproportionately huge compared to shelters (`2.55m x 2.35m`). When standing next to a house, agents look like giants standing outside miniature dollhouses, rather than humans inhabiting realistic buildings.
5. **No interior visibility or home life ("They don't go in and I can't see in"):** When agents enter shelter, they remain rendered on the exterior or clipped behind an opaque sprite. The operator cannot enter the house, observe the interior hearth, see stored goods, or watch how agents decorate, rest, sleep, and maintain their homestead.
6. **No construction action feedback:** When agents build structures, hew timber, or cultivate gardens, buildings pop into existence instantaneously with zero visual progress, tool animations, or construction particle effects.
7. **Frozen on launch:** The viewer initializes paused at `maxHb` in `playbackMode = "live"`. When agents are resting or waiting in shelter, the operator is greeted by a completely frozen image displaying `NO ACTION RECORDED`.

Chrome DevTools MCP forensic analysis of the live viewport across East Valley (Alpha Continent, HB 5277+) and West Dawn (Beta Continent, HB 7247+) confirmed every issue and isolated the exact architectural root causes in `world-sim/scripts/export_viewer_snapshot.py` and `world-sim/viewer/prototype/index.html`.

**Phase 10JZ establishes the comprehensive specification** to upgrade the data export pipeline, introduce real-time 3D fauna rendering, integrate GPU precipitation particles, rescale architecture to true human proportions, implement a cutaway dollhouse interior system with an "Enter House" camera mode, embody agent actions with construction feedback, and modernize viewer playback controls.

---

## 2. Forensic Root-Cause Matrix

| Observed Issue | Frontend Root Cause (`prototype/index.html`) | Backend Export Root Cause (`export_viewer_snapshot.py`) |
|---|---|---|
| **Invisible Animals** | 0 occurrences of `fauna`, `animal`, `cow`, `horse`, or `snake` in Three.js scene creation routines. | Line 408 exports `"wildlife"` only; `world_state.get("fauna")` is completely excluded from the exported dictionary. |
| **Abnormal Sliding Motion** | Rigid billboard `SpriteMaterial` linearly interpolated via `Math.sin(alpha * Math.PI * 2) * 0.024` with zero directional flipping or footfall cadence. | None (temporal coordinates are faithfully preserved in `position_timeline`). |
| **Missing Weather in 3D** | Sky dome and directional light are static; zero Three.js particle systems or storm shaders exist in the scene. | Weather snapshot exists in data but is only bound to `#weather-hud` text. |
| **Distorted Scale (Giant Humans)** | Shelters are sized `2.55m x 2.35m` (`index.html:1379-1380`) while characters are `1.44m` tall (`index.html:1931`). The shelter art is a single texture-sheet sprite, so there is no modeled doorway or clear entry height at all. | None (visual prop sizing artifact). |
| **Opaque Houses / No Interior** | Shelters are single opaque exterior 2D sprites; zero interior meshes, cutaway planes, or indoor furnishings exist. `door` appears only as an object-type substring match (`index.html:1398`), not as a rendered doorway mesh. | `_in_shelter` is computed in `FirstPairRuntime` (`first_pair_runtime.py:1242`), but its result is not exported and the frontend renders agents at outdoor tile coordinates. |
| **No Visible Construction** | Objects are rendered as static props based purely on heartbeat existence; no action particles, scaffolding rings, or tool effects are spawned. | Per-heartbeat action outcomes record `build` and `hew_timber`, but frontend ignores construction events during frame rendering. |
| **Frozen on Load** | `isPlaying` defaults to `false` and `currentHb` defaults to `maxHb`. At tick 7247 in West, both agents are resting, rendering zero visible delta. | None (canonical store reflects true idle/resting state). |

---

## 3. Data Pipeline Upgrades (`export_viewer_snapshot.py`)

In `build_pair_snapshot(pair_name, store, true_map)`:

### 3.1 Fauna, Compound & Shelter State Export
The snapshot payload dictionary returned at line 400 must explicitly expose:

> **Implementation note (shelter occupancy):** `_in_shelter` is **not** a `survival` module function — it is an instance method `FirstPairRuntime._in_shelter(self, tile_id: str)` at `first_pair_runtime.py:1242`, and the export script runs standalone without a runtime instance. Phase 10KB must therefore add a module-level `_agent_in_shelter(tile_id, world_state)` helper inside `export_viewer_snapshot.py` (or a shared `backend/world/` module) that reimplements the same predicate: resolve `tile_id` to `(x, y)` and continent, then scan `world_state["public_objects"]` for records whose `object_type` contains any of the shelter kinds used by the runtime (`shelter`, `hut`, `wall`, `roof`, `cabin`, `tent`, `lean`, `cave`, `cavern`, `overhang`, `grotto`, `burrow`, `stable`, `cellar`) on the same continent within the runtime's adjacency radius. The runtime's already-computed per-agent `sheltered` observation flag (`first_pair_runtime.py:689`) is an acceptable alternative source. Do not call `survival._in_shelter`; it does not exist.

```python
return {
    "agents": agents,
    "exported_tick": world_state.get("tick"),
    "exported_at_utc": world_state.get("updated_at_utc"),
    "home_continent": home_continent,
    "current_positions": world_state.get("tile_occupancy", {}),
    "vitals": world_state.get("vitals", {}),
    "weather": weather_snapshot,
    "wildlife": list(world_state.get("wildlife") or []),
    "fauna": list(world_state.get("fauna") or []),               # Phase 10JN: cows, horses, snakes
    "compounds": world_state.get("compounds", {}),              # Phase 10JX: compound network graph
    "chronicle": build_chronicle(heartbeats, name_by_hash),
    "public_objects": world_state.get("public_objects", {}),
    "shelter_occupancy": {                                      # Agents currently inside shelter/compound
        agent: _agent_in_shelter(position, world_state)
        for agent, position in current_positions.items()
    },
    ...
}
```

### 3.2 Fauna & Building Temporal Reconciliation
For timeline scrubbing, each heartbeat record in `extract_per_heartbeat()` must preserve detailed action schemas:
- `offer_food`: target animal ID, resource offered, trust delta.
- `milk_animal`: target cow ID, yield.
- `strike_animal`: target animal ID, weapon used, damage dealt, kill status.
- `hew_timber`: target tree tile, tool durability delta, timber yield.
- `build` / `addon_to`: target compound, room type, material cost, structural progression.

---

## 4. 3D Fauna & Wildlife Subsystem (`prototype/index.html`)

### 4.1 Animal Sprite & Entity Registry
A dedicated `FaunaManager` manages active animal entities in the Three.js scene:
- **Species Textures/Sprites:** Distinct visual sprites for:
  - `cow`: Peaceful domestic cattle, gentle grazing animation bob.
  - `horse`: Tall equine silhouette, alert head carriage.
  - `snake`: Low-slung serpent on ground level.
  - `deer`: Graceful wild herbivore.
  - `wolf`: Predatory canine silhouette.
- **Elevation Clamping:** Every animal entity is height-clamped via `getTerrainHeight(cid, x, z)` to ensure perfect contact with the heightmap terrain without floating or sinking into slopes.
- **Positional Interpolation:** When scrubbing or playing between heartbeats $N$ and $N+1$, animal positions smoothly interpolate using lerp with terrain elevation re-sampling at each frame.

### 4.2 Interactive Status Pills & Screen Overlays
Each visible animal renders a lightweight screen-space tag anchored above its head:
- **Cow:** `[Cow (Untamed, Trust: 0)]` or `[Cow (Tamed, Milk: Ready)]` with green accent.
- **Horse:** `[Horse (Untamed, Trust: 0)]` or `[Horse (Tamed, Mount)]` with amber accent.
- **Snake:** `[Snake (Hazard, Alert)]` or `[Snake (Coiled/Sleeping)]` with crimson accent.
- **Deer / Wolf:** `[Deer (Wild, Grazing)]` / `[Wolf (Threat, Stalking)]`.

---

## 5. Architectural Rescaling & Human-Scale Proportions

To eliminate the "giant agents outside tiny doghouses" distortion:
- **Shelter / House Footprint:** Rescaled from `2.55m x 2.35m` to a realistic human architectural scale of `5.4m` width, `4.6m` depth, and `4.2m` height.
- **Doorway Clearance:** Clear entrance height of `2.2m` allowing `1.44m` agents to realistically pass through doors without crouching.
- **Compound Spacing:** Modular addons (`addon_to`) snap cleanly along cardinal edges, forming coherent multi-room homestead compounds rather than crowded overlapping icons.

---

## 6. Living Compound Interior: Dollhouse Cutaway & "Enter House" Mode

### 6.1 Dollhouse Cutaway Architecture
When the camera zooms close ($\le 9\text{m}$), or when the user toggles **"Enter House"**, or when an agent enters a building:
1. **Roof Transparency / Lift-Off:** The exterior roof thatch fades to transparent (`opacity: 0.12`), revealing the complete interior floor plan.
2. **Low-Sill Interior Walls:** Perimeter walls are cut to sill height ($1.1\text{m}$) so isometric and elevated camera angles have completely unobstructed sightlines into the room.
3. **Furnished Living Spaces:**
   - **Central Hearth & Chimney:** Stone firepit with warm flickering point light (`0xff9922`), crackling flame sprites, glowing embers, and radiating heat rings.
   - **Sleeping Quarters:** Woven straw mattresses, fur bedrolls, and resting blankets.
   - **Pantry & Root Cellar:** Storage baskets, wooden barrels, hanging dried herbs, and cellar trapdoors showing real stored resources (berries, grain, honeycomb, fish).
   - **Crafting & Tool Bench:** Knapping stump, tool rack displaying flint knives, stone axes, and hewn timber wedges.
   - **Compound Addon Doorways:** Visible archways leading into the attached animal stable (with resting cows/horses) and enclosed garden.

```
+-------------------------------------------------------------+
|                     ATTACHED STABLE                         |
|   [ Cow Resting ]     [ Feeding Trough ]     [ Hay Bales ]  |
+--------------------------[ Doorway ]------------------------+
|                                                             |
|   [ Bedroll / Sleep ]       (O) CENTRAL HEARTH   [ Tool Rack]
|                              Flickering Fire                |
|                                                             |
|   [ Storage Baskets ]       [ Work Table ]     [ Root Cellar|
|    Berries & Honey           Flint & Timber      Trapdoor ] |
+--------------------------[ Doorway ]------------------------+
|                      EXTERIOR PORCH                         |
+-------------------------------------------------------------+
```

### 6.2 Embodied In-House Agent Behaviors
When an agent is `_in_shelter` (e.g. resting, warming up, sleeping, or idle):
- The agent figure transitions from the outdoor terrain to **interior room coordinates**:
  - Seated comfortably by the glowing hearth (`[ADAM: Resting by Fire — Warmth 100%]`).
  - Lying in the sleeping quarters (`[EVE: Sleeping on Fur Bedroll — Vitality Regening]`).
  - At the storage container (`[ADAM: Retrieving Honeycomb from Pantry]`).
  - At the craft bench (`[EVE: Maintaining Flint Blade]`).

### 6.3 "Enter House" Camera Mode
A dedicated camera view button **`🏠 Enter House`** (or `Inspect Interior`) is added to the masthead camera cluster:
- Smoothly animates the camera down to an intimate interior perspective ($3.5\text{m}$ from the hearth at eye level, pitch $28^\circ$).
- Centers the view on Adam, Eve, and the crackling fire.
- Displays real-time interior biometrics (Warmth rising, Vitality regen at $1.50\times$ compound rate, Shelter insulation status).

---

## 7. 3D Atmospheric Weather & Dynamic Lighting Subsystem

### 7.1 GPU Precipitation Particle System
A global `THREE.LineSegments` or `THREE.Points` particle system spanning an $80 \times 80$ meter volume centered on the camera focus:
- **Precipitation Count:** 2,000 rain streaks.
- **Velocity & Drift:** Downward velocity of $28\,\text{m/s}$ with wind-shear slant based on continent wind direction.
- **Ground Splashes:** Minor ground-level ring ripples when raindrops strike the terrain elevation.

### 7.2 Dynamic Environmental Atmospherics
Based on `env.weather`:
| Weather State | Sun Color & Intensity | Fog Color & Exp2 Density | Sky Turbidity | Rain Particle Visibility |
|---|---|---|---|---|
| **Clear** | `0xfff4df`, `0.92` | `0x7ca0be`, `0.0065` | `3.4` (azure) | `false` |
| **Overcast** | `0xd0d8e0`, `0.62` | `0x8fa0b0`, `0.0085` | `5.8` (slate) | `false` |
| **Rain** | `0x9aa8b8`, `0.38` | `0x607080`, `0.0125` | `7.8` (dark charcoal) | `true` (opacity 0.42) |
| **Storm** | `0x505864`, `0.22` | `0x3a4855`, `0.0180` | `10.0` (deep thunderhead) | `true` (opacity 0.65) + wind slant |

---

## 8. Embodied Action Feedback & Movement Mechanics

### 8.1 Directional Facing & Stepping Cadence
- **Directional Sprite Flipping:** When an agent travels East ($x_{t} > x_{t-1}$), the figure sprite scales with `scale.x = +baseWidth`; when traveling West ($x_{t} < x_{t-1}$), `scale.x = -baseWidth`. Agents face their direction of travel rather than staring blankly forward.
- **Two-Phase Walk Gait:** Replace the single-frequency sine bob with a cadence that compresses down on footfall and rises on stride extension, creating natural weight transfer.

### 8.2 Construction & Physical Action Particle FX
When `getAgentActionAtHb` returns an active physical manipulation:
- **`hew_timber`:** Spawns woodchip particle bursts and tool strike impact arcs on the target tree tile.
- **`build` / `addon_to`:** Displays temporary timber framing scaffolding and sawdust particles on the target tile while construction is active.
- **`plant_crop` / `harvest_crop`:** Displays soil tilling particles and green foliage harvesting burst.
- **`offer_food` / `milk_animal`:** Spawns a warm interaction arc between agent and animal with heart or milk drop micro-icon.

---

## 9. Modernized Observatory UX & Smart Launch Playback

### 9.1 Eliminating the "Frozen on Load" Dead End
- **Recent Activity Auto-Scrub:** When the observatory opens in `live` mode at `maxHb`, if agents are resting or have `NO ACTION RECORDED`, the player automatically offers a prominent **"▶ Replay Recent Activity (Last 30 HB)"** button that smoothly rewinds to the last major action sequence and plays forward.
- **Live Stream Idle Indicator:** When truly live and idle, the status badge pulses with `IDLE IN SHELTER — REPLAY RECENT (SPACE)` so the operator immediately understands the simulation is healthy and running, not crashed.

---

## 10. Required Test Coverage for Candidate Phase 10KB

Candidate Phase 10KB must implement automated verification in `tests/test_viewer_fidelity.py`:
1. `test_export_includes_fauna_and_compounds`: Asserts `export_viewer_snapshot.py` includes `"fauna"`, `"compounds"`, and `"shelter_occupancy"` keys in output payload with correct schemas.
2. `test_fauna_coordinates_ground_clamped`: Verifies exported fauna entities have valid continent coordinates matching `true_map.json`.
3. `test_weather_particle_visibility_contract`: Verifies `rain` and `storm` states activate precipitation lines while `clear` deactivates them.
4. `test_architectural_scale_proportions`: Asserts house footprint scale ($\ge 5.0\text{m}$) maintains realistic proportion to agent height ($1.44\text{m}$).
5. `test_cutaway_interior_activation`: Verifies camera proximity and `_in_shelter` status trigger roof transparency and interior furnishings.
6. `test_directional_facing_logic`: Asserts horizontal sprite flipping activates on westward trajectory.
7. `test_action_fx_spawning`: Asserts physical actions trigger corresponding particle FX definitions.

---

## 11. Governance & Phase Progression

- **Phase Chain:**
  - `10JX`: Compound Settlement Architecture Implementation (Done `f26b137`).
  - `10JY`: Metadata Sync (Done `7b34639`, hash-corrected `72172f3`).
  - `10JZ`: 3D Continuous World Observatory Visual Fidelity Specification (this document) -- Docs only.
  - `10KA`: Metadata Sync -- Record 10JZ hash in `phase_index.md`, name 10KB candidate.
  - `10KB`: Implementation candidate -- TDD implementation of fauna rendering, architectural rescaling, dollhouse interior cutaways, 3D weather particle system, directional walking cadence, and action particle FX.
- **Constitutional Guardrails:**
  - Docs-only specification.
  - No edits to live stores (`.runtime/`) or daemon processes.
  - Stage ONLY `world-sim/docs/phase_10jz_continuous_observatory_visual_fidelity_and_action_embodying_spec.md`. Never `git add -A` or `git add .`.
  - Pure LF line endings (`CRLF=0`).
