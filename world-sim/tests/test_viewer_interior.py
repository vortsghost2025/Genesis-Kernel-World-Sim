"""Tests for Phase 10OX: interior camera cooperation fix.

Specification: docs/phase_10ov_interior_camera_cooperation_fix_spec.md
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

PROTOTYPE_HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"


def _get_prototype_script() -> str:
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "prototype index.html must contain an inline script"
    return max(scripts, key=len)


def test_interior_button_snaps_and_branch_passes_immediate():
    script = _get_prototype_script()
    assert 'camInterior.onclick = () => applyCameraMode("interior", true)' in script
    assert "new THREE.Vector3(targetX + 0.1, sh + 0.4, targetZ - 1.6),\n      immediate" in script


def test_interior_clearance_and_framing():
    script = _get_prototype_script()
    assert 'activeCamMode === "interior") ? 1.45 : 3.0' in script
    assert "camera.fov = 58;" in script
    # camera inside the room, looking at the back wall, never the door
    assert "new THREE.Vector3(targetX + 0.2, sh + 1.55, targetZ + 1.35)" in script


def test_interior_volume_is_enclosed_room():
    script = _get_prototype_script()
    assert "const wallH = 1.9;" in script
    assert "roof:" in script
    assert "spec.roof" in script
    # front door-gap walls are full height too
    assert '{ id: "front_left",  width: frontSegW, height: wallH, depth: wallT' in script
    # figures sit across the room, not in the camera's face
    assert "(isEve ? -1.0 : 0.9)" in script
    assert "(isEve ? -0.7 : -0.9)" in script


def test_wall_roof_texture_and_warm_light():
    script = _get_prototype_script()
    assert "logWallMat" in script and "roofMat" in script
    assert "spec.roof" in script and "slopeLen" in script
    assert "new THREE.PointLight(0xffb45e" in script
    assert "sillWallMat = logWallMat" in script


def test_person_cameras_gaze_at_nearest_shelter():
    script = _get_prototype_script()
    assert "function getNearestShelterXY(pairName, fromX, fromZ)" in script
    assert "const shelterA = getNearestShelterXY(pairName, ax, az);" in script
    assert "const shelterE = getNearestShelterXY(pairName, ex, ez);" in script
    # elevated shelter-ward vantage (agent + house in one frame)
    assert "camX = ax - ux * 7.0;" in script
    assert "camX = ex - ux * 7.0;" in script
    assert "lookX = shelterA.x;" in script
    assert "lookX = shelterE.x;" in script
    assert "function clearCameraSpot(cid, cam, look)" in script
    assert "clearCameraSpot(cid, new THREE.Vector3(camX," in script


def test_cutaway_hides_whole_tile_and_restores_all():
    script = _get_prototype_script()
    assert "cutawayShelterProps = []" in script
    assert "cutawayShelterProps.push(child)" in script
    assert "for (const prop of cutawayShelterProps) {" in script
    # re-hide must be re-appliable after object-set rebuilds, with stale reset
    assert "function hideExteriorPropsForInterior()" in script
    assert "hideExteriorPropsForInterior();" in script
    # sealed interior: every object prop hides, no neighbor sprite peeks over the wall
    assert "child.visible = false;" in script


def test_sync_stays_interior_props_refresh_only():
    script = _get_prototype_script()
    assert 'if (activeCamMode === "interior" && !immediateCam) {' in script
    assert "refreshInteriorProps();" in script
    assert "function refreshInteriorProps()" in script
    # refresh must not touch the camera
    fn = re.search(r"function refreshInteriorProps\(\) \{.*?\n\}", script, re.DOTALL).group(0)
    assert "smoothMoveCamera" not in fn
    assert "applyCameraMode" not in fn
