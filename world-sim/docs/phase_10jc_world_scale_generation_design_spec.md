# Phase 10JC — World-Scale Generation from Young-Earth Geography — Design Specification

**Status:** DESIGN SPECIFICATION ONLY (revision 2 — supersedes the 2026-09-21 noise-terrain draft)
**Phase:** 10JC
**Next metadata-sync phase:** 10JD
**Named implementation candidate:** 10JE
**Implementation authorization:** NOT GRANTED by this document
**Heartbeat authorization:** NONE — no heartbeat of any number is authorized by this document
**Commit / push authorization:** NONE
**Canonical-write authorization:** NONE

This document defines the smallest safe architecture for making the world
*the size of the world to its inhabitants*: a true map large enough that no
living agent can ever reach its edge, while every existing authored tile,
landmark, mystery, and door remains byte-preserved.

Revision 2 records the operator design decision of 2026-09-21: the world is
not synthetic noise. **The world is Earth, stripped back to its dawn** —
real continents, real oceans, real mountain spines and river valleys,
downsampled into the tile grid, with every trace of civilization absent.
The first pair wakes on a young Earth and names it themselves.

Scale target (operator-approved 2026-09-21): the whole Earth at roughly one
degree per tile — between approximately 65,000 and 80,000 tiles total,
which is exactly the experiential "size of the world" for a pair who move
one edge per heartbeat and see one tile deep.

The design follows the append-oriented continuity rule established by 10IZ:
old content stays valid and byte-exact, existing IDs remain stable, and new
geography appears only through an explicit, operator-authorized migration
of canonical data.

---

## 0. Phase identifier determination and relationship to 10IZ/10JB

### Phase identifier

`10JC` is the correct identifier for this design phase.

Phase-index inspection (2026-09-21) confirms:

- `10IZ` (spec) and `10JA` (sync) are Done.
- `10JB` is named as the 10IZ implementation candidate; it has no
  phase-index row and is NOT started and NOT authorized.
- `10JC` is the first free identifier after `10JB`.

Therefore the chains are:

- 10IZ -> 10JA -> 10JB  (fog integration of the living first pair)
- 10JC -> 10JD -> 10JE  (world-scale generation, this document)

### What 10JC is and is not

10JC designs how a *very large true map* is produced as a canonical data
artifact from real Earth geography. It does not change runtime behavior,
observation rules, movement rules, the action vocabulary, or any
living-civilization state.

10IZ defines how the living first pair connects to the existing true map.
10JC defines how the true map becomes world-sized. The two are independent
designs with one shared artifact: `data/world/true_map.json`.

### Inspection-question cross-map

| Question | Answered in |
| --- | --- |
| 1. How big must the world be to be "the size of the world to them"? | section 1 |
| 2. What geography is the world made of? | section 5 |
| 3. How are the existing 14 tiles, 6 landmarks, 2 mysteries, and the 10IZ habitat preserved? | sections 4, 5.7 |
| 4. How do visibility and movement behave at scale? | sections 6, 11 |
| 5. What is generated, what is sampled, what is authored? | sections 5, 7, 8 |
| 6. How is determinism and rebuildability proven with a real-world dataset? | section 10 |
| 7. What does this cost at runtime? | section 11 |
| 8. What are the ordering constraints relative to 10JB? | section 12 |
| 9. Which content domains remain intentionally unresolved? | section 16 |
| 10. How do failure and rollback work? | section 14 |

---

# 1. DESIGN GOAL AND CURRENT BASELINE

## 1.1 The experiential target

The first pair explores at a maximum of one travel edge per heartbeat and
sees with a fog radius of approximately one tile. Their per-agent known
maps store only what they have personally observed, so agent-side state
stays small no matter how large the true world is. That property is
guaranteed by the Phase-7 fog architecture and is the reason scale is
cheap for the inhabitants.

"World-sized" is therefore defined experientially, not absolutely:

> The world is large enough that at the maximum exploration rate, across
> every heartbeat the civilization will ever run, the pair can never visit,
> see, or fully map the whole of it, and every horizon implies more world
> beyond it.

## 1.2 Scale arithmetic — and the terrestrial coincidence

At one new tile per heartbeat per agent, a pair combining their knowledge
gains at most on the order of 2 new tiles of map per heartbeat. Even an
unrealistically long-lived civilization of ten thousand heartbeats would
know on the order of tens of thousands of tiles.

