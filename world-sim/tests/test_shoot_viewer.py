"""The viewer capture tool: headless, so a screenshot never needs a window.

The reason this exists: asking the operator to hold a desktop window in the
foreground made my problem his, and he was right to call that out. A capture
must not depend on what he is doing, and it must not touch the GPU that crashed
twice -- so it runs Chrome headless with software WebGL (SwiftShader).

The URL building is pure and tested here; the capture itself is exercised by
running the tool, which needs Chrome and the network.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

from shoot_viewer import BASE, build_url  # noqa: E402


def test_a_plain_civ_url():
    assert build_url("east", "") == f"{BASE}/?civ=east"


def test_a_camera_is_appended_not_replaced():
    assert build_url("west", "adam") == f"{BASE}/?civ=west&cam=adam"


def test_an_override_url_wins_untouched():
    """So a deployment's direct URL or a local file can be shot as-is."""
    other = "https://genesis-civilization-observatory-abc123.vercel.app/?civ=west"
    assert build_url("east", "adam", override=other) == other


def test_the_tool_uses_software_webgl():
    """Pinned deliberately: the GPU crashed twice, so a capture must never use
    it. If someone removes this flag, this test is the tripwire."""
    src = (WORLD_SIM / "scripts" / "shoot_viewer.py").read_text(encoding="utf-8")
    assert "--use-angle=swiftshader" in src
    assert "headless=True" in src


def test_it_waits_for_painted_frames_not_a_fixed_sleep():
    """A screenshot taken too early is an empty blue field."""
    src = (WORLD_SIM / "scripts" / "shoot_viewer.py").read_text(encoding="utf-8")
    assert "requestAnimationFrame" in src
    assert "min-frames" in src or "min_frames" in src


def test_it_can_drive_the_viewers_own_controls():
    """The interior view has no URL flag, so the tool must be able to click."""
    src = (WORLD_SIM / "scripts" / "shoot_viewer.py").read_text(encoding="utf-8")
    assert "--click" in src
    assert ".click(" in src
