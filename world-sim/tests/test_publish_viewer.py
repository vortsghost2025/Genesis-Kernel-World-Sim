"""The publish guard: a deployment becomes the public viewer only if verified.

The public URL was broken ~daily by unverified deployments (traced 2026-11-14
to the project's Git integration, since disconnected). These tests pin the two
pure decisions that keep a bad build from ever reaching the alias:

  parse_deploy_url  - must return a specific deployment, never the bare alias;
  assess            - must refuse a 404 page, an empty build, a stale build
                      that lacks the viewer's own code, or a dead texture.

Both are pure, so they are cheap and need no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

from publish_viewer import ALIAS, MARKERS, assess, parse_deploy_url  # noqa: E402

GOOD_HTML = "<!doctype html>" + "x" * 60_000 + "".join(MARKERS)


def _good_probes() -> dict:
    return {
        "root": {"status": 200, "bytes": 320_000},
        "paths": {"assets/grass_tuft.webp": {"status": 200, "bytes": 200_000},
                  "viewer_data.js": {"status": 200, "bytes": 26_000_000}},
        "html": GOOD_HTML,
    }


# --- parse_deploy_url -------------------------------------------------------

def test_reads_the_url_out_of_ansi_coloured_cli_output():
    raw = ("\x1b[1m>\x1b[0m Deploying...\n"
           "Preview   https://genesis-civilization-observatory-abc123xyz.vercel.app\n"
           '  "url": "https://genesis-civilization-observatory-abc123xyz.vercel.app"\n')
    assert parse_deploy_url(raw) == (
        "https://genesis-civilization-observatory-abc123xyz.vercel.app")


def test_never_returns_the_bare_alias_as_a_target():
    """The alias is not a deployment and must never be probed as one."""
    raw = f"Production  https://{ALIAS}\n"
    assert parse_deploy_url(raw) is None


def test_returns_none_when_there_is_no_deployment_line():
    assert parse_deploy_url("") is None
    assert parse_deploy_url("Error: Something went wrong") is None


# --- assess -----------------------------------------------------------------

def test_a_verified_deployment_is_accepted():
    ok, reasons = assess(_good_probes())
    assert ok, reasons


def test_a_404_page_is_refused():
    probes = _good_probes()
    probes["root"] = {"status": 404, "bytes": 74}
    probes["html"] = "The page could not be found"
    ok, reasons = assess(probes)
    assert not ok
    assert any("root status" in r for r in reasons)


def test_an_empty_build_is_refused_even_when_it_returns_200():
    """The exact failure that broke the public URL: 200 with no viewer in it."""
    probes = _good_probes()
    probes["html"] = "<html><body>Nothing here</body></html>"
    ok, reasons = assess(probes)
    assert not ok
    assert any("missing" in r for r in reasons)
    assert any("not the viewer" in r for r in reasons)


def test_a_stale_build_missing_one_marker_is_refused():
    probes = _good_probes()
    probes["html"] = GOOD_HTML.replace("groundCoverKindFor", "")
    ok, reasons = assess(probes)
    assert not ok
    assert any("groundCoverKindFor" in r for r in reasons)


@pytest.mark.parametrize("path", ["assets/grass_tuft.webp", "viewer_data.js"])
def test_a_dead_asset_is_refused(path):
    probes = _good_probes()
    probes["paths"][path] = {"status": 500, "bytes": 0}
    ok, reasons = assess(probes)
    assert not ok
    assert any(path in r for r in reasons)


def test_an_asset_returning_200_with_no_bytes_is_refused():
    probes = _good_probes()
    probes["paths"]["viewer_data.js"] = {"status": 200, "bytes": 0}
    ok, reasons = assess(probes)
    assert not ok
    assert any("no bytes" in r for r in reasons)


def test_the_marker_list_is_the_viewer_s_own_code():
    """If a marker is dropped from the viewer, this guard silently weakens."""
    html = (WORLD_SIM / "viewer" / "prototype" / "index.html").read_text(encoding="utf-8")
    missing = [m for m in MARKERS if m not in html]
    assert not missing, f"publish markers no longer exist in the viewer: {missing}"


# --- diagnosability of a failed deploy --------------------------------------

def test_a_deploy_that_yields_no_url_is_retried_once():
    """Measured 2026-11-15 10:21: one bare "could not read a deployment URL
    (rc=1)" with nothing else, and a manual deploy minutes later succeeded --
    so the failure was transient and the tool had no way to show that."""
    src = (WORLD_SIM / "scripts" / "publish_viewer.py").read_text(encoding="utf-8")
    assert "for attempt in (1, 2):" in src, "the deploy must be retried once"
    assert "time.sleep(15)" in src


def test_a_failed_deploy_logs_the_cli_output_tail():
    """So the next abort is diagnosable instead of a dead end."""
    src = (WORLD_SIM / "scripts" / "publish_viewer.py").read_text(encoding="utf-8")
    assert "produced no URL (rc=" in src
    assert "tail[:400]" in src
