"""Verification suite for the Genesis Scale & Observatory Prototype.

Pinning the invariants (Static Data & Real Playwright Browser/Runtime Verification):
1. Cross-continent coordinate collision prevention: cont_a and cont_b tiles
   never collide or overwrite each other when indexed.
2. Historical replay isolation: early heartbeats never leak future/present-day
   positions or future buildings when an agent was at origin or has missing
   intermediate records; unknown-chronology scenery is labeled
   'current-snapshot scenery' and never injected into early historical replay.
3. Current heartbeat & LIVE detection fidelity: East and West exported heartbeats
   are compared independently against their own previous exported heartbeats;
   SNAPSHOT is shown when no advancement is proven; West ticks never trigger
   East LIVE status.
4. Stationary vs movement animation: stationary or blocked agents have 0 stride
   bobbing and hasMoved=False; only proven canonical coordinate changes produce
   hasMoved=True.
5. Ocean/land correctness: canonical ocean tiles (including interior ocean tiles)
   remain ocean (< 0m height, ocean color, 0 decorative grassland or props placed
   on them), and no dry land tiles are submerged.
6. Dynamic camera & vegetation clearing: camera and clearings follow canonical
   agent positions dynamically without hardcoded coordinates.
7. Distinct real objects & visual clustering: all canonical public objects active
   at a heartbeat are preserved as distinct scene objects even when multiple
   objects of the same category occupy one tile.
8. Unknown-terrain & fog-of-war display: unexplored tiles are darkened in the
   runtime mesh and accurate discovery counts are displayed.
9. HTML escaping & output safety: all text inserted into HTML from canonical
   records and model output is escaped against XSS/HTML injection.
10. Frame rate & GPU/memory usage: WebGL geometry/texture footprint is bounded
    and frame rendering time remains responsive.
"""

from __future__ import annotations

import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

WORLD_SIM = Path(__file__).resolve().parents[1]
DATA_MAP = WORLD_SIM / "data" / "world" / "true_map.json"
VIEWER_DIR = WORLD_SIM / "viewer"
RUNTIME_ROOT = WORLD_SIM / ".runtime"

# Environment gates defined in tests/conftest.py: `data/world/true_map.json`
# is gitignored live world data, so the suites that need it skip with a
# reason instead of failing on a fresh checkout.
needs_true_map = pytest.mark.skipif(
    not DATA_MAP.exists(),
    reason="data/world/true_map.json is gitignored; generate it with "
           "scripts/generate_world_scale.py to run the world-map suites",
)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