The Earth at one-degree cells is a grid of approximately 360 x 180 =
64,800 cells; at a slightly finer cell it reaches roughly 80,000. That is
the same order as the approved experiential target. In other words:

**A tile-for-degree map of the real Earth is, by sheer coincidence, almost
exactly "the size of the world" to a pair who will never exceed tens of
thousands of tiles of lifetime travel.**

This coincidence is what makes the young-Earth design practical instead of
merely poetic.

## 1.3 Operator-approved scale target

Approved 2026-09-21:

- the whole Earth, one grid cell per degree-class tile;
- final cell size fixed during 10JE so the total lands in the approved
  65,000-80,000 tile range;
- two canonical continents corresponding to two real landmasses (see
  section 5.5).

## 1.4 Current baseline

The existing canonical true map (inspected under 10IZ) contains:

- 2 continents;
- 6 regions;
- 14 tiles;
- 6 landmarks;
- 2 mysteries;
- 12 directed travel edges;
- empty top-level `resources` and `hazards` arrays.

The living first-pair civilization (12 heartbeats, tick 12, both agents at
`public-shared-center`, meeting stone standing) does not consume the true
map today; that connection is the 10IZ/10JB chain, not this one.

Nothing in this document authorizes changing any of the above.

---

# 2. AUTHORITY MODEL (unchanged)

Consistent with 10IZ section 2.1:

- **The true map is the geography authority.** Continents, regions,
  coordinates, terrain, biomes, water, travel edges, landmarks, and later
  resources, hazards, and mysteries.
- **The living first-pair store is the civilization authority.** Identity,
  positions, memory, messages, goals, questions, public objects, heartbeat
  history, policies, known maps, evidence, provenance.
- **The generator is neither.** The generator defined here is a build-time
  tool that samples a real-world dataset into geography. It never runs
  inside a heartbeat, never runs at runtime, never holds civilization
  authority, and never writes canonical data without a separately
  authorized migration.

---

# 3. GENERATOR-AS-BUILD-TOOL ARCHITECTURE

## 3.1 Core decision

World-scale content is produced by a deterministic generator run in
scratch, whose output is an ordinary static `true_map.json` of exactly the
shape the existing schema, validator, and fog engine already consume.

Consequences:

- the true-map schema does not change;
- the Python validator (`validate_true_map`) does not change;
- the fog engine does not change;
- the runtime does not change;
- 10JB does not change;
- governance does not change: validate, hash, one authorized write.

The world is *sampled at authoring time and static at runtime*. No
procedural sampling, tessellation, or dataset access exists in any runtime
path.

## 3.2 Why real geography instead of synthetic noise

Revision 1 of this design proposed seeded value-noise terrain. The operator
replaced it with real Earth geography, which is strictly better here:

1. **Coherence is free.** Real orogeny, drainage basins, desert belts,
   and coastlines are already consistent; no noise-tuning effort can match
   geology.
2. **The ocean question dissolves.** Revision 1 needed an artificial
   impassable ocean frame to terminate rectangular continents. A real
   Earth needs no frame: the oceans simply are there, and the map edge is
   the real edge of the map projection.
3. **Narrative truth.** This repository is called Genesis. The pair's
   world being the young Earth — every landmark a place that really
   exists, waiting to be named by the first people — is the strongest
   possible fit to the canon.
4. **Mysteries and landmarks get a real backbone.** Great rifts, calderas,
   falls, capes, and ranges are sampled from reality, then named by hand.
5. **The far continent problem solves itself.** Continent B is a real
   ocean away; unreachable by walking, visible on no horizon, present in
   every direction the sea faces.

## 3.3 Generator guarantees (required of 10JE)

1. **Deterministic:** identical inputs (dataset revision, generation seed,
   input map, authored registries, generator version) produce a
   byte-identical output file.
2. **Pure:** reads only its declared inputs; writes only its declared
   output artifact; no network at generation time (the dataset is a
   pre-fetched, hash-pinned local fixture), no provider, no
   clock-dependence, no environment dependence, no randomness outside its
   seeded algorithm.
3. **Stdlib only at run time:** sampling, mapping, and validation use only
   the Python standard library. Any dataset decoding must also be stdlib
   or the dataset must be pre-converted to a stdlib-readable form (plain
   JSON/CSV grids) in a separate, documented preparation step.
