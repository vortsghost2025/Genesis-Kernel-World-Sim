# Phase 10PE — House Finish (Specification)

## Operator report (2026-11-07)

"when i look form the outside they have like 10 houses attached together
but it looks like they are inside a bathroom stall"

Two complaints, both verified:

1. **Exterior mega-cluster.** The West lane built cabins/shelters on many
   adjacent tiles. Each exterior shelter sprite is 5.4×4.4 world units
   wide on a 1-unit tile grid (`createShelterSprite`), so every sprite
   engulfs ~5×5 tiles and neighbors interpenetrate into one attached
   mush. The agents' architecture is real; the unreadable overlap is the
   render scale.
2. **Stall interior.** The 10PD room has flat-ish proportions: a 1.25-wide
   full-height door cut reads as a missing wall, there are no windows,
   trim, or chimney — three flat walls and a low ceiling. It reads as a
   bathroom stall, not a house.

## Fix (viewer-only, 10PE spec → 10PF sync → 10PG implementation)

**A. Exterior shelters shrink to readable scale.**
`createShelterSprite` gains a global factor 0.62 (5.4 → ~3.35 wide,
4.4 → ~2.7 tall), applied to width, height and shadow radii. The
interior volume spec (always explicit 5.4×4.4) is untouched. Adjacent
houses stop interpenetrating; the cabin cluster reads as cabins.

**B. Interior stall-breakers.**
1. Door gap 1.25 → 0.95 wide, full height, with a lintel beam across
   the top — a doorway, not a missing wall.
2. Glowing windows: small emissive amber planes on the back wall and
   one side wall at eye height (roughly centered on the room axis).
3. Corner posts on all four corners + a stone-look base skirting around
   the room.
4. Chimney: a small box through the back roof slope so the outside silhouette
   breaks the plain gable.

## Verification

1. Update/add tests in `test_viewer_interior.py`: shelter factor 0.62
   (5.4*0.62 ≈ 3.35), door gap 0.95 + lintel, windows present, chimney
   present, interior spec still 5.4×4.4. 50-test viewer grouping green.
2. `node --check`; local renders east/west (interior + settlement exterior
   at 1600×900 and 900×800), read with own vision: distinct cabins
   outside, windowed cabin inside, zero page errors.
3. Deploy, re-pin the alias, live probe: same reads, zero page errors.
   `git diff --check`, CRLF 0, unique phase IDs.

## Out of scope

No backend, cognition, prompt, canonical, fauna, viewer-data or
agent-reachable change. Interior room footprint, camera, hide logic and
all other modes stay. Phase chain: 10PE (spec) → 10PF (metadata sync) →
10PG (implementation candidate).
