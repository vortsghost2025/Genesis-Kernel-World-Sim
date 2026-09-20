# Phase 10IZ — First-Pair World Expansion / Fog Integration — Design Specification

**Status:** DESIGN SPECIFICATION ONLY  
**Phase:** 10IZ  
**Next metadata-sync phase:** 10JA  
**Named implementation candidate:** 10JB  
**Implementation authorization:** NOT GRANTED by this document  
**Heartbeat authorization:** NONE — heartbeat 13 remains out of scope  
**Commit / push authorization:** NONE  
**Canonical-write authorization:** NONE

This document defines the smallest safe architecture for connecting the living first-pair civilization runtime to the existing true-map / fog-of-war world model without rewriting the first 12 heartbeats, discarding the meeting stone, replacing the living store, or making dormant Phase-7 files authoritative.

The design follows an append-oriented continuity rule: old evidence stays valid, existing IDs remain stable, and new behavior is introduced through additive state, explicit migration records, and operator-gated cutover.

---

## 0. Phase identifier determination and question cross-map

### Phase identifier

`10IZ` is the correct identifier for this design phase.

The established phase convention is:

- specification at `L`
- metadata synchronization at `L+1`
- named implementation candidate at `L+2`

Therefore the chain is:

`10IZ` → `10JA` → `10JB`

`10J` is an older single-letter phase identifier and is distinct from the later two-letter identifier `10JA`; there is no naming collision.

### Inspection-question cross-map

The ten inspection questions that drove this phase are answered by the following sections:

| Question | Answered in |
| --- | --- |
| 1. What does the first-pair runtime currently expose as an observation? | §1, §5 |
| 2. What currently authorizes and validates movement? | §1, §6 |
| 3. Where does the current three-tile topology come from? | §1, §6 |
| 4. How should the three-tile habitat enter the true map without rewriting history? | §4 |
| 5. How should Adam and Eve's known maps be initialized from genuine history? | §5, §8 |
| 6. How should movement work after fog integration? | §6 |
| 7. Which action vocabulary remains authoritative? | §7 |
| 8. What happens to the dormant Phase-7 agent state? | §2, §5 |
| 9. What world-content mechanics remain intentionally unresolved? | §14 |
| 10. How does migration fail safely and roll back? | §9, §11 |

---

# 1. CURRENTLY PROVEN

The following facts are the design baseline established by the inspection record.

## 1.1 Living civilization state

The living civilization is the state under `.runtime/first-pair`.

At the current boundary:

- heartbeat record count is 12;
- canonical world tick is 12;
- `east_adam` is at `public-shared-center`;
- `east_eve` is at `public-shared-center`;
- the meeting stone exists as the single public object;
- heartbeat 13 has not run.

No part of this specification authorizes heartbeat 13.

## 1.2 Current observation construction

The first-pair runtime currently constructs local observation from the runtime policy topology, not from the true map and not from radius-based fog.

With a valid position and active movement grant:

`visible_tiles = [current_position] + get_adjacent_tiles(runtime_policy, current_position)`

The current observation shape is conceptually:

```text
{
  tile_id: current_position,
  visible_tiles: [...tile ids...],
  objects_here: [...living-store public objects on current tile...]
}
```

If there is no current position, the habitat's `observation_boundaries` are used as a fallback.

Therefore the effective live source of spatial visibility is the policy topology whenever a position exists.

## 1.3 Current movement validation

Movement is currently authorized through the living runtime policy and movement grant.

The move executor verifies, in sequence:

1. the target belongs to the policy's allowed tile set;
2. the target is adjacent according to `get_adjacent_tiles(runtime_policy, current_position)`;
3. the movement grant is active;
4. the existing co-location rule is respected.

A hard-coded continuity rule currently permits co-location only at `public-shared-center`.

That rule becomes significant once the world expands because it prevents Adam and Eve from occupying the same newly discovered tile.

## 1.4 Current topology source

The three-tile topology originates in the first-pair persistence declaration and is represented in runtime policy state.

The declaration includes the current three-tile adjacency and declares adjacent tile IDs visible.

`get_adjacent_tiles(...)` reads adjacency from the runtime policy topology.

The topology is therefore living-runtime policy data, not true-map geography.

## 1.5 Current object semantics

Public objects are living-civilization state.

The meeting stone is not merely scenery. Its creation, ownership, inscription, and provenance are already part of first-pair history.

Object creation is constrained to the acting agent's current tile and the tile must belong to the runtime's allowed topology.

This behavior should remain intact after fog integration.

## 1.6 Existing true-map / fog system

A separate Phase-7 world stack already exists.

The inspected true map contains:

