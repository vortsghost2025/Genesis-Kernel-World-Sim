# Phase 10OI Specification: Integrate the Canonical Continents Into the Globe

> **Phase Chain:** 10OF (`7001d89`, impl) -> 10OG (`91b66bc`, sync, hash-corrected `e8238d9`/`3a5a5b8`) -> 10OI (specification, this document) -> 10OJ (metadata sync) -> 10OK (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10OK following explicit operator authorization.

---

## 1. Origin: Operator Review of the Live Globe

The operator opened the deployed World Atlas (build 10NS, deployment `nwq4cio1n`,
zoomed back to frame the disc) and confirmed what he liked and what remains:

> "the globe is good i like the mapping of it ... we come to the issue you must
> have is adding the 2 squares of current landmass to the globe itself."

This is an accurate description of the current state, and it is the last
structural gap in the globe work.

## 2. Measured Current State (verified against the source and the render)

### 2.1 The globe carries procedural continents; the real ones do not

- `buildPlanetSurface` (Phase 10NS) emits one 361x181 sphere at
  `GLOBE_RADIUS + computePlanetHeight(lon, lat)`, where the height comes from
  `planetBaseField` (three-octave lattice noise) plus `PLANET_LANDMARKS`.
- `computePlanetHeight` **forces a flat plain inside each canonical patch box**:

  ```js
  if (Math.abs(dLon) <= half && Math.abs(lat - p.lat) <= half) {
      return PLANET_PATCH_PLAIN_H;      // 0.5
  }
  ```

  So within `cont_a`'s and `cont_b`'s 0.2222-rad boxes the planet is a flat
  disc, and the *only* thing that gives those boxes shape is the separately
  projected flat continent mesh.

### 2.2 The flat continent meshes are projected, not integrated

- `buildContinentMesh` builds a 200x200-tile `PlaneGeometry` from the canonical
  data, and `setContinentProjection(cid, true)` re-derives every vertex through
  `computeGlobePosition` onto the sphere.
- Result: a **square-edged patch** whose interior is the real Dolomite terrain
  and whose exterior edge is a straight line in longitude/latitude, sitting on
  a procedural planet whose terrain stops at that same straight line.

That is exactly the "2 squares on the globe" the operator is describing. The
operator likes the globe's own mapping, so the fix direction is to bring the
real continents *into* the planet rather than to change the planet.

### 2.3 The data required already exists and is already loaded

| Available | Source |
|---|---|
| Canonical elevation per tile | `terrainDB[cid].elev` (40,000 entries) |
| Canonical terrain type | `terrainDB[cid].terr` (`"ocean"` marks sea tiles) |
| Canonical water type | `terrainDB[cid].water` |
| Canonical biome | `terrainDB[cid].biome` |
| Built height field | `heightLookup[cid]`, already produced by `computeContinentHeightField(elev, terr, out, settleMask, waterMask)` at the `buildContinentMesh` call site |

No new payload, no new file, no backend change.

## 3. Scope

**100% viewer-side.** No agent cognition, prompt, or behavioural change. No
canonical world-state mutation. Local (human-scale) rendering untouched: the
valley views keep the flat 1 unit = 1 metre mapping and the current continent
meshes exactly as they are.

## 4. Design

### 4.1 The planet samples canonical height inside each patch box

Replace the `PLANET_PATCH_PLAIN_H` early return with a canonical lookup:

1. Invert the sample's longitude/latitude back to the canonical tile coordinate
   using the same mapping `computeGlobePosition` uses forward:
   `t = (lon - patch.lon) / SPAN + 0.5`, `x = t * 200 - 100`, likewise `y`.
2. If `terr[idx] === "ocean"`, return a **negative** depth so the tile reads as
   ocean on the planet (`PLANET_CANONICAL_OCEAN_DEPTH`, e.g. -38).
3. Otherwise return `heightLookup[cid][idx] + PLANET_CANONICAL_LIFT` (a small
   positive lift, e.g. +2.0, so the coastline sits just above sea level and the
   projected flat mesh rests on it rather than inside it).

The inverse mapping must be the exact algebraic inverse of `computeGlobePosition`
so the planet's terrain and the flat mesh's terrain coincide inside the box.
The two are asserted equal by test, not assumed.

### 4.2 Feathered boundary

Outside but near a patch box, blend canonical height into procedural height over
a margin (`PLANET_PATCH_FEATHER = 0.030` rad) so the planet does not show a
cliff where the canonical box ends. Blend weight is 1 inside the box, falls to 0
across the margin, and 0 beyond it.

### 4.3 What happens to the flat continent meshes

They stay. They carry the settlements, objects, scenery, fauna and the action
effects, and re-projecting them is what keeps the human-scale and orbit views
from drifting apart. They now sit on planet terrain that matches their own
coastline, so the square edge disappears from the outside while the interior is
unchanged.

The planet surface under them is produced by `buildPlanetSurface`, which is
built once at load. `heightLookup` is produced by `buildContinentMesh`, so
`buildPlanetSurface` must run **after** both continent meshes are built, or the
canonical data must be read directly. The implementation must order this
correctly and the ordering is covered by a test that asserts the planet mesh
exists and its geometry is non-degenerate after boot.

### 4.4 What this does not do

- It does **not** join the canonical continents to the procedural landmasses.
  They remain distinct landmasses, which is honest: the canonical continents are
  real places and the rest of the planet is generated.
- It does **not** change `GLOBE_PATCHES`, the 97-degree separation, or the
  framing.
- It does **not** add any land the agents could reach. The globe remains
  viewer-side; the reach/behaviour thread is unaffected and no tame is implied.

## 5. Acceptance Criteria

1. `computePlanetHeight` inside a patch box returns the canonical height for
   that tile, not `PLANET_PATCH_PLAIN_H`.
2. Canonical `"ocean"` tiles inside a patch box return a negative depth.
3. The inverse tile mapping used by the planet equals the forward mapping used
   by `computeGlobePosition`, to within 1e-6, over the whole box.
4. Feathering: height is continuous across the box boundary (no step), verified
   by sampling a transect that crosses it.
5. Determinism: two calls at the same coordinate return identical values.
6. Local views are unaffected: the flat ocean plane, the local camera framing
   constants and `computeLocalPosition` are unchanged.
7. Orbit still projects both continents and the planet; a rendered orbit frame
   shows the canonical continents with real coastlines and no square edges.
8. All previously green suites remain green; `node --check` clean; CRLF=0;
   `git diff --check` clean.

## 6. Verification Protocol

1. Write tests from the criteria (red), then implement.
2. Run all five existing suites plus the new ones.
3. Rebuild `viewer-deploy`, render East / West / Orbit with camera-settle
   detection, and **read the screenshots myself** before reporting success.
4. Specifically check the orbit frame for: a visible coast, no straight-edge
   square boundary around either canonical continent, and the settlements still
   visible on top.

## 7. Risk Register

| Risk | Mitigation |
|---|---|
| Seam/cliff at the patch-box boundary | feathering, asserted by a transect test |
| Planet terrain z-fights the projected flat mesh | canonical lift keeps the mesh above the surface |
| `heightLookup` not yet built when the planet mesh is constructed | explicit ordering, asserted by a boot test |
| Inverse mapping drift from the forward mapping | criterion 3 pins them to each other |
| The continents look smaller/less dramatic at planet scale | verified by looking, not by reasoning; framing is adjustable without another phase |
