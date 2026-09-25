# West Pair Habitat — Design Document

**Status:** DESIGN DOCUMENT — no canonical data change is authorized by it
**Companion to:** 10JC (world-scale generation), the world-content side
branch, and GLM's parallel runtime parameterization work
**Prepared from:** canonical true map state at tick 338+ (post
world-content deployment; 80,000 tiles, 58 named regions, 289 landmarks)

---

## 1. Placement decision

### Coordinates: (49,49), (50,49), (51,49) on continent B

The chosen row sits on a **coastal bluff in The Southeastern Marches**,
directly above the authored Dawn Isle cluster. This is not an invention —
it is the strongest natural habitat site on the continent, discovered by
probing the actual terrain:

```text
            x=48        x=49        x=50        x=51        x=52
y=47..48    hill        hill        hill        hill        hill      (bluff top)
y=49        hill       [ADAM]      [CENTER]     [EVE]       hill      <-- habitat row
y=50     (hidden)      (hidden)  DAWN COVE   grassland    hill       <-- authored Dawn Isle
y=51                     forest (authored)   hill         forest     <-- coastal forest
y=52                WEST CLIFFS (hill, authored)
y=53                WEST CLIFFS (mountain, Seagull's Rest + MST_WEST_LIGHT)
```

Why this is the right ground:

1. **It mirrors the East habitat structurally.** Three adjacent walkable
   tiles in a row, with the shared tile in the middle and bigger
   geography one step away. The East pair's home row is (-1,-1)..(1,-1)
   above the Origin Valley; the West pair's home row is above the Dawn
   Cove coast.
2. **It mirrors but does not copy.** The East pair woke in a temperate
   valley with a river. The West pair wakes on a warm coast *above the
   sea*. Adam-on-B's first look is morning light on water. Different
   biome, different first sensory fact: salt, not loam.
3. **The doors already exist topologically.** The 10JE generator wired
   `cont_b_gen_50_49 <-> cont_b_origin_000` and
   `cont_b_gen_51_49 <-> cont_b_origin_001` when it laid the walk lattice.
   Substituting the habitat tiles into those coordinates preserves the
   door graph — the retrofit rewires edge endpoints, it does not cut
   them.
4. **Coherent story geometry.** The West Cliffs authored pair
   ((48,52)-(48,53)) lies a short diagonal southwest — and the far
   continent's mystery (`mst_west_light`, The Lantern of the West) sits
   on (48,53), six Manhattan steps from the West shared center. The
   East pair's mystery sits 4 steps from their center. Symmetric
   narrative distance.

---

## 2. Starting habitat declaration

### Tile additions (3 tiles, retrofit-replacing generated tiles)

These three entries REPLACE the generated tiles at the same coordinates
(`cont_b_gen_49_49`, `cont_b_gen_50_49`, `cont_b_gen_51_49` are removed
from the map; their incident edges are retargeted to the new IDs — see
section 5).

```json
{
  "tile_id": "west-start-adam",
  "continent_id": "cont_b",
  "region_id": "cont_b_dawn_bluff_habitat",
  "coordinates": {"x": 49, "y": 49},
  "terrain": "grassland",
  "biome": "warm_coast",
  "elevation": 0.559,
  "water": null,
  "resources": [],
  "hazards": [],
  "landmark_ids": [],
  "blocks_travel": false
}
```

```json
{
  "tile_id": "west-shared-center",
  "continent_id": "cont_b",
  "region_id": "cont_b_dawn_bluff_habitat",
  "coordinates": {"x": 50, "y": 49},
  "terrain": "grassland",
  "biome": "warm_coast",
  "elevation": 0.587,
  "water": null,
  "resources": [],
  "hazards": [],
  "landmark_ids": [],
  "blocks_travel": false
}
```

```json
{
  "tile_id": "west-start-eve",
  "continent_id": "cont_b",
  "region_id": "cont_b_dawn_bluff_habitat",
  "coordinates": {"x": 51, "y": 49},
  "terrain": "grassland",
  "biome": "warm_coast",
  "elevation": 0.611,
  "water": null,
  "resources": [],
  "hazards": [],
  "landmark_ids": [],
  "blocks_travel": false
}
```

Naming conventions hold: `public-start-adam` ↔ `west-start-adam`; the
region `cont_a_first_pair_habitat` ↔ new `cont_b_dawn_bluff_habitat`
(region record below). Elevations carry the real terrain's slope upward
west-to-east, matching the underlying generated hill heights
(0.557 / 0.585 / 0.612 adjusted to grassland-appropriate values within a
few hundredths). Terrain changes from `hill` to `grassland` are the one
authored divergence from the generated ground: a grassy terrace on the
bluff — the kind of sheltered shelf that reads as "a place to wake up."