- 2 continents;
- 6 regions;
- 14 existing tiles;
- 6 landmarks;
- 2 mysteries;
- explicit travel edges;
- empty resources;
- empty hazards.

The fog engine already supports pure operations for:

- empty known-map creation and validation;
- world-position validation;
- coordinate/radius visibility;
- local observation construction;
- merging observations into a known map;
- named places;
- hypotheses;
- contact evidence.

The inspection found no implemented mystery-reveal path consuming the mystery reveal threshold.

## 1.7 Dormant Phase-7 agent files

Separate files under `data/agents/east_adam` and `data/agents/east_eve` belong to the older Phase-7 / autonomous-daemon stack.

The inspected dormant Adam self-state contains old daemon-era concepts such as:

- `budget-exhausted`;
- `model_calls_used_this_hour`;
- `whisper_cooldown`.

The dormant world positions do not match the lived first-pair positions.

Those files are not currently read by the living first-pair runtime and must not become authoritative during this migration.

## 1.8 Two spatial systems are currently disconnected

The live first-pair runtime does not currently use:

- `data/world/true_map.json`;
- the Phase-7 fog engine;
- dormant `data/agents/*/known_map.json`;
- dormant `data/agents/*/world_position.json`;
- dormant `data/agents/*/self_state.json`.

That separation is the architectural problem this phase solves.

---

# 2. ARCHITECTURAL CONFLICTS

The integration must resolve the following conflicts explicitly rather than hiding them behind adapters.

## 2.1 Two world authorities

Today there are effectively two spatial worlds:

- the living first-pair three-tile habitat;
- the larger Phase-7 true map.

Resolution:

- **true map = authoritative geography**;
- **living first-pair store = authoritative civilization state**.

The true map describes where geography, terrain, routes, and world landmarks exist.

The living store remains the only authority for first-pair identities, positions, memories, goals, questions, messages, public objects, heartbeat history, policies, and civilization provenance.

## 2.2 Two observation sources inside the living stack

The living runtime already contains two observation concepts:

- policy-topology adjacency;
- habitat `observation_boundaries`.

Current runtime behavior effectively prefers policy adjacency when a position exists.

Resolution:

- fog-derived local observation becomes the single active geography-observation source after cutover;
- the habitat boundary record is retained as historical declaration;
- no old declaration is rewritten.

## 2.3 Dormant agent positions conflict with lived history

Dormant Phase-7 world-position files do not describe the current first-pair civilization.

Resolution:

- they remain untouched;
- they are never loaded by the first-pair fog adapter;
- they are explicitly treated as historical artifacts;
- no authority transfer occurs by filename coincidence.

## 2.4 Action vocabulary mismatch

The old fog/exploration stack includes concepts such as:

- `observe`;
- `rest`;
- `gather`;
- `move_local`.

The living pair uses its own seven-action model.

Resolution:

- the first-pair action vocabulary remains authoritative;
- no action is renamed merely to match old Phase-7 code.

## 2.5 Coordinate visibility versus graph movement

Fog visibility is coordinate/radius based.

Movement is graph/travel-edge based.

This is intentional but means coordinate placement controls what can be seen while travel edges control what can be traversed.

The specification therefore treats habitat coordinates and travel edges as a coupled design decision.

## 2.6 Directed true-map edges versus safe first-pair return movement

The inspected true-map graph uses authored directed edges.

Blindly exposing a one-way deep-world path could strand a first-pair agent.

Resolution:

- habitat internal edges and the initial habitat-to-world doors are explicitly modeled as bidirectional pairs of directed edges;
- deeper existing Phase-7 edges remain as authored unless a later phase changes them;
- tests must prove the first discovery step always has a return route.

## 2.7 Co-location rule is habitat-specific

The hard-coded rule allowing co-location only at `public-shared-center` made sense in the original habitat.

In a larger world it may become restrictive.

Resolution for this cutover:

- keep the rule unchanged initially;
- document it as an explicit near-term design decision;
- do not silently generalize it as part of fog integration.

## 2.8 `adjacent_tile_ids_visible` versus radius visibility

The historical declaration says adjacent tile IDs are visible.

The fog engine uses radius and conditions.

Resolution:

- after cutover, radius-based fog determines geographic visibility;
- the historical flag remains as provenance, not active geometry logic.

## 2.9 Prompt contamination risk

The true-map / fog system contains implementation-oriented field names that do not belong in cognition prompts.

Resolution:

- the adapter emits a cognition-safe observation projection;
- implementation names such as `true_map` and `known_map` must never appear in the agent-facing observation;
- `true_landmark_id`, if present in raw fog output, is projected as `landmark_id`;
- the existing contamination checks remain a backstop.

