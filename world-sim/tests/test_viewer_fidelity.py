"""Test suite for Phase 10KB: Continuous World Observatory Visual Fidelity.

Verifies:
1. export_viewer_snapshot.py exports fauna, compounds, and shelter_occupancy.
2. Standalone shelter occupancy detection logic for viewer exports.
3. prototype/index.html includes 3D fauna rendering (cow, horse, snake, deer, wolf).
4. prototype/index.html includes 3D atmospheric weather particle system.
5. prototype/index.html includes smart recent-action replay controls.
6. prototype/index.html includes dollhouse interior cutaway and 'Enter House' mode.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

WORLD_SIM = Path(__file__).resolve().parent.parent
EXPORTER_PATH = WORLD_SIM / "scripts" / "export_viewer_snapshot.py"
PROTOTYPE_HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"


def test_exporter_contract_includes_fauna_and_compounds():
    """export_viewer_snapshot.py must export fauna, compounds, and shelter_occupancy."""
    src = EXPORTER_PATH.read_text(encoding="utf-8")
    assert '"fauna"' in src, "export_viewer_snapshot.py must export fauna list"
    assert '"compounds"' in src, "export_viewer_snapshot.py must export compounds dictionary"
    assert '"shelter_occupancy"' in src, "export_viewer_snapshot.py must export shelter_occupancy"


def test_standalone_shelter_detection():
    """Test the module-level shelter detection helper in export_viewer_snapshot.py."""
    import sys
    if str(WORLD_SIM) not in sys.path:
        sys.path.insert(0, str(WORLD_SIM))
    from scripts import export_viewer_snapshot

    world_state = {
        "tile_occupancy": {
            "adam": "cont_a_gen_35_51",
            "eve": "cont_a_gen_10_10"
        },
        "public_objects": {
            "shelter-01": {
                "object_type": "shelter_hut",
                "tile_id": "cont_a_gen_35_51",
                "status": "active"
            }
        }
    }
    assert hasattr(export_viewer_snapshot, "is_agent_sheltered"), (
        "export_viewer_snapshot must provide is_agent_sheltered helper"
    )
    assert export_viewer_snapshot.is_agent_sheltered("adam", world_state) is True
    assert export_viewer_snapshot.is_agent_sheltered("eve", world_state) is False


def test_prototype_html_fauna_rendering():
    """prototype/index.html must implement 3D fauna rendering for domestic & wild animals."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    assert "fauna" in html, "prototype/index.html must process fauna data"
    assert "cow" in html.lower(), "prototype/index.html must render cows"
    assert "horse" in html.lower(), "prototype/index.html must render horses"
    assert "snake" in html.lower(), "prototype/index.html must render snakes"


def test_prototype_html_weather_particles():
    """prototype/index.html must implement a 3D precipitation particle system."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    assert "rain" in html.lower(), "prototype/index.html must handle rain"
    assert ("rainLines" in html or "rainPoints" in html or "precipitation" in html.lower()), (
        "prototype/index.html must instantiate a 3D rain particle system"
    )


def test_prototype_html_smart_recent_replay():
    """prototype/index.html must provide recent action replay / smart launch."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    assert ("replayRecent" in html or "btn-replay-recent" in html or "replay_recent" in html), (
        "prototype/index.html must provide a recent activity replay control"
    )


def test_prototype_html_dollhouse_interior_mode():
    """prototype/index.html must provide interior cutaway or Enter House mode."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    assert ("interior" in html.lower() or "enter-house" in html.lower() or "btn-interior" in html), (
        "prototype/index.html must provide an interior / Enter House mode"
    )


def test_prototype_html_action_particles_and_feedback():
    """prototype/index.html must implement visual action particle FX for physical actions."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    assert "actionFxGroup" in html, (
        "prototype/index.html must instantiate actionFxGroup"
    )
    assert "hew_timber" in html, "prototype/index.html must handle hew_timber action FX"
    assert "scaffolding" in html, "prototype/index.html must handle build scaffolding FX"
    assert "harvest_crop" in html, "prototype/index.html must handle crop action FX"

