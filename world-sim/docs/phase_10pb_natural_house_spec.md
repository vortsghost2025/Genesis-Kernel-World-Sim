# Phase 10PB — Natural House (Specification)

## Operator report (2026-11-07, with two screenshots)

1. Focus Adam: "when i try to look through adam i see nothing but trees."
   The person-follow camera looks across the wilderness; whatever the
   settlement is doing is behind the camera.
2. Enter House: "the house is kinda better it looks like a cardboard box
   and they are just standing there its not very natural." The 10PA room
   has flat, untextured walls and a flat ceiling slab, so from outside it
   reads as a brown shipping box; inside it is shadow-flat. The agents are
   stiff billboards with no warm light.

## Root causes

1. `applyCameraMode("adam"|"eve")` (~4543) places the camera SW of the
   agent looking NE at a fixed +14-tiles gaze — pure wilderness. Nothing
   biases the view toward the settlement the agent belongs to.
2. `buildInteriorVolumeSpec`/`rebuildInteriorVolume` (~4013) build walls
   and ceiling from `sillWallMat` (flat 0x5c3c20) with a stack-of-plates
   ceiling slab. Flat + unlit = cardboard. `rebuildInteriorProps` only
   adds a point light when a hearth exists on the tile (West often has
   none), so West rooms are lit by the outside sun alone.

## Fix (viewer-only, 10PB spec → 10PC sync → 10PD implementation)

1. **Textured volume.** Procedural canvas textures matching the hut
   palette: horizontal log walls for the four walls, thatch for the roof;
   the wooden floor canvas stays. Flat colour goes.
2. **Pitched roof instead of slab.** Two slanted thatch boxes meeting at
   a ridge (~34°), so from outside the diorama reads as a house, not a
   box, while inside the same slanted underside caps the room.
3. **Warm interior light, always.** One amber point light in the room
   whenever interior mode is active, independent of a hearth prop. The
   room glows from the inside.
4. **Person cameras face the settlement.** Focus Adam/Eve compute the
   direction to the nearest shelter/cabin/hut (same search as interior)
   and gaze along it — the house sits beyond the agent in frame instead
   of behind the camera. Falls back to the current fixed gaze when no
   shelter exists.

## Verification

1. Update `test_viewer_interior.py` (wall/roof texture materials, pitched
   roof boxes, light present, shelter-biased gaze); 50-test viewer
   grouping green; `node --check`.
2. Local renders east/west at 1600×900, read with own vision: textured log
   walls, thatch roof read from outside and inside, warm interior,
   Focus Adam keeps the house beyond the agent, zero page errors.
3. Deploy, re-pin the alias, live probe: same reads, zero page errors.
   `git diff --check`, CRLF 0, unique phase IDs.

## Out of scope

No backend, cognition, prompt, canonical, fauna, viewer-data or
agent-reachable change. Figure artwork stays (billboards); the win is
walls, roof, light and framing. Phase chain: 10PB (spec) → 10PC
(metadata sync) → 10PD (implementation candidate).