## 2.10 Legacy dual-sim data remains out of scope

Other old east/west world-state artifacts remain part of previous architecture.

Resolution:

- the new adapter reads only the declared true-map input plus the living first-pair store;
- no legacy dual-sim state becomes an implicit fallback.

---

# 3. CONTINUITY INVARIANTS

These are non-negotiable.

1. All 12 existing heartbeat records remain byte-preserved.
2. Heartbeat 13 is not run by this design phase.
3. `meeting-stone-center` remains intact with its inscription, ownership, and provenance.
4. Existing agent IDs remain unchanged.
5. Existing identity files remain unchanged.
6. Existing memories remain unchanged.
7. Existing messages remain unchanged.
8. Existing goals remain unchanged.
9. Existing questions remain unchanged.
10. Existing completed evidence remains valid.
11. The migration never rewrites an old heartbeat to make it appear fog-aware.
12. The three habitat tile IDs remain exactly:
    - `public-start-adam`
    - `public-shared-center`
    - `public-start-eve`
13. Existing first-pair positions at migration remain `public-shared-center` for both agents.
14. Runtime policy 001 is retained as historical state.
15. Any topology-aware successor is additive as policy 002.
16. The existing movement grant reference remains compatible.
17. One movement edge per heartbeat remains the maximum normal traversal.
18. No dormant `data/agents/*` file becomes authoritative.
19. No hidden true-map tile appears in an agent prompt unless it is visible under the fog rule.
20. Migration and rollback are operator-authorized, provenance-recorded operations.
21. No commit, push, heartbeat, or canonical write is authorized merely by approving this specification.

---

# 4. PROPOSED WORLD-MAPPING MODEL

## 4.1 Dual-layer model

The world is modeled in two layers.

### Geography layer

`data/world/true_map.json`

Responsibilities:

- continents;
- regions;
- coordinates;
- terrain;
- biome;
- travel edges;
- fixed/natural landmarks;
- later resources, hazards, and authored mysteries.

The first-pair runtime treats this layer as read-only during normal heartbeats.

### Civilization layer

`.runtime/first-pair/*`

Responsibilities:

- agent identity;
- live positions;
- memory;
- messages;
- goals;
- questions;
- public objects;
- heartbeat history;
- policy/grants;
- per-agent known maps;
- evidence and migration provenance.

This remains the living authority.

## 4.2 Embed the existing habitat instead of replacing it

The three existing habitat tile IDs are added to the true map as a new region on continent A.

Proposed region:

`cont_a_first_pair_habitat`

Proposed coordinates:

| Tile | Coordinate |
| --- | --- |
| `public-start-adam` | `(-1, -1)` |
| `public-shared-center` | `(0, -1)` |
| `public-start-eve` | `(1, -1)` |

This preserves every historical first-pair tile reference.

There is no ID translation layer and no heartbeat rewrite.

## 4.3 Initial door model

The preferred smallest mapping uses existing geography rather than inventing a new corridor tile.

Initial bidirectional door A:

`public-shared-center` ↔ `cont_a_origin_000`

Initial bidirectional door B:

`public-start-eve` ↔ `cont_a_origin_001`

Each bidirectional relation is represented as the two directed edges required by the current true-map graph model.

Why two doors:

- `cont_a_origin_000` is radius-visible from the shared center;
- `cont_a_origin_001` is radius-visible from Eve's start tile;
- movement and visibility remain locally coherent;
- neither path requires inventing a new geography tile;
- each initial discovery has an explicit return edge.

If implementation review shows that only one door is desired, door A is the minimum viable seam. The second door can remain a later authored connection.

## 4.4 Discovery consequences of the proposed coordinates

With radius 1:

- from `public-shared-center`, `cont_a_origin_000` becomes visible;
- from `public-start-eve`, `cont_a_origin_001` becomes visible;
- from `public-start-adam`, no additional existing Phase-7 tile is immediately radius-visible under the inspected coordinate layout.

This is an intentional consequence of the coordinate placement.

The design phase itself reveals nothing to Adam or Eve. Visibility changes only after an authorized implementation and cutover heartbeat.

## 4.5 Meeting stone projection into geography

The meeting stone remains authoritative in the living store.

For geography/fog purposes it is also represented as an agent-created landmark projection on `public-shared-center`.

Proposed landmark ID:

`lm_meeting_stone_center`

Proposed kind:

`meeting_stone`

The projected landmark description must preserve the real inscription without inventing new history.

The living public object remains the source of truth for ownership and creation provenance.

The true-map landmark is a spatial projection so future fog observations can recognize that a built landmark physically exists there.

