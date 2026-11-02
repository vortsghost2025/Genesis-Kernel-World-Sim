# Phase 10MY Specification: Valley Hydrology, Islands & Seasonal Foliage

> **Phase Chain:** 10MW (impl, Done `c578992`) -> 10MX (metadata sync, Done `43ac7e5`, hash-corrected `e337f7d`) -> 10MY (specification, this document) -> 10MZ (metadata sync) -> 10NA (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10NA following explicit operator authorization.

---

## 1. Origin: Measured Rendering Gaps on Canonical Map Data

Following the Phase 10MW visual verification (`c578992`), four factual questions were checked directly against `world-sim/viewer/continent_terrain.json` and `world-sim/viewer/prototype/index.html`:

### 1.1 Animals render at ground level, but are mostly out of the village camera frustum
- `updateFaunaFigures` (`prototype/index.html` lines 3040–3127) renders active `cow`, `horse`, `snake`, `deer`, and `wolf` entities on `getTerrainHeight(cid, tx, tz)` with floating status badges (`SNAKE [Hazard]`, `HORSE [Untamed (0 trust)]`, `COW [Untamed (0 trust)]`).
- In the close valley landscape view, only animals on or adjacent to the settlement tiles appear in frame; the remaining fauna sit 4–44 tiles away. No fauna changes are needed or in scope here.

### 1.2 Rivers and lakes exist in canonical data, but the viewer has zero water surface geometry
- **Measured canonical water counts (`continent_terrain.json`):**
  - `cont_a` (East): **1,242 `river` tiles**, **42 `lake` tiles**, **4,656 `sea` tiles**. Nearest river tile to the East built-structure centroid `(-8.0, -1.7)` (68 structures spanning `x -23..10`, `y -7..6`) is at `(0, 0)` — **7 tiles Chebyshev / 8.1 tiles Euclidean**. The next multi-tile river channel sits at `(35, 58)`-class bends 13+ tiles out. Nearest lake `(-53, -2)` is 45 tiles out; nearest sea is 87 tiles out (East is landlocked for viewer purposes).
  - `cont_b` (West): **920 `river` tiles**, **43 `lake` tiles**, **4,658 `sea` tiles**. Nearest river channel to the West built-structure centroid `(42.8, 50.5)` (164 structures spanning `x 32..51`, `y 42..56`) is at `(35, 58)` — **7 tiles Chebyshev / 10.8 tiles Euclidean**. Nearest sea tiles `(50, 50)` / `(53, 50)` are **7 tiles Chebyshev / 7.2 tiles Euclidean** from the same centroid. Nearest lake `(63, 6)` is 44-45 tiles out.
- **Root cause in `prototype/index.html`:**
  - The terrain vertex loop (line 1534) sets `isRiver = (w === "river" || w === "stream" || w === "freshwater") ? 1.0 : 0.0` (omitting `w === "lake"`), packs `biomeChannel = 0.85` into vertex color `G`, and the fragment shader (lines 1651–1653) merely mixes `valleyAndForest` with `vec3(0.16, 0.42, 0.60)` when `h < 12.0` — which is then overwritten whenever `massifBlend` or 3D conifer trees sit on top of it, and has no recessed riverbed channel, shoreline bank, or translucent water surface mesh.
  - Because `cont_a`'s nearest river is a single isolated tile `(0, 0)` while its next multi-tile river channel sits 13+ tiles away (and `cont_b`'s nearest river channel sits 7 tiles away), a viewer looking from the settlement sees green grass where a valley river should flow.

### 1.3 Islands are absent in both lakes and coastal sea
- Neither `computeContinentHeightField` nor `buildContinentMesh` generates island landforms inside lake basins (`42–43` canonical lake tiles per continent) or offshore in the coastal sea margin (`13` tiles from West).

