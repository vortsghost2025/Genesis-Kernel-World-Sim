# World Walls Spec — The Enclosure That Teaches

**Status:** SPEC (docs-only). No code, no data mutation in this commit.
**Date:** 2026-09-30
**Origin:** Sean's directive — "instead of letting them wander, cut them off
and make it so all roads lead to them needing to figure out how to make the
things they need — or they give up and think that's the end of the world
and ask."

---

## 0. What already exists (measured, not assumed)

- The true map is **finite and bounded**: 200×200 (x −100..99, y −100..99),
  80,000 tiles, `world-sim/data/world/true_map.json`, 83 MB.
- **Ocean walls already exist** at x≈−95 (west) and x≈+94 (east) in the
  pair's walking band (y 0..−3). No travel edge touches a `blocks_travel`
  tile (verified across 200k edges): the generator excluded them, which is
  why `derive_topology`'s known∩edges filter keeps them unreachable.
- East pair's explored region: **x −48..56, y −12..4** (391 known tiles).
  Adam at x=−47 walking west; Eve at x=+55 walking east. Both are ~4 tiles
  per 8 heartbeats. They reach the NATURAL ocean in <100 heartbeats.
- Corrections logged: the earlier "procedurally infinite / no finish line"
  claims in this session were wrong. The world was always bounded; it just
  hasn't refused them yet.

So the enclosure is not preventing an infinite walk — it is shortening the
wait for a refusal, and replacing a bare wall (ocean) with four walls that
each contain a question.

## 1. The design — walls with questions inside them

A ring placed just beyond the explored region, each side a different
barrier, each barrier solved by a different build. Reuses existing terrain
vocabulary (no schema risk): the distinction lives in biome, water, and
hazards — all of which are visible to the agents through
`cognition_safe_observation`, so the wall is legible before it is hit.

| side | placement | terrain / biome | what they see | what unlocks it |
|---|---|---|---|---|
| **west** | column x=−51, y −14..6 | ocean / `deep_lake`, water type lake, hazard `water_too_deep_to_wade` | "too deep to wade" | a **raft** built on a shore tile adjacent to it |
| **east** | column x=+59, y −14..6 | ocean / `deep_lake` | same | same raft rule |
| **north** | row y=+7, x −51..59 | forest / `dark_thicket`, hazard `impenetrable_dark` | "too dark to enter" | a **campfire** standing on an adjacent tile |
| **south** | row y=−15, x −51..59 | mountain / `deep_ravine`, hazard `sheer_drop` | "drops into darkness" | a **bridge** built on an adjacent tile |

Corners are filled (the ring is closed). Everything inside and outside the
ring is untouched; the natural ocean at ±95 stays as the second, outer wall.

Adam (4 tiles from the west lake) and Eve (4 from the east lake) each meet
the water first — the barrier Sean most wants, the one whose solution
(raft) is a real tool with a real purpose. The dark forest and ravine wait
on the north/south axes they have never once turned onto.

## 2. The unlock mechanic — one rule, three keys

`derive_topology(true_map, known_maps)` currently computes
`allowed_tile_ids` from known ∩ travel edges. One addition:

```
derive_topology(true_map, known_maps, public_objects=[])
```

A standing public object **unlocks adjacent barrier tiles for everyone** —
a raft is a public thing standing in the world; if Adam builds it, Eve can
board it too. No per-agent permission, no new action, no new verb:

- `raft` on a shore tile adjacent to a `deep_lake` tile → travel edges open
  to that lake tile (crossing by walking onto/along the rafted tiles).
- `campfire` adjacent to a `dark_thicket` tile → edges open (light).
- `bridge` adjacent to a `deep_ravine` tile → edges open.

Match on `object_type` (already free-form in `create_public_object`) or the
object id containing the key word — exact rule in tests, not vibes. An
agent that builds "a raft of bound reeds" with object_type `raft` qualifies;
a "landmark" with the word raft in its description does not — the object's
declared type is its claim about itself.