4. **Scratch-only:** generation targets scratch/fixture paths only;
   canonical application is a separate authorized step.
5. **Self-validating:** the run ends by validating its own output with the
   existing validator plus the Earth-specific invariants of section 15;
   an invalid artifact is a failed run, not a repairable one.

---

# 4. EMBED, NEVER REGENERATE: PRESERVATION OF THE EXISTING WORLD

## 4.1 The embed rule

The generator's first input is the canonical true map as it exists at
generation time. Every existing record is carried into the output
**byte-exact**:

- both continents and all 6 regions;
- all 14 existing tiles with their exact IDs, coordinates, terrain, biomes,
  elevation, water, resource tags, hazard tags, landmark references, and
  `blocks_travel` values;
- all 6 existing landmarks with their hidden names and descriptions;
- both existing mysteries with their reveal thresholds;
- all 12 existing travel edges;
- and, once the 10JB chain has landed its M1 true-map extension, the
  habitat region `cont_a_first_pair_habitat`, the three preserved habitat
  tiles (`public-start-adam`, `public-shared-center`, `public-start-eve`),
  the meeting-stone landmark projection `lm_meeting_stone_center`, and the
  habitat edges and 10IZ door edges.

After 10JB M1 this is the 17-tile world (14 Phase-7 + 3 habitat). The
generator never re-derives, re-randomizes, renames, or repositions any
embedded record. Sampled Earth data fills only the coordinates the
existing world does not occupy.

## 4.2 The heartland override

Where a preserved tile's coordinates land on the Earth grid, the preserved
record wins absolutely. If the sampled Earth data says that cell is ocean
or mountain, the embedded tile still stands exactly as authored — the
geography bends around the heartland, never through it. Sampled terrain
applies only to cells with no existing record.

## 4.3 Collision is failure

No generated tile may share a coordinate with an existing tile on the same
continent. No generated landmark, mystery, region, or edge may reuse an
existing ID or duplicate an existing edge. Any collision aborts
generation. There is no rename path.

## 4.4 History untouched

This phase never touches heartbeat history, memory, goals, questions,
messages, identity, public objects, runtime policy records, known maps,
dormant `data/agents/*` files, or any living-store state. Geography
expansion cannot rewrite lived history.

---

# 5. THE YOUNG-EARTH GEOGRAPHY MODEL

## 5.1 Source data

Terrain is sampled from real Earth data, not synthesized:

- a public-domain global elevation grid (NOAA ETOPO-class) provides land
  mask, elevation, and ocean mask;
- a public-domain physical-geography source (Natural Earth class) provides
  coastline, river, and lake features.

Hard requirements on any dataset:

- public-domain or CC0-equivalent license only; the license text and
  source URL are recorded in the generation manifest;
- the dataset file is fetched once, pinned by SHA-256, stored as a
  scratch fixture, and that hash is recorded in the manifest;
- regeneration against a different dataset revision is a different
  generation run with a different manifest.

Exact dataset selection and version is a 10JE implementation decision,
recorded as evidence. Dataset decoding must be stdlib-readable (plain
JSON/CSV grids); any format conversion happens in a separate, documented
preparation step, never inside the generator's deterministic core.

## 5.2 The Earth grid

One tile per Earth grid cell, on a longitude/latitude-style integer grid:

```text
x in [-180, 180)     (longitude cell index, signed)
y in [-90, 90)       (latitude cell index, signed)
```

At 1.0-degree cells this is 360 x 180 = 64,800 cells; at 0.9-degree cells
it is 80,000. The final cell size is fixed during 10JE so the total lands
inside the approved 65,000-80,000 tile budget, and is recorded in the
manifest.

The signed-index layout is chosen because every existing coordinate falls
inside it without renumbering:

- habitat row at (-1,-1), (0,-1), (1,-1);
- existing `cont_a` tiles at x in [-1, 3], y in [-1, 2];
- existing `cont_b` tiles at x in [48, 53], y in [50, 53].

## 5.3 The anchor

The grid's real-world anchor — which real longitude/latitude cell occupies
coordinate (0,0) — is chosen so that the habitat row and its neighboring
existing `cont_a` tiles land on land inside the East African Rift region:
the canonical home country. The default anchor places:

- `cont_a` on the African landmass — the home continent;
- `cont_b`, whose existing tiles sit at x in [48, 53], across the ocean
  eastward on the next continental margin the anchor puts them on — the
  far shore. The exact landmass correspondence is recorded as 10JE
  evidence alongside the anchor choice, not promised here.

Anchor selection at 10JE must include evidence that all preserved `cont_a`
coordinates land on land, and must state where preserved `cont_b`
coordinates land.

## 5.4 Land, ocean, and ice classification

Each cell is classified from the datasets:

- **Ocean cells:** terrain `ocean`, biome `open_sea`,
  `water: {"type": "sea", "drinkable": false}`, `blocks_travel: true`,
  no travel edges.
- **Ice cells** (ice sheets and permanent sea ice, from the elevation/
  feature data): terrain `ice`, biome `ice_sheet`, `blocks_travel: true`,
  no travel edges. The poles are the real edge of the walkable world.
- **Land cells:** terrain and biome from real elevation, latitude band,
  and feature data, per the mapping table in section 5.6. Land elevation
  is stored as the real elevation normalized to [0, 1] against Earth's
  maximum (~8.8 km), so elevation becomes genuinely meaningful rather than
  decorative.

## 5.5 Two canonical continents over a real Earth

The schema requires every tile to name a continent, and fog visibility is
per-continent. The generated world therefore maps the Earth's landmasses
onto exactly the two canonical continent IDs:

- `cont_a` covers the home landmass and its hemisphere-adjacent islands
  and margins;
- `cont_b` covers the far landmass and its hemisphere-adjacent islands and
  margins.

The deterministic partition rule (nearest canonical landmass per cell,
with a fixed tie-break) is fixed at 10JE and recorded in the manifest.
Ocean cells are assigned to the continent of their nearest land cell under
the same rule, so that radius visibility across coastal water behaves
uniformly. This coarseness is deliberate canon simplification: the pair
will never perceive continent IDs; they will perceive land and sea.

## 5.6 Vocabulary extensions (requires operator confirmation, section 18)

Existing terrain values remain: `grassland, forest, hill, mountain,
coast`. The Earth mapping adds these terrain values:

```text
ocean      (blocked sea)
ice        (blocked ice)
desert     (arid belts and dune seas)
savanna    (tropical grassland bands)
jungle     (equatorial rainforest)
tundra     (subpolar barrens)
```

and these biome values:

```text
open_sea, ice_sheet, arid_desert, savanna, rainforest, taiga,
tundra, mediterranean
```

The mapping table (dataset class -> terrain/biome assignment) is fixed at
10JE and recorded in the manifest.

## 5.7 Regions over real geography

The 6 existing regions keep their exact IDs and membership over existing
tiles. Generated tiles receive generated region IDs drawn from major real
geographic provinces of their canonical continent (for example:
`cont_a_sahara_shield`, `cont_a_congo_basin`, `cont_a_rift_highlands`,
`cont_b_<far-shore province names>`). The generated region list is fixed
at 10JE from the anchor and partition evidence, validated for province
coherence, and recorded in the manifest. No existing region's membership
changes.

## 5.8 Inland water

Real rivers and lakes from the feature dataset mark tiles with
`water: {"type": "river" | "lake", "drinkable": true}`. River and
lake-shore tiles remain walkable by default; only the real dataset's
ocean/sea cells are `sea`-typed. Coasts keep terrain `coast` where a land
cell directly borders ocean.

---

# 6. TRAVEL EDGES ON THE EARTH GRID

## 6.1 Generation rule

For every pair of 4-neighbor (north/south/east/west) cells on the same
canonical continent where neither tile has `blocks_travel: true`, the
generator emits two directed edges (one per direction), `mode: "walk"`.
No diagonal edges are generated. No edge touches an ocean or ice tile.
Islands with no land neighbor receive no edges: they are unreachable until
sea travel exists, which is correct for a young Earth.

## 6.2 The seam and the poles

No edges cross the antimeridian seam (the x = -180 | 180 boundary). No
edges leave the grid at the poles. Both cuts run through ocean and ice,
so no walker is ever affected; the seam is recorded as a known,
deliberate discontinuity.

## 6.3 Preservation — including the existing long edges

