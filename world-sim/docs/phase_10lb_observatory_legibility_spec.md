# Phase 10LB Specification: Observatory Legibility — Interiors, Locomotion, Atmosphere

> **Phase Chain:** 10KZ (impl, Done `f8cced2`; corrected `462f325`) -> 10LA (metadata sync, Done `602ccfc`, hash-corrected `97c593d`) -> 10LB (specification, this document) -> 10LC (metadata sync) -> 10LD (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10LD following explicit operator authorization.

---

## 1. Purpose & Why Now

Four backend mechanics — load-bearing construction (10KM), horizon sighting (10KQ), pastoral attraction (10KH), goal dedup (10KZ) — are verified green and **behaviourally inert in the live lanes**. Measured at HB 6296/8182: East took 161 moves and 2 builds per 100 heartbeats with zero `hew_timber`, zero `addon_to`, zero craft; West took 36 `ask_human` with zero builds.

Phase 10LB deliberately stops adding mechanics. It makes the simulation **legible** instead — visible through the observatory whether or not the agents' behaviour changes. Sean's field reports set the scope: *"I don't see them go into their houses… I want to see them take down trees and find rocks and build things… they don't move proper, it's like a static figure sliding."*

The data required for all of it **already exists** in the viewer payload. Nothing in this spec invents a mechanic.

---

## 2. What The Payload Already Provides (verified)

Measured from `viewer/viewer_data.js`, exported 2026-10-31T13:43Z:

| Capability needed | Already in payload |
| :--- | :--- |
| Per-heartbeat agent position | `position_timeline` — a **dense dict keyed 1..6296 (East) and 1..8182 (West)**, every heartbeat, `{"east_adam": "<tile_id>", ...}` |
| Whether an agent is indoors | `shelter_occupancy` — currently `{"west_eve": true}`, i.e. **live interior data exists right now** |
| Weather and its schedule | `weather` — `{"current": "rain", "next": "clear", "changes_at_heartbeat": 8208}` |
| Interiors to furnish | East: 11 `shelter`, 2 `lean-to`, 2 `storage_box`, 1 `roof`. West: 9 `shelter`, 3 `lean-to`, plus **`bed` x2, `table` x2, `chair` x2, `door` x2, `chest` x3, `barrel` x2** |
| Settlements to render | East 83 public objects; **West 261**, including 30 `crafting_surface`, 32 `tool`, 41 `storage`, 35 `container`, 5 `forge`, 3 `furnace`, 3 `well` |
| Compound graphs | `compounds` — **empty (0) in both lanes** |

West's object inventory is far richer than what the observatory shows: it has built furniture and a forge, and the viewer renders it as undifferentiated props.

---

## 3. Scope

### 3.1 In Scope (Phase 10LD Candidate), in priority order

1. **Interior legibility.** When an agent is sheltered (`shelter_occupancy[ref] === true`) or the camera enters a shelter, render an interior the operator can actually see into.
2. **Locomotion.** Replace the current single-frequency vertical sine with directional facing and a two-phase walk gait.
3. **Atmosphere.** Drive the existing particle system from the real weather schedule rather than a static current-state read.
4. **Object differentiation.** Render the distinct object types that already exist as visually distinct props.

### 3.2 Explicitly Out of Scope

- **Construction FX (scaffolding, woodchips, tree-felling).** `hew_timber`, `addon_to`, and `build` on structural types have never fired in either lane. These will be implemented as **honest placeholders only** — no fabricated animation over behaviour that does not exist. Revisit only after a live `hew_timber` event is recorded.
- Any backend mechanic. No changes to `fauna.py`, `first_pair_runtime.py`, goal handling, or action dispatch.
- Live store writes or daemon changes.
- Camera controls further change — the input path is fixed (`9a9db4f`, `2611d6c`) and must not regress.

---

## 4. Design Invariants

1. **Show what is, not what we wish.** Every visual must be derived from a field present in the payload. If a behaviour has never occurred, its visual is absent, not simulated.
2. **Deterministic replay.** All visuals derive from `position_timeline[hb]` and object records at that heartbeat — scrubbing the timeline must reproduce the same scene, never a generated one.
3. **No regression of the camera path.** The `controls` `start` listener, the `camAnimating` gate, and the `_lastCamSyncHb` poll gate must all remain intact. Implementation must not reintroduce per-frame or per-poll camera forcing.
4. **Bounded cost.** The timeline is up to 8,182 frames of position data and 261 objects; rendering must stay interactive. Precompute per-heartbeat scene deltas at load, do not re-derive per frame.

---

## 5. Architectural Specifications

### 5.1 Interior Legibility

Current state: `toggleInteriorCutaway` and the `cam-interior` button exist (10KB) and drop the roof when the camera is close. The gap is that interiors are empty and agents are drawn at their outdoor tile even when sheltered.

Phase 10LD:

- **Roof and wall treatment.** On `shelter_occupancy[ref] === true`, or on camera proximity to a shelter, fade the roof and cut perimeter walls to sill height. Reuse the existing `toggleInteriorCutaway` entry point; no new camera mode.
- **Furnishing from real records.** Interiors are populated from `public_objects` whose `tile_id` falls inside the shelter:
  - West already has `bed`, `table`, `chair`, `door`, `chest`, `barrel` — render these as the interior props they are.
  - East has `shelter`, `lean-to`, `storage_box`, `roof` — render a storage/sleeping arrangement from those types.
  - `campfire` inside a shelter becomes the hearth (the shared-hearth mechanic already exists in `_nearby_fire`; this only *shows* it).
- **Agent placement.** A sheltered agent is drawn **inside** at the shelter's tile, not clipped behind the exterior sprite. Already available: `shelter_occupancy` tells us which of the two agents, and `position_timeline` tells us where the shelter is at that heartbeat.
- **No invented contents.** If a shelter's record lists no objects, the interior is an empty floor. Do not populate it with props the agents never built.

Tests: a sheltered agent renders inside; a non-sheltered agent does not; an empty shelter renders an empty floor; scrubbing to a heartbeat where the agent was outside restores the outdoor placement.

### 5.2 Locomotion

Current state (verified, `index.html`): `strideBob = Math.sin(alpha * Math.PI * 2) * 0.024` — a single vertical sine with no directional component. That is the "cardboard cutout sliding" Sean described.

Phase 10LD:

- **Directional facing.** Derive heading from consecutive `position_timeline` entries for that agent: `dx = x[t] - x[t-1]`, `dz = z[t] - z[t-1]`. Set the sprite's horizontal scale to face the direction of travel, matching the existing per-agent `charW`. Idle agents keep their last facing — no snapping to a default.
- **Two-phase gait.** Replace the single sine with a cadence that compresses on footfall and rises on stride extension. Amplitude stays at the current 0.024 m order of magnitude; the change is the *shape*.
- **Speed-consistent cadence.** Step cadence derives from distance travelled between heartbeats, so a replay at 2x does not double the stride rate.
- **Stationarity is visible.** An agent with zero displacement across several heartbeats shows a settled idle pose, not a frozen mid-stride.

Tests: eastward travel flips one way and westward the other; zero displacement yields idle facing preserved and gait amplitude decaying to rest; two heartbeats of movement produce two complete gait phases.

### 5.3 Atmosphere

Current state: a 2,000-streak `THREE.LineSegments` precipitation volume exists, and weather-keyed fog/lighting tables exist. The gap is that the visible state is read from the snapshot's `current` rather than its **schedule**.

Phase 10LD:

- Drive weather visuals from `weather.changes_at_heartbeat`: the renderer must transition at the recorded heartbeat, not when the page happens to reload.
- Both lanes currently read `{"current": "rain"}` — so rain is real and present in both lanes right now, and this is immediately visible.
- Scrubbing the timeline re-evaluates weather at the scrubbed heartbeat.

Tests: a heartbeat before `changes_at_heartbeat` renders the prior state; the change heartbeat renders the new state; clear state disables precipitation entirely.

### 5.4 Object Differentiation

Render distinct meshes/tints for the object types already present, at minimum: `campfire` (flicker already exists), `shelter`, `hut`, `lean-to`, `roof`, `wall`, `door`, `storage_box`/`chest`/`barrel`, `table`, `chair`, `bed`, `crafting_surface`, `forge`, `furnace`, `well`, `tool`, `landmark`. West's 261 objects span most of these; rendering them identically is why West looks like clutter.

---

## 6. Required Test Coverage for Phase 10LD

In `tests/test_viewer_legibility.py`:

1. `test_position_timeline_is_dense_and_complete` — the payload provides a position for every agent at every heartbeat in range.
2. `test_sheltered_agent_position_is_inside_shelter` — a sheltered agent is placed at the shelter tile.
3. `test_empty_shelter_renders_empty_floor` — no fabricated props.
4. `test_directional_facing_matches_travel_heading`.
5. `test_idle_agent_preserves_last_facing`.
6. `test_gait_cadence_is_derived_from_displacement`.
7. `test_weather_transitions_at_recorded_heartbeat`.
8. `test_clear_weather_disables_precipitation`.
9. `test_known_object_types_have_distinct_visual_ids`.
10. `test_no_camera_regression_after_legibility_change` — asserts the `start` listener, `camAnimating` gate, and `_lastCamSyncHb` gate are all still present in the source.
11. `test_construction_fx_absent_until_hew_timber_recorded` — the FX group contains no scaffolding/woodchip emitters unless a `hew_timber` or `build` event exists in the timeline at that heartbeat.

---

## 7. Governance & Progression

- **Phase Chain:**
  - `10KZ`: Goal Lifecycle Implementation (Done `f8cced2`, corrected `462f325`).
  - `10LA`: Metadata Sync (Done `602ccfc`, hash-corrected `97c593d`).
  - `10LB`: Observatory Legibility Specification (this document) -- Docs only.
  - `10LC`: Metadata Sync -- Record 10LB hash in `phase_index.md`, name 10LD candidate.
  - `10LD`: Implementation candidate -- interiors, locomotion, atmosphere, object differentiation.
- **Constitutional Guardrails:**
  - Docs-only specification; no implementation code is authorized under Phase 10LB.
  - No backend mechanic changes; no live store writes.
  - Construction FX must remain absent until a live `hew_timber`/structural `build` is recorded.
  - Stage ONLY `world-sim/docs/phase_10lb_observatory_legibility_spec.md`. Never `git add -A` or `git add .`.
  - Pure LF line endings (`CRLF=0`).
