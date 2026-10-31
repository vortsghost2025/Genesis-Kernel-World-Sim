# Phase 10LJ Specification: Continental Relief, Interior Volume & Settlement Consolidation

> **Phase Chain:** 10LH (impl, Done `689b9f9`; prompt fix `02b1d17`) -> 10LI (metadata sync, Done) -> 10LJ (specification, this document) -> 10LK (metadata sync) -> 10LM (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10LM following explicit operator authorization.

---

## 1. Origin: Operator Field Report, Verified Against Source

Sean, inspecting the live observatory: *"the mountain ranges are tiny… they should be massive with some trails and caves and stuff; the houses are bigger than the mountains; I still find it weird they constructed 9 houses instead of 1 large house — if they were actually gathering materials it would be a massive waste of resource to have 10 houses; if the things were the right dimensions it would be easier to see inside the houses when they are inside, where right now they are bigger than the houses."*

Every clause was checked against the source. The first three are **correct**, the fourth is **correct about perception but wrong about the ratio**, and the fifth is a genuine design gap.

### 1.1 The world has almost no vertical relief

Terrain is generated in `prototype/index.html`:

```js
const gentleBase = 0.18 + eClamped * 1.15;              // 0.18 .. 1.33 m
const mtnPeak = Math.pow(Math.max(0.0, eClamped - 0.52), 1.65) * 8.2;   // 0 .. 8.2 m
```

A **two-pass 5x5 Gaussian** (`rebuild` at lines 1235-1268) then smooths the field, which attenuates peaks further. Net result on a 200x200 continent: **total elevation range under ~10 metres**, and that includes smoothing losses.

### 1.2 Consequence: a shelter is taller than a mountain

| Object | Measured size | Notes |
| :--- | :--- | :--- |
| Terrain maximum | **~9.7 m** pre-smoothing, less after | `gentleBase + mtnPeak` |
| Mountain peak sprite | `4.4w x 4.1h`, `sc = 0.85 + (seed % 35)/100` | **3.5 - 4.9 m**, one per tile |
| Shelter | `5.4w x 4.4h`, profile scale 1.1 | **5.9 x 4.8 m** |
| Agent | `charH = 1.44` | unchanged |
| Cave sprite | `3.6 x 3.65` | one per tile, 3.6 m |
| Trails | **none** | no concept exists |

So the tallest mountain (~4.9 m) is shorter than a house (~4.8 m), and a "cave" is a 3.6 m billboard. Sean's observation is arithmetically exact.

### 1.3 The 9-houses problem is a consolidation-gap, confirmed

West holds **9 shelters, 33 distinct structure tiles, 261 public objects** (41 storage, 35 container, 32 tool, 30 crafting_surface). East holds **11 shelters across 25 tiles**. Nobody has ever used `addon_to`; `world_state.compounds` is empty in both lanes.

The reason is now measurable rather than speculative. The 10KM structural floor makes a shelter cost **2 hewn timber**, and the 10LH schema fix means `addon_to` at last validates. But an agent has no reason to prefer attaching a room to an existing shelter over declaring another standalone one: `_execute_build` charges the same declared materials either way, and the `addon_to` discount (half the structural floor) is invisible unless the agent already knows to attach.

Sean's instinct is the right incentive model: **materials that must be individually gathered make a duplicate shelter expensive**, so consolidation should be the rational choice. Nothing currently enforces that.

---

## 2. Scope

### 2.1 In Scope (Phase 10LM Candidate)

1. **Continental vertical relief.** Raise the real terrain elevation range so mountain ranges read as mountain ranges.
2. **Mountain ranges and ridges.** Mountains spanning multiple tiles, generated from the height field rather than one billboard per tile.
3. **Caves as terrain features.** Openings in mountain faces, tied to elevation and rock rather than a flat 3.6 m sprite.
4. **Foot trails.** Paths derived from the agents' actual `position_timeline` history — where they have walked becomes visible.
5. **Interior volume.** Real floor and wall meshes so an agent indoors occupies actual space rather than standing against a flat billboard.
6. **Consolidation pressure.** Make attaching materially cheaper than duplicating, and disclose that in the prompt.

### 2.2 Out of Scope

- Any backend mechanic beyond the `addon_to` disclosure. No new action types.
- Changing the agent figure size (1.44 m is correct for a human-scale world) or the shelter footprint (5.4 x 4.4 m is correct — see §3.4).
- Weather, fauna, locomotion, or camera-input code beyond the clearance adjustments §3.1 forces.
- New flora or fauna.

---

## 3. Design Invariants

1. **Scale conservatism on agents and buildings.** `charH = 1.44` and the 5.4 x 4.4 shelter stay. A 1.44 m human in a 5.4 x 4.4 room is a 27% height ratio, which is right. The problem is the *terrain*, not the house. Do not shrink houses to fix the mountain problem.
2. **Props stay grounded.** Every prop and agent already clamps to `getTerrainHeight`. Raising relief means these must remain flush, not float or sink — this is the primary regression risk.
3. **Camera clearance must follow.** `smoothMoveCamera` enforces `groundH + minClearance`; camera-mode view heights (52 m landscape, 1.52 m human eye) must be re-evaluated against taller terrain.
4. **Derived, not invented.** Trails come from `position_timeline`; caves from the height field; nothing is placed by hand.
5. **Bounded cost.** Height field is 200x200 per continent and is already computed once at load. Range generation must not become per-frame work.

---

## 4. Architectural Specifications

### 4.1 Vertical relief (`prototype/index.html`, terrain generation)

Current constants (`gentleBase`, `mtnPeak`) and the two-pass 5x5 smoothing are the entire vertical range of the world.

Phase 10LM:

- Raise `mtnPeak`'s multiplier so that elevation 1.0 produces a genuine mountain, and lower the exponent's onset so mid-high ground gains height. Target: **maximum terrain elevation 30-60 m**, with hills at 2-6 m and plains under 1 m.
- Keep smoothing, but widen its kernel selectively for ridges or the peaks become pyramids. A 5x5 Gaussian on a 50 m peak is what currently flattens them.
- **Camera clearance is the coupling risk.** `smoothMoveCamera`'s `minClearance` (1.45 m human/agent modes, 3.0 m otherwise) is a *minimum above ground*, so it still holds — but `activeCamMode` view heights are absolute offsets and must be re-checked (e.g. the 52 m landscape offset from a 60 m peak is now inside the mountain).
- Tests: terrain max elevation now exceeds a floor (30 m); ocean stays below 0; props sit flush on a synthetic 50 m peak (`getTerrainHeight` agreement); camera minimum clearance never goes below the ground on sampled peaks.

### 4.2 Mountain ranges and ridges

Currently a single `createMountainPeakSprite(4.4 x 4.1)` per mountain tile with `scale 0.85-1.20`.

Phase 10LM:

- Generate ranges by **connected runs of high-elevation tiles**. A range is a chain: a contiguous set of mountain tiles, rendered as a ridge whose height follows the smoothed height field, not a per-tile sprite.
- Peaks are placed at local maxima within a range and scaled by that maximum's elevation, not by `seed % 35`.
- The peak sprite's aspect may stay, but its **scale must derive from terrain height**, so a 50 m summit reads as a summit.
- Tests: a synthetic range of five mountain tiles produces one connected ridge, not five sprites; the highest tile carries the largest peak; a lone mountain tile still renders.

### 4.3 Caves and trails

- **Caves.** Place at terrain tile boundaries where elevation is high and the neighbourhood drops steeply (a cliff face), rather than by `seed`. Size scales with the face it sits in.
- **Trails.** Derive from `position_timeline`: for each agent, consecutive heartbeats whose positions differ produce a walk segment; render frequently-walked segments as a visible path. This makes *"they walked here"* legible, which is exactly what Sean is asking for when he says he can't see them doing anything.
- Tests: a synthetic 100-heartbeat walk produces trail segments matching the walked tiles; caves only appear at elevation transitions, not on plains; trail rendering has no effect on gameplay state.

### 4.4 Interior volume

Sean: *"if the things were the right dimensions it would be easier to see inside the houses."*

The ratio is already correct — the fault is that there is **no interior volume at all**. `toggleInteriorCutaway` fades the roof and `rebuildInteriorProps` places furniture, but the shelter is a flat billboard: the agent stands *against* a picture rather than *inside* a room.

Phase 10LM:

- Give the cutaway a real floor plane at the shelter's tile and low sill walls at the perimeter, so interior space exists as geometry.
- Place sheltered agents (from `shelter_occupancy`) on that floor at interior coordinates, already done positionally; the point is that there is now a floor to stand on.
- Keep furniture placement driven by real `public_objects` records only — an empty shelter stays an empty floor.
- Tests: interior mode produces a floor mesh and perimeter walls; sheltered agents rest on the floor plane (`y == floorY + charH`), not clipping or floating; an empty shelter renders an empty floor and no props; exterior mode disposes of interior geometry.

### 4.5 Consolidation pressure and disclosure

- **Cost.** `_execute_build`'s `addon_to` path already discounts structural timber to half the floor. Widen that to all declared materials for the structural component and disclose the discount, so attaching is *visibly* cheaper.
- **Disclosure.** Add a prompt line sourced from the runtime: attaching to an existing structure declines the structural component. Same pattern as the recipe disclosure and the timber requirement — facts, generated from the table that enforces them.
- **Tests:** attaching resolves to a strictly lower material cost than the equivalent standalone build on every structural type; the disclosure renders in the full prompt and names `addon_to`; no banned directive phrases.

---

## 5. Required Test Coverage for Phase 10LM

In `tests/test_continental_relief.py` and additions to `test_viewer_legibility.py`:

1. `test_terrain_max_elevation_exceeds_floor` — max height >= 30 m (or the recorded measured baseline plus a stated margin).
2. `test_ocean_stays_below_zero`.
3. `test_prop_grounding_on_synthetic_peak` — a 50 m peak keeps props flush.
4. `test_camera_clearance_never_below_ground`.
5. `test_mountain_range_is_one_ridge` — contiguous high tiles form one ridge object.
6. `test_peak_scale_follows_elevation` — the tallest tile carries the largest peak.
7. `test_caves_only_at_elevation_transitions`.
8. `test_trails_derived_from_position_timeline` — walked segments become paths.
9. `test_interior_has_floor_and_sill_walls`.
10. `test_sheltered_agent_rests_on_floor_plane`.
11. `test_empty_shelter_stays_empty`.
12. `test_interior_geometry_disposed_on_exit`.
13. `test_addon_costs_strictly_less_than_standalone`.
14. `test_addon_discount_disclosed_in_prompt`.

---

## 6. Governance & Progression

- **Phase Chain:**
  - `10LH`: Action Schema Parity & Build Unblocking (Done `689b9f9`, prompt fix `02b1d17`).
  - `10LI`: Metadata Sync (Done).
  - `10LJ`: Continental Relief, Interior Volume & Settlement Consolidation Specification (this document) -- Docs only.
  - `10LK`: Metadata Sync -- Record 10LJ hash in `phase_index.md`, name 10LM candidate.
  - `10LM`: Implementation candidate -- relief, ranges, caves, trails, interior volume, consolidation.
- **Constitutional Guardrails:**
  - Docs-only specification; no implementation code is authorized under Phase 10LJ.
  - Do not shrink buildings or agents; the fault is terrain scale (invariant 1).
  - Terrain changes must not regress prop grounding or camera clearance.
  - No live store writes.
  - Stage ONLY `world-sim/docs/phase_10lj_continental_relief_and_interior_volume_spec.md`. Never `git add -A` or `git add .`.
  - Pure LF line endings (`CRLF=0`).
