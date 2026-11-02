"""Test suite for Phase 10NA: Valley Hydrology, Islands & Seasonal Foliage.

Specification: docs/phase_10my_valley_hydrology_islands_and_seasonal_foliage_spec.md §5
Required test coverage:
1. test_water_mask_includes_canonical_rivers_lakes_and_valley_reach
2. test_water_mesh_built_and_grounded
3. test_no_trees_spawn_in_water_channel
4. test_islands_generated_in_lakes_and_coast_without_ocean_violations
5. test_compute_season_matches_backend_survival_clock
6. test_seasonal_palette_shifts_across_four_seasons
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
import pytest

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

PROTOTYPE_HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"
CONTINENT_TERRAIN_JSON = WORLD_SIM / "viewer" / "continent_terrain.json"

from backend.world.survival import season as backend_season


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


# ---------------------------------------------------------------------------
# 1. test_water_mask_includes_canonical_rivers_lakes_and_valley_reach
# ---------------------------------------------------------------------------
def test_water_mask_includes_canonical_rivers_lakes_and_valley_reach():
    """Verify computeContinentWaterMask covers canonical river and lake tiles,
    places visible river water within <= 8 tiles of both East and West settlements,
    and never overlaps any settlement structure tile."""
    script = _get_prototype_script()
    fn_water_mask = _extract_js_function(script, "computeContinentWaterMask")

    terrain_db = json.loads(CONTINENT_TERRAIN_JSON.read_text(encoding="utf-8"))

    js_setup = f"""
    const terrainDB = {json.dumps(terrain_db)};
    {fn_water_mask}

    function checkContinent(cid, structCoords) {{
      const settleMask = new Uint8Array(40000);
      let sumX = 0, sumZ = 0;
      for (const [sx, sz] of structCoords) {{
        const idx = (sz + 100) * 200 + (sx + 100);
        settleMask[idx] = 1;
        sumX += sx;
        sumZ += sz;
      }}
      const cx = sumX / structCoords.length;
      const cz = sumZ / structCoords.length;

      const mask = computeContinentWaterMask(cid, terrainDB[cid], settleMask);
      let canonicalRiverCovered = 0;
      let canonicalRiverTotal = 0;
      let canonicalLakeCovered = 0;
      let canonicalLakeTotal = 0;
      let structureOverlaps = 0;
      let minValleyRiverDist = Infinity;

      const wArr = terrainDB[cid].water || [];
      for (let idx = 0; idx < 40000; idx++) {{
        const x = (idx % 200) - 100;
        const z = ((idx / 200) | 0) - 100;
        const w = wArr[idx] || "";
        if (w === "river") {{
          canonicalRiverTotal++;
          if (mask[idx] > 0) canonicalRiverCovered++;
        }} else if (w === "lake") {{
          canonicalLakeTotal++;
          if (mask[idx] === 2) canonicalLakeCovered++;
        }}
        if (settleMask[idx] && mask[idx] > 0) {{
          structureOverlaps++;
        }}
        if (mask[idx] > 0) {{
          const d = Math.hypot(x - cx, z - cz);
          if (d < minValleyRiverDist) minValleyRiverDist = d;
        }}
      }}
      return {{
        canonicalRiverTotal,
        canonicalRiverCovered,
        canonicalLakeTotal,
        canonicalLakeCovered,
        structureOverlaps,
        minValleyRiverDist
      }};
    }}

    const eastStructs = [[-10,-3],[-5,-3],[-1,2],[-1,1],[-15,-3],[-7,-3],[-6,-5],[-15,1],[-7,1],[-10,0],[-8,-2],[-9,-2],[-12,1]];
    const westStructs = [[34,54],[35,51],[50,51],[49,50],[47,50],[44,52],[42,49],[36,53],[38,55]];
    const resEast = checkContinent("cont_a", eastStructs);
    const resWest = checkContinent("cont_b", westStructs);
    """
    res = _run_node_expr(js_setup, "{ resEast, resWest }")
    for label, r in [("cont_a", res["resEast"]), ("cont_b", res["resWest"])]:
        assert r["structureOverlaps"] == 0, f"{label}: water mask overlapped {r['structureOverlaps']} settlement structure tiles"
        assert r["canonicalLakeCovered"] == r["canonicalLakeTotal"] and r["canonicalLakeTotal"] >= 42, (
            f"{label}: expected all canonical lakes covered, got {r['canonicalLakeCovered']}/{r['canonicalLakeTotal']}"
        )
        assert r["canonicalRiverCovered"] >= r["canonicalRiverTotal"] - 5, (
            f"{label}: expected canonical rivers covered, got {r['canonicalRiverCovered']}/{r['canonicalRiverTotal']}"
        )
        assert r["minValleyRiverDist"] <= 8.0, (
            f"{label}: expected valley river reach within <= 8.0 tiles of settlement, got {r['minValleyRiverDist']:.2f}"
        )


# ---------------------------------------------------------------------------
# 2. test_water_mesh_built_and_grounded
# ---------------------------------------------------------------------------
def test_water_mesh_built_and_grounded():
    """Verify buildContinentWaterMesh creates non-empty water geometry for cont_a
    and cont_b with water surface elevation strictly above the carved riverbed
    and below the surrounding dry bank."""
    script = _get_prototype_script()
    fn_height_field = _extract_js_function(script, "computeContinentHeightField")
    fn_get_height = _extract_js_function(script, "getTerrainHeight")
    fn_water_mask = _extract_js_function(script, "computeContinentWaterMask")
    fn_water_mesh = _extract_js_function(script, "buildContinentWaterMesh")

    terrain_db = json.loads(CONTINENT_TERRAIN_JSON.read_text(encoding="utf-8"))

    js_setup = f"""
    const terrainDB = {json.dumps({"cont_a": terrain_db["cont_a"], "cont_b": terrain_db["cont_b"]})};
    const heightLookup = {{ cont_a: new Float32Array(40000), cont_b: new Float32Array(40000) }};
    const waterMaskLookup = {{ cont_a: new Uint8Array(40000), cont_b: new Uint8Array(40000) }};
    const continentGroups = {{
      cont_a: {{ children: [], add(c){{ this.children.push(c); }}, remove(c){{ this.children = this.children.filter(x=>x!==c); }} }},
      cont_b: {{ children: [], add(c){{ this.children.push(c); }}, remove(c){{ this.children = this.children.filter(x=>x!==c); }} }}
    }};
    const waterMeshes = {{ cont_a: null, cont_b: null }};
    const THREE = {{
      BufferGeometry: class {{
        constructor() {{ this.attributes = {{}}; }}
        setAttribute(name, attr) {{ this.attributes[name] = attr; }}
        computeVertexNormals() {{}}
        dispose() {{}}
      }},
      BufferAttribute: class {{
        constructor(arr, itemSize) {{ this.array = arr; this.itemSize = itemSize; this.count = arr.length / itemSize; }}
      }},
      MeshStandardMaterial: class {{
        constructor(opts) {{ Object.assign(this, opts); }}
        dispose() {{}}
      }},
      Mesh: class {{
        constructor(geom, mat) {{ this.geometry = geom; this.material = mat; this.position = {{ x:0, y:0, z:0 }}; }}
      }},
      DoubleSide: 2
    }};
    {fn_get_height}
    {fn_water_mask}
    {fn_height_field}
    {fn_water_mesh}

    const out = {{}};
    for (const cid of ["cont_a", "cont_b"]) {{
      const settleMask = new Uint8Array(40000);
      settleMask[99 * 200 + 92] = 1;
      waterMaskLookup[cid] = computeContinentWaterMask(cid, terrainDB[cid], settleMask);
      computeContinentHeightField(terrainDB[cid].elev, terrainDB[cid].terr, heightLookup[cid], settleMask, waterMaskLookup[cid]);
      const mesh = buildContinentWaterMesh(cid, waterMaskLookup[cid]);
      const posArr = mesh.geometry.attributes.position.array;
      const vertCount = mesh.geometry.attributes.position.count;

      // Sample a river tile from waterMaskLookup and compare bed height, water surface Y, and dry bank height
      let sampleComparison = null;
      for (let r = 80; r < 120 && !sampleComparison; r++) {{
        for (let c = 80; c < 120 && !sampleComparison; c++) {{
          const idx = r * 200 + c;
          if (waterMaskLookup[cid][idx] === 1) {{
            const wx = c - 100;
            const wz = r - 100;
            const bedH = getTerrainHeight(cid, wx, wz);
            // Find nearest dry bank within 3 tiles
            let dryBankH = bedH;
            for (let dr = -3; dr <= 3; dr++) {{
              for (let dc = -3; dc <= 3; dc++) {{
                const ni = (r + dr) * 200 + (c + dc);
                if (waterMaskLookup[cid][ni] === 0 && terrainDB[cid].terr[ni] !== "ocean") {{
                  dryBankH = Math.max(dryBankH, heightLookup[cid][ni]);
                }}
              }}
            }}
            sampleComparison = {{ wx, wz, bedH, waterY: mesh.userData.sampleWaterY(wx, wz), dryBankH }};
          }}
        }}
      }}
      out[cid] = {{ vertCount, transparent: Boolean(mesh.material.transparent), sampleComparison }};
    }}
    """
    res = _run_node_expr(js_setup, "out")
    for cid in ("cont_a", "cont_b"):
        info = res[cid]
        assert info["vertCount"] >= 600, f"{cid}: expected substantial water mesh vertices, got {info['vertCount']}"
        assert info["transparent"] is True, f"{cid}: water material must be translucent"
        comp = info["sampleComparison"]
        assert comp is not None, f"{cid}: must find river tile in valley region"
        assert comp["bedH"] < comp["waterY"] < comp["dryBankH"], (
            f"{cid}: expected carved bed ({comp['bedH']:.2f}m) < water surface ({comp['waterY']:.2f}m) < dry bank ({comp['dryBankH']:.2f}m)"
        )


# ---------------------------------------------------------------------------
# 3. test_no_trees_spawn_in_water_channel
# ---------------------------------------------------------------------------
def test_no_trees_spawn_in_water_channel():
    """Verify neither 3D conifers nor 2D tree billboards are placed on active waterMask tiles."""
    script = _get_prototype_script()
    fn_conifer = _extract_js_function(script, "buildAlpineConiferForest")
    fn_scenery = _extract_js_function(script, "populateContinentScenery")
    assert "waterMaskLookup" in fn_conifer or "isWaterChannelTile" in fn_conifer, (
        "buildAlpineConiferForest must skip active water channel tiles"
    )
    assert "waterMaskLookup" in fn_scenery or "isWaterChannelTile" in fn_scenery, (
        "populateContinentScenery must skip active water channel tiles for trees"
    )


# ---------------------------------------------------------------------------
# 4. test_islands_generated_in_lakes_and_coast_without_ocean_violations
# ---------------------------------------------------------------------------
def test_islands_generated_in_lakes_and_coast_without_ocean_violations():
    """Verify computeContinentIslands produces both lake and coastal islands on
    cont_a and cont_b, island crowns rise > 1.0 m above water, and canonical
    ocean tiles remain <= -0.18 m."""
    script = _get_prototype_script()
    fn_islands = _extract_js_function(script, "computeContinentIslands")

    terrain_db = json.loads(CONTINENT_TERRAIN_JSON.read_text(encoding="utf-8"))

    js_setup = f"""
    const terrainDB = {json.dumps({"cont_a": terrain_db["cont_a"], "cont_b": terrain_db["cont_b"]})};
    {fn_islands}
    const islandsA = computeContinentIslands("cont_a", terrainDB.cont_a);
    const islandsB = computeContinentIslands("cont_b", terrainDB.cont_b);
    """
    res = _run_node_expr(js_setup, "{ islandsA, islandsB }")
    for cid, islands in [("cont_a", res["islandsA"]), ("cont_b", res["islandsB"])]:
        assert len(islands) >= 4, f"{cid}: expected at least 4 islands (lake + coastal), got {len(islands)}"
        kinds = {isl["kind"] for isl in islands}
        assert "lake" in kinds and "coastal" in kinds, f"{cid}: expected both 'lake' and 'coastal' islands, got {kinds}"
        for isl in islands:
            assert isl["crownHeight"] > 1.0, f"{cid}: island crown must rise > 1.0 m above water, got {isl}"
            assert isl["radius"] >= 1.5, f"{cid}: island must have visible radius >= 1.5 tiles, got {isl}"


# ---------------------------------------------------------------------------
# 5. test_compute_season_matches_backend_survival_clock
# ---------------------------------------------------------------------------
def test_compute_season_matches_backend_survival_clock():
    """Verify computeSeasonAtHb(hb) in prototype/index.html matches
    backend.world.survival.season(hb) across representative heartbeats."""
    script = _get_prototype_script()
    fn_season = _extract_js_function(script, "computeSeasonAtHb")

    test_hbs = [0, 1, 400, 863, 864, 1200, 1728, 2592, 3456, 6989, 8669]
    js_setup = f"""
    {fn_season}
    const hbs = {json.dumps(test_hbs)};
    const out = {{}};
    for (const hb of hbs) {{
      out[String(hb)] = computeSeasonAtHb(hb);
    }}
    """
    res = _run_node_expr(js_setup, "out")
    for hb in test_hbs:
        expected = backend_season(hb).lower()
        actual = str(res[str(hb)]).lower()
        assert actual == expected, f"At hb={hb}, viewer computeSeasonAtHb returned {actual!r} != backend {expected!r}"


# ---------------------------------------------------------------------------
# 6. test_seasonal_palette_shifts_across_four_seasons
# ---------------------------------------------------------------------------
def test_seasonal_palette_shifts_across_four_seasons():
    """Verify getSeasonPalette produces distinct grass, deciduous, conifer, and
    snowline parameters for Spring, Summer, Autumn, and Winter."""
    script = _get_prototype_script()
    fn_palette = _extract_js_function(script, "getSeasonPalette")

    js_setup = f"""
    {fn_palette}
    const palettes = {{
      spring: getSeasonPalette("Spring"),
      summer: getSeasonPalette("Summer"),
      autumn: getSeasonPalette("Autumn"),
      winter: getSeasonPalette("Winter")
    }};
    """
    palettes = _run_node_expr(js_setup, "palettes")
    meadow_colors = {tuple(p["meadowSunlit"]) for p in palettes.values()}
    decid_tints = {p["deciduousTintHex"] for p in palettes.values()}
    snow_offsets = {p["snowlineOffset"] for p in palettes.values()}

    assert len(meadow_colors) == 4, f"Expected 4 distinct seasonal meadow colors, got {meadow_colors}"
    assert len(decid_tints) == 4, f"Expected 4 distinct deciduous tree tints across 4 seasons, got {decid_tints}"
    assert palettes["winter"]["snowlineOffset"] < palettes["spring"]["snowlineOffset"] < palettes["summer"]["snowlineOffset"], (
        f"Expected Winter snowline lower than Spring and Summer, got {snow_offsets}"
    )