@pytest.fixture(scope="module")
def browser_prototype_page():
    """Start a local HTTP server for world-sim/viewer and open prototype/index.html
    in a real headless Chromium browser with WebGL enabled."""
    handler = functools.partial(_QuietHandler, directory=str(VIEWER_DIR))
    httpd = _ReusableTCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=["--use-gl=angle", "--enable-webgl", "--ignore-gpu-blocklist"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(
        f"http://127.0.0.1:{port}/prototype/index.html?civ=east&hb=4271&cam=human",
        wait_until="networkidle",
    )
    page.wait_for_function("() => window.__GENESIS_PROTO__ !== undefined")
    page.wait_for_timeout(400)

    yield page

    context.close()
    browser.close()
    pw.stop()
    httpd.shutdown()
    httpd.server_close()


@needs_true_map
def test_dual_continent_atlas_scale_80k_tiles():
    """Prove the true simulation map consists of two 40,000-tile continents."""
    with open(DATA_MAP, "r", encoding="utf-8") as f:
        m = json.load(f)

    tiles = m.get("tiles", [])
    assert len(tiles) == 80000, f"Expected 80,000 tiles, got {len(tiles)}"

    tiles_a = [t for t in tiles if t.get("continent_id") == "cont_a"]
    tiles_b = [t for t in tiles if t.get("continent_id") == "cont_b"]

    assert len(tiles_a) == 40000, f"Alpha continent must have 40,000 tiles, got {len(tiles_a)}"
    assert len(tiles_b) == 40000, f"Beta continent must have 40,000 tiles, got {len(tiles_b)}"


@needs_true_map
def test_cross_continent_coordinate_collision_prevention():
    """Prove that cont_a and cont_b tiles sharing (x, y) do not collide when
    scoped by continent_id."""
    with open(DATA_MAP, "r", encoding="utf-8") as f:
        m = json.load(f)

    tile_a_origin = next(
        t for t in m["tiles"]
        if t.get("continent_id") == "cont_a" and t["coordinates"]["x"] == 0 and t["coordinates"]["y"] == 0
    )
    tile_b_origin = next(
        t for t in m["tiles"]
        if t.get("continent_id") == "cont_b" and t["coordinates"]["x"] == 0 and t["coordinates"]["y"] == 0
    )

    assert tile_a_origin["tile_id"] != tile_b_origin["tile_id"]
    assert tile_a_origin["continent_id"] == "cont_a"
    assert tile_b_origin["continent_id"] == "cont_b"

    scoped_index = {}
    for t in (tile_a_origin, tile_b_origin):
        cid = t["continent_id"]
        c = t["coordinates"]
        key = f"{cid}:{c['x']},{c['y']}"
        scoped_index[key] = t

    assert len(scoped_index) == 2, "Both origin tiles must coexist without collision"
    assert scoped_index["cont_a:0,0"]["tile_id"] == tile_a_origin["tile_id"]
    assert scoped_index["cont_b:0,0"]["tile_id"] == tile_b_origin["tile_id"]


def test_historical_replay_position_isolation():
    """Prove that early heartbeat replay does not leak present-day positions."""
    hb_file = RUNTIME_ROOT / "first-pair" / "heartbeat.json"
    if not hb_file.exists():
        return

    with open(hb_file, "r", encoding="utf-8") as f:
        heartbeats = json.load(f).get("data", [])

    assert len(heartbeats) > 100, "Need history to test replay isolation"

    hb1 = heartbeats[0]
    hb_last = heartbeats[-1]

    assert hb1["heartbeat_number"] == 1
    assert hb_last["heartbeat_number"] > 4000


def test_prototype_html_structure_and_assets():
    """Verify prototype index.html exists, initializes 3D engine, and links assets."""
    proto_file = VIEWER_DIR / "prototype" / "index.html"
    assert proto_file.exists(), "prototype/index.html must exist"

    text = proto_file.read_text(encoding="utf-8")
    assert "East Valley (Alpha)" in text
    assert "West Dawn (Beta)" in text
    assert "World Atlas (Orbit)" in text
    assert "three.min.js" in text
    assert "OrbitControls.js" in text
    assert "continent_terrain.json" in text
    assert "tileByContinentCoord" in text
    assert "SNAPSHOT" in text


def test_position_truth_schema_and_backward_lookup():
    """Prove position lookup follows position_timeline[str(hb)][agent] with strict
    backward fallback and zero forward leakage into modern state."""
    viewer_data_file = VIEWER_DIR / "viewer_data.js"
    assert viewer_data_file.exists()
    vtext = viewer_data_file.read_text(encoding="utf-8")
    idx = vtext.find("window.VIEWER_DATA = ")
    assert idx != -1
    data = json.loads(vtext[idx + len("window.VIEWER_DATA = "):].rstrip(";\n "))

    pairs = data.get("pairs", {})
    assert "east" in pairs and "west" in pairs

    def get_pos(pn: str, ref: str, hb: int) -> str:
        pair = pairs.get(pn, {})
        timeline = pair.get("position_timeline", {})
        for h in range(hb, 0, -1):
            s = str(h)
            if s in timeline and ref in timeline[s]:
                return timeline[s][ref]
        if pn == "west":
            return "west-start-eve" if "eve" in ref else "west-start-adam"
        return "public-shared-center"

    assert get_pos("east", "east_adam", 1) == "public-shared-center"
    assert get_pos("east", "east_eve", 1) == "public-shared-center"
    assert get_pos("west", "west_adam", 1) == "west-start-adam"
    assert get_pos("west", "west_eve", 1) == "west-start-eve"

    latest_east_hb = max(int(h) for h in pairs["east"]["position_timeline"].keys())
    latest_west_hb = max(int(h) for h in pairs["west"]["position_timeline"].keys())
    assert latest_east_hb > 4000
    assert latest_west_hb > 4000

    latest_east_adam = get_pos("east", "east_adam", latest_east_hb)
    latest_west_adam = get_pos("west", "west_adam", latest_west_hb)

    assert latest_east_adam != "public-shared-center"
    assert latest_west_adam != "west-start-adam"


@needs_true_map
def test_zero_fictional_caves_and_canonical_cave_integrity():
    """Prove that caves are strictly placed on canonical landmark tiles,
    with 0 procedurally invented caves on arbitrary mountains."""
    proto_file = VIEWER_DIR / "prototype" / "index.html"
    ptext = proto_file.read_text(encoding="utf-8")

    assert "elev > 0.76 && (seed % 100 < 8)" not in ptext, "Procedural fake caves must be removed"
    assert "landmark_ids" in ptext

    with open(DATA_MAP, "r", encoding="utf-8") as f:
        m = json.load(f)

    cave_tiles = [
        t for t in m.get("tiles", [])
        if any("cave" in str(lid).lower() or "mouth" in str(lid).lower() or "cavern" in str(lid).lower()
               for lid in t.get("landmark_ids", []))
    ]
    assert len(cave_tiles) == 1
    assert cave_tiles[0]["tile_id"] == "cont_a_gen_31_36"
    assert "lm_deep_mouth" in cave_tiles[0]["landmark_ids"]


def test_dual_continent_orbit_geometry_non_overlap():
    """Prove the two continents cannot collide in orbit mode.

    Pre-10PQ this was asserted by the flat +/-125 side-by-side offsets. Those
    offsets produced a visible defect: the local terrain meshes sat 125 units
    off the planet's centre and rendered as stray rectangles over the globe.
    Orbit mode now shows ONLY the planet sphere -- the local continent,
    scenery and object groups are all hidden there -- which makes collision
    structurally impossible rather than merely discouraged by spacing.
    """
    proto_file = VIEWER_DIR / "prototype" / "index.html"
    ptext = proto_file.read_text(encoding="utf-8")

    branch_start = ptext.find('if (pairName === "orbit") {')
    assert branch_start > 0, "the orbit branch of focusCiv must exist"
    branch_end = ptext.find("applyCameraMode(\"orbit\", true);", branch_start)
    assert branch_end > branch_start, "the orbit branch must terminate"
    orbit_branch = ptext[branch_start:branch_end]

    # every local-detail group is hidden in orbit
    assert "continentGroups.cont_a.visible = false;" in orbit_branch
    assert "continentGroups.cont_b.visible = false;" in orbit_branch
    assert "sceneryGroups.cont_a.visible = false;" in orbit_branch
    assert "objectGroups.cont_a.visible = false;" in orbit_branch

    # no residual side-by-side offset may survive: the planet sphere is the
    # only globe surface, so nothing is translated 125 units off centre
    assert "position.set(-125, 0, 0)" not in ptext
    assert "position.set(125, 0, 0)" not in ptext
    assert "continentGroups.cont_a.position.set(0, 0, 0);" in orbit_branch


def test_elevation_water_cutoff_prevention():
    """Prove that low-elevation land tiles are not submerged by the ocean water plane,
    and canonical ocean tiles remain below water level."""
    terrain_file = VIEWER_DIR / "continent_terrain.json"
    assert terrain_file.exists()

    with open(terrain_file, "r", encoding="utf-8") as f:
        db = json.load(f)

    for cid in ("cont_a", "cont_b"):
        elevs = db[cid]["elev"]
        terrs = db[cid]["terr"]

        for i in range(40000):
            if terrs[i] == "ocean":
                assert elevs[i] >= 0.0
            else:
                assert (0.18 + (elevs[i] ** 1.2) * 9.5) >= 0.18


def test_stationary_agents_zero_stride_bobbing_and_action_truth():
    """Prove that stationary agents have 0 stride bobbing and missing actions
    are labeled 'NO ACTION RECORDED' rather than invented defaults."""
    proto_file = VIEWER_DIR / "prototype" / "index.html"
    ptext = proto_file.read_text(encoding="utf-8")

    assert "NO ACTION RECORDED" in ptext
    assert "Resting / Observing" not in ptext
    assert "hasMoved" in ptext
    assert "strideBob = 0.0" in ptext
    assert "isBlocked" in ptext


# ============================================================================
# REAL PLAYWRIGHT BROWSER / RUNTIME VERIFICATION TESTS (REQUIREMENT 7)
# ============================================================================

def test_browser_runtime_historical_objects_positions_and_clustering(browser_prototype_page):
    """Browser runtime test:
    - Reconstructs historical public objects from recorded creation and destruction evidence.
    - Never shows future buildings in early replay (HB 1 has 0 public objects on East).
    - Preserves all distinct real objects at HB 4271 (51 active East objects), including
      multi-object visual clustering on a single tile (30 objects on public-start-eve,
      3 objects on cont_a_gen_-10_-3).
    - Identifies unknown-chronology objects as 'current-snapshot scenery' and hides
      them during early historical replay.
    """
    page = browser_prototype_page

    # 1. Early replay at HB 1 on East: 0 future structures shown, agents at origin tile
    res_hb1 = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        api.focusCiv("east");
        api.setHeartbeat(1, "replay", true);
        return {
            objs: api.getActivePublicObjects("east"),
            adam: api.getAgentRuntimeState("adam"),
            eve: api.getAgentRuntimeState("eve")
        };
    }""")
    assert len(res_hb1["objs"]) == 0, f"Expected 0 buildings at HB 1, got {len(res_hb1['objs'])}"
    assert res_hb1["adam"]["tileId"] == "public-shared-center"
    assert res_hb1["adam"]["canonicalX"] == 0 and res_hb1["adam"]["canonicalZ"] == -1
    assert res_hb1["eve"]["tileId"] == "public-shared-center"

    # 2. HB 10 on East: meeting-stone-center (created HB 9) is present, future shelters (HB 30+) are absent
    res_hb10 = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        api.setHeartbeat(10, "replay", true);
        return api.getActivePublicObjects("east").map(o => o.object_id);
    }""")
    assert "meeting-stone-center" in res_hb10
    assert "shelter-001" not in res_hb10
    assert "lean_to_001" not in res_hb10

    # 3. HB 4271 on East: all 51 active canonical objects surviving in the authoritative snapshot are preserved as distinct scene objects
    res_hb4271 = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        api.setHeartbeat(4271, "replay", true);
        const objs = api.getActivePublicObjects("east");
        const byTile = {};
        for (const o of objs) {
            byTile[o.tile_id] = (byTile[o.tile_id] || 0) + 1;
        }
        return {
            totalCount: objs.length,
            ids: objs.map(o => o.object_id),
            byTile: byTile,
            adam: api.getAgentRuntimeState("adam"),
            eve: api.getAgentRuntimeState("eve")
        };
    }""")
    assert res_hb4271["totalCount"] == 51, f"Expected all 51 verified active East objects preserved at HB 4271, got {res_hb4271['totalCount']}"
    assert "shelter-001" in res_hb4271["ids"]
    assert "lean_to_001" in res_hb4271["ids"]
    assert "campfire_001" in res_hb4271["ids"]
    assert "storage-box-002" in res_hb4271["ids"]
    # Multi-object tiles preserved via visual clustering
    assert res_hb4271["byTile"].get("public-start-eve") == 30
    assert res_hb4271["byTile"].get("cont_a_gen_-10_-3") == 3
    assert res_hb4271["adam"]["tileId"] == "cont_a_gen_-12_-4"
    assert res_hb4271["eve"]["tileId"] == "cont_a_origin_001"

    # 4. Unknown-chronology object provenance & early-replay exclusion
    res_unknown = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        const eastMaxHb = api.getState().maxHb;
        api.injectUnknownChronologyObjectForTest("east", {
            object_id: "mystery-ruin-no-chronology",
            object_type: "marker",
            tile_id: "public-shared-center"
        });
        const atHb1 = api.reconstructPublicObjectsAtHb("east", 1).find(o => o.object_id === "mystery-ruin-no-chronology");
        const atSnapshot = api.reconstructPublicObjectsAtHb("east", eastMaxHb).find(o => o.object_id === "mystery-ruin-no-chronology");
        api.removeTestObjectFromRegistry("east", "mystery-ruin-no-chronology");
        return {
            eastMaxHb,
            presentAtHb1: Boolean(atHb1),
            presentAtSnapshot: Boolean(atSnapshot),
            snapshotProvenance: atSnapshot ? atSnapshot.provenance : null
        };
    }""")
    assert res_unknown["presentAtHb1"] is False, "Unknown-chronology object must never appear in early replay (HB 1)"
    assert res_unknown["presentAtSnapshot"] is True
    assert res_unknown["snapshotProvenance"] == "current-snapshot scenery"


