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
    assert "new THREE.Vector3(targetX + 0.3, sh + 0.35, targetZ - 1.2),\n      immediate" in script


def test_interior_clearance_and_framing():
    script = _get_prototype_script()
    assert 'activeCamMode === "interior") ? 1.45 : 3.0' in script
    assert "camera.fov = 55;" in script
    assert "new THREE.Vector3(targetX - 0.4, sh + 0.95, targetZ + 2.9)" in script


def test_cutaway_hides_whole_tile_and_restores_all():
    script = _get_prototype_script()
    assert "cutawayShelterProps = []" in script
    assert "const onTile = (coords.tileId != null && ud.tile_id === coords.tileId);" in script
    assert "Math.max(dx, dz) <= 2" in script
    assert "cutawayShelterProps.push(child)" in script
    assert "for (const prop of cutawayShelterProps) {" in script
    # re-hide must be re-appliable after object-set rebuilds, with stale reset
    assert "function hideExteriorPropsForInterior()" in script
    assert "hideExteriorPropsForInterior();" in script


def test_sync_stays_interior_props_refresh_only():
    script = _get_prototype_script()
    assert 'if (activeCamMode === "interior" && !immediateCam) {' in script
    assert "refreshInteriorProps();" in script
    assert "function refreshInteriorProps()" in script
    # refresh must not touch the camera
    fn = re.search(r"function refreshInteriorProps\(\) \{.*?\n\}", script, re.DOTALL).group(0)
    assert "smoothMoveCamera" not in fn
    assert "applyCameraMode" not in fn