The 12 existing edges and the 10IZ habitat/door edges are embedded
byte-exact. Inspection note: several existing edges span more than one
grid step (e.g. `cont_a_origin_001` (1,0) to `cont_a_east_000` (3,0); the
`cont_b` edges (51,50)->(53,50) and (50,51)->(48,52)). These authored
long edges remain valid as explicit records and are preserved; the
generated 4-neighbor grid additionally fills in the intermediate cells
and their adjacencies. The Phase-7 coordinate movement module
(`local_movement.py`) does not consult edge records, and the 10IZ
derived-topology model consumes edges explicitly — both remain satisfied.

## 6.4 Volume estimate

Two continental land grids plus surrounding shallows yield on the order of
300,000 directed edge records (fewer than a full rectangular grid since
ocean carries none). The exact count is recorded in the candidate
manifest.

## 6.5 Modes and locks

Only `mode: "walk"` is generated. `locked_by` remains unused. Sea
travel, fords, and passes are future authored capability content.

---

# 7. LANDMARKS

## 7.1 Preserved landmarks

All 6 existing landmarks are embedded byte-exact (hidden names and
descriptions included), and the meeting-stone projection
`lm_meeting_stone_center` is preserved exactly as the 10IZ chain defines
it.

## 7.2 Real-feature landmarks

Generated landmarks are sampled from real notable geography: highest
peaks of major ranges, great waterfalls, great lakes, calderas, canyons,
capes, rift escarpments, glaciers. The feature list is curated at 10JE
from the datasets and recorded in the manifest.

Existing landmark kinds remain: `river, tree, mountain_peak, cove,
rock_formation, cliff_ledge`. The Earth model requests these additional
kinds (section 18):

```text
waterfall, great_lake, crater, canyon, cape, glacier, rift_escarpment
```

Placement density stays rare: landmarks are exceptions, not texture.

## 7.3 Names and descriptions

Notable real features receive hand-written hidden names and descriptions
through the authored registry (the craft layer). Minor sampled features
receive generator-fallback names from seeded word lists. The pair's own
names for these places will live in their known maps, as before: on the
young Earth, their names are the first names anything has ever had.

## 7.4 Authored override registry

A hand-written registry pins landmarks at chosen coordinates with chosen
names and descriptions. Merge is deterministic: a registry pin suppresses
any generated landmark at its coordinate. Authored content wins;
generation fills everything else.

---

# 8. MYSTERIES

## 8.1 Authored only

The generator never creates mysteries. Mysteries enter the world only
through the authored registry.

## 8.2 Preservation

The 2 existing mysteries (`mst_east_echo`, `mst_west_light`, each with
reveal threshold 3) are embedded byte-exact.

## 8.3 Hidden until a reveal mechanic exists

No mystery-reveal mechanic exists in the engine, and the fog observation
path does not read the `mysteries` array. Generated and authored mysteries
remain invisible until a future dedicated phase implements reveal
semantics. World-scale generation must never leak mystery existence into
any observation, prompt, or cognition-path fixture.

---

# 9. RESOURCES AND HAZARDS

Consistent with the current canonical state and 10IZ section 14:

- the top-level `resources` and `hazards` arrays remain empty;
- tile-level tags use only the existing vocabulary:

```text
resources: fruit, reeds, wood, stone, shells, driftwood
hazards:   steep_slope, unstable_rocks, dense_thorns, strong_tide
```

- tags are assigned coherently from the mapped biome (wood in forest,
  jungle, and taiga; stone in hills and mountains; fruit in savanna and
  warm biomes; shells and driftwood on coasts; thorns in dense woodland;
  unstable rocks on mountains; strong tides on exposed coasts);
- no economy, gathering, depletion, or hazard-effect mechanic is
  introduced.

---

# 10. DETERMINISM, REBUILDABILITY, AND PROVENANCE

## 10.1 Byte-identical rebuild

The same pinned dataset + the same generation seed + the same input map +
the same registries + the same generator version must produce a
byte-identical output file. This is a test, executed twice in scratch
with hash comparison.

## 10.2 Provenance location

Generator provenance (dataset source URL, license, SHA-256 pin, cell
size, anchor, generation seed, generator version, input-map hash,
output-map hash, tile/edge/landmark/region counts, generation timestamp)
is recorded in the migration manifest and evidence bundle.

Provenance is **not** written into `true_map.json`: the schema's top
level is closed (`additionalProperties: false`) and this design leaves
the schema untouched. The world file stays pure geography; lineage lives
in evidence.

## 10.3 Seed canon