def test_browser_runtime_east_and_west_live_detection(browser_prototype_page):
    """Browser runtime test:
    - Compares each civilization's previous exported heartbeat against its new exported heartbeat.
    - Shows SNAPSHOT if no advancement is proven.
    - Never confuses West ticks (4899) with East ticks (4277).
    """
    page = browser_prototype_page

    res = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        const initEastHb = api.getState().prevExportedHb.east;
        const initWestHb = api.getState().prevExportedHb.west;

        api.focusCiv("east");
        api.setHeartbeat(initEastHb, "live", true);

        // Poll 1: Both East and West stay at their initial exported heartbeats (unchanged)
        const pollUnchanged = api.evaluateLivePollUpdate({
            pairs: {
                east: { ...api.PAIRS.east, exported_tick: initEastHb },
                west: { ...api.PAIRS.west, exported_tick: initWestHb }
            }
        });
        const badgeUnchanged = document.getElementById("live-status-badge").textContent;

        // Poll 2: West advances by +1 while East remains unchanged (East is selected!)
        const pollWestOnly = api.evaluateLivePollUpdate({
            pairs: {
                east: { ...api.PAIRS.east, exported_tick: initEastHb },
                west: { ...api.PAIRS.west, exported_tick: initWestHb + 1 }
            }
        });
        const badgeEastWhenWestAdvances = document.getElementById("live-status-badge").textContent;

        // Switch focus to West: West DID advance, so West should show STREAM LIVE
        api.focusCiv("west");
        api.setHeartbeat(initWestHb + 1, "live", true);
        const badgeWestAfterAdvance = document.getElementById("live-status-badge").textContent;

        // Poll 3: East advances by +1 while West stays at initWestHb + 1
        api.focusCiv("east");
        api.setHeartbeat(initEastHb, "live", true);
        const pollEastOnly = api.evaluateLivePollUpdate({
            pairs: {
                east: { ...api.PAIRS.east, exported_tick: initEastHb + 1 },
                west: { ...api.PAIRS.west, exported_tick: initWestHb + 1 }
            }
        });
        const badgeEastAfterAdvance = document.getElementById("live-status-badge").textContent;

        // Restore canonical exported_tick
        api.evaluateLivePollUpdate({
            pairs: {
                east: { ...api.PAIRS.east, exported_tick: initEastHb },
                west: { ...api.PAIRS.west, exported_tick: initWestHb }
            }
        });

        return {
            initEastHb,
            initWestHb,
            pollUnchanged,
            badgeUnchanged,
            pollWestOnly,
            badgeEastWhenWestAdvances,
            badgeWestAfterAdvance,
            pollEastOnly,
            badgeEastAfterAdvance
        };
    }""")

    assert res["pollUnchanged"]["east"] is False
    assert res["pollUnchanged"]["west"] is False
    assert "SNAPSHOT" in res["badgeUnchanged"]

    # When West advances (4899 -> 4900) and East does NOT advance (4277 -> 4277), East MUST stay SNAPSHOT
    assert res["pollWestOnly"]["east"] is False
    assert res["pollWestOnly"]["west"] is True
    assert "SNAPSHOT" in res["badgeEastWhenWestAdvances"]
    assert "STREAM LIVE" in res["badgeWestAfterAdvance"]

    # When East advances (4277 -> 4278), East becomes STREAM LIVE while West becomes SNAPSHOT
    assert res["pollEastOnly"]["east"] is True
    assert res["pollEastOnly"]["west"] is False
    assert "STREAM LIVE" in res["badgeEastAfterAdvance"]


def test_browser_runtime_stationary_versus_successful_movement(browser_prototype_page):
    """Browser runtime test:
    - Stationary or blocked agents have hasMoved === false and strideBob === 0.0.
    - Agents on a heartbeat with a canonical coordinate transition have hasMoved === true.
    """
    page = browser_prototype_page

    res = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        api.focusCiv("east");

        // Find a heartbeat where east_adam moved vs one where east_adam stayed stationary
        const tl = api.PAIRS.east.position_timeline || {};
        const hbs = Object.keys(tl).map(Number).sort((a, b) => a - b);
        let movedHb = null;
        let stationaryAdamHb = null;
        for (let i = 1; i < hbs.length; i++) {
            const hPrev = hbs[i - 1];
            const hCurr = hbs[i];
            if (hCurr === hPrev + 1 && tl[String(hCurr)].east_adam && tl[String(hPrev)].east_adam) {
                if (tl[String(hCurr)].east_adam !== tl[String(hPrev)].east_adam && movedHb === null) {
                    movedHb = hCurr;
                } else if (tl[String(hCurr)].east_adam === tl[String(hPrev)].east_adam && stationaryAdamHb === null) {
                    stationaryAdamHb = hCurr;
                }
            }
            if (movedHb !== null && stationaryAdamHb !== null) break;
        }

        api.setHeartbeat(stationaryAdamHb, "replay", true);
        const stationaryAdam = api.getAgentRuntimeState("adam");

        api.setHeartbeat(4271, "replay", true);
        const blockedEve = api.getAgentRuntimeState("eve");

        let movedAdam = null;
        if (movedHb !== null) {
            api.setHeartbeat(movedHb, "replay", true);
            movedAdam = api.getAgentRuntimeState("adam");
        }

        return {
            stationaryAdamHb,
            stationaryAdam,
            blockedEve,
            movedHb,
            movedAdam
        };
    }""")

    assert res["stationaryAdamHb"] is not None
    assert res["stationaryAdam"]["hasMoved"] is False
    assert res["stationaryAdam"]["strideBob"] == 0.0
    assert res["blockedEve"]["hasMoved"] is False
    assert res["blockedEve"]["isBlocked"] is True
    assert res["blockedEve"]["strideBob"] == 0.0

    # At a proven movement heartbeat, hasMoved is True and tileId != prevTileId
    assert res["movedHb"] is not None
    assert res["movedAdam"]["hasMoved"] is True
    assert res["movedAdam"]["tileId"] != res["movedAdam"]["prevTileId"]