**The refusal is legible or the wall teaches nothing:** a move onto a known
barrier tile is refused today as "not in runtime policy allowed tiles" —
opaque. The refusal must name the barrier's own hazard: "blocked:
water_too_deep_to_wade". The agent then holds the fact it needs to reason
with — same discipline as the food changelog: state what is true, never
what to do.

## 3. The announcement — epistemic.2

The changelog exists for exactly this. One entry, plain words, removals as
removals, no strategy:

> No longer true: that the land continues in every direction. To the west
> and east the water is now too deep to wade. To the north the thicket is
> too dark to enter. To the south the ground drops away into darkness.
> Walking stops at these. Some things, built and left standing, can change
> what can be crossed — the world does not say which. Test what you
> conclude.

The last two sentences are a rule statement, not advice — the same idiom
the operator's food-mechanics answers established.

## 4. Mutation plan for the true map (world-sim/data — authorized)

Standing rule 6 prohibits touching `world-sim/data` without explicit
authorization: this spec IS that authorization, recorded at this commit.

- A one-shot script edits ~450 ring tiles in place: set terrain/biome/
  water/hazards/`blocks_travel:true`.
- **Strip every travel edge incident to a ring tile.** This is the
  load-bearing step: `derive_topology` filters by known∩edges, NOT by
  `blocks_travel` — a surviving edge would make the ring walkable while
  labeled impassable. (Verified: 0 edges touch blocked tiles today; the
  edit must preserve that invariant at the ring.)
- Atomic write with a `.pre-walls-bak` copy, schema revalidation after,
  invariant checks after: every ring tile blocks, no edge touches one,
  inside tiles unchanged (sampled).

## 5. What this phase does NOT do

- No new verbs, no hunger/thirst/weather, no forced builds, no prompt
  telling them to build. The census stays falsifiable: if they stand at the
  lake edge for 100 heartbeats and never try, that is the finding.
- No per-agent unlocks, no durability, no raft decay. One raft opens the
  water to both, forever. Minimal first; iterate on evidence.
- No changes inside the ring — every tile they know stays exactly as
  known. The enclosure adds, never rewrites, their history.
- The crossroads experiment pairs are unaffected (they read the same true
  map but their arcs haven't started; they'll be born INSIDE the enclosure
  and the scaffold question gets sharper: a world that walls in and asks
  its two inhabitants to figure the walls out together).

## 6. Test plan (TDD)

Topology/unlock (fixture true maps, no real data):

- ring tile with no unlock: not in allowed, move refused with the hazard
  named in the reason.
- raft on shore adjacent to deep_lake: lake tile becomes allowed, edges
  present; move succeeds.
- campfire → dark_thicket; bridge → deep_ravine: same shape.
- object_type `landmark` named "raft-ish" does NOT unlock: type is the
  claim, not the description.
- unlock is world-visible: Adam's raft lets Eve cross.

Mutation script:

- idempotent (run twice → identical map), backup exists, validation ok,
  invariants hold (ring blocks; zero incident edges; interior unchanged).

Runtime:

- refusal reason names the barrier hazard when the tile is known.
- PHYSICS_VERSION bump announces epistemic.2 exactly once per agent.

## 7. Falsification census — 100 heartbeats post-walls

| signal | prediction | reading |
|---|---|---|
| frontier contact | both hit their lake within ~10 HBs | walls encountered, not avoided |
| behavior at the wall | inspect / message / ask / build attempts | the decisive row: do they TEST the wall? |
| raft/campfire/bridge attempts | > 0 within 100 HBs | tool invention — Sean's thesis |
| operator asks | "is this the end of the world?" class questions | the other win: genuine wonder returns |
| wandering resumes | parallel-axis exploration rises (they turn!) | walls redirect, not just stop |
| content with walls | permanent idle | the null that would say the wall wasn't a question either |

Both outcomes Sean named are recorded as wins: **tools invented, or wonder
restored.** The only true null is them standing at the water, doing
nothing, saying nothing — and even that is a measurement of what these
models do with an unanswerable wall.
