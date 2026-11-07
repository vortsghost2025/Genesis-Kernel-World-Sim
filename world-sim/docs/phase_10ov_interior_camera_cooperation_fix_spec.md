# Phase 10OV — Interior Camera Cooperation Fix (Specification)

## Operator report (2026-11-07)

"when i try to enter home to view its not very cooperative and the view
looks like its not in the house."

## What Enter House actually does (verified in source)

"Enter House" does not move the camera inside the house mesh. It hides the
real shelter prop (`toggleInteriorCutaway`, index.html ~4164) and shows a
separate dollhouse diorama (`interiorGroup`): a floor plus low sill walls
(0.62 high) at the shelter's terrain position, with a hearth/bed/table/etc.
rebuilt from the tile's public objects. Agents are repositioned into it by
`updateAllAgentFigures` (~5411). Only the FIRST object prop within 1.2
units (`cutawayShelterProp`, singular) is hidden.

## Defect 1: it does not settle (measured)

- The interior branch calls `smoothMoveCamera(..., false)` — hardcoded,
  ignoring the `immediate` argument — so the camera slow-lerps
  (0.12/frame) from wherever it was. Local repro probe: scripted target
  (0.6, 4.56, 3.8) but the live camera was still at (1.66, 9.44, 25.72)
  mid-flight; the 3-second screenshot still showed the old landscape
  framing. No snap, no settle.
- `syncHeartbeatScene` re-runs `applyCameraMode` on every heartbeat where
  `currentHb` changed, so during play/live the camera is re-aimed from
  scratch each tick — even after the operator orbits somewhere useful.
  The view fights the operator.

## Defect 2: it does not read as inside (measured)

- `smoothMoveCamera` gives every mode except human/adam/eve a 3.0 minimum
  terrain clearance. Interior is not in that list, so the scripted
  `sh + 1.85` camera is raised to terrain + 3.0 (repro: 4.56 for terrain
  ~1.5). From +3.0 looking down at fov 36, the sill-wall diorama reads as a
  tiny top-down model, not an interior — and the settled screenshot shows
  neighboring huts (only one prop within 1.2 units is hidden) and the
  village forest crowding the frame.

## Fix (viewer-only)

1. **Snap on entry.** The interior branch passes `immediate` through to
   `smoothMoveCamera`, and the button calls `applyCameraMode("interior",
   true)`. Re-clicking when the operator has parked elsewhere still snaps
   (that is the explicit act of entering).
2. **Low across-the-floor framing.** Camera at `(targetX - 0.4, sh + 0.95,
   targetZ + 2.9)`, target `(targetX + 0.3, sh + 0.35, targetZ - 1.2)`,
   fov 55. "interior" joins the 1.45 terrain-clearance list so the
   clearance rule no longer yanks it up to +3.0. Sill walls in the near
   foreground, floor, agents and hearth beyond: an interior view.
3. **Heartbeat-stay.** While interior is active, `syncHeartbeatScene`
   refreshes only the interior props (`rebuildInteriorProps` for the
   active tile); it does not re-aim the camera or rebuild the volume.
   Exiting to another mode still runs `toggleInteriorCutaway(false)`.
4. **Hide the whole shelter tile.** Replace the singular first-child hide
   with hiding every object prop on the target tile plus any shelter-type
   prop within Chebyshev 2 of the target; restore all on exit. Neighboring
   huts stop standing over the diorama.

## Verification plan

1. New tests in `world-sim/tests/test_viewer_interior.py`: static contract
   (button wires immediate=true; interior branch passes immediate; clearance
   list contains interior; hide-all + restore-all present; sync skips camera
   re-aim in interior while refreshing props) plus `node --check`.
2. Repro script re-run: camera settles at the scripted low framing
   immediately (camera ≈ target within epsilon on the settle read), hidden
   count covers every shelter-type prop on the tile.
3. Local renders east/west at 1600×900 and 900×800, read with the model's
   own vision: dollhouse floor and figures fill the frame, no neighboring
   hut roof overhead, zero page errors. Orbit mode unchanged.
4. Deploy, re-pin the alias, live probe: same settle read + zero page
   errors. `git diff --check`, CRLF 0, unique phase IDs.

## Out of scope

No backend, cognition, prompt, canonical, fauna or agent-reachable change.
The diorama concept stays (floor + sill walls + rebuilt props); only the
camera, settling behaviour and prop hiding change. Phase chain:
10OV (spec) → 10OW (metadata sync) → 10OX (implementation candidate).