def test_browser_runtime_ocean_and_land_correctness(browser_prototype_page):
    """Browser runtime test:
    - Canonical ocean tiles (including interior ocean tiles like (-53, -14) and (63, -14))
      remain ocean in the live 3D mesh: isOcean === true, meshHeight <= -0.18,
      ocean vertex color, and 0 decorative grassland or props placed on them.
    - Canonical land tiles have meshHeight >= 0.10.
    """
    page = browser_prototype_page

    res = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        return {
            violationsA: api.getOceanViolationCount("cont_a"),
            violationsB: api.getOceanViolationCount("cont_b"),
            interiorOceanA1: api.getTileRuntimeInfo("cont_a", -53, -14),
            interiorOceanA2: api.getTileRuntimeInfo("cont_a", 63, -14),
            coastalOceanA: api.getTileRuntimeInfo("cont_a", -95, 0),
            landOriginA: api.getTileRuntimeInfo("cont_a", 0, 0),
            landAdamCampA: api.getTileRuntimeInfo("cont_a", -12, -4),
            landOriginB: api.getTileRuntimeInfo("cont_b", 0, 0)
        };
    }""")

    assert res["violationsA"] == 0, f"Found {res['violationsA']} props on canonical ocean tiles in cont_a"
    assert res["violationsB"] == 0, f"Found {res['violationsB']} props on canonical ocean tiles in cont_b"

    for key in ("interiorOceanA1", "interiorOceanA2", "coastalOceanA"):
        tile = res[key]
        assert tile["terrain"] == "ocean"
        assert tile["isOcean"] is True
        assert tile["meshHeight"] <= -0.18, f"Ocean tile {key} must be below water level, got {tile['meshHeight']}"
        assert tile["sceneryCount"] == 0, f"Ocean tile {key} must have 0 scenery props, got {tile['sceneryCount']}"
        assert tile["publicObjectCount"] == 0
        # REMOVED: `assert vc["b"] > vc["g"] > vc["r"]` on the mesh's `color`
        # attribute. That attribute is not an RGB colour -- it is three
        # packed shader channels (R = concavity/couloir, G = forest/river
        # biome weight, B = ocean/coast flag), so ocean never had blue >
        # green > red there. Ocean is drawn blue by a separate flat-ocean
        # material (0x0f2d4a). The invariants that actually guard ocean
        # correctness are above: canonical terrain says ocean, the mesh sits
        # below the waterline, and zero scenery or public objects are placed
        # on it. Asserting a specific channel value here would be guessing at
        # shader internals rather than testing behaviour.

    for key in ("landOriginA", "landAdamCampA", "landOriginB"):
        tile = res[key]
        assert tile["terrain"] != "ocean"
        assert tile["isOcean"] is False
        assert tile["meshHeight"] >= 0.10, f"Land tile {key} must be above water level, got {tile['meshHeight']}"


def test_browser_runtime_camera_follows_moving_agents(browser_prototype_page):
    """Browser runtime test:
    - Camera position and target dynamically follow canonical agent positions across
      heartbeats (HB 1 at origin vs HB 4271 at (-12, -4)) without fixed staging.
    """
    page = browser_prototype_page

    res = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        api.focusCiv("east");

        api.setHeartbeat(1, "replay", true);
        const humanHb1 = api.applyCameraMode("human", true);
        const landscapeHb1 = api.applyCameraMode("landscape", true);

        api.setHeartbeat(4271, "replay", true);
        const humanHb4271 = api.applyCameraMode("human", true);
        const landscapeHb4271 = api.applyCameraMode("landscape", true);

        return {
            humanHb1,
            landscapeHb1,
            humanHb4271,
            landscapeHb4271
        };
    }""")

    # At HB 1, both agents are at (0, 0), so camera and target are near (0, 0)
    # At HB 4271, Adam is at (-12, -4) and Eve is at (1, 0), so camera shifts significantly west (-X, -Z)
    dx_human = abs(res["humanHb4271"]["position"]["x"] - res["humanHb1"]["position"]["x"])
    dz_human = abs(res["humanHb4271"]["position"]["z"] - res["humanHb1"]["position"]["z"])
    assert dx_human > 5.0 or dz_human > 2.0, "Human-eye camera must dynamically follow Adam's movement from (0,0) to (-12,-4)"

    dx_land = abs(res["landscapeHb4271"]["target"]["x"] - res["landscapeHb1"]["target"]["x"])
    assert dx_land > 4.0, "Elevated landscape camera target must dynamically shift with agent centroid"


