"""The viewer build's swap must never half-happen or leave the old tree in front.

Measured defect (2026-11-14): the build had left a `viewer-deploy.old/` behind.
The swap renamed the previous build to that FIXED name, so when a locked file
had stopped the previous cleanup the name was still occupied, the rename failed
on Windows, the stale directory stayed, and every later build collided with it.
Worse, `main()` returned 0 even when the promotion failed -- and since the old
bundle is itself a valid viewer, the publish path would have verified and
shipped the PREVIOUS build while every check passed.

These tests drive the swap directly in a temporary viewer tree. No network, no
browser, no GPU.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import build_viewer_deploy as bvd  # noqa: E402


@pytest.fixture
def viewer(tmp_path, monkeypatch):
    """A throwaway viewer/ tree with the module's paths pointed at it."""
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir()
    monkeypatch.setattr(bvd, "VIEWER", viewer_dir)
    monkeypatch.setattr(bvd, "PUBLISHED", viewer_dir / "viewer-deploy")
    return viewer_dir


def _stage_build(viewer: Path, marker: str) -> Path:
    """Create a staging build and point DIST at it, as the build would."""
    staging = viewer / "viewer-deploy.staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "index.html").write_text(marker, encoding="utf-8")
    bvd.DIST = staging
    return staging


def _publish(viewer: Path, marker: str) -> Path | None:
    _stage_build(viewer, marker)
    return bvd._publish_staging()


def test_a_clean_build_publishes_and_leaves_nothing_behind(viewer):
    published = _publish(viewer, "v1")
    assert published == viewer / "viewer-deploy"
    assert (published / "index.html").read_text(encoding="utf-8") == "v1"
    assert not list(viewer.glob("viewer-deploy.old*")), "leftover .old dir"
    assert not (viewer / "viewer-deploy.staging").exists()


def test_the_second_build_replaces_the_first(viewer):
    _publish(viewer, "v1")
    published = _publish(viewer, "v2")
    assert (published / "index.html").read_text(encoding="utf-8") == "v2"
    assert not list(viewer.glob("viewer-deploy.old*"))


def test_a_leftover_old_dir_can_no_longer_block_the_swap(viewer):
    """THE regression: the old swap renamed onto this fixed name and collided."""
    _publish(viewer, "v1")
    (viewer / "viewer-deploy.old").mkdir()          # stale, as a lock would leave
    (viewer / "viewer-deploy.old" / "index.html").write_text("stale", encoding="utf-8")

    published = _publish(viewer, "v2")
    assert published is not None, "the swap collided with the leftover .old dir"
    assert (published / "index.html").read_text(encoding="utf-8") == "v2"


def test_sweep_removes_every_leftover_shape_and_the_staging_dir(viewer):
    (viewer / "viewer-deploy.old").mkdir()
    (viewer / "viewer-deploy.old-1234-5678").mkdir()
    (viewer / "viewer-deploy.staging").mkdir()

    stubborn = bvd._sweep_stale_dirs()

    assert stubborn == []
    assert not list(viewer.glob("viewer-deploy.old*"))
    assert not (viewer / "viewer-deploy.staging").exists()


def test_sweep_reports_a_locked_dir_instead_of_raising(viewer, monkeypatch):
    """A locked tree must never be fatal, and must not be forgotten."""
    locked = viewer / "viewer-deploy.old"
    locked.mkdir()
    real_rmtree = shutil.rmtree

    def fake_rmtree(path, *a, **kw):
        if Path(path) == locked:
            raise PermissionError("in use by another process")
        return real_rmtree(path, *a, **kw)

    monkeypatch.setattr(bvd.shutil, "rmtree", fake_rmtree)
    stubborn = bvd._sweep_stale_dirs()
    assert stubborn and "viewer-deploy.old" in stubborn[0]
    assert locked.exists(), "the sweep should leave it, not destroy it half-way"


def test_quarantine_names_are_unique_so_they_cannot_collide(viewer):
    names = set()
    for i in range(3):
        target = viewer / f"victim{i}"
        target.mkdir()
        q = bvd._quarantine(target)
        assert q is not None and q != target
        assert q.name.startswith("victim")
        assert ".old-" in q.name
        names.add(q.name)
    assert len(names) == 3, "quarantine names collided"


def test_a_failed_promotion_reports_failure_rather_than_success(viewer, monkeypatch):
    """If the swap cannot complete, the build must NOT claim success."""
    monkeypatch.setattr(bvd, "_quarantine", lambda path: None)
    (viewer / "viewer-deploy").mkdir()          # previous build in place
    assert _publish(viewer, "v2") is None


def test_main_fails_the_build_when_the_swap_fails():
    """Pin the contract in the source: main() must return non-zero on None.

    A silent success here is the dangerous case -- the previous bundle is a
    valid viewer, so the publish verifier would accept it and ship the OLD
    build while every check passed.
    """
    src = (WORLD_SIM / "scripts" / "build_viewer_deploy.py").read_text(encoding="utf-8")
    assert "final = _publish_staging()" in src
    assert "if final is None:" in src
    assert "return 1" in src


def test_the_swap_uses_a_unique_name_not_a_fixed_one():
    """The exact defect: a fixed `.old` name that a leftover could occupy."""
    src = (WORLD_SIM / "scripts" / "build_viewer_deploy.py").read_text(encoding="utf-8")
    assert 'VIEWER / "viewer-deploy.old"' not in src
    assert "os.getpid()" in src and "_QUARANTINE_SEQ" in src