The input map's existing `seed` field is retained unchanged
(recommendation; see section 18). The generation seed is separate and
lives only in the manifest.

---

# 11. SIZE AND PERFORMANCE ASSESSMENT

## 11.1 Artifact size estimate

Pretty-printed (`indent=2`, matching existing canonical write style):

- tiles: ~65,000-80,000 records of roughly 250-350 bytes each;
- travel edges: on the order of 300,000 directed records;
- landmarks, regions, continents, mysteries: negligible.

Expected artifact size: approximately 50-60 MB.

## 11.2 Runtime cost analysis

- JSON parse of ~50-60 MB: on the order of 1-2 seconds;
- `validate_true_map` over the full artifact: single-digit seconds, run
  at generation and migration time;
- `get_visible_tile_ids` is an O(n) scan over one continent's tiles:
  tens of thousands of distance checks per observation, measured in tens
  of milliseconds in CPython.

Context: an authorized heartbeat already spends on the order of a hundred
seconds in provider cognition. A one-time ~1-2 second map load per
observation build is within the existing performance envelope of an
operator-gated, manually sequenced heartbeat pipeline.

## 11.3 Optional future optimizations (explicitly out of scope)

If measurement ever shows pain, each is a separate future phase with
identical behavior and its own tests:

- a per-continent coordinate spatial index making observation O(radius)
  instead of O(continent);
- compact (non-indented) canonical JSON or a normalized edge encoding;
- lazy/streaming load.

None is justified by current numbers.

---

# 12. RELATIONSHIP TO 10IZ / 10JB (ORDERING)

## 12.1 Independence of design, dependence of data

10JC changes no 10IZ decision. The two chains share one artifact
(`data/world/true_map.json`), so their *write ordering* matters even
though their designs are independent.

## 12.2 Recommended ordering

1. **10JB first.** Its M1 migration adds the habitat region, habitat
   tiles, meeting-stone projection, habitat edges, and door edges to the
   canonical true map, and its cutover connects the living pair to fog
   observation on the 17-tile world.
2. **10JD** sync for this spec (metadata only).
3. **10JE** generator implementation and scratch candidate artifact.
4. A separately authorized world-expansion migration applying the
   generated map.

Rationale: with 10JB first, the generator's input map already contains
the habitat and doors, so the embed rule (section 4) preserves them
automatically, and the pair walks the 17-tile designed world — the river,
the oak, the summit with its hidden echo — before the world becomes
planetary.

## 12.3 Tolerated alternative

If 10JE completes before 10JB M1, the generator input is the 14-tile map,
and the 10JB M1 migration would then target the expanded map instead of
the 14-tile map, with equal byte-preservation requirements. Legal, not
recommended: it doubles the review surface of 10JB M1.

## 12.4 Nothing here modifies 10JB scope

10JB remains bounded exactly as 10IZ section 13 defines it.

---

# 13. CONTINUITY INVARIANTS

Non-negotiable:

1. Every existing true-map record (2 continents, 6 regions, 14 tiles, 6
   landmarks, 2 mysteries, 12 edges, plus the 10IZ habitat extension once
   it exists) survives byte-exact into the generated map. The heartland
   override (section 4.2) is absolute.
2. No existing ID of any kind is reused, renamed, or repositioned.
3. No heartbeat is run by any part of this design; heartbeats 13 and
   beyond remain individually authorized.
4. The living first-pair store is never read by the generator and never
   modified by any generation run.
5. Dormant `data/agents/*` files remain dormant and untouched.
6. The schema (`schemas/fog_of_war/true_map.schema.json`) and the Python
   validator are unchanged.
7. The fog engine and all runtime code are unchanged.
8. No mystery, hidden landmark name, or any non-visible geography may
   appear in any agent-facing observation or prompt, before or after
   expansion.
9. The top-level `resources` and `hazards` arrays remain empty.
10. Ocean and ice tiles never receive travel edges; no edge crosses the
    antimeridian seam.
11. **Zero human artifacts.** The young Earth contains no roads, no
    cities, no ruins, no agriculture, no anthropic land classification.
    Any dataset class that encodes human modification is excluded by the
    mapping table. "Stripped back to the start" is an invariant, not a
    mood.
12. Generation is scratch-only; canonical application is a separate,
    operator-authorized migration with recorded before/after hashes.
13. Approving this specification authorizes no commit, push, migration,
    canonical write, or heartbeat.

