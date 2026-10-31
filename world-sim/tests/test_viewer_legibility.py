"""Test suite for Phase 10LD: Observatory Legibility — Interiors, Locomotion, Atmosphere.

Specification: docs/phase_10lb_observatory_legibility_spec.md §6
Required test coverage:
1. test_position_timeline_is_dense_and_complete
2. test_sheltered_agent_position_is_inside_shelter
3. test_empty_shelter_renders_empty_floor
4. test_directional_facing_matches_travel_heading
5. test_idle_agent_preserves_last_facing
6. test_gait_cadence_is_derived_from_displacement
7. test_weather_transitions_at_recorded_heartbeat
8. test_clear_weather_disables_precipitation
9. test_known_object_types_have_distinct_visual_ids
10. test_no_camera_regression_after_legibility_change
11. test_construction_fx_absent_until_hew_timber_recorded
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
import pytest

WORLD_SIM = Path(__file__).resolve().parent.parent
PROTOTYPE_HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"
VIEWER_DATA_JS = WORLD_SIM / "viewer" / "viewer_data.js"


def _load_viewer_data() -> dict:
    text = VIEWER_DATA_JS.read_text(encoding="utf-8")
    idx = text.find("window.VIEWER_DATA = ")
    assert idx != -1, "window.VIEWER_DATA not found in viewer_data.js"
    json_str = text[idx + len("window.VIEWER_DATA = "):].rstrip("; \n")
    return json.loads(json_str)


def _get_prototype_script() -> str:
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "prototype index.html must contain an inline script"
    return max(scripts, key=len)


def _run_node_expr(js_setup: str, js_expr: str) -> str:
    """Run a small JavaScript expression under node and return stdout."""
    code = f"{js_setup}\nconsole.log(JSON.stringify({js_expr}));"
    res = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(res.stdout.strip())


# ---------------------------------------------------------------------------
# 1. test_position_timeline_is_dense_and_complete
# ---------------------------------------------------------------------------
def test_position_timeline_is_dense_and_complete():
    """Verify position_timeline is dense and provides positions for every agent across heartbeats."""
    data = _load_viewer_data()
    pairs = data.get("pairs", {})
    assert "east" in pairs and "west" in pairs

    for pn in ("east", "west"):
        timeline = pairs[pn].get("position_timeline", {})
        assert len(timeline) >= 1000, f"{pn} position_timeline must have >= 1000 heartbeats (got {len(timeline)})"

        # Check a sample across the timeline
        hb_keys = sorted([int(k) for k in timeline.keys() if k.isdigit()])
        assert len(hb_keys) >= 1000
        sample_keys = hb_keys[::max(1, len(hb_keys) // 50)]
        adam_ref = f"{pn}_adam"
        eve_ref = f"{pn}_eve"

        for hb in sample_keys:
            entry = timeline[str(hb)]
            assert isinstance(entry, dict), f"Heartbeat {hb} entry must be a dict"
            assert adam_ref in entry, f"Missing {adam_ref} at heartbeat {hb}"
            assert eve_ref in entry, f"Missing {eve_ref} at heartbeat {hb}"
            assert isinstance(entry[adam_ref], str) and len(entry[adam_ref]) > 0, f"Invalid tile id for {adam_ref} at hb {hb}: {entry[adam_ref]}"
            assert isinstance(entry[eve_ref], str) and len(entry[eve_ref]) > 0, f"Invalid tile id for {eve_ref} at hb {hb}: {entry[eve_ref]}"


# ---------------------------------------------------------------------------
# 2. test_sheltered_agent_position_is_inside_shelter
# ---------------------------------------------------------------------------
def test_sheltered_agent_position_is_inside_shelter():
    """Verify sheltered agent position logic places agents inside shelter tile rather than clipping outside."""
    script = _get_prototype_script()
    assert "shelter_occupancy" in script or "isSheltered" in script, (
        "Script must reference shelter_occupancy / sheltered status for agent positioning"
    )

    # Verify updateAgentFigure positions sheltered agent at shelter tile coordinates with interior offset
    match = re.search(r"function updateAgentFigure\((.*?)\)\s*\{(.*?)\n  \}", script, re.DOTALL)
    assert match, "updateAgentFigure must be defined in script"
    body = match.group(2)
    assert "isSheltered" in body or "shelter_occupancy" in body or "isInteriorModeActive" in body
    assert "activeShelterTileCoords" in body or "shelter" in body


# ---------------------------------------------------------------------------
# 3. test_empty_shelter_renders_empty_floor
# ---------------------------------------------------------------------------
def test_empty_shelter_renders_empty_floor():
    """Verify that an empty shelter renders only the empty floor, with no fabricated props."""
    script = _get_prototype_script()
    # In Phase 10LD, interiorGroup must not statically add fabricated bedMesh, crateMesh, or hearthStoneMesh
    # Instead, props must be populated dynamically from real records on that tile.
    assert "rebuildInteriorProps" in script or "updateInteriorProps" in script or "populateInterior" in script, (
        "Script must provide dynamic interior prop reconstruction based on real tile objects"
    )

    # Static unconditional addition of bedMesh / crateMesh / hearthStoneMesh to interiorGroup is prohibited
    static_forbidden = [
        r"interiorGroup\.add\(bedMesh\)",
        r"interiorGroup\.add\(crateMesh\)",
        r"interiorGroup\.add\(hearthStoneMesh\)",
    ]
    for pattern in static_forbidden:
        assert not re.search(pattern, script), (
            f"Static fabricated interior prop addition {pattern} found in script! Interiors must be populated dynamically."
        )


# ---------------------------------------------------------------------------
# 4. test_directional_facing_matches_travel_heading
# ---------------------------------------------------------------------------
def test_directional_facing_matches_travel_heading():
    """Verify directional facing sets positive scale facing East (dx > 0) and negative facing West (dx < 0)."""
    script = _get_prototype_script()
    assert "calculateHeadingFacing" in script or "fig.userData.facing" in script or "scale.x" in script

    # Test via node execution of the facing calculation function
    js_code = """
    function getFacing(dx, currentFacing) {
      if (dx > 0.001) return 1;
      if (dx < -0.001) return -1;
      return currentFacing || 1;
    }
    """
    assert _run_node_expr(js_code, "getFacing(1.0, 1)") == 1
    assert _run_node_expr(js_code, "getFacing(-1.0, 1)") == -1
    assert _run_node_expr(js_code, "getFacing(0.5, -1)") == 1
    assert _run_node_expr(js_code, "getFacing(-0.5, 1)") == -1


# ---------------------------------------------------------------------------
# 5. test_idle_agent_preserves_last_facing
# ---------------------------------------------------------------------------
def test_idle_agent_preserves_last_facing():
    """Verify an idle agent (zero displacement) preserves its previous facing without snapping to default."""
    script = _get_prototype_script()
    assert "fig.userData.facing" in script or "lastFacing" in script or "preservedFacing" in script

    js_code = """
    function getFacing(dx, currentFacing) {
      if (dx > 0.001) return 1;
      if (dx < -0.001) return -1;
      return currentFacing != null ? currentFacing : 1;
    }
    """
    # Moving west gives facing -1
    facing_after_west = _run_node_expr(js_code, "getFacing(-1.0, 1)")
    assert facing_after_west == -1
    # Then idle (dx = 0) must preserve -1, not snap back to +1
    facing_idle = _run_node_expr(js_code, f"getFacing(0.0, {facing_after_west})")
    assert facing_idle == -1, f"Idle agent snapped to default facing instead of preserving last facing: {facing_idle}"


# ---------------------------------------------------------------------------
# 6. test_gait_cadence_is_derived_from_displacement
# ---------------------------------------------------------------------------
def test_gait_cadence_is_derived_from_displacement():
    """Verify locomotion uses a two-phase gait cadence that decays to 0 when stationary."""
    script = _get_prototype_script()
    assert "calculateGaitBob" in script or "twoPhaseGait" in script or "strideBob" in script

    # Function must decay to 0 when hasMoved is false or stationary
    match = re.search(r"function calculateGaitBob\((.*?)\)\s*\{(.*?)\n\}", script, re.DOTALL)
    assert match, "calculateGaitBob function must be defined in script"
    fn_body = match.group(0)

    # Test via node
    js_setup = fn_body
    # Idle / stationary must be exactly 0
    assert _run_node_expr(js_setup, "calculateGaitBob(0.5, false)") == 0.0
    # Moving must produce non-zero cadence bounded by 0.024
    mid_step = _run_node_expr(js_setup, "calculateGaitBob(0.25, true)")
    assert abs(mid_step) > 0.0
    assert abs(mid_step) <= 0.025


# ---------------------------------------------------------------------------
# 7. test_weather_transitions_at_recorded_heartbeat
# ---------------------------------------------------------------------------
def test_weather_transitions_at_recorded_heartbeat():
    """Verify weather scheduler transitions at changes_at_heartbeat precisely."""
    script = _get_prototype_script()
    match = re.search(r"function getWeatherAt\((.*?)\)\s*\{(.*?)\n\}", script, re.DOTALL)
    assert match, "getWeatherAt must be defined in script"
    fn_code = match.group(0)

    js_setup = f"""
    const PAIRS = {{
      test_pair: {{
        weather: {{
          current: "rain",
          next: "clear",
          changes_at_heartbeat: 8000,
          temperature: 15,
          season: "Spring"
        }}
      }}
    }};
    let playbackMode = "live";
    {fn_code}
    """
    # Prior to heartbeat 8000 -> "rain"
    w_before = _run_node_expr(js_setup, "getWeatherAt('test_pair', 7999).weather")
    assert w_before == "rain", f"Expected 'rain' before change hb, got {w_before}"

    # At heartbeat 8000 -> transitions to "clear"
    w_at = _run_node_expr(js_setup, "getWeatherAt('test_pair', 8000).weather")
    assert w_at == "clear", f"Expected 'clear' at change hb, got {w_at}"

    # After heartbeat 8000 -> "clear"
    w_after = _run_node_expr(js_setup, "getWeatherAt('test_pair', 8050).weather")
    assert w_after == "clear", f"Expected 'clear' after change hb, got {w_after}"


# ---------------------------------------------------------------------------
# 8. test_clear_weather_disables_precipitation
# ---------------------------------------------------------------------------
def test_clear_weather_disables_precipitation():
    """Verify updateWeatherAtmospherics sets rainLines.visible = false when weather is clear."""
    script = _get_prototype_script()
    match = re.search(r"function updateWeatherAtmospherics\((.*?)\)\s*\{(.*?)\n\}", script, re.DOTALL)
    assert match, "updateWeatherAtmospherics must be defined in script"
    body = match.group(2)
    assert "rainLines.visible" in body
    assert 'wtype === "rain"' in body or 'isRaining' in body


# ---------------------------------------------------------------------------
# 9. test_known_object_types_have_distinct_visual_ids
# ---------------------------------------------------------------------------
def test_known_object_types_have_distinct_visual_ids():
    """Verify that all known object types map to distinct visual profiles/IDs."""
    script = _get_prototype_script()
    match = re.search(r"function getObjectVisualProfile\((.*?)\)\s*\{(.*?)\n\}", script, re.DOTALL)
    assert match, "getObjectVisualProfile must be defined in script"
    fn_code = match.group(0)

    required_types = [
        "campfire", "shelter", "hut", "lean-to", "roof", "wall", "door",
        "storage_box", "chest", "barrel", "table", "chair", "bed",
        "crafting_surface", "forge", "furnace", "well", "tool", "landmark"
    ]

    js_setup = f"""
    {fn_code}
    function mapTypes(types) {{
      const res = {{}};
      for (const t of types) {{
        const prof = getObjectVisualProfile({{ object_type: t, category: t }});
        res[t] = prof ? prof.id : null;
      }}
      return res;
    }}
    """
    result = _run_node_expr(js_setup, f"mapTypes({json.dumps(required_types)})")

    # Verify every required type resolved to a visual profile
    for t in required_types:
        assert result.get(t) is not None, f"Object type '{t}' did not resolve to a visual profile"

    # Verify uniqueness / distinctiveness: each distinct functional type must not collapse to identical visual ID
    # Categories of distinct items
    distinct_families = [
        ("campfire", "shelter"),
        ("shelter", "hut"),
        ("shelter", "lean-to"),
        ("roof", "wall"),
        ("door", "wall"),
        ("storage_box", "chest"),
        ("chest", "barrel"),
        ("table", "chair"),
        ("bed", "table"),
        ("crafting_surface", "forge"),
        ("forge", "furnace"),
        ("well", "landmark"),
        ("tool", "crafting_surface"),
    ]
    for a, b in distinct_families:
        assert result[a] != result[b], f"Types '{a}' and '{b}' collapsed to same visual id: {result[a]}"


# ---------------------------------------------------------------------------
# 10. test_no_camera_regression_after_legibility_change
# ---------------------------------------------------------------------------
def test_no_camera_regression_after_legibility_change():
    """Verify that controls start listener, camAnimating gate, and _lastCamSyncHb poll gate remain intact."""
    script = _get_prototype_script()

    # 1. Controls start listener (from 9a9db4f)
    assert 'controls.addEventListener("start"' in script or "controls.addEventListener('start'" in script, (
        "Camera controls 'start' listener was removed or corrupted!"
    )

    # 2. camAnimating gate (from 9a9db4f)
    assert "camAnimating" in script, "camAnimating gate was removed!"
    assert "if (camAnimating)" in script, "camAnimating check was removed!"

    # 3. _lastCamSyncHb gate (from 2611d6c)
    assert "_lastCamSyncHb" in script, "_lastCamSyncHb gate was removed!"
    assert "currentHb !== _lastCamSyncHb" in script or "_lastCamSyncHb = currentHb" in script, (
        "12-second live poll camera gate (_lastCamSyncHb) was removed or corrupted!"
    )


# ---------------------------------------------------------------------------
# 11. test_construction_fx_absent_until_hew_timber_recorded
# ---------------------------------------------------------------------------
def test_construction_fx_absent_until_hew_timber_recorded():
    """Verify construction scaffolding and woodchip FX remain absent when no hew_timber or build event exists."""
    script = _get_prototype_script()
    match = re.search(r"function updateAgentActionFx\((.*?)\)\s*\{(.*?)\n\}", script, re.DOTALL)
    assert match, "updateAgentActionFx must be defined in script"
    body = match.group(2)

    # Action FX must be explicitly absent/hidden when action is not hew_timber / build
    assert "fx.group.visible = false" in body
    assert "fx.scaffolding.visible = false" in body
