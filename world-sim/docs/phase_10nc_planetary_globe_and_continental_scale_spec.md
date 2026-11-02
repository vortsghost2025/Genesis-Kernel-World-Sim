# Phase 10NC Specification: Planetary Globe Rendering & Continental Scale

> **Phase Chain:** 10NA (impl, Done `1de0373`) -> 10NB (metadata sync, Done `39decfa`, hash-corrected `824155d`) -> 10NC (specification, this document) -> 10ND (metadata sync) -> 10NE (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10NE following explicit operator authorization.

---

## 1. Origin: Operator Field Report

Sean, inspecting the World Atlas orbit view: the Earth renders as "two flat squares" rather than a globe, and the world does not feel massive — "starting in Florida and Persia kinda far away."

### 1.1 Measured root cause

The orbit view is a flat-plane composition, verified in `world-sim/viewer/prototype/index.html`:

| Element | Current code | Effect |
| :--- | :--- | :--- |
| Continent mesh | `new THREE.PlaneGeometry(200, 200, SEG, SEG)` in `buildContinentMesh` | Flat 200x200 unit squares, no curvature |
| Ocean | `globalOceanGeom = new THREE.PlaneGeometry(900, 700, 1, 1)` | Flat blue plane under the continents |
| Orbit placement | `focusCiv()` sets `cont_a.position.set(-125, 0, 0)` and `cont_b.position.set(125, 0, 0)` | Two flat rectangles 250 units apart |
| Orbit camera | `smoothMoveCamera(new THREE.Vector3(0, 195, 235), ...)`, `camera.fov = 44` | Orthographic-feeling top-down over a plane |
| Orbit atmosphere | `scene.background.setHex(0x0f2d4a)`, `skyDome.visible = false`, `scene.fog.density = 0.0005` | Flat ocean colour, no sky, no horizon |

### 1.2 The scale arithmetic

With the continent mesh 200 world units across and agents at `1.44` units (`charH`, line 1931), **one tile equals one metre**. A continent is therefore a 200 x 200 metre box — roughly a suburban block — and the two continents sit 250 metres apart. That is why the orbit view reads as two small flat squares: it is one.

The operator's reference frame is continental-to-planetary. Matching it requires the orbit view to render at continent scale, which is a different scale from the human-scale valley views. These two scales are currently fused into one and must be separated.

### 1.3 Constraint

The human-scale valley views (agent `1.44` units beside a `5.4 x 4.4` hut) are approved and working. They must not be broken to fix the orbit view. Any scale change is therefore **orbit-mode only**, and local views keep `1` unit = `1` metre.

---

## 2. Scope

### 2.1 In Scope (Candidate Phase 10NE)

1. **Planetary globe mesh.** Replace the flat orbit plane with a sphere at planetary radius; project each continent's existing 200x200 grid onto a patch of that sphere.
2. **Orbit-only scale separation.** Orbit mode renders at continent/planet scale; every local mode (`human`, `landscape`, `adam`, `eve`, `topdown`, `interior`) keeps `1` unit = `1` metre.
3. **Ocean surface as a sphere, not a plane.** The Great Ocean becomes the sphere's remaining surface rather than a `PlaneGeometry(900, 700)`.
4. **Atmospheric depth.** Sky dome, horizon haze, and fog scaled for the globe radius so distance reads as planetary rather than tabletop.
5. **Orbit camera and controls.** Curved-surface-aware orbit controls and a default viewing distance that shows the whole planet.
6. **Transition.** A clean handoff between globe and human-scale views without popping or misplacement.

### 2.2 Out of Scope

- **No simulation, cognition, prompt, or behavioural changes.** The 200x200 tile grid, the heartbeat clock, and all agent logic are untouched. Phase is 100% rendering.
- **No new world data.** The canonical `true_map.json` is read as-is; continents are projected, not expanded.
- **No changes to local-scale rendering**, anything inside `buildContinentMesh`'s elevation, the hydrology/island meshes, or the flora/scenery systems.
- **No changes to live stores or runtime processes.**

---

## 3. Design Invariants

1. **Local scale is frozen.** Any tile coordinate rendered in a non-orbit mode must map to the same world position it maps to today. `1` unit = `1` metre in all local modes, always.
2. **No canonical-data mutation.** The globe is a projection of existing tile data. `data/world/true_map.json` is never written.
3. **Ocean invariant preserved.** `test_ocean_stays_below_zero` and `getOceanViolationCount(cid) === 0` must remain green. Ocean tiles must stay below the continent surface in both flat and spherical projections.
4. **Single source of truth for terrain height.** Both the flat local mesh and the spherical globe derive elevation from the same `heightLookup` / `computeContinentHeightField`. No second elevation generator.
5. **Determinism.** Globe projection is a pure function of tile coordinates and constants. No RNG, no per-frame drift.
6. **Reversible.** If the globe cannot be made to read correctly, reverting to the flat orbit view is a contained change; no data migration.

---

## 4. Architectural Specifications

### 4.1 Planetary sphere (`buildPlanetGlobe`)

- Build one sphere per scene at planetary radius derived from the continent extent, with enough segments that a 200-tile continent reads as a continent rather than a smudge.
- Map each continent's grid onto a spherical patch: convert tile `(x, y)` to spherical coordinates, applying the same elevation field, and displace radially by that elevation so mountains remain mountains on the curve.
- Oceans fill the remaining sphere surface, replacing `globalOceanGeom`.
- Keep the two continents geographically distinct and separated by ocean, as they are today.

### 4.2 Scale separation

- Introduce an explicit scale factor applied **only** while `selectedPair === "orbit"`.
- Local modes use scale `1.0` (today's behaviour, unchanged).
- Orbit mode uses the planetary scale, applied to the globe group.
- Switching modes recomputes positions from tile coordinates using the active scale, so no state is carried across the boundary.

### 4.3 Atmosphere and camera

- `skyDome.visible` restored true in orbit mode; ocean background colour retired in favour of the sky dome.
- `scene.fog` density and colour scaled to the globe radius so distant continents haze rather than clip.
- Default orbit camera distance derived from the globe radius, with the planet filling the frame.
- Orbit controls constrained so the camera cannot pass inside the surface.

### 4.4 Fauna, hydrology, islands on the globe

- `faunaFiguresGroup`, water meshes, `islandGroups`, `sceneryGroups`, and `objectGroups` must all project onto the globe in orbit mode using the same coordinate mapping as the terrain, so nothing floats or sinks when the view switches.
- Per-heartbeat scrubbing continues to work identically in both views.

---

## 5. Required Test Coverage for Phase 10NE

In `tests/test_planetary_globe.py`:

1. `test_globe_projection_preserves_local_coordinates` — a tile's position in a local mode is identical before and after the globe change.
2. `test_ocean_stays_below_zero_on_sphere` — `test_ocean_stays_below_zero` and `getOceanViolationCount` remain green with the spherical projection active.
3. `test_globe_uses_single_elevation_source` — the globe's elevation derives from the same `heightLookup`/`computeContinentHeightField` entries as the flat mesh; no second generator.
4. `test_mode_switch_recomputes_positions` — switching between orbit and a local mode re-derives positions from tile coordinates with the correct scale and produces no intercepting artifacts.
5. `test_projection_is_pure_and_deterministic` — identical tile coordinates and constants yield identical globe positions; no RNG involved.
6. `test_fauna_and_objects_project_with_terrain` — fauna, water, islands, scenery, and objects share the globe coordinate mapping in orbit mode.
7. `test_all_existing_viewer_tests_green` — the full existing viewer/relief/hydrology suites remain green with default settings.

---

## 6. Governance & Progression

- **Phase Chain:**
  - `10NA`: Valley Hydrology, Islands & Seasonal Foliage Implementation (Done `1de0373`).
  - `10NB`: Metadata Sync (Done `39decfa`, hash-corrected `824155d`).
  - `10NC`: Planetary Globe Rendering & Continental Scale Specification (this document) — Docs only.
  - `10ND`: Metadata Sync — Record 10NC hash in `phase_index.md`, name 10NE candidate.
  - `10NE`: Implementation candidate — TDD implementation of the planetary globe, orbit-only scale separation, spherical ocean, and atmosphere.
- **Constitutional Guardrails:**
  - Docs-only specification; no implementation code is authorized under Phase 10NC.
  - 100% rendering scoped; zero simulation, cognition, prompt, or behavioural change.
  - Local human-scale rendering must not regress.
  - No writes to `data/`, live stores, or daemons.
  - Stage ONLY `world-sim/docs/phase_10nc_planetary_globe_and_continental_scale_spec.md`. Never `git add -A` or `git add .`.
  - Pure LF line endings (`CRLF=0`).
