# Phase 10OY — Enclosed Interior (Specification)

## Operator report (2026-11-07, with screenshot)

"its not right at all it looks like they are standing at a campfire outside
its not inside a house at all"

## What he sees (his screenshot, East replay)

Adam and Eve stand on the wooden deck of the Enter House diorama around
the rebuilt hearth. There are no walls above knee height (dollhouse sill
walls are 0.62 high, front ones 0.48), no roof, and the forest, snow and
neighbor structures are fully visible behind them. It reads as an outdoor
platform, not an interior. Nothing encloses them.

## Fix (viewer-only, 10OY spec → 10OZ sync → 10PA implementation)

1. **Full-height volume.** `buildInteriorVolumeSpec`: walls go from 0.62 to
   1.9 units tall (front door-gap walls too), plus a ceiling slab at
   floor + 1.9. The diorama becomes an enclosed room: floor, four walls,
   roof. From inside, the forest and neighbor huts are gone.

2. **Camera goes inside the room.** Current camera sits OUTSIDE the front
   kerb at `targetZ + 2.9` looking in. New camera sits inside near the
   front-right: `(targetX + 0.7, sh + 1.35, targetZ + 1.15)` looking across
   the room to `(targetX - 0.4, sh + 0.55, targetZ - 1.1)`, fov 58. Eye
   ~1.35 under a 2.02 ceiling, target at torso height across the room. Near
   plane 0.25 clears the front wall (~0.5–0.6 away). Re-clicking Enter
   House still snaps (10OX behaviour preserved); heartbeat-stay preserved.

3. **Nothing else changes.** The exterior-hide logic (whole tile +
   Chebyshev 2, re-appliable), exterior restore, props rebuild, and all
   other camera modes stay as 10OX left them. The settled framing is
   verified by the existing interior tests updated to the new numbers.

## Verification

1. Update `test_viewer_interior.py` framing assertions (fov 58, inside-room
   vectors, wall height 1.9, ceiling present); 49-test viewer grouping green.
2. `node --check`; local renders east/west: the room encloses the frame
   (floor + walls + ceiling, hearth, both agents), no forest/neighbor hut
   in the background, zero page errors.
3. Deploy, re-pin the alias, live probe: same settled read, zero page
   errors. `git diff --check`, CRLF 0, unique phase IDs.

## Out of scope

No backend, cognition, prompt, canonical, fauna, viewer-data or
agent-reachable change. The dollhouse convention stays (an interior
volume, not a camera-inside-the-texture-sprite); it now just has walls
and a roof. Phase chain: 10OY (spec) → 10OZ (metadata sync) → 10PA
(implementation candidate).