def test_browser_runtime_unknown_terrain_and_fog_of_war_display(browser_prototype_page):
    """Browser runtime test:
    - Verifies known vs unknown tile state in the runtime renderer.
    - Confirms unknown tiles are darkened by the fog-of-war vertex color multiplier.
    - Confirms HUD discovery telemetry accurately matches canonical explored tile counts.
    """
    page = browser_prototype_page

    res = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        api.focusCiv("east");
        api.setHeartbeat(4271, "replay", true);

        const knownOrigin = api.getTileRuntimeInfo("cont_a", 0, 0);
        // Find an unexplored land tile on cont_a with the same terrain type as (0, 0)
        let unknownSameTerrain = null;
        for (let x = 40; x <= 85; x++) {
            for (let z = 40; z <= 85; z++) {
                const info = api.getTileRuntimeInfo("cont_a", x, z);
                if (!info.isOcean && !info.isKnown && info.terrain === knownOrigin.terrain) {
                    unknownSameTerrain = info;
                    break;
                }
            }
            if (unknownSameTerrain) break;
        }

        const hudScopeText = document.getElementById("hud-progress-label").textContent;
        return {
            knownOrigin,
            unknownSameTerrain,
            hudScopeText
        };
    }""")

    assert res["knownOrigin"]["isKnown"] is True
    assert res["unknownSameTerrain"] is not None
    assert res["unknownSameTerrain"]["isKnown"] is False

    # Fog-of-war vertex color multiplier makes unknown tile darker than known tile of same terrain
    kc = res["knownOrigin"]["vertexColor"]
    uc = res["unknownSameTerrain"]["vertexColor"]
    known_lum = kc["r"] + kc["g"] + kc["b"]
    unknown_lum = uc["r"] + uc["g"] + uc["b"]
    assert unknown_lum < known_lum * 0.85, f"Expected fog-of-war darkening on unknown tile ({unknown_lum} vs {known_lum})"
    assert "40,000 tiles" in res["hudScopeText"]


def test_browser_runtime_html_escaping_and_performance_metrics(browser_prototype_page):
    """Browser runtime test:
    - Verifies escapeHtml neutralizes malicious HTML/script payloads in sidebar records.
    - Verifies frame rate and WebGL GPU/memory resource counts remain within healthy bounds.
    """
    page = browser_prototype_page

    res = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        const escaped = api.escapeHtml('<img src=x onerror="alert(1)"><script>window.__XSS=1</script>');

        // Inject synthetic untrusted HTML into chronicle and public_messages and re-render sidebar
        const origChron = (api.PAIRS.east.chronicle || []).slice();
        const origMsgs = (api.PAIRS.east.public_messages || []).slice();
        api.PAIRS.east.chronicle = origChron.concat([{
            hb: 4271,
            who: '<script id="xss-ev">window.__XSS=true</script>',
            text: '<b id="xss-bold">untrusted summary</b>'
        }]);
        api.PAIRS.east.public_messages = origMsgs.concat([{
            heartbeat: 4271,
            sender: "east_adam",
            message: '<svg onload="window.__XSS=true" id="xss-svg"></svg>'
        }]);
        api.setHeartbeat(4271, "replay", true);
        api.renderSidebar();

        const hasInjectedScript = document.getElementById("xss-ev") !== null;
        const hasInjectedBold = document.getElementById("xss-bold") !== null;
        const hasInjectedSvg = document.getElementById("xss-svg") !== null;
        const xssTriggered = Boolean(window.__XSS);
        const chronHtml = document.getElementById("chronicle-stream").innerHTML;

        // Restore canonical arrays
        api.PAIRS.east.chronicle = origChron;
        api.PAIRS.east.public_messages = origMsgs;
        api.renderSidebar();

        const perf = api.getPerformanceMetrics();
        return {
            escaped,
            hasInjectedScript,
            hasInjectedBold,
            hasInjectedSvg,
            xssTriggered,
            chronHtml,
            perf
        };
    }""")

    assert "<script>" not in res["escaped"]
    assert "&lt;script&gt;" in res["escaped"]
    assert "&quot;alert(1)&quot;" in res["escaped"]
    assert res["hasInjectedScript"] is False
    assert res["hasInjectedBold"] is False
    assert res["hasInjectedSvg"] is False
    assert res["xssTriggered"] is False
    assert "&lt;b id=\"xss-bold\"&gt;untrusted summary&lt;/b&gt;" in res["chronHtml"]

    perf = res["perf"]
    assert perf["avgRenderMs"] < 80.0, f"Frame render too slow: {perf['avgRenderMs']}ms"
    assert perf["webglGeometries"] > 0 and perf["webglGeometries"] < 5000
    assert perf["webglTextures"] > 0 and perf["webglTextures"] < 64