---

# 5. FOG / KNOWN-MAP MODEL

## 5.1 Per-agent known maps

Each living first-pair agent gets its own persisted known map inside `.runtime/first-pair`.

Preferred files:

```text
.runtime/first-pair/known_map_east_adam.json
.runtime/first-pair/known_map_east_eve.json
```

A single combined fog-state file is possible but is not preferred because separate files preserve the existing Phase-7 known-map concept and make per-agent provenance clearer.

## 5.2 Genuine-history seeding

Known maps are not initialized from dormant Phase-7 files.

They are seeded deterministically from actual first-pair history.

The migration algorithm replays existing heartbeat evidence and derives, per agent:

- tiles occupied;
- tiles visible under the historical adjacency model;
- first observed heartbeat for each known tile;
- actual visit count for occupied tiles;
- known agent-created landmarks;
- named places supported by first-pair history.

No field is backfilled from speculation.

## 5.3 Conservative replay rule

For each historical heartbeat:

1. read the recorded position for the agent;
2. mark the occupied tile as observed and visited;
3. reconstruct historical adjacency using the then-active three-tile policy;
4. mark adjacent historically visible tiles as observed;
5. increment visit count only for the occupied tile;
6. retain the earliest observed tick;
7. never infer a visit merely from visibility.

This preserves the difference between “saw” and “stood on.”

## 5.4 Expected migration result for the three habitat tiles

Because the pair has operated within the three-tile habitat for 12 heartbeats and the historical observation model exposed adjacency, both agents are expected to know all three habitat tile IDs by migration.

The migration script must compute this from the records rather than hard-code the conclusion.

## 5.5 Meeting-stone known landmark

The migration seed records the meeting stone as a known landmark for each agent only if the historical record proves that the agent observed it.

The inspection record indicates both agents were present when it existed at the shared center, so the expected result is that both know it.

The seeding code must still derive the first observed tick from evidence.

## 5.6 Fog observation adapter

The adapter calls the existing pure fog functions using:

- true map;
- acting agent position;
- acting agent known map;
- current visibility conditions.

The raw fog result is projected into the living observation contract.

The living runtime continues to receive:

```text
tile_id
visible_tiles
objects_here
```

and gains an additive detail field, for example:

```text
visible_tile_details
```

The exact additive key can be chosen during implementation, but the compatibility rule is fixed: existing tile-ID consumers continue to receive a list of tile IDs.

## 5.7 No hidden-map leakage

The cognition projection must include only:

- current tile;
- radius-visible tiles;
- safe terrain/biome/landmark details for those tiles;
- living-store objects the agent can legitimately perceive.

It must not include:

- the entire true map;
- undiscovered tile IDs;
- hidden mysteries;
- non-visible landmarks;
- implementation terms such as `true_map` or `known_map`;
- dormant Phase-7 agent state.

## 5.8 Update cycle

At a successful heartbeat:

1. build local fog observation;
2. generate cognition-safe observation;
3. merge genuinely observed data into that agent's known map;
4. persist the updated known map;
5. derive any topology update required by the movement model;
6. continue the living heartbeat pipeline.

Known-map persistence failure is a heartbeat failure condition, not a warning.

---

# 6. MOVEMENT MODEL

## 6.1 Keep the existing movement seam

The living runtime already has a clear seam:

`get_adjacent_tiles(runtime_policy, current_tile)`

That seam is preserved.

The major change is how the active policy topology is produced.

## 6.2 Derived policy topology

The topology in `runtime-policy-first-pair-002` is derived from:

`travel_edges(true_map)` restricted to `known tiles`

The default design uses the union of Adam's and Eve's known tiles for the shared runtime policy because the current runtime has one shared policy topology.

Conceptually:

```text
known_union = known_tiles(adam) ∪ known_tiles(eve)

active_edges =
    true_map.travel_edges
    where edge.from ∈ known_union
      and edge.to   ∈ known_union
```

Allowed tile IDs are the known tiles reachable within this graph plus the current valid habitat set.

## 6.3 Why union knowledge is the default

A single shared runtime policy already exists.

Using the union:

- preserves that seam;
- avoids introducing per-agent policies in the same migration;
- supports a collaborative pair who can communicate discoveries;
- is the smallest architectural change.

Per-agent movement authority is a legitimate later refinement, but it would require policy/schema changes beyond this phase.

## 6.4 Observation remains per-agent

Shared movement topology does not make observations shared.

Adam's cognition receives Adam's local visibility.

Eve's cognition receives Eve's local visibility.

The known-map union affects legal path availability, not what each agent literally sees in a given heartbeat.

## 6.5 Policy 002