### 1.4 Seasonal foliage is completely static
- `backend/world/survival.py` defines `DAY_LENGTH = 72`, `SEASON_DAYS = 12`, `SEASON_LENGTH = 864`, `SEASONS = ("spring", "summer", "autumn", "winter")`, and `season(heartbeat_number) -> SEASONS[(heartbeat_number // 864) % 4]`.
- In `prototype/index.html`, `getWeatherAt(pairName, hb)` (lines 3162–3186) reads a static `w.season || "Spring"` string and never derives the season from `hb` during timeline scrubbing or replay, and neither the GLSL terrain shader (`meadowCol`, `forestCol`), the 3D conifer `InstancedMesh`, nor the deciduous tree sprites respond to the season.

---

## 2. Scope & Explicit "Done" Definition

### 2.1 In Scope (Candidate Phase 10NA)

1. **Valley Hydrology (Translucent Water Surface Mesh + Carved Riverbed & Valley Reach):**
   - Build a dedicated, translucent 3D water surface mesh (`buildContinentWaterMesh(cid)`) per continent covering canonical `river` and `lake` tiles plus a continuous valley-floor river reach connected to each settlement's nearest canonical river system so water is visibly present in the valley view (`4–7` tiles from the settlement) with a real opposite bank ("the other side").
   - Carve a subtle recessed riverbed / lakebed trough (`0.35–0.65 m` below the surrounding bank) with sandy/pebble shoreline banks (`sand/shingle` transition) in `computeContinentHeightField` and clear 3D conifer / 2D billboard trees out of the active water channel so trees never grow out of the river.
   - Render the water surface with animated specular ripples, shoreline foam/tint, and sky reflection so it reads unmistakably as water from both valley landscape and orbit views.

