# Phase 10OP — Settlement Camera Presets + Follow-Agent (Specification)

## Operator request (2026-11-06)

After 10OO kept both continents on the orbit disc, the operator picked the
viewer follow-up from the menu: add settlement camera presets and a
follow-agent toggle to the local (East/West) views. Approved with "go".

## Current state (measured in source, not guessed)

- `world-sim/viewer/prototype/index.html` camera toolbar (lines ~708-715)
  has six buttons: human, landscape, focus Adam, focus Eve, top-down,
  interior. There is no settlement-specific preset.
- `applyCameraMode("landscape")` already blends a settlement centroid into
  the framing: it averages every `PAIRS[pairName].public_objects[*].tile_id`
  coordinate (78%) with the Adam/Eve midpoint (22%). That is a blended
  overview, not a settlement preset, and it still weights the agents.
- `applyCameraMode("adam"|"eve")` re-aims only when `syncHeartbeatScene`
  sees a new `currentHb` (or an explicit immediate call). During playback,
  `updateAllAgentFigures` interpolates the figure between the previous and
  current tile every animation frame, so the camera target can sit a full
  tile behind the visible figure mid-stride. There is no continuous
  per-frame follow state.
- Live exported data on 2026-11-06: east has 184 public objects (campfires,
  shelters, lean-tos, landmarks, storage, food processors) around
  `cont_a_origin_001` and nearby `cont_a_gen_*` tiles at hb 10256; west has
  394 public objects (shelters, cabins, storage, crafting surfaces, forges,
  landmarks, roads, walls, furniture) clustered around `cont_b_gen_34..39_47..55`
  at hb 10877. A dynamic centroid is therefore more honest than hardcoding
  one camp tile that may drift as the lanes build.

## Fix (viewer-only)

1. Add one pure helper, `getSettlementCentroid(pairName)`, that reads
   `PAIRS[pairName].public_objects`, resolves each `tile_id` through
   `tilesById` coordinates, falls back to the existing
   `/_(-?\d+)_(-?\d+)$/` id parse when the tile record is missing, and
   returns `{ x, z, count }` or `null` when there are no usable objects.
   Refactor the existing landscape branch to call this helper so the blend
   math cannot drift from the new preset.

2. Add a `"settlement"` camera mode and a `🏘️ Settlement` button
   (`#cam-settlement`) in the camera toolbar. In local East/West views it
   frames the settlement centroid purely: fov 48, fog density 0.0018,
   camera south of the centroid with the same line-of-sight terrain
   clearance sampling the landscape mode uses, target at the centroid.
   If `getSettlementCentroid` returns null, fall back to the Adam/Eve
   midpoint (not the continent origin) so an object-less lane still gets a
   sensible view. In orbit/World Atlas the existing orbit branch still
   wins; the settlement button is inert there exactly like the other local
   camera buttons.

3. Add a follow-agent state `followAgent` (`null | "adam" | "eve"`) with
   two toggle buttons `🎥 Adam` (`#cam-follow-adam`) and `🎥 Eve`
   (`#cam-follow-eve`), class `cam-btn follow-btn` so the mode-button
   active-class sweep does not erase their state. Clicking the active
   follow button clears the follow; clicking the other agent switches the
   follow target. Enabling follow performs one `applyCameraMode(agent)`
   framing, then the `animate` loop, after `updateAllAgentFigures`,
   translates `camera.position` by the same delta that moves
   `controls.target` onto the agent figure's chest and calls
   `controls.update()`. That preserves the operator's zoom/orbit offset
   while tracking the per-frame interpolated figure position. Follow is
   disabled in orbit mode and cleared when the operator switches civ or
   picks a non-agent camera mode.

4. Expose `followAgent` in `window.__GENESIS_PROTO__.getState()` and add a
   `setFollowAgent(agent)` proto method so browser probes can verify the
   toggle without private state access.

## Verification plan

1. New tests in `world-sim/tests/test_viewer_settlement_follow.py`:
   - Node-extract `getSettlementCentroid` with stubbed `PAIRS`/`tilesById`:
     coordinate-bearing tile ids, regex-fallback ids (`cont_b_gen_35_51`),
     mixed input, and empty objects returning null.
   - Static contract tests: the three buttons exist; their onclick handlers
     are wired; `applyCameraMode` has a `settlement` branch that activates
     `#cam-settlement` and calls `getSettlementCentroid`; the animate loop
     contains the follow-agent delta block before `renderer.render`; the
     proto API exposes `followAgent` and `setFollowAgent`.
2. `node --check` on the extracted inline viewer script.
3. Targeted pytest suites: new file plus `test_planetary_globe.py`,
   `test_continental_relief.py`, `test_viewer_data_contract.py`,
   `test_viewer_legibility.py`, `test_viewer_fidelity.py`; then the CI list
   locally if time permits (browser-runtime-only failures that already fail
   identically on HEAD stay out of scope).
4. `git diff --check` exit 0, CRLF count 0 for touched files, phase-ID
   uniqueness regex `10[A-Z][A-Z]` still holds.
5. Local Playwright renders at 1600x900 and 900x800 for east and west:
   settlement mode target equals the exported public-object centroid within
   1e-6; follow Adam moves the camera target with the figure across two
   heartbeats; screenshots read with the model's own vision for page errors
   and framing.
6. Deploy the viewer build, curl the deployment URL and the pretty alias for
   HTTP 200, and run a live browser probe: `applyCameraMode("settlement")`
   target matches the live centroid, and `setFollowAgent("adam")` +
   `setHeartbeat` across a movement changes the camera target.

## Out of scope

No backend, cognition, prompt, behavioural, canonical, `GLOBE_PATCHES`,
orbit-framing or agent-reachable changes. No `world-sim/data` writes. Local
camera/UI only; orbit keeps the 10OO framing. Phase chain:
10OP (spec) → 10OQ (metadata sync) → 10OR (implementation).
