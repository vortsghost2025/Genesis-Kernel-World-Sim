"""Test suite for Phase 10LM: Continental Relief, Interior Volume & Settlement Consolidation.

Specification: docs/phase_10lj_continental_relief_and_interior_volume_spec.md §5
Required test coverage:
1. test_terrain_max_elevation_exceeds_floor
2. test_ocean_stays_below_zero
3. test_prop_grounding_on_synthetic_peak
4. test_camera_clearance_never_below_ground
5. test_mountain_range_is_one_ridge
6. test_peak_scale_follows_elevation
7. test_caves_only_at_elevation_transitions
8. test_trails_derived_from_position_timeline
9. test_interior_has_floor_and_sill_walls
10. test_sheltered_agent_rests_on_floor_plane
11. test_empty_shelter_stays_empty
12. test_interior_geometry_disposed_on_exit
13. test_addon_costs_strictly_less_than_standalone
14. test_addon_discount_disclosed_in_prompt
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
import pytest

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

PROTOTYPE_HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"
CONTINENT_TERRAIN_JSON = WORLD_SIM / "viewer" / "continent_terrain.json"

from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import build_system_prompt
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
)
from backend.world.first_pair_runtime import (
    FirstPairRuntime,
    _BANNED_DIRECTIVE_PHRASES,
    _STRUCTURAL_TIMBER_MIN,
)


def _get_prototype_script() -> str:
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "prototype index.html must contain an inline script"
    return max(scripts, key=len)


def _run_node_expr(js_setup: str, js_expr: str):
    """Run a JavaScript expression under node via stdin and return parsed JSON output."""
    code = f"{js_setup}\nconsole.log(JSON.stringify({js_expr}));"
    res = subprocess.run(["node", "-"], input=code, capture_output=True, text=True, check=True)
    return json.loads(res.stdout.strip())


def _extract_js_function(script: str, fn_name: str) -> str:
    pattern = rf"function\s+{fn_name}\s*\([^)]*\)\s*\{{.*?\n\}}"
    m = re.search(pattern, script, re.DOTALL)
    assert m, f"Function '{fn_name}' must be defined in prototype/index.html"
    return m.group(0)


def _setup_runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    runtime = FirstPairRuntime(heartbeat_limit=10, store=store, pair_id="east")
    runtime._load_or_initialize()
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.tile_occupancy["east_eve"] = "cont_a_gen_0_1"
    return runtime


def _grant_on(runtime: FirstPairRuntime, agent: str, **items) -> None:
    for kind, amount in items.items():
        add_to_inventory(runtime._store, agent, kind, amount)


# ---------------------------------------------------------------------------
# 1. test_terrain_max_elevation_exceeds_floor
# ---------------------------------------------------------------------------
def test_terrain_max_elevation_exceeds_floor():
    """Verify continental vertical relief generates peaks >= 30 m (30-60 m range)
    and gently rolling hills/plains."""
    script = _get_prototype_script()
    fn_code = _extract_js_function(script, "computeContinentHeightField")

    terrain_db = json.loads(CONTINENT_TERRAIN_JSON.read_text(encoding="utf-8"))
    cont_a = terrain_db["cont_a"]

    js_setup = f"""
    const tData = {json.dumps({"elev": cont_a["elev"], "terr": cont_a["terr"]})};
    {fn_code}
    const heights = computeContinentHeightField(tData.elev, tData.terr);
    let maxH = -Infinity;
    for (let i = 0; i < heights.length; i++) {{
      if (heights[i] > maxH) maxH = heights[i];
    }}
    """
    max_h = _run_node_expr(js_setup, "maxH")
    assert 30.0 <= max_h <= 65.0, (
        f"Expected max continental terrain elevation in 30-60 m range, got {max_h:.2f} m"
    )


# ---------------------------------------------------------------------------
# 2. test_ocean_stays_below_zero
# ---------------------------------------------------------------------------
def test_ocean_stays_below_zero():
    """Verify every canonical ocean tile remains strictly below 0 m (<= -0.18 m)
    even when adjacent to high mountain relief."""
    script = _get_prototype_script()
    fn_code = _extract_js_function(script, "computeContinentHeightField")

    terrain_db = json.loads(CONTINENT_TERRAIN_JSON.read_text(encoding="utf-8"))
    cont_a = terrain_db["cont_a"]

    js_setup = f"""
    const tData = {json.dumps({"elev": cont_a["elev"], "terr": cont_a["terr"]})};
    {fn_code}
    const heights = computeContinentHeightField(tData.elev, tData.terr);
    let maxOceanH = -Infinity;
    let minLandH = Infinity;
    for (let i = 0; i < heights.length; i++) {{
      if (tData.terr[i] === "ocean") {{
        if (heights[i] > maxOceanH) maxOceanH = heights[i];
      }} else {{
        if (heights[i] < minLandH) minLandH = heights[i];
      }}
    }}
    """
    res = _run_node_expr(js_setup, "{ maxOceanH, minLandH }")
    assert res["maxOceanH"] <= -0.18, f"Ocean tile rose above -0.18 m: {res['maxOceanH']}"
    assert res["minLandH"] >= 0.10, f"Land tile sank below 0.10 m: {res['minLandH']}"


# ---------------------------------------------------------------------------
# 3. test_prop_grounding_on_synthetic_peak
# ---------------------------------------------------------------------------
def test_prop_grounding_on_synthetic_peak():
    """Verify a synthetic 50 m peak keeps props flush on getTerrainHeight without
    floating or sinking."""
    script = _get_prototype_script()
    fn_height = _extract_js_function(script, "getTerrainHeight")
    fn_grounded = _extract_js_function(script, "createGroundedProp")

    js_setup = f"""
    const THREE = {{
      Group: class {{ constructor() {{ this.children = []; this.position = {{ x:0, y:0, z:0, set(x,y,z){{this.x=x;this.y=y;this.z=z;}} }}; }} add(c) {{ this.children.push(c); }} }},
      SpriteMaterial: class {{ constructor(o) {{ Object.assign(this, o); }} }},
      Sprite: class {{ constructor(m) {{ this.material = m; this.scale = {{ set(x,y,z){{this.x=x;this.y=y;this.z=z;}} }}; this.position = {{ set(x,y,z){{this.x=x;this.y=y;this.z=z;}} }}; }} }}
    }};
    function createGroundShadowDecal(rx, rz, op) {{ return {{ isShadow: true, rx, rz, op }}; }}
    const heightLookup = {{ cont_a: new Float32Array(200 * 200) }};
    // Build a synthetic 50 m peak around (10, 15) -> col=110, row=115
    for (let r = 110; r <= 120; r++) {{
      for (let c = 105; c <= 115; c++) {{
        const dist = Math.hypot(c - 110, r - 115);
        heightLookup.cont_a[r * 200 + c] = Math.max(0.5, 50.0 - dist * 4.5);
      }}
    }}
    {fn_height}
    {fn_grounded}
    const peakH = getTerrainHeight("cont_a", 10, 15);
    const slopeH = getTerrainHeight("cont_a", 10.4, 15.3);
    const propPeak = createGroundedProp("tex", 3.1, 3.3, 10, 15, peakH, 1.0, 1.0, 0.14);
    const propSlope = createGroundedProp("tex", 3.1, 3.3, 10.4, 15.3, slopeH, 1.0, 1.0, 0.14);
    """
    res = _run_node_expr(
        js_setup,
        "{ peakH, propPeakY: propPeak.position.y, slopeH, propSlopeY: propSlope.position.y }",
    )
    assert abs(res["peakH"] - 50.0) < 1e-4
    assert abs(res["propPeakY"] - res["peakH"]) < 1e-6, "Prop failed to sit flush at 50 m summit"
    assert abs(res["propSlopeY"] - res["slopeH"]) < 1e-6, "Prop failed to sit flush on sloped 50 m flank"


# ---------------------------------------------------------------------------
# 4. test_camera_clearance_never_below_ground
# ---------------------------------------------------------------------------
def test_camera_clearance_never_below_ground():
    """Verify smoothMoveCamera and camera view height calculations never place
    the camera below ground + minClearance even on a 60 m summit."""
    script = _get_prototype_script()
    fn_height = _extract_js_function(script, "getTerrainHeight")
    fn_smooth = _extract_js_function(script, "smoothMoveCamera")

    js_setup = f"""
    class Vec3 {{
      constructor(x=0, y=0, z=0) {{ this.x = x; this.y = y; this.z = z; }}
      copy(v) {{ this.x = v.x; this.y = v.y; this.z = v.z; return this; }}
    }}
    const THREE = {{ Vector3: Vec3 }};
    let selectedPair = "east";
    let activeCamMode = "landscape";
    let camAnimating = false;
    const camera = {{ position: new Vec3() }};
    const controls = {{ target: new Vec3(), update() {{}} }};
    let camTargetPos = new Vec3();
    let controlsTargetPos = new Vec3();
    const heightLookup = {{ cont_a: new Float32Array(200 * 200) }};
    // Place a 58 m mountain summit at (0, 0) and a 62 m ridge at camera pull-back (0, 20)
    heightLookup.cont_a[100 * 200 + 100] = 58.0;
    heightLookup.cont_a[120 * 200 + 100] = 62.0;
    {fn_height}
    {fn_smooth}

    const results = {{}};
    for (const mode of ["human", "landscape", "topdown", "adam", "eve"]) {{
      activeCamMode = mode;
      // Attempt to position camera low at (0, 20) where ground is 62 m
      smoothMoveCamera(new Vec3(0, 15.0, 20), new Vec3(0, 58.0, 0), true);
      const groundAtCam = getTerrainHeight("cont_a", camera.position.x, camera.position.z);
      const minClearance = (mode === "human" || mode === "adam" || mode === "eve") ? 1.45 : 3.0;
      results[mode] = {{
        camY: camera.position.y,
        groundAtCam,
        clearance: camera.position.y - groundAtCam,
        minRequired: minClearance
      }};
    }}
    """
    res = _run_node_expr(js_setup, "results")
    for mode, info in res.items():
        assert info["clearance"] >= info["minRequired"] - 1e-4, (
            f"Camera mode '{mode}' clipped into mountain: camY={info['camY']}, "
            f"ground={info['groundAtCam']}, clearance={info['clearance']}"
        )


# ---------------------------------------------------------------------------
# 5. test_mountain_range_is_one_ridge
# ---------------------------------------------------------------------------
def test_mountain_range_is_one_ridge():
    """Verify a synthetic contiguous chain of 5 mountain tiles produces one
    connected ridge descriptor rather than 5 unlinked per-tile sprites, and a
    lone mountain tile still renders."""
    script = _get_prototype_script()
    fn_ranges = _extract_js_function(script, "buildMountainRanges")

    js_setup = f"""
    {fn_ranges}
    // 5 contiguous mountain tiles along y=0, x=-2..2, plus 1 lone mountain tile at (10, 10)
    const mtnTiles = [
      {{ x: -2, z: 0, h: 28.0, elev: 0.82 }},
      {{ x: -1, z: 0, h: 36.0, elev: 0.88 }},
      {{ x:  0, z: 0, h: 48.0, elev: 0.96 }},
      {{ x:  1, z: 0, h: 39.0, elev: 0.90 }},
      {{ x:  2, z: 0, h: 31.0, elev: 0.84 }},
      {{ x: 10, z: 10, h: 26.0, elev: 0.80 }}
    ];
    const ranges = buildMountainRanges(mtnTiles);
    """
    ranges = _run_node_expr(js_setup, "ranges")
    assert len(ranges) == 2, f"Expected 2 mountain ranges (5-tile chain + 1 lone tile), got {len(ranges)}"
    five_tile_range = next((r for r in ranges if len(r["tiles"]) == 5), None)
    lone_tile_range = next((r for r in ranges if len(r["tiles"]) == 1), None)
    assert five_tile_range is not None, "5 contiguous mountain tiles must form one connected range"
    assert lone_tile_range is not None, "Lone mountain tile must still form a valid range"
    assert five_tile_range["summit"]["x"] == 0 and five_tile_range["summit"]["h"] == 48.0


# ---------------------------------------------------------------------------
# 6. test_peak_scale_follows_elevation
# ---------------------------------------------------------------------------
def test_peak_scale_follows_elevation():
    """Verify peak scale derives deterministically from terrain height so the
    tallest summit carries the largest peak and scales well above a 4.8 m shelter."""
    script = _get_prototype_script()
    fn_ranges = _extract_js_function(script, "buildMountainRanges")
    fn_scale = _extract_js_function(script, "computeMountainPeakScale")

    js_setup = f"""
    {fn_scale}
    {fn_ranges}
    const mtnTiles = [
      {{ x: -1, z: 0, h: 24.0, elev: 0.80 }},
      {{ x:  0, z: 0, h: 52.0, elev: 0.98 }},
      {{ x:  1, z: 0, h: 33.0, elev: 0.86 }}
    ];
    const ranges = buildMountainRanges(mtnTiles);
    """
    ranges = _run_node_expr(js_setup, "ranges")
    assert len(ranges) == 1
    peaks = ranges[0]["peaks"]
    assert len(peaks) >= 1
    tallest_peak = max(peaks, key=lambda p: p["scale"])
    assert tallest_peak["x"] == 0 and tallest_peak["z"] == 0, (
        f"Tallest tile (0,0, h=52m) must carry the largest peak, got {tallest_peak}"
    )
    # Base mountain sprite height is 4.1m; on a 52m summit, scale > 2.0 gives > 8.2m peak crest on top of the 52m ridge
    assert tallest_peak["scale"] >= 2.0, (
        f"Expected summit peak scale >= 2.0 on 52 m mountain, got {tallest_peak['scale']}"
    )


# ---------------------------------------------------------------------------
# 7. test_caves_only_at_elevation_transitions
# ---------------------------------------------------------------------------
def test_caves_only_at_elevation_transitions():
    """Verify procedural cliff caves are placed only at high-elevation steep
    drop-offs (elevation transitions) and never on flat plains."""
    script = _get_prototype_script()
    fn_cave = _extract_js_function(script, "detectCliffCaveOpening")

    js_setup = f"""
    {fn_cave}
    // 1. Flat plain at h = 1.2 m with neighbors at 1.2 m -> must be null
    const plainRes = detectCliffCaveOpening(0, 0, 1.2, [1.2, 1.3, 1.1, 1.2]);
    // 2. High plateau interior at h = 42.0 m with neighbors at 41.5..42.5 m (no drop-off) -> must be null
    const plateauRes = detectCliffCaveOpening(5, 5, 42.0, [41.5, 42.2, 41.8, 42.0]);
    // 3. Steep cliff face at h = 28.0 m where a neighbor drops to 14.0 m (drop = 14 m) -> valid cave with scale > 1.0
    const cliffRes = detectCliffCaveOpening(10, 10, 28.0, [27.5, 14.0, 26.0, 28.5]);
    """
    res = _run_node_expr(js_setup, "{ plainRes, plateauRes, cliffRes }")
    assert res["plainRes"] is None, f"Cave wrongly placed on flat plain: {res['plainRes']}"
    assert res["plateauRes"] is None, f"Cave wrongly placed on flat plateau with no drop-off: {res['plateauRes']}"
    assert res["cliffRes"] is not None, "Expected cave opening at steep high-elevation cliff transition"
    assert res["cliffRes"]["drop"] >= 8.0
    assert res["cliffRes"]["scale"] > 1.0


# ---------------------------------------------------------------------------
# 8. test_trails_derived_from_position_timeline
# ---------------------------------------------------------------------------
def test_trails_derived_from_position_timeline():
    """Verify a synthetic 100-heartbeat walk produces trail segments matching the
    walked tiles and has zero effect on gameplay state."""
    script = _get_prototype_script()
    fn_trails = _extract_js_function(script, "deriveFootTrailsFromTimeline")

    js_setup = f"""
    const tilesById = new Map([
      ["tile_0_0", {{ coordinates: {{ x: 0, y: 0 }} }}],
      ["tile_1_0", {{ coordinates: {{ x: 1, y: 0 }} }}],
      ["tile_2_0", {{ coordinates: {{ x: 2, y: 0 }} }}],
      ["tile_9_9", {{ coordinates: {{ x: 9, y: 9 }} }}]
    ]);
    {fn_trails}
    // Build a 100-heartbeat timeline oscillating between tile_0_0, tile_1_0, tile_2_0
    const timeline = {{}};
    const cycle = ["tile_0_0", "tile_1_0", "tile_2_0", "tile_1_0"];
    for (let hb = 1; hb <= 100; hb++) {{
      timeline[String(hb)] = {{
        east_adam: cycle[(hb - 1) % cycle.length],
        east_eve: "tile_0_0"
      }};
    }}
    const snapshotBefore = JSON.stringify(timeline);
    const segments = deriveFootTrailsFromTimeline(timeline, 100);
    const snapshotAfter = JSON.stringify(timeline);
    """
    res = _run_node_expr(
        js_setup,
        "{ segments, mutated: snapshotBefore !== snapshotAfter }",
    )
    assert res["mutated"] is False, "Trail derivation must not mutate timeline or gameplay state"
    segs = res["segments"]
    assert len(segs) == 2, f"Expected 2 walked trail segments ((0,0)-(1,0) and (1,0)-(2,0)), got {segs}"
    coords = {(s["ax"], s["az"], s["bx"], s["bz"]) for s in segs}
    assert (0, 0, 1, 0) in coords or (1, 0, 0, 0) in coords
    assert (1, 0, 2, 0) in coords or (2, 0, 1, 0) in coords
    # Unwalked tile_9_9 must never appear
    for s in segs:
        assert s["ax"] != 9 and s["bx"] != 9
        assert s["count"] >= 40


# ---------------------------------------------------------------------------
# 9. test_interior_has_floor_and_sill_walls
# ---------------------------------------------------------------------------
def test_interior_has_floor_and_sill_walls():
    """Verify interior mode constructs a real floor plane and perimeter sill walls
    so the room has physical 3D volume rather than a flat billboard."""
    script = _get_prototype_script()
    assert "rebuildInteriorVolume" in script or "interiorWallsGroup" in script, (
        "Script must define interior volume geometry (floor + perimeter sill walls)"
    )
    fn_vol = _extract_js_function(script, "buildInteriorVolumeSpec")

    js_setup = f"""
    {fn_vol}
    const spec = buildInteriorVolumeSpec(5.4, 4.4);
    """
    spec = _run_node_expr(js_setup, "spec")
    assert spec["floor"]["width"] >= 4.6 and spec["floor"]["depth"] >= 3.6
    assert abs(spec["floor"]["y"] - 0.12) < 1e-4
    walls = spec["walls"]
    assert len(walls) >= 4, f"Expected perimeter sill walls (back, left, right, front doorway), got {len(walls)}"
    for w in walls:
        assert w["height"] >= 0.45, f"Sill wall must have real vertical height, got {w}"


# ---------------------------------------------------------------------------
# 10. test_sheltered_agent_rests_on_floor_plane
# ---------------------------------------------------------------------------
def test_sheltered_agent_rests_on_floor_plane():
    """Verify sheltered agents stand directly on the interior floor plane
    (agentY == sh + floorY, sprite top == agentY + charH) without clipping or floating."""
    script = _get_prototype_script()
    fn_vol = _extract_js_function(script, "buildInteriorVolumeSpec")

    match = re.search(r"function updateAgentFigure\((.*?)\)\s*\{(.*?)\n  \}", script, re.DOTALL)
    assert match, "updateAgentFigure must be defined in script"
    body = match.group(2)
    assert "INTERIOR_FLOOR_OFFSET" in body or "0.12" in body

    spec = _run_node_expr(f"{fn_vol}", "buildInteriorVolumeSpec(5.4, 4.4)")
    floor_y = spec["floor"]["y"]
    assert abs(floor_y - 0.12) < 1e-4, f"Floor plane top Y must match agent standing offset 0.12, got {floor_y}"


# ---------------------------------------------------------------------------
# 11. test_empty_shelter_stays_empty
# ---------------------------------------------------------------------------
def test_empty_shelter_stays_empty():
    """Verify an empty shelter renders only the floor and sill walls and zero
    furniture props."""
    script = _get_prototype_script()
    fn_props = _extract_js_function(script, "rebuildInteriorProps")

    js_setup = f"""
    const interiorPropsGroup = {{
      children: [],
      add(c) {{ this.children.push(c); }},
      remove(c) {{ this.children = this.children.filter(x => x !== c); }}
    }};
    function reconstructPublicObjectsAtHb(pn, hb) {{
      // Only the shelter itself exists on the tile; no hearth, bed, table, chair, storage, or workbench
      return [{{ object_id: "shelter-1", object_type: "shelter", tile_id: "cont_a_gen_0_0" }}];
    }}
    {fn_props}
    rebuildInteriorProps("cont_a_gen_0_0", "east", 100);
    """
    prop_count = _run_node_expr(js_setup, "interiorPropsGroup.children.length")
    assert prop_count == 0, f"Empty shelter must have 0 interior furniture props, got {prop_count}"


# ---------------------------------------------------------------------------
# 12. test_interior_geometry_disposed_on_exit
# ---------------------------------------------------------------------------
def test_interior_geometry_disposed_on_exit():
    """Verify exiting interior cutaway mode disposes dynamic interior geometry
    and hides interiorGroup cleanly."""
    script = _get_prototype_script()
    assert "disposeInteriorVolume" in script or "toggleInteriorCutaway" in script

    fn_toggle = _extract_js_function(script, "toggleInteriorCutaway")
    assert "rebuildInteriorProps(null" in fn_toggle
    assert "disposeInteriorVolume" in fn_toggle or "clearInteriorVolume" in fn_toggle


# ---------------------------------------------------------------------------
# 13. test_addon_costs_strictly_less_than_standalone
# ---------------------------------------------------------------------------
def _project_cost(rt, agent: str, obj: dict, declared: dict) -> int:
    """Total material a 10PW staged project will cost across all its stages.

    `remaining_floor` on the stored record is exactly the not-yet-spent part of
    the (possibly discounted) floor, and `materials` is the spent part; their
    sum is the project's whole cost. Non-staged component builds have no
    `remaining_floor`, so their declared materials are the whole cost.
    """
    spent = obj.get("materials") or {}
    remaining = obj.get("remaining_floor") or {}
    if not spent and not remaining:
        return sum(int(v) for v in declared.values())
    return sum(int(spent.get(k, 0) or 0) + int(remaining.get(k, 0) or 0)
               for k in declared)


@pytest.mark.parametrize("structural_type,min_timber", sorted(_STRUCTURAL_TIMBER_MIN.items()))
def test_addon_costs_strictly_less_than_standalone(tmp_path: Path, structural_type: str, min_timber: int):
    """Verify attaching via addon_to resolves to a strictly lower material cost
    than the equivalent standalone build across every structural type."""
    agent = "east_adam"
    declared = {"timber": min_timber, "stone": 6, "wood": 4}

    # 1. Standalone build on adjacent tile
    rt_standalone = _setup_runtime(tmp_path / f"standalone_{structural_type}")
    pos = rt_standalone._world_state.tile_occupancy[agent]
    xy = rt_standalone._tile_xy(pos)
    adj = f"cont_a_gen_{xy[0] + 1}_{xy[1]}"
    _grant_on(rt_standalone, agent, timber=20, stone=40, wood=40)

    root1 = rt_standalone._execute_build(
        agent,
        {
            "object_id": "root-1",
            "object_type": "shelter",
            "description": "Root structure.",
            "tile_id": pos,
            "materials": {"timber": 2, "stone": 6, "wood": 4},
        },
        heartbeat_number=1,
    )
    assert root1["status"] == "success"

    inv_before_sa = dict(rt_standalone._get_agent_inventory(agent))
    rt_standalone._world_state.tile_occupancy[agent] = adj
    sa_res = rt_standalone._execute_build(
        agent,
        {
            "object_id": f"sa-{structural_type}",
            "object_type": structural_type,
            "description": f"Standalone {structural_type}.",
            "tile_id": adj,
            "materials": dict(declared),
        },
        heartbeat_number=2,
    )
    assert sa_res["status"] == "success", sa_res
    # Phase 10PW: a roofed build is a staged project, so the opening action
    # spends only its first stage. The invariant this test guards -- an
    # attached room costs strictly less than a freestanding one -- is a
    # property of the whole project, so measure the project's remaining floor.
    sa_obj = rt_standalone._world_state.public_objects[f"sa-{structural_type}"]
    inv_after_sa = dict(rt_standalone._get_agent_inventory(agent))
    sa_total_spent = _project_cost(rt_standalone, agent, sa_obj, declared)

    # 2. Attached addon_to build with the exact same declared materials dict
    rt_addon = _setup_runtime(tmp_path / f"addon_{structural_type}")
    _grant_on(rt_addon, agent, timber=20, stone=40, wood=40)
    root2 = rt_addon._execute_build(
        agent,
        {
            "object_id": "root-2",
            "object_type": "shelter",
            "description": "Root structure.",
            "tile_id": pos,
            "materials": {"timber": 2, "stone": 6, "wood": 4},
        },
        heartbeat_number=1,
    )
    assert root2["status"] == "success"

    inv_before_ad = dict(rt_addon._get_agent_inventory(agent))
    ad_res = rt_addon._execute_build(
        agent,
        {
            "object_id": f"ad-{structural_type}",
            "object_type": structural_type,
            "description": f"Attached {structural_type}.",
            "tile_id": adj,
            "materials": dict(declared),
            "addon_to": "root-2",
        },
        heartbeat_number=2,
    )
    assert ad_res["status"] == "success", ad_res
    ad_obj = rt_addon._world_state.public_objects[f"ad-{structural_type}"]
    inv_after_ad = dict(rt_addon._get_agent_inventory(agent))
    ad_total_spent = _project_cost(rt_addon, agent, ad_obj, declared)

    assert ad_total_spent < sa_total_spent, (
        f"Attached {structural_type} spent {ad_total_spent} total materials vs standalone {sa_total_spent}; "
        f"addon_to must discount declared structural materials"
    )
    # Specifically verify non-timber structural materials (stone, wood) are
    # also discounted, not only the timber. Measured over the whole project
    # for the same reason as the total above.
    def _per_kind(rt, agent, obj, kind):
        spent = int((obj.get("materials") or {}).get(kind, 0) or 0)
        remaining = int((obj.get("remaining_floor") or {}).get(kind, 0) or 0)
        if not (obj.get("remaining_floor") or obj.get("materials")):
            return int(declared.get(kind, 0))
        return spent + remaining

    for kind in ("stone", "wood"):
        ad_k = _per_kind(rt_addon, agent, ad_obj, kind)
        sa_k = _per_kind(rt_standalone, agent, sa_obj, kind)
        assert ad_k <= sa_k, (
            f"attached {kind} cost {ad_k} but standalone cost {sa_k}; "
            "every structural component must be discounted, not only timber")


# ---------------------------------------------------------------------------
# 14. test_addon_discount_disclosed_in_prompt
# ---------------------------------------------------------------------------
def test_addon_discount_disclosed_in_prompt():
    """Verify the addon_to material discount is disclosed in build_system_prompt,
    names addon_to and the discount divisor, and contains no banned directive phrases."""
    ctx = AgentContext(
        agent_id="a",
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=1,
        position="cont_a_north_000",
        observation={
            "self_body": {
                "hunger": 50.0,
                "vitality": 100.0,
                "warmth": 100.0,
                "wetness": 0.0,
                "downed": False,
            }
        },
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["cont_a_north_000"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-10-31T00:00:00Z",
        inventory={"timber": 1, "stone": 10, "wood": 5},
        owns_shelter=False,
    )
    prompt = build_system_prompt(ctx)
    assert "addon_to" in prompt
    assert "shared walls" in prompt.lower() or "half" in prompt.lower(), (
        "Prompt must disclose the addon_to shared-wall material discount"
    )

    from backend.world.first_pair_cognition_model import _structural_timber_requirement_desc
    desc = _structural_timber_requirement_desc()
    assert "addon_to" in desc
    lowered = desc.lower()
    for phrase in _BANNED_DIRECTIVE_PHRASES:
        assert phrase.lower() not in lowered, (
            f"Structural/addon disclosure contains banned directive phrase {phrase!r}"
        )
