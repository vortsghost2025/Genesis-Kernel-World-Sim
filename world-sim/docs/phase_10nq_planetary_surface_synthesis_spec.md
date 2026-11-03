# Phase 10NQ Specification: Planetary Surface Synthesis (Fill the Globe)

> **Phase Chain:** 10NM (`5ae72cf`, impl) -> 10NP (`03ad580`, sync, hash-corrected `4aa7f3d`) -> 10NQ (specification, this document) -> 10NR (metadata sync) -> 10NS (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10NS following explicit operator authorization.

---

## 1. Origin: Operator Observation After the 10NM Globe Fix

After 10NM landed, the operator confirmed the globe itself works and stated the remaining gap directly:

> "so good news is we have a globe now we need to actually make the planet the globe
> just has the 2 squares on it rest of the globe is empty"

That is an accurate description of the rendering, and it is now measurable rather than impressionistic.

## 2. Measured Current State (verified against the source and rendered output)

| Fact | Value | Source |
|---|---|---|
| Globe radius | `GLOBE_RADIUS = 900.0` | `prototype/index.html`, scale constant block |
| Ocean shell orbit mesh | `SphereGeometry(GLOBE_RADIUS - 0.6, 64, 48)` = radius **899.4** | `globalOceanGlobeGeom`, added in 10NG |
| Ocean shell colour | flat `MeshBasicMaterial` `0x0f2d4a` | one unbroken colour, no relief, no coastlines |
| Agent continent patches | `cont_a { lon: -0.85, lat: 0.30 }`, `cont_b { lon: 0.85, lat: -0.30 }` | `GLOBE_PATCHES` |
| Patch angular span | `GLOBE_CONTINENT_SPAN = 200 / 900` = **0.2222 rad** (12.7 deg) | derived constant |
| Total land rendered in orbit | two 200x200-tile squares, 0.33% of the sphere's surface area | `2 * (0.2222/pi)^2` of a 4pi sphere |
| Terrain synthesis available today | `computeContinentHeightField` (flat-layout only, 2 call sites) | no lattice-noise helper exists in the viewer |
| Orbit-mode lighting | existing sun light + `scene.fog` at `globeFogDensity = 0.32 / (R * 3)` | `applyCameraMode` orbit branch |
| Local-mode rendering | flat 1 unit = 1 metre, `controls.maxDistance = 550`, camera far 1600 | verified unchanged since 10NM |

**Root cause:** the globe is an ocean shell plus two conformally-projected flat continent
patches. Nothing synthesizes any other land, so the remaining 99.67% of the sphere is one
unbroken blue surface. The operator's read is correct and complete.

## 3. Scope

**100% viewer-side.** No agent cognition, prompt, or behavioural change. No mutation of
canonical world state. The only live contract is that when the camera returns to a local
view, every pixel of the human-scale world must be byte-identical to today's output.

## 4. Design

### 4.1 One full sphere replaces the ocean shell in orbit mode

Replace the orbit-mode "coloured ball" with a single dense sphere at radius
`GLOBE_RADIUS + h(theta, phi)`, where `h` is a signed displacement:

- `h <= 0` is ocean, coloured by depth (bathymetry bands: abyss, deep, shelf).
- `h > 0` is land, coloured by latitude-aware biome.
- Coastlines are the single `h == 0` boundary of one mesh, so there is no seam, no
  z-fighting and no floating edge (the reason the current 899.4 shell cannot simply have
  land dropped on top of it).

The old `globalOceanGlobe` shell is **not deleted**; it stays referenced so `focusCiv`
and the local-mode restore path are untouched, and `setOceanProjection` gains a third
state (see 4.4).

### 4.2 Deterministic, seamless spherical noise

A lattice hash `hash3(i, j, k, seed)` over the integer cell of each sample direction,
trilinearly interpolated. Sampling is done in 3D on the unit-sphere direction rather
than on the equirectangular `(theta, phi)` grid, which makes the field continuous across
the antimeridian and non-degenerate at the poles. Three octaves:

| octave | frequency | weight | purpose |
|---|---|---|---|
| 1 | 2.5 | 1.00 | major landmass continents and ocean basins |
| 2 | 7.0 | 0.42 | regional coastlines, seas, subcontinents |
| 3 | 19.0 | 0.16 | islands, archipelagos, coastal detail |

Land exists where the weighted sum exceeds a sea-level threshold tuned so that roughly
30-35% of the sphere is land, matching Earth's ratio.

### 4.3 Fixed landmark set

In addition to noise land, eight named fixed landmasses are stamped so the atlas has a
legible, describable geography rather than an organic blob: two polar ice caps, a
supercontinent centred near the canonical patches, two mid-latitude continents at
antipodal-ish longitudes, one equatorial archipelago belt, one southern island
continent, and one small isolated oceanic island pair far from everything (an
exploration target). Positions and radii are constants in `PLANET_LANDMARKS`.

### 4.4 Canonical patch compositing (load-bearing constraint)

The two agent continents are projected as separate flat patches at radius
`GLOBE_RADIUS + h`. They **must not be intersected** by procedural terrain, and the
settlement side of each must remain recognisable. Therefore:

- Inside each patch's latitude/longitude bounding box (half-span `GLOBE_CONTINENT_SPAN / 2`
  = 0.1111 rad about `{lon, lat}`), the planet height is forced to a low plain
  (`h = PLANET_PATCH_PLAIN_H`, a small positive value), regardless of noise.
