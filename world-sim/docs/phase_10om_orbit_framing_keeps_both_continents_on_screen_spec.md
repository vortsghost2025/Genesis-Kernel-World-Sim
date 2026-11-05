# Phase 10OM — Orbit Framing Keeps Both Continents On Screen (Specification)

## Defect (operator report, 2026-11-05)

After 10OK composited the two canonical continents into the planet, the
operator reported from the live globe: "it also seems like i only see one of
the 2 sections on the globe?"

## Root cause (measured, not guessed)

`GLOBE_PATCHES` puts cont_a at (lon -0.85, lat +0.30) and cont_b at
(lon +0.85, lat -0.30). In `computeGlobePosition` both patch centres have
x = cos(lat)·cos(lon) = +0.6304 (≈ +567 world units), mirrored in y and z;
they sit 101.8° apart on the sphere. The 10OK-era default orbit camera was
`orbitDir = (0.88, 0.42, 0.22).normalize()` at `dist = GLOBE_RADIUS * 3.2`,
which put cont_a ~59° and cont_b ~54° off the camera axis.

Projecting both patch centres with the live camera (probe run against the
deployed build) shows NDC x scales with 1/aspect:

| viewport | canvas aspect | cont_a ndcX | cont_b ndcX | on disc? |
|---|---|---|---|---|
| 1600×900 | 1.442 | +0.525 | -0.345 | both |
| 1200×900 | 0.969 | +0.781 | -0.513 | both |
| 1000×850 | 0.779 | +0.972 | -0.638 | both, cont_a at the very edge |
| 900×800  | 0.697 | **+1.086** | -0.713 | **cont_a OFF-SCREEN** |

So on any window narrower than ~1000 px the cont_a patch slides past the
right canvas edge and the globe reads as ONE continent. At wide windows
both are visible but asymmetric (0.525 vs -0.345), which is why the defect
was not caught in the 1600×900 verification renders.

## Fix (viewer-only)

Aim the default orbit camera along the exact bisector of the two patch
centres — +x with a slight 0.15 elevation — and stand off 4.5 radii:

- `const dist = GLOBE_RADIUS * 4.5;`
- `const orbitDir = new THREE.Vector3(1.0, 0.15, 0.0).normalize();`
- `domeScale` raised from `GLOBE_RADIUS * 4.2` to `GLOBE_RADIUS * 5.0` so the
  camera at 4.5R stays inside the sky dome.

At 4.5R both patch centres sit at 48°–55° off-axis and project to
|ndc| < 0.65 even at aspect 0.697, symmetric left/right of disc centre.
Sun positioning already derives from orbitDir, so the visible hemisphere
stays lit. `controls.maxDistance` (5R) and `camera.far` (8R) already
accommodate 4.5R.

## Verification plan

1. New regression test in `tests/test_planetary_globe.py`: project both
   patch centres with the real constants at aspects 1.442 / 0.969 / 0.779 /
   0.697 and assert both are in front of the camera and |ndc| < 0.9.
2. Update the two hardcoded framing constants in
   `test_orbit_framing_reaches_beyond_the_flat_ceiling_at_runtime`.
3. `node --check` on the extracted viewer script; full CI test list
   (89 files) plus the planetary/viewer suites locally.
4. Local renders at 1600×900, 1200×900 and 900×800, read as images: both
   continents fully on the disc in all three.
5. Deploy, re-pin the alias, and re-run the live NDC probe at 900×800 and
   1600×900 against the deployed URL.

## Out of scope

`GLOBE_PATCHES`, the 101.8° separation, planet geometry, local (flat) views,
and anything the agents can reach. 100% viewer-side framing change; no
cognition, prompt, behavioural or canonical change. Phase chain:
10OM (spec) → 10ON (metadata sync) → 10OO (implementation).