2. **Islands (Lake & Coastal Archipelago Landforms):**
   - Synthesize deterministic small islands (`buildContinentIslands(cid)` / heightfield & water-mask integration):
     - **Lake islands:** 1–2 small vegetated/rocky eyots inside the canonical lake basins.
     - **Coastal islands:** Small offshore islands in the coastal sea margin (including off West's nearby coast and visible in the World Atlas orbit view) with sandy/rocky shorelines and low coastal pines, while strictly preserving `test_ocean_stays_below_zero` on canonical `terr === "ocean"` tiles (`computeContinentHeightField` invariant).

3. **Seasonal Foliage (`computeSeasonAtHb(hb)` + 4-Season Palette Wiring):**
   - Implement `computeSeasonAtHb(hb, fallbackSeason)` in `prototype/index.html` matching `backend/world/survival.py` (`SEASON_LENGTH = 864`, cycling `Spring -> Summer -> Autumn -> Winter` as `hb` advances or scrubs).
   - Wire a 4-state seasonal palette (`uSeason` uniform / per-season tinting) into:
     - **Pasture & valley grass shader (`meadowCol`):** Fresh golden-lime in `Spring`, deep lush emerald in `Summer`, warm golden-amber / ochre meadow in `Autumn`, and frost-silvered / snow-dusted pasture in `Winter`.
     - **Deciduous trees & foothill forest:** Blossom/fresh green in `Spring`, rich canopy green in `Summer`, burnt orange / crimson / gold foliage in `Autumn`, and frosted / snow-tipped boughs in `Winter`.
     - **Alpine snowline:** Lower snowline threshold in `Winter`, higher in `Summer`.

4. **Orbit-View Cordillera Continuity (Closing the 10MW Carry-Over Note):**
   - Extend the `computeContinentHeightField` regional cordillera envelope so the World Atlas (`orbit`) view shows coherent interior mountain backbones rather than ranges clipped only to the settlement edge, while keeping all 78 existing tests green.

### 2.2 Explicitly Out of Scope

- **No agent cognition, prompt, or runtime behavioural changes.** This phase is 100% viewer-side (`world-sim/viewer/prototype/index.html` and viewer tests). It will not make agents walk across the river or change their movement decisions (the spatial reach question documented in Phase 10KD remains separate).
- **No new fauna species or backend persistence mutations.**
- **No changes to `world-sim/data` or live daemon/runtime processes.**

---

## 3. Design Invariants

1. **Canonical Ocean Invariant Preserved:** In `computeContinentHeightField(elevArr, terrArr, outArr, settlementMask)`, every tile with `terrArr[idx] === "ocean"` must remain `<= -0.18 m` (`test_ocean_stays_below_zero`). Offshore islands are rendered via a dedicated island mesh (`islandGroups[cid]`) placed in coastal sea waters outside the canonical land grid's ocean-height check, or on non-ocean coastal/lake tiles, so `getOceanViolationCount(cid) === 0` and `test_ocean_stays_below_zero` remain 100% green.
2. **Prop & Structure Grounding:** No river trough may be carved underneath an existing settlement structure (`settleMask[idx] === 1`) or agent spawn tile. The valley river reach must pass `4–8` tiles beside the settlement cottages, never under them.
3. **Zero Trees in Active Water:** Neither `buildAlpineConiferForest` nor `populateContinentScenery` may place trees inside `river` or `lake` channel tiles.
4. **Exact Season Parity with `survival.py`:** `computeSeasonAtHb(hb)` must use `DAY_LENGTH = 72`, `SEASON_DAYS = 12`, `SEASON_LENGTH = 864`, `SEASONS = ["Spring", "Summer", "Autumn", "Winter"]`, matching `backend/world/survival.py::season(heartbeat_number)` case-insensitively for all non-negative integers `hb`.
5. **Single-Pass Geometry Budget:** Water meshes and island meshes are built once per continent at load (and updated via uniforms/materials on season change), adding at most 2 draw calls per continent.

---

## 4. Architectural Specifications

### 4.1 Valley Hydrology (`computeContinentWaterMask` & `buildContinentWaterMesh`)

1. **Water Mask Synthesis (`computeContinentWaterMask(cid, tData, settleMask)`):**
   - Marks all canonical `water[idx] === "river"` and `water[idx] === "lake"` tiles (`waterMask[idx] = 1` for river, `2` for lake).
   - Connects the nearest canonical river tiles near `(settleCx, settleCz)` into a continuous meandering valley river ribbon (`width = 2.0–3.2` tiles) passing `5–8` tiles in front/side of the village meadow (`dzS ∈ [4..10]` or alongside the meadow apron) while strictly excluding any tile within `3.0` tiles of a built structure (`settleMask`).
2. **Riverbed & Bank Relief (`computeContinentHeightField`):**
   - Where `waterMask[idx] > 0`, depress the terrain bed by `0.45 m` relative to the smoothed bank elevation and grade a `1.5`-tile pebble/sand bank ramp (`couloir/biome` channel flagged so the GLSL shader renders wet shingle/sand along the water's edge).
3. **3D Translucent Water Ribbon & Lake Mesh (`buildContinentWaterMesh(cid)`):**
   - Construct a dedicated `THREE.BufferGeometry` mesh over all `waterMask[idx] > 0` cells (plus a `0.45`-tile shoreline overlap into adjacent bank slopes so the water surface tucks cleanly into the banks without air gaps).
   - Vertex `y` sits at `bankHeight - 0.12 m` (above the carved bed `bankHeight - 0.45 m`, below the dry bank `bankHeight`).
   - Material: translucent custom-shaded or `MeshStandardMaterial` (`color: 0x1ca3ec`, `roughness: 0.18`, `metalness: 0.12`, `transparent: true`, `opacity: 0.84`) with animated flow ripples and bright shoreline foam highlights so the river glistens in both `landscape` and `orbit` camera modes.

### 4.2 Lake & Coastal Islands (`buildContinentIslands`)

1. **Deterministic Island Descriptors (`computeContinentIslands(cid, tData)`):**
   - Derives `3–5` islands per continent deterministically from continent seed + canonical lake/sea coordinates:
     - **Lake eyots:** Positioned inside the multi-tile lake basins (`x = -53` and `x = 63` lake strips).
     - **Coastal archipelago islands:** Positioned in the coastal sea waters (`4–12` tiles off the coastline, including off West's eastern/southern coast and East's outer coast).
2. **3D Island Geometry (`buildContinentIslands(cid)`):**
   - Renders each island as a multi-layered 3D landform in `islandGroups[cid]` (submerged shoal apron + sandy/rocky shoreline ring + vegetated crown rising `1.8–6.5 m` above sea/lake level, topped with instanced coastal conifers/boulders).
   - Because islands live in `islandGroups[cid]` rather than mutating `sceneryGroups[cid]` on `terr === "ocean"` tiles, `getOceanViolationCount(cid)` remains `0`.

### 4.3 Seasonal Foliage (`computeSeasonAtHb` & Shader/Scenery Palette)

1. **Season Resolver (`computeSeasonAtHb(hb, fallbackSeason)`):**
   - For numeric `hb >= 0`: `idx = Math.floor(hb / 864) % 4`, returning `"Spring"`, `"Summer"`, `"Autumn"`, or `"Winter"`.
   - Exposes `getSeasonPalette(seasonName)` returning structured RGB vectors for:
     - `meadowSunlit`, `meadowLush`, `meadowAccent`
     - `coniferDark`, `coniferLit`
     - `deciduousTint` (applied to deciduous tree sprite materials)
     - `snowlineOffset` (`-4.5 m` in Winter, `+0.0 m` in Spring/Autumn, `+3.5 m` in Summer)
2. **Live & Replay Sync (`updateSeasonalFoliage(seasonName)`):**
   - Called from ` updateWeatherAtmospherics(pairName, hb)` whenever `hb` or `selectedPair` changes.
   - Updates shader uniforms (`uSeasonMeadowA`, `uSeasonMeadowB`, `uSeasonAccent`, `uSeasonForestA`, `uSeasonForestB`, `uSeasonSnowOffset`), deciduous tree sprite material colors, and conifer instance/material tint in `O(1)` GPU uniform updates without rebuilding meshes.

---

## 5. Required Test Coverage for Phase 10NA

New test suite `world-sim/tests/test_valley_hydrology_seasons_islands.py` (plus regression run of all 78 existing tests):

1. `test_water_mask_includes_canonical_rivers_lakes_and_valley_reach` — verifies `computeContinentWaterMask` covers canonical `river` and `lake` tiles and places visible river water within `<= 8` tiles of both East and West settlements without overlapping any settlement structure tile.
2. `test_water_mesh_built_and_grounded` — verifies `buildContinentWaterMesh` creates non-empty water geometry for `cont_a` and `cont_b` with water surface elevation strictly above the carved riverbed and below the surrounding dry bank.
3. `test_no_trees_spawn_in_water_channel` — verifies neither 3D conifers nor 2D tree billboards are placed on active `waterMask` tiles.
4. `test_islands_generated_in_lakes_and_coast_without_ocean_violations` — verifies `computeContinentIslands` produces both lake and coastal islands on `cont_a` and `cont_b`, island crowns rise `> 1.0 m` above water, and `test_ocean_stays_below_zero` / `getOceanViolationCount` remain green.
5. `test_compute_season_matches_backend_survival_clock` — verifies `computeSeasonAtHb(hb)` in `prototype/index.html` matches `backend.world.survival.season(hb)` across `hb = 0, 400, 864, 1728, 2592, 6989, 8669`.
6. `test_seasonal_palette_shifts_across_four_seasons` — verifies `getSeasonPalette` produces distinct grass, deciduous, conifer, and snowline parameters for `Spring`, `Summer`, `Autumn`, and `Winter`.

---

## 6. Governance & Progression

- **Phase Chain:**
  - `10MW`: Dolomite Range Composition (Done `c578992`).
  - `10MX`: Metadata Sync (Done `43ac7e5`, hash-corrected `e337f7d`).
  - `10MY`: Valley Hydrology, Islands & Seasonal Foliage Specification (this document) — Docs only.
  - `10MZ`: Metadata Sync — Record 10MY hash in `phase_index.md`, name 10NA implementation candidate.
  - `10NA`: Implementation candidate — valley hydrology water meshes, lake/coastal islands, 4-season foliage wiring, and orbit cordillera continuity.
- **Constitutional Guardrails:**
  - Docs-only specification; no implementation code is authorized under Phase 10MY.
  - Viewer-only scope for 10NA; zero changes to backend cognition, agent prompts, or runtime stores.
  - Pure LF line endings (`CRLF=0`).