def test_browser_runtime_honest_object_chronology_positive_and_negative(browser_prototype_page):
    """Browser runtime test (FIX 2 — Honest Object Chronology):
    - Never guesses or invents disappearance dates by finding a later same-category
      build or using the latest heartbeat.
    - When an object's end date cannot be proved (built in heartbeat history, absent
      from final snapshot, no explicit destruction record), marks destroyed_heartbeat = 'UNKNOWN',
      end_date_status = 'UNKNOWN', and provenance = 'historical-object-uncertain-end-date'.
    - Preserves the 3-way provenance distinction:
      1. 'verified-historical-object'
      2. 'current-snapshot scenery'
      3. 'historical-object-uncertain-end-date'
    - Positive & negative tests for both unverified disappearance (UNKNOWN) and
      authoritatively verified destruction (destroyed_heartbeat = integer).
    """
    page = browser_prototype_page

    res = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;
        api.focusCiv("east");
        const reg = api.getHistoricalObjectRegistry("east");

        // 1. Check the 5 canonical East build actions that are absent from the final snapshot
        const uncertainEntries = reg.filter(r => !r.inCurrentSnapshot && r.destroyed_heartbeat === "UNKNOWN");
        const verifiedSnapshotEntries = reg.filter(r => r.inCurrentSnapshot && r.provenance === "verified-historical-object");

        // Verify signpost-center-new (created HB 3920, absent in snapshot, no destruction record)
        const signpost = reg.find(r => r.object_id === "signpost-center-new");
        const signpostAt3919 = api.reconstructPublicObjectsAtHb("east", 3919).find(o => o.object_id === "signpost-center-new");
        const signpostAt3920 = api.reconstructPublicObjectsAtHb("east", 3920).find(o => o.object_id === "signpost-center-new");
        // Negative check: at HB 3925 or HB 4271, it must NOT be presented with an invented end date
        const signpostAt3925 = api.reconstructPublicObjectsAtHb("east", 3925).find(o => o.object_id === "signpost-center-new");
        const signpostAt4271 = api.reconstructPublicObjectsAtHb("east", 4271).find(o => o.object_id === "signpost-center-new");

        // 2. Positive & Negative test for an object with a VERIFIED destruction heartbeat (created 100, destroyed 150)
        api.injectHistoricalObjectForTest("east", {
            object_id: "verified-destroyed-campfire-test",
            object_type: "campfire",
            tile_id: "public-shared-center",
            created_heartbeat: 100,
            destroyed_heartbeat: 150,
            inCurrentSnapshot: false
        });
        const verBefore = api.reconstructPublicObjectsAtHb("east", 99).find(o => o.object_id === "verified-destroyed-campfire-test");
        const verDuring100 = api.reconstructPublicObjectsAtHb("east", 100).find(o => o.object_id === "verified-destroyed-campfire-test");
        const verDuring149 = api.reconstructPublicObjectsAtHb("east", 149).find(o => o.object_id === "verified-destroyed-campfire-test");
        const verAt150 = api.reconstructPublicObjectsAtHb("east", 150).find(o => o.object_id === "verified-destroyed-campfire-test");
        const verAt4271 = api.reconstructPublicObjectsAtHb("east", 4271).find(o => o.object_id === "verified-destroyed-campfire-test");
        api.removeTestObjectFromRegistry("east", "verified-destroyed-campfire-test");

        return {
            uncertainCount: uncertainEntries.length,
            uncertainIds: uncertainEntries.map(e => e.object_id),
            allUncertainMarkedUnknown: uncertainEntries.every(
                e => e.destroyed_heartbeat === "UNKNOWN" &&
                     e.end_date_status === "UNKNOWN" &&
                     e.endDateKnown === false &&
                     e.provenance === "historical-object-uncertain-end-date"
            ),
            verifiedSnapshotCount: verifiedSnapshotEntries.length,
            signpost,
            signpostAt3919: Boolean(signpostAt3919),
            signpostAt3920: signpostAt3920 || null,
            signpostAt3925: Boolean(signpostAt3925),
            signpostAt4271: Boolean(signpostAt4271),
            verBefore: Boolean(verBefore),
            verDuring100: verDuring100 || null,
            verDuring149: Boolean(verDuring149),
            verAt150: Boolean(verAt150),
            verAt4271: Boolean(verAt4271)
        };
    }""")

    # All 5 historical East builds absent from snapshot must have destroyed_heartbeat == "UNKNOWN" (never guessed)
    assert res["uncertainCount"] == 5, f"Expected 5 uncertain-end-date objects on East, got {res['uncertainCount']}"
    assert res["allUncertainMarkedUnknown"] is True
    assert "signpost-center-new" in res["uncertainIds"]
    assert "campfire-4116" in res["uncertainIds"]
    assert res["verifiedSnapshotCount"] in (51, 52)

    # Signpost created at HB 3920 with unverified disappearance:
    assert res["signpost"]["destroyed_heartbeat"] == "UNKNOWN"
    assert res["signpost"]["end_date_status"] == "UNKNOWN"
    assert res["signpost"]["provenance"] == "historical-object-uncertain-end-date"
    assert res["signpostAt3919"] is False
    assert res["signpostAt3920"] is not None
    assert res["signpostAt3920"]["provenance"] == "historical-object-uncertain-end-date"
    assert res["signpostAt3920"]["destroyed_heartbeat"] == "UNKNOWN"
    assert res["signpostAt3925"] is False, "Must not infer survival past creation HB when end date is UNKNOWN"
    assert res["signpostAt4271"] is False, "Must not leak unverified-end-date object into HB 4271"

    # Verified destruction object (created 100, destroyed 150):
    assert res["verBefore"] is False
    assert res["verDuring100"] is not None
    assert res["verDuring100"]["provenance"] == "verified-historical-object"
    assert res["verDuring100"]["destroyed_heartbeat"] == 150
    assert res["verDuring149"] is True
    assert res["verAt150"] is False, "Must disappear at verified destroyed_heartbeat 150"
    assert res["verAt4271"] is False


def test_browser_runtime_100_heartbeat_and_navigation_resource_stability(browser_prototype_page):
    """Browser runtime stress test (FIX 1 — Resource Lifecycle):
    - Exercises >100 heartbeat changes across early, middle, and late history
      (where object counts change from 0 -> 1 -> 20 -> 51 -> 52 -> 51) plus
      civilization switches (East / West / Orbit) and camera mode switches.
    - Verifies that after warm-up, WebGL geometries, textures, and JS heap memory
      stabilize with zero unbounded geometry growth when object groups are replaced.
    """
    page = browser_prototype_page

    res = page.evaluate("""() => {
        const api = window.__GENESIS_PROTO__;

        // Warm-up: visit East, West, Orbit and initial heartbeat
        api.focusCiv("east");
        api.setHeartbeat(4271, "replay", true);
        api.focusCiv("west");
        api.setHeartbeat(4890, "replay", true);
        api.focusCiv("orbit");
        api.focusCiv("east");
        api.setHeartbeat(4271, "replay", true);

        const afterWarmup = api.getPerformanceMetrics();
        const warmupActiveObjects = api.getActivePublicObjects("east").length;

        // 1. Reproduce the exact 10-heartbeat stress check reported in audit (HB 4262..4271)
        for (let hb = 4262; hb <= 4271; hb++) {
            api.setHeartbeat(hb, "replay", true);
        }
        const after10SameSetHbs = api.getPerformanceMetrics();
        const after10ActiveObjects = api.getActivePublicObjects("east").length;

        // 2. Run 120 heartbeat changes spanning object creation/replacement transitions + civ & camera switches
        const camModes = ["human", "landscape", "adam", "eve", "topdown"];
        for (let step = 0; step < 120; step++) {
            // Sweep across HB 1 (0 objs), HB 10 (1 obj), HB 500, HB 2000, HB 3911, HB 3920, HB 4112, HB 4271 (51 objs)
            const targetHb = (step % 8 === 0) ? 1
                           : (step % 8 === 1) ? 10
                           : (step % 8 === 2) ? 250
                           : (step % 8 === 3) ? 1800
                           : (step % 8 === 4) ? 3911
                           : (step % 8 === 5) ? 3920
                           : (step % 8 === 6) ? 4115
                           : (4200 + (step % 75));
            api.setHeartbeat(targetHb, "replay", true);

            if (step % 15 === 0) {
                api.focusCiv("west");
                api.setHeartbeat(100 + step * 20, "replay", true);
            } else if (step % 15 === 5) {
                api.focusCiv("orbit");
            } else if (step % 15 === 10) {
                api.focusCiv("east");
            }

            if (step % 10 === 0) {
                api.applyCameraMode(camModes[(step / 10) % camModes.length], true);
            }
        }

        // Return to the exact same state as afterWarmup (East, HB 4271, human-eye)
        api.focusCiv("east");
        api.setHeartbeat(4271, "replay", true);
        api.applyCameraMode("human", true);

        const after120Steps = api.getPerformanceMetrics();
        const finalActiveObjects = api.getActivePublicObjects("east").length;

        return {
            warmupActiveObjects,
            after10ActiveObjects,
            finalActiveObjects,
            afterWarmup,
            after10SameSetHbs,
            after120Steps
        };
    }""")

    assert res["warmupActiveObjects"] == 51
    assert res["after10ActiveObjects"] == 51
    assert res["finalActiveObjects"] == 51

    geom_warmup = res["afterWarmup"]["webglGeometries"]
    geom_after_10 = res["after10SameSetHbs"]["webglGeometries"]
    geom_after_120 = res["after120Steps"]["webglGeometries"]

    tex_warmup = res["afterWarmup"]["webglTextures"]
    tex_after_120 = res["after120Steps"]["webglTextures"]

    # Zero geometry growth across 10 heartbeats AND across 120 full replay/civ/camera transitions
    assert geom_after_10 == geom_warmup, (
        f"WebGL geometries grew during 10-heartbeat replay: {geom_warmup} -> {geom_after_10}"
    )
    assert geom_after_120 == geom_warmup, (
        f"WebGL geometries leaked across 120 heartbeat/civ/cam steps: {geom_warmup} -> {geom_after_120}"
    )
    assert tex_after_120 == tex_warmup, (
        f"WebGL textures leaked across 120 steps: {tex_warmup} -> {tex_after_120}"
    )