The migration adds a successor policy record:

`runtime-policy-first-pair-002`

Characteristics:

- topology derived from known-map/true-map state;
- same movement grant reference as policy 001 unless an implementation review proves that incompatible;
- policy 001 retained;
- explicit active-policy transition recorded in migration provenance.

No old policy record is rewritten.

## 6.6 One-edge-per-heartbeat

One movement action traverses one authorized travel edge.

No coordinate teleportation is introduced.

Coordinates determine visibility, not direct movement.

## 6.7 Habitat and door edge direction

The habitat's internal edges and initial world doors must be return-safe.

For this reason they are encoded bidirectionally as explicit directed pairs.

Existing deeper true-map edges remain as authored.

A test must prove that the first expansion move can return to the habitat without depending on an unauthored reverse edge.

## 6.8 Co-location rule

At cutover the existing rule remains:

co-location is allowed only at `public-shared-center`.

This preserves behavior exactly.

However the rule must be surfaced in operator documentation because it means:

- if Adam occupies a new tile, Eve cannot join him there;
- if Eve occupies a new tile, Adam cannot join her there.

A later dedicated phase may generalize co-location after deliberate design.

Fog integration does not silently do so.

---

# 7. ACTION MODEL

## 7.1 Keep the seven-action first-pair vocabulary

The living first-pair actions remain authoritative.

No old fog/exploration action vocabulary replaces them.

`move` continues to mean move one legal edge.

Public-object actions continue to operate on living civilization state.

Messages, `ask_human`, and `request_capability` remain unchanged.

## 7.2 `move`

`move` validates against the derived runtime-policy topology.

No agent may move to a tile simply because the tile exists in the true map.

The target must be known/authorized through the derived topology.

## 7.3 Public-object operations

Public object creation remains current-tile scoped.

The meeting stone remains a living-store public object.

If fog exposes a tile, that alone does not authorize creating an object on a remote visible tile.

## 7.4 `observe`

No explicit Phase-7 `observe` action is adopted.

Local observation occurs naturally as part of each heartbeat's context construction.

## 7.5 `rest`

No old `rest` action is adopted merely for compatibility.

The existing first-pair no-action behavior remains the equivalent no-op path.

## 7.6 `move_local`

Not adopted.

The first-pair `move` action already owns movement semantics.

## 7.7 `gather`

Deferred.

The inspected true map has no authored resources.

Adding `gather` now would create an action with no honest world content behind it.

Future resource collection should arrive through a dedicated capability phase once resources and rules are authored.

## 7.8 Future capabilities

`request_capability` remains the deliberate extension seam.

New capabilities are not smuggled into this migration.

## 7.9 `ask_human`

The human-question path remains unchanged.

Any pending question about whether the world extends beyond the habitat is answered only through the existing operator channel.

The migration does not fabricate an operator answer.

---

# 8. PERSISTENCE / REPLAY MODEL

## 8.1 New persisted files

The migration adds per-agent known-map state in the living store.

Preferred:

```text
.runtime/first-pair/known_map_east_adam.json
.runtime/first-pair/known_map_east_eve.json
```

## 8.2 Additive policy state

Policy 002 is added rather than replacing policy 001.

The persistence layer must support selecting the active successor without deleting the original record.

## 8.3 Heartbeat evidence

New heartbeats may add an optional additive field such as:

```text
revealed_tiles: {
  east_adam: [...],
  east_eve: [...]
}
```

Old heartbeat records remain valid because the field is absent historically.

No migration backfills the field into old records.

## 8.4 Known-map evidence digests

Evidence bundles should gain additive per-agent known-map digests.

This makes fog-state mutation auditable without changing prior evidence formats.

## 8.5 Reconstruction

Known maps are derived-but-persisted state.

They must be reconstructible from:

1. the deterministic migration seed based on heartbeats 1–12;
2. subsequent heartbeat positions;
3. visibility rules active for those heartbeats;
4. recorded revealed-tile evidence where available.

The persistent copy exists for efficient runtime use.

Replayability remains a requirement.

## 8.6 Living store remains single civilization writer

The fog adapter does not create a second civilization database.

Positions remain in the living store.

Public objects remain in the living store.

Messages remain in the living store.

Known maps are added to that same authority.

---

# 9. MIGRATION PLAN

Migration is an explicit operator operation, separate from merely landing code.

## M0 — Preflight and provenance

Before any canonical write:

- verify the branch and expected implementation phase;
- verify heartbeat count remains 12;
- verify tick remains 12;
- verify both agents remain at `public-shared-center`;
- verify meeting stone identity and inscription;
- hash the canonical inputs required for migration;
- produce a migration manifest.

