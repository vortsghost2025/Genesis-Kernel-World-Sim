# Objects are landmarks — sightline extension

**One change.** A tile carrying a public object is visible from Chebyshev
distance 2 instead of the normal radius-1 Manhattan disc. Type-blind:
every object is a landmark, the same physics the wall unlock already
applies to rafts and campfires.

---

## 1. Why

West Eve built 90 objects across every terrain and material. None of them
changed anything about the world. She asked the operator what they were
for; the honest answer was "nothing." She stopped building — not because
she was told to, but because the record never contradicted the conclusion
that building was meaningless.

Meanwhile the wall unlock already gives objects meaning in exactly one
place: a campfire by a thicket opens the thicket. The physics of
"standing things are visible" is already in the world's vocabulary. This
extends it to the one thing every object already does by standing there:
**it makes the tile legible from farther away.**

The rule is deliberately type-blind. Matching on "cairn" or "landmark"
would privilege a vocabulary; the wall unlock's type-matching exists
because it gates travel. This does not gate anything — it extends
*knowledge*, and knowledge does not care what the thing is called.

## 2. The rule

From an observer at `(x, y)`, the normal visible set is the Manhattan
disc of radius 1: self, north, south, east, west. If any tile within
**Chebyshev distance 2** — the 5×5 square — carries a public object on
the observer's continent, that tile joins the visible set with its full
details: terrain, biome, resources, hazards, water.

The extended tiles go through the same projection as normal ones: they
appear in `visible_tiles` and `visible_tile_details`, and they merge into
the agent's known map like any other observation.

## 3. What this gives them

- **Every object Eve built has a reason to exist**: a storage at a
  crossroads tells both agents that tile's terrain without walking there.
- **Building near someone becomes socially legible**: a shared cairn
  extends both agents' knowledge of the area around it.
- **The wall corridor becomes a building project**: Adam walked the
  western shore and mapped it step by step; a line of cairns would make
  the route visible to Eve from her own survey line.

## 4. Deliberately NOT here

- No type matching, no vocabulary privileges, no "special" objects.
- No range beyond 2 — the extension is a boundary, not a broadcast.
- No new action, no prompt slot, no instruction. The world carries the
  fact; the agents decide what to do with it.