---

# 14. FAILURE AND ROLLBACK

## 14.1 Generation failure

Any of the following aborts generation with a failed status and no
artifact:

- dataset hash mismatch against its pin;
- nondeterminism detected (two-run hash mismatch);
- self-validation errors (`validate_true_map` or section 15 invariants);
- any embed violation (missing or altered existing record);
- any ID or coordinate collision;
- any edge invariant violation (cross-continent, blocked-tile touch,
  seam crossing, asymmetric pair);
- malformed authored content registry;
- any human-artifact classification surviving the mapping.

Generation failures produce a diagnostic report only. Partial artifacts
are never promoted.

## 14.2 Migration failure

The later authorized migration applies the same abort discipline as 10IZ
M1: validate the candidate before replacing canonical data, record old
and new hashes, and abort before write if the diff includes anything
undeclared.

## 14.3 Rollback

Rollback of an applied expansion is never automatic. If authorized, it
restores the recorded pre-expansion map hash via compensating migration.
Because expansion is *additive around a byte-exact embed*, rollback
removes exactly the generated records and retains every embedded record.
No destructive repository operation is part of any rollback path.

---

# 15. TEST PLAN (for 10JE)

All tests run against scratch fixtures and scratch outputs only. No test
touches canonical data, providers, daemons, or networks.

1. **Dataset pin:** the recorded dataset SHA-256 matches the fixture
   actually consumed; mismatched input aborts.
2. **Determinism:** two runs, byte-identical output hash.
3. **Embed integrity:** property test that every record of a fixture
   input map appears byte-exact in the output, including the non-adjacent
   existing edges.
4. **Validator compliance:** output passes `validate_true_map`.
5. **Grid completeness:** every grid cell exists exactly once; no
   out-of-grid tiles; every coordinate within bounds.
6. **Classification:** ocean and ice tiles carry the required terrain,
   biome, water, and `blocks_travel` values and zero edges; land cells
   carry a mapped terrain/biome pair from the approved table; no
   human-artifact class survives.
7. **Anchor evidence:** all preserved `cont_a` coordinates land on land;
   the landing of preserved `cont_b` coordinates is recorded.
8. **Edge invariants:** 4-neighbor symmetry; no cross-continent edges;
   no blocked-tile edges; no seam crossings; preserved edges intact.
9. **Landmark coherence:** kinds match feature classes; IDs unique;
   registry pins suppress generated landmarks at pinned coordinates.
10. **Mystery containment:** output mysteries equal exactly the registry
    plus embedded set; observation-path tests confirm mysteries never
    surface.
11. **Vocabulary containment:** every terrain/biome/resource/hazard/
    landmark-kind value in the output is in the approved vocabulary.
12. **Performance budget:** measured parse, validation, and observation
    scan times on the full-size artifact, recorded as evidence.
13. **First-pair fog rehearsal:** using the 10IZ adapter design on a
    scratch expanded map, observation from `public-shared-center` with
    radius 1 yields exactly the expected visible set, with zero leakage
    beyond.
14. **Regression:** existing fog, movement, and contract suites pass
    unchanged against a fixture copy of the expanded map.

---

# 16. CONTENT DOMAINS INTENTIONALLY LEFT UNRESOLVED

Unchanged from 10IZ section 14, restated so scale smuggles nothing in:

1. **Resources/economy:** no gather, no inventory, no consumption.
2. **Hazard effects:** tags only; no damage, no mechanics beyond
   `blocks_travel`.
3. **Mystery reveal:** no reveal mechanic; threshold fields unread.
4. **Sea travel:** the oceans are real and uncrossed; boats/ports are a
   future authored capability (`request_capability` is the seam).
5. **Co-location rule:** shared-center-only rule is untouched.
6. **Per-agent movement authority:** 10IZ's union-of-known-maps default
   is unchanged.

## 16.1 The known gap: vast before dense

A young Earth is vast before it is dense. On day one after expansion the
pair would find real deserts, real mountains, real rivers — and no
economy, no hazard mechanics, and no revealed mysteries yet. This is
accepted honestly and is not a blocker: it matches the question the pair
actually asked ("is the world bigger?"), not a question about what to do
in it.

The follow-through is a named future phase: a **world-content seeding
phase** (authored resources, hazard meaning, mystery placement, and named
regions laid into the generated geography) to be designed after 10JE has
produced a candidate map to work against. That phase has its own
spec, sync, and implementation chain and is not part of 10JC-10JE.