No heartbeat runs.

### Snapshot rule

The inspection record proposed a pre-migration snapshot.

Because preservation policy forbids casual backup creation, implementation must not create any backup/snapshot unless the operator explicitly authorizes that migration step.

If authorization is granted, the snapshot path and hashes become part of migration provenance.

## M1 — True-map extension

Operator-authorized canonical data edit.

Add:

- `cont_a_first_pair_habitat` region;
- the three preserved habitat tile IDs and coordinates;
- the meeting-stone landmark projection;
- internal habitat edges;
- selected initial door edges.

Requirements:

- validate the candidate true map before replacing canonical data;
- record old and new hashes;
- do not author resources/hazards as part of this phase;
- do not alter unrelated existing tiles.

## M2 — Known-map and policy migration

Run the migration script against a scratch copy first.

The script:

1. replays heartbeat history;
2. produces Adam's known map;
3. produces Eve's known map;
4. validates both;
5. derives runtime-policy-first-pair-002;
6. validates movement/grant compatibility;
7. creates migration provenance;
8. only then, under explicit operator authorization, writes the new additive living-store state.

No old heartbeat, memory, goal, question, message, identity, or public-object record is edited.

## M3 — Runtime integration cutover

Implementation code is designed to remain inert until the migration prerequisites are present.

Before cutover:

- no known-map files → legacy observation path;
- no policy 002 → legacy topology path.

After an explicitly authorized migration marker identifies the cutover:

- fog observation becomes active;
- policy 002 becomes active;
- no automatic fallback to legacy geography occurs on fog failure.

The exact feature-gate marker must be explicit and testable; mere file presence should not be the sole irreversible signal if a clearer migration-state record exists.

## M4 — First post-migration verification heartbeat

This is separately operator-authorized.

It is not part of the design phase.

The verification report must prove:

- exactly one heartbeat ran;
- previous 12 heartbeats remain unchanged;
- fog observation contained only legitimate radius-visible tiles;
- no hidden map data leaked;
- known-map updates match what was observed;
- topology update matches known tiles and authored travel edges;
- the meeting stone still resolves from living state;
- evidence was exported;
- no automatic next heartbeat was scheduled.

---

# 10. TEST PLAN

Implementation phase 10JB is test-driven.

## 10.1 Pure adapter tests

Test:

- true-map load and validation;
- known-map load and validation;
- current-tile observation;
- radius-1 visibility;
- visibility-condition handling;
- landmark projection;
- living-object merge into observation;
- cognition-safe field projection;
- no hidden-map leakage.

## 10.2 Known-map merge tests

Test:

- first observation;
- repeated observation idempotence;
- first-observed tick immutability;
- visit counts increment only on actual occupancy;
- landmark discovery;
- named-place preservation;
- two agents remain independently tracked.

## 10.3 History seeding tests

Using synthetic heartbeat histories, prove:

- occupied tile becomes visited;
- adjacent tile becomes observed under historical topology;
- visit count is not invented for merely visible tiles;
- earliest observation tick wins;
- repeated migration generates byte-equivalent semantic state.

Then run a scratch migration over a copy of the real first-pair store and verify the expected three-tile knowledge without touching canonical state.

## 10.4 Topology derivation tests

Test:

- unknown destination is excluded;
- known destination with no travel edge is excluded;
- known travel edge is allowed;
- habitat internal edges are bidirectional;
- initial door edges are return-safe;
- one movement action maps to one edge;
- union-of-known-map semantics are deterministic.

## 10.5 Co-location regression tests

Prove the current rule remains intact:

- both may occupy `public-shared-center`;
- second arrival on any other occupied tile is blocked.

Document this as expected behavior, not an accidental failure.

## 10.6 Fail-closed tests

Missing/corrupt:

- true map;
- Adam known map;
- Eve known map;
- active derived policy;
- required migration marker;

must not produce fabricated observations or partially mutate civilization state.

## 10.7 Prompt-safety tests

Agent-facing observation must not contain:

- `true_map`;
- `known_map`;
- hidden tile IDs;
- hidden mystery data;
- dormant-state values;
- implementation-only field names prohibited by contamination rules.

## 10.8 Migration tests

On scratch state:

- old heartbeat bytes unchanged;
- old memory bytes unchanged;
- old goals bytes unchanged;
- old questions bytes unchanged;
- old messages bytes unchanged;
- identity unchanged;
- public object unchanged;
- only declared additive migration files/records appear.

## 10.9 First-discovery simulation

Simulate, without canonical mutation:

- both agents at shared center;
- fog radius 1;
- `cont_a_origin_000` legitimately visible;
- move path from center to origin 000 legal if door A is authored;
- return path legal;
- no extra true-map tiles leak.