- Outside those boxes, synthesis is free.

This is asserted by test, not assumed (see 6).

### 4.5 Colour and lighting

Reuse the existing orbit-mode fog and sun light. Colour is per-vertex and assigned from
the height/biome table so the mesh needs no texture and adds no HTTP payload:

| band | h range | colour intent |
|---|---|---|
| abyss | h < -60 | near-black indigo |
| deep | -60..-20 | deep blue |
| shelf | -20..-1 | teal to pale shelf |
| shore | -1..+2 | sand |
| lowland | +2..+30 | latitude-dependent grass / taiga / desert |
| highland | +30..+90 | rock, greyer with altitude |
| summit | > 90 | snow above a latitude-adjusted snowline |

Polar caps: `abs(lat) > 1.25 rad` blends to ice, which also covers the two octave-1 polar
landmarks without a special case.

### 4.6 Mode switching and the `setOceanProjection` third state

`setOceanProjection(useGlobe)` becomes a three-way projection so the planet sphere, the
899.4 shell and the flat plane never fight:

- `useGlobe === false` -> flat plane visible, shell hidden, planet hidden (local views,
  exactly as today).
- `useGlobe === true` -> planet sphere visible, shell hidden, flat plane hidden (orbit).
- `useGlobe === "shell"` -> shell visible only (reserved for the legacy orbit appearance;
  unused by any caller in 10NS but retained so the existing
  `test_orbit_switches_ocean_to_sphere_and_back` contract is not silently broken).

### 4.7 Performance budget

A 360 x 180 equirect sample grid (129,600 positions) keeps the sphere smooth at the
10NM framing distance while staying inside the existing vertex budget for a software-
rendered render loop. Height and colour are computed once at build time into a single
`BufferGeometry`; nothing is recomputed per frame.

## 5. Strict Scope Boundary

1. No change to any backend module, cognition model, prompt, or action.
2. No change to canonical `true_map.json` / `continent_terrain.json`.
3. No change to local (human-scale) rendering: flat plane, `computeLocalPosition`,
   `computeContinentHeightField`, scenery, fauna and the camera framing constants.
4. No new HTTP payloads, no new textures, no new files served.
5. The 13 untracked viewer/cinema files are not staged.

## 6. Acceptance Criteria

1. `renderOrbitView` produces a sphere with visible curvature, multiple non-canonical
   landmasses, ocean depth variation and polar caps.
2. Instrumented render (THREE prototype hooks, as used in 10NJ/10NM) reports the planet
   mesh present and the flat ocean plane hidden in orbit mode, and both restored in local
   mode.
3. Local-mode camera settles at the same coordinates as before this phase (the 10NM
   baseline of roughly `[-7.5, 8.8, 26]`), proving no local framing drift.
4. `test_planet_height_is_flat_inside_canonical_patches` - inside every patch bbox the
   synthesised height equals `PLANET_PATCH_PLAIN_H`.
5. `test_planet_noise_is_seamless_and_deterministic` - equal values at `phi` and
   `phi + 2pi`, equal values at the poles, and identical output across two calls.
6. `test_planet_has_land_outside_canonical_patches` - a measurable fraction of sampled
   directions outside the two patch boxes are land, so the atlas is no longer empty.
7. All previously green suites remain green; `node --check` clean; CRLF=0;
   `git diff --check` clean.

## 7. Verification Protocol (same loop that caught 10NJ and 10NM)

1. Implement behind tests.
2. Run the four existing suites plus new tests.
3. Rebuild `viewer-deploy`, render East / West / Orbit with camera-settle detection.
4. **Read the screenshots myself** before reporting anything as working. Captions are not
   evidence; instrumented numbers and the image are.
