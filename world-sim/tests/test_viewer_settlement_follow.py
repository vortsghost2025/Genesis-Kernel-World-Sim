"""Tests for Phase 10OR: settlement camera preset + follow-agent toggles.

Specification: docs/phase_10op_settlement_presets_and_follow_agent_spec.md
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


def _get_prototype_script() -> str:
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "prototype index.html must contain an inline script"
    return max(scripts, key=len)


def _extract_js_function(script: str, fn_name: str) -> str:
    pattern = rf"function\s+{fn_name}\s*\([^)]*\)\s*\{{.*?\n\}}"
    m = re.search(pattern, script, re.DOTALL)
    assert m, f"Function '{fn_name}' must be defined in prototype/index.html"
    return m.group(0)


def _run_node(js: str):
    res = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, check=True)
    return json.loads(res.stdout.strip())


def test_settlement_and_follow_buttons_exist_and_are_wired():
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    assert 'id="cam-settlement"' in html
    assert 'id="cam-follow-adam"' in html
    assert 'id="cam-follow-eve"' in html
    assert 'cam-settlement").onclick = () => applyCameraMode("settlement", false)' in html
    assert 'cam-follow-adam").onclick = () => toggleFollowAgent("adam")' in html
    assert 'cam-follow-eve").onclick = () => toggleFollowAgent("eve")' in html
    # Follow buttons must survive the per-mode active-class sweep.
    assert '.cam-btn:not(.follow-btn)' in html


def test_apply_camera_mode_has_settlement_branch_using_centroid():
    script = _get_prototype_script()
    assert '} else if (mode === "settlement") {' in script
    branch = script.split('} else if (mode === "settlement") {', 1)[1]
    branch = branch.split('} else if (mode === "adam") {', 1)[0]
    assert 'getElementById("cam-settlement").classList.add("active")' in branch
    assert "getSettlementCentroid(pairName)" in branch
    assert "settle ? settle.x : (ax + ex) * 0.5" in branch
    # Landscape blend must share the same centroid helper (no drift).
    assert "const settle = getSettlementCentroid(pairName);" in script
    assert "settle.x * 0.78 + agentCx * 0.22" in script
    # Non-agent modes release the follow lock.
    assert "setFollowAgentState(null);" in script


def test_animate_tracks_follow_agent_before_render():
    script = _get_prototype_script()
    animate_start = script.index("function animate(time) {")
    animate_src = script[animate_start:]
    follow_idx = animate_src.index("if (followAgent && selectedPair !== \"orbit\")")
    render_idx = animate_src.index("renderer.render(scene, camera);")
    assert follow_idx < render_idx, "follow block must run before the frame render"
    block = animate_src[follow_idx:render_idx]
    assert "const delta = desired.clone().sub(controls.target);" in block
    assert "camera.position.add(delta);" in block
    assert "controls.target.copy(desired);" in block
    assert "controls.update();" in block


def test_proto_exposes_follow_agent_state():
    script = _get_prototype_script()
    assert "followAgent," in script
    assert "setFollowAgent(agent) {" in script
    assert "toggleFollowAgent(agent) {" in script
    assert "setFollowAgentState(agent);" in script


def test_get_settlement_centroid_coordinates_regex_fallback_and_empty():
    script = _get_prototype_script()
    fn = _extract_js_function(script, "getSettlementCentroid")
    js = (
        "var PAIRS = { east: { public_objects: {\n"
        "  a: { tile_id: 'cont_a_gen_2_3' },\n"
        "  b: { tile_id: 'cont_a_gen_4_5' },\n"
        "  c: { tile_id: 'missing_gen_10_-2' },\n"
        "  d: {},\n"
        "  e: { tile_id: 'nope' } } }, west: { public_objects: {} } };\n"
        "var tilesById = new Map([\n"
        "  ['cont_a_gen_2_3', { coordinates: { x: 2, y: 3 } }],\n"
        "  ['cont_a_gen_4_5', { coordinates: { x: 4, y: 5 } }]\n"
        "]);\n"
        + fn
        + "\nconsole.log(JSON.stringify({ east: getSettlementCentroid('east'), west: getSettlementCentroid('west') }));\n"
    )
    d = _run_node(js)
    east = d["east"]
    assert east["count"] == 3, "two coordinate tiles + one regex fallback must count"
    assert abs(east["x"] - (16.0 / 3.0)) < 1e-9
    assert abs(east["z"] - 2.0) < 1e-9, "coordinates.y maps to world z"
    assert d["west"] is None, "empty public_objects must return null for agent fallback"