### Region addition

```json
{
  "region_id": "cont_b_dawn_bluff_habitat",
  "continent_id": "cont_b",
  "name": "Dawn Bluff Habitat"
}
```

### Interior edges (bidirectional, mode walk)

```json
{"from_tile_id": "west-start-adam",   "to_tile_id": "west-shared-center", "mode": "walk"}
{"from_tile_id": "west-shared-center", "to_tile_id": "west-start-adam",   "mode": "walk"}
{"from_tile_id": "west-shared-center", "to_tile_id": "west-start-eve",    "mode": "walk"}
{"from_tile_id": "west-start-eve",    "to_tile_id": "west-shared-center", "mode": "walk"}
```

### Door edges (bidirectional, return-safe, to authored geography)

```json
{"from_tile_id": "west-shared-center", "to_tile_id": "cont_b_origin_000", "mode": "walk"}
{"from_tile_id": "cont_b_origin_000", "to_tile_id": "west-shared-center", "mode": "walk"}
```

```json
{"from_tile_id": "west-start-eve", "to_tile_id": "cont_b_origin_001", "mode": "walk"}
{"from_tile_id": "cont_b_origin_001", "to_tile_id": "west-start-eve", "mode": "walk"}
```

Door A (center to `cont_b_origin_000`, the Dawn Cove coast) mirrors the
East pair's door to the river valley: it is the "first wonder" step.
Door B (Eve's start to the grassland) mirrors the East door to the oak
forest. Because the generated map already carries these endpoints'
adjacency, the retrofit preserves the lattice's symmetry.

### Visible landmarks at spawn (radius 1, fog rules as live)

From `west-shared-center`, tick 1, before any movement:

- the habitat row (3 tiles)
- `cont_b_origin_000` — coast tile, sea water, landmark
  **lm_dawn_cove**: *"A quiet curve of coast where the sun first touches
  the shore."*

That second line is doing narrative work: the Dawn Cove's authored
description is a *sunrise* landmark. The West pair's first visible
wonder is literally the place where the sun arrives on their continent.
East got a river that whispers; West gets a shore that dawns.

### Nearby points of interest (1–4 tiles)

| Place | Distance from center | What it is |
| --- | --- | --- |
| Dawn Cove (lm_dawn_cove) | 1 | Authored coast landmark; first wonder |
| Coastal forest (cont_b_origin_002, (50,51)) | 2 | Authored forest tile; their "oak forest" analog |
| Foam Teeth (lm_south_rocks, (53,50)) | 4 | Sharp rocks at low tide |
| Seagull's Rest (lm_west_ledge, (48,53)) | 6 | Cliff ledge over the western sea |
| **The Lantern of the West** (mst_west_light, (48,53)) | 6 | Continent B's mystery — theirs to earn |

---

## 3. Starting context — what the West pair sees when they wake

Tick 1, `west-start-adam`, fog radius 1, clear conditions. Adam-on-B sees:

- three tiles of grass-and-salt meadow on a bluff, rolling west to east;
- the shared center one step east, and the sea-sound coming from the
  south;
- NO immediate door tile in his first view (his nearest authored ground
  is diagonal) — his first heartbeat curiosity points east, toward the
  center, and south, toward the sound.

Eve's first view (`west-start-eve`): the center one step west and —
because `cont_b_origin_001` (grassland, warm coast) is directly south and
visible — the edge of the Dawn Isle meadow below the bluff.

Neither sees the cove on heartbeat 1; the center holder sees it at
heartbeat 2. The first day's negotiation is thereby *shaped* by geography:
whoever holds center first sees the sea first and reports it. That is a
different first conversation than the East pair had (whose world was
symmetric and empty), and it will produce a different civilization
texture — reconnaissance hierarchy, not just symmetric greeting.

The nearest "walk to something interesting" is Dawn Cove (1 step from
center). The nearest *quest-scale* geography is the West Cliffs mystery,
6 steps away — within reach in their first week of heartbeats, exactly
when the mystery reveal mechanic (companion spec) could fire for the
first time on either continent.

---

## 4. Eventual contact geography

### Honest structural answer

Continents A and B are **separate graphs**. `travel_edges` never cross
`continent_id`; fog visibility is computed per-continent
(`get_visible_tile_ids` filters on `continent_id`). The ocean frame is
real and blocked on both. Today, the two pairs are unreachable to each
other by any legal move, at any distance, forever. This is the correct
state for the freeze/catch-up era: two clean parallel civilizations, one
planet, no leakage.

### Where contact would eventually come from

If and when a future phase authors a crossing, the geometry candidates:

1. **A southern strait (recommended future design).** Continent A's
   habitat sits at y=-1; continent B's at y=49. Aligning the narrative
   latitudes for a crossing is simplest along a southern band: an island
   chain / chain of coast tiles ("reef steps") bridging the two frames at
   transit distance. Each "stepping stone" tile would be a `coast` tile
   with `blocks_travel=false` and authored edges; 5–10 stepping tiles
   make an uncrossable-without-commitment but real route.
2. **Boats (cleaner, later).** `TravelEdge.mode` already supports
   non-walk values; the schema has `locked_by`. Sea travel as a
   capability both pairs must build toward is the most honest epic gate:
   contact happens when *either* civilization invents watercraft, not
   because geography allowed a shortcut.
3. **Shared mystery resonance (most poetic).** Each continent holds one
   authored mystery that fires on repeated presence. If both are revealed
   and their descriptions answer one another (the Singing Stone hears
   something; the Lantern answers something), the first "contact" is
   not a person — it is two wonders noticing each other, and the pairs
   having to explain that to each other later.

### Distance math (the number the runtime plan asked for)

Because the graphs are disjoint, literal distance is ∞. In the proposed
southern-strait build:

| Leg | Tiles (approx) |
| --- | --- |
| East habitat (0,-1) to A's east/south rim | ~100 |
| Strait chain (authored) | ~10–20 |
| B's rim to West habitat (50,49) | ~150 on the long arc, fewer on a short coast-hop |
| **Total one-way walk, 1 edge/heartbeat** | **~260–270+** |

At the runtime's maximum of one edge per heartbeat, a direct,
never-distracted agent could cross in under 300 heartbeats. Real agents
with goals, patrols, and conversations would take many times that. This
is right: contact between worlds should be an *expedition*, not a week.

Expected first contact, realistically: not physical. The first sign will
be asymmetrical evidence — the far shore's mystery behavior, or a
structure one pair finds that neither remembers building (once
agent-created landmarks are projected into geography, 10JC §7/§16.6
territory). "Smoke from a fire" first; a face much later.

---

## 5. Deployment mechanics (for the authorized retrofit phase)

This section defines the exact mutation for when a retrofit is
separately authorized. This document authorizes none of it.

1. **Remove** tile records for `cont_b_gen_49_49`, `cont_b_gen_50_49`,
   `cont_b_gen_51_49` (they are replaced, not overlaid — one tile per
   coordinate).
2. **Insert** the three habitat tile records and the
   `cont_b_dawn_bluff_habitat` region record.
3. **Retarget edges:** every directed edge referencing a removed tile id
   is rewritten to its replacement (6 external neighbors across the 3
   tiles, 12 directed edges; plus the two door pairs in section 2 which
   the generated lattice already implies).
4. **Retarget or retire resources:** the top-level resource record
   `res_cont_b_gen_51_49_stone` (stone ×2) references a removed tile.
   Recommended: retarget to `west-start-eve` (keep the frugal stone
   vein; the West pair finds stone on their ground, like the East pair
   found fruit on theirs). Retiring it is also acceptable.
5. **Validate:** `validate_true_map` must pass; the embed gate (all
   other records byte-exact) applies exactly as in the content deploy
   (``deploy_world_content.py``'s gate is the model).
6. **Fog/known maps:** no East pair state is read or written. West known
   maps are created fresh by the runtime at activation, seeded from
   genuine history per 10IZ §5 — which for West means empty-at-birth,
   and honestly so.

### East-pair safety invariants for that phase

- all 80,000-3 untouched tiles remain byte-exact, including every East
  landmark, region name, resource, edge, and the meeting-stone
  projection;
- `mst_east_echo` and `mst_west_light` records unchanged;
- the seven authored continent-B tiles unchanged;
- East canonical store untouched (they are frozen mid-history; nothing
  about their 338-tick civilization is re-read, re-derived, or edited).

---

## 6. Why this habitat is worth living in

The East pair's story began with symmetry and emptiness — two equal
starts, a bare center they filled themselves with a stone.

The West pair's story begins above the sea, with the sun arriving at a
cove one step away, a forest behind it, sharp rocks down the shore, a
lantern flashing (someday) from a cliff they can see the shape of by
week one. Their frontier arcs south and west; the wide tame bluff opens
north behind them. Their first disagreements will be about the water:
follow it, avoid it, name it.

The East pair had a river and an ancient oak. The West pair gets a dawn
shore, a ledge of gulls, and a light that waits on the horizon and will
not explain itself.

Good ground to be born on.