---

# 17. FILES THAT WOULD CHANGE (inventory only, nothing authorized)

## 17.1 Under 10JE (implementation candidate), all scratch-first

```text
world-sim/scripts/worldgen/                     # new generator package (pure, stdlib)
world-sim/scripts/worldgen/datasets/            # pinned, hash-locked source fixtures (scratch)
world-sim/scripts/worldgen/content_registry.json  # authored pins (starts near-empty)
world-sim/tests/test_worldgen_*.py              # new tests
scratch output: generated candidate map + manifest (gitignored)
```

## 17.2 Under a separately authorized expansion migration

```text
world-sim/data/world/true_map.json              # replaced by validated candidate
migration manifest + evidence bundle            # recorded in canonical format
```

## 17.3 This phase

```text
world-sim/docs/phase_10jc_world_scale_generation_design_spec.md   # this document
```

The phase-index row for 10JC belongs to 10JD and is not part of this
phase.

---

# 18. DESIGN DECISIONS REQUIRING EXPLICIT OPERATOR CONFIRMATION BEFORE 10JE

1. **Young-Earth template:** the whole real Earth, stripped of all human
   trace, as the geography of the true map.
2. **Scale:** one tile per degree-class cell; final cell size fixed in
   10JE within the approved 65,000-80,000 tile budget.
3. **Anchor:** coordinate (0,0) placed so the preserved habitat row lands
   on land in the East African Rift region; `cont_b` existing-tile
   landing recorded as 10JE evidence rather than promised here.
4. **Oceans and ice:** blocked (`blocks_travel: true`), edgeless, real.
   No antimeridian crossing. Boats are a future capability.
5. **Vocabulary additions:** terrain values `ocean, ice, desert, savanna,
   jungle, tundra`; biome values `open_sea, ice_sheet, arid_desert,
   savanna, rainforest, taiga, tundra, mediterranean`; landmark kinds
   `waterfall, great_lake, crater, canyon, cape, glacier,
   rift_escarpment`.
6. **Datasets:** public-domain/CC0-class only, hash-pinned, license
   recorded in the manifest; exact sources selected at 10JE.
7. **Zero human artifacts** as a hard invariant (section 13.11).
8. **Mysteries authored-only**; generator never places one.
9. **Provenance in the manifest; schema untouched; map `seed` field
   unchanged.**
10. **Ordering:** 10JB lands before the world-expansion migration.
    ~50-60 MB canonical artifact accepted at current runtime cost.
11. **No heartbeats** bundled with generation or migration; the first
    heartbeat on the expanded map is a separate explicit authorization.

No choice above is implicit in this document.

---

# 19. ACCEPTANCE CRITERIA FOR THIS SPECIFICATION

Phase 10JC is complete when this document clearly establishes:

- the operator's experiential definition of "world-sized" and the
  approved whole-Earth scale;
- the young-Earth template: real geography, zero human artifacts, dawn
  of the world;
- the generator-as-build-tool architecture with a static canonical
  artifact and a hash-pinned public-domain dataset;
- byte-exact embedding of the entire existing world, including the 10IZ
  habitat once applied, with the heartland override absolute;
- the grid, anchor, classification, edge, region, landmark, mystery, and
  resource/hazard rules;
- determinism and rebuildability requirements;
- provenance-in-manifest with the schema untouched;
- measured performance expectations at ~50-60 MB;
- the ordering relationship to 10JB without modifying 10JB scope;
- continuity invariants, fail-closed generation, authorized migration,
  explicit rollback;
- the named post-10JE world-content seeding phase as the answer to
  "vast before dense";
- bounded 10JE scope with scratch-only discipline;
- no authorization of implementation, migration, commit, push, or any
  heartbeat.

---

# 20. STOP BOUNDARY

This document is the end of the 10JC design phase.

After writing and verifying this file:

- do not implement the generator;
- do not fetch or pin a dataset into any canonical location;
- do not edit `true_map.json` or any schema;
- do not run a migration;
- do not run any heartbeat;
- do not add the 10JC phase-index row (that is 10JD);
- do not commit unless the operator explicitly authorizes it;
- do not push.

The next allowed step is 10JD metadata synchronization or an explicitly
authorized review/correction of this specification.