## 10.10 Regression suite

Run:

- first-pair runtime tests;
- persistence tests;
- runner tests;
- fog adapter tests;
- migration tests;
- contamination/no-leak tests.

A 10JB implementation is not accepted while any continuity test fails.

---

# 11. FAILURE / ROLLBACK CONDITIONS

## 11.1 Fail closed, never fabricate

After migration cutover, the runtime must not silently fall back to the legacy three-tile observation model if fog state is broken.

If required geography or fog state is invalid:

- the cycle fails closed;
- no normal action is executed;
- no fabricated observation is shown;
- no partial position movement is persisted.

The exact safe error-record mechanism must use the existing first-pair failure semantics.

## 11.2 Migration abort conditions

Abort before canonical write if any of these fail:

- heartbeat count is not 12 at the expected migration boundary;
- world tick differs from the approved boundary;
- either agent position differs unexpectedly;
- meeting stone is missing or changed;
- true-map validation fails;
- known-map seed validation fails;
- topology derivation fails;
- migration diff includes an undeclared file;
- old canonical records would be modified;
- credentials or secrets appear in migration output.

## 11.3 Post-write stop conditions

Stop before any heartbeat if:

- post-migration manifest differs outside approved additions;
- policy 002 does not resolve the expected three habitat tiles;
- either known map cannot validate;
- a dormant Phase-7 file changed;
- a legacy heartbeat hash changed;
- the meeting stone changed;
- a prompt-safety test leaks hidden geography.

## 11.4 Rollback semantics

Rollback is never automatic and never silent.

If rollback is explicitly authorized:

- record that rollback is occurring;
- use the approved pre-migration material or a deterministic compensating migration;
- restore the pre-cutover active-policy state;
- remove/deactivate only the migration additions specified by the rollback plan;
- revalidate heartbeat 1–12 hashes and living-state invariants;
- record post-rollback hashes.

No generic `git reset`, `git clean`, stash, or destructive repository operation is part of the rollback procedure.

## 11.5 True-map rollback

The true-map extension is additive.

If an operator authorizes reversal, remove only the habitat additions introduced by the migration and restore the recorded pre-migration map hash.

Unrelated world geography remains untouched.

---

# 12. FILES THAT WOULD CHANGE

This is a design inventory for implementation candidate 10JB. It does not authorize the changes.

## 12.1 Expected implementation files

```text
world-sim/data/world/true_map.json
world-sim/backend/world/first_pair_fog_adapter.py          # new
world-sim/backend/world/first_pair_runtime.py
world-sim/backend/world/first_pair_persistence.py
world-sim/scripts/migrate_first_pair_fog.py                # new
world-sim/tests/test_first_pair_fog_adapter.py              # new
world-sim/tests/test_first_pair_migration.py                # new
world-sim/docs/phase_10iz_first_pair_world_expansion_fog_integration_spec.md
```

Additional existing tests may require additive updates.

Metadata/index documentation belongs to 10JA.

## 12.2 Canonical runtime additions

Expected additive living-store state after an authorized migration:

```text
.runtime/first-pair/known_map_east_adam.json
.runtime/first-pair/known_map_east_eve.json
```

plus an additive policy-002 record and migration provenance in the repository's established canonical format.

## 12.3 Files that must not be rewritten by migration

The migration does not rewrite existing:

```text
heartbeat history
memory
goals
questions
messages
identity
existing public-object history
runtime policy 001
```

It also does not touch dormant:

```text
data/agents/east_adam/*
data/agents/east_eve/*
```

except in a future separately authorized archival/cleanup phase.

---

# 13. BOUNDED IMPLEMENTATION PHASES

10JB should be executed as four bounded units.

## 10JB-1 — Pure fog adapter and replay seed

Scope:

- add pure adapter;
- add cognition-safe projection;
- add deterministic historical known-map seeding;
- add topology derivation;
- add tests.

Constraints:

- no canonical writes;
- no runtime cutover;
- no heartbeat;
- scratch fixtures only.

Stop condition:

all adapter, replay, topology, and no-leak tests pass.

## 10JB-2 — Runtime integration behind an inert gate

Scope:

- wire first-pair context construction to the adapter;
- wire derived policy loading;
- preserve legacy path while migration gate is inactive;
- add fail-closed semantics for post-cutover state;
- keep seven-action vocabulary.

Constraints:

- no canonical migration;
- no true-map edit;
- no heartbeat.

Stop condition:

legacy regression suite and fog integration tests both pass.

## 10JB-3 — Migration artifact and canonical candidate

Scope:

- implement migration script;
- prepare true-map extension candidate;
- validate migration against scratch copy of current living store;
- produce exact diff/manifests;
- verify old records remain byte-identical.

Constraints:

- canonical candidate only;
- no actual canonical write until explicit operator authorization;
- no heartbeat.

Stop condition:

operator can inspect an evidence-backed migration plan with exact intended mutations.

## 10JB-4 — Operator-authorized migration and cutover verification

Scope only after explicit approval:

- apply true-map extension;
- seed living known maps;
- append policy 002;
- append migration provenance;
- activate cutover;
- run at most the specifically authorized verification heartbeat;
- export evidence immediately.

Constraints:

- no recurring runner;
- no automatic next heartbeat;
- no commit or push unless separately authorized.

Stop condition:

migration invariants and the single authorized cutover verification all pass.

---

# 14. CONTENT GAPS AND FUTURE PLUG-IN POINTS

These are intentionally not solved by 10IZ.

## 14.1 Resources

The inspected true map has no authored resources.

Therefore:

- no gathering economy is introduced;
- no inventory/resource loop is invented;
- later deterministic or authored resources can plug into true-map tile content.

## 14.2 Hazards

The inspected true map has no authored hazards.

Therefore:

- fog integration exposes no invented hazards;
- later hazard content must enter through a separate authored phase with explicit mechanics.

## 14.3 Mysteries

Mysteries exist in the true-map schema/data, but the inspection found no implemented reveal mechanic that consumes the reveal threshold.

Therefore:

- mystery data remains hidden;
- the fog adapter must not expose mysteries merely because a tile is visible;
- mystery-reveal logic is a future dedicated phase.

## 14.4 Gather capability

`gather` remains deferred until actual resources and rules exist.

## 14.5 Co-location policy

The existing shared-center-only rule is retained for cutover but should receive a later explicit decision before the pair is expected to travel together.

## 14.6 Directed deep-world paths

The initial habitat doors are made return-safe.

Whether the entire existing Phase-7 travel graph should remain directed, become bidirectional, or gain route semantics is a later world-design decision.

## 14.7 Dynamic geography authored by agents

The meeting stone establishes that agent-created structures can become real geography.

A later design may generalize a rule for projecting durable living-store constructions into true-map landmarks without letting the runtime directly rewrite hidden geography ad hoc.

---

# 15. DESIGN DECISIONS REQUIRING EXPLICIT OPERATOR CONFIRMATION BEFORE 10JB-4

The design can be implemented and scratch-tested before these are exercised, but canonical migration should not proceed until the operator confirms:

1. **Habitat coordinates:** approve `(-1,-1)`, `(0,-1)`, `(1,-1)`.
2. **Initial doors:** approve center↔origin-000 and whether Eve-start↔origin-001 is included immediately.
3. **Shared movement knowledge:** approve union-of-known-maps for policy topology.
4. **Co-location:** keep shared-center-only at cutover, as specified.
5. **Meeting stone projection:** approve a true-map landmark projection while retaining the living object as authority.
6. **Cutover visibility:** accept that the first authorized fog heartbeat at the shared center can reveal `cont_a_origin_000`.
7. **Snapshot/provenance mechanism:** explicitly authorize any pre-migration snapshot before one is created.
8. **Heartbeat:** separately authorize the first post-migration heartbeat when ready.

No choice above is implicitly approved by the existence of this document.

---

# 16. ACCEPTANCE CRITERIA FOR THIS SPECIFICATION

Phase 10IZ is complete when the documentation clearly establishes all of the following:

- the living first-pair store remains civilization authority;
- the true map becomes geography authority;
- existing three-tile IDs remain stable;
- old heartbeats are not rewritten;
- known maps are seeded only from genuine history;
- fog controls visibility without leaking hidden geography;
- movement remains graph-based and one-edge-per-heartbeat;
- policy topology becomes derived, additive state;
- the seven-action vocabulary remains intact;
- dormant Phase-7 agent state stays dormant;
- resources/hazards are not invented;
- mystery reveal remains deferred;
- migration is staged and operator-gated;
- failure is fail-closed;
- rollback is explicit and provenance-recorded;
- implementation is bounded under 10JB;
- heartbeat 13 is still not authorized.

---

# 17. STOP BOUNDARY

This document is the end of the 10IZ design phase.

After writing and verifying this file:

- do not implement the adapter;
- do not edit `true_map.json`;
- do not write known-map files;
- do not create policy 002;
- do not run a migration;
- do not run heartbeat 13;
- do not commit;
- do not push.

The next allowed step is 10JA metadata synchronization or an explicitly authorized review/correction of this specification.

