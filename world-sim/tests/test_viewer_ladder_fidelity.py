"""The viewer may not keep its own version of the ladder.

The ladder lives in `backend/world/first_pair_runtime.py` (`_STRUCTURE_RUNGS`).
The viewer keeps a copy of it -- `RUNG_TABLE` in `viewer/prototype/index.html` --
because the HUD names the next rung. Two copies of one table is how a render
starts lying about the world, and it already happened: the backend gained `hall`
(7) and `stead` (8) in 10TC, the viewer's SPRITES were updated for them, but
`RUNG_TABLE` was not -- so for a pair owning both, no rung above 6 was found and
the HUD named "next: hall" on a settlement that already had one.

This test ties the two together so they cannot drift again.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_runtime import _STRUCTURE_RUNGS  # noqa: E402

VIEWER = WORLD_SIM / "viewer" / "prototype" / "index.html"


def _viewer_rung_table() -> dict[str, dict]:
    html = VIEWER.read_text(encoding="utf-8")
    m = re.search(r"const RUNG_TABLE\s*=\s*\[(.*?)\];", html, re.S)
    assert m, "RUNG_TABLE not found in the viewer"
    out: dict[str, dict] = {}
    for entry in re.finditer(
            r'\{\s*name:\s*"([^"]+)"\s*,\s*rung:\s*(\d+)\s*,\s*weight:\s*(\d+)\s*\}',
            m.group(1)):
        name, rung, weight = entry.group(1), int(entry.group(2)), int(entry.group(3))
        out[name] = {"rung": rung, "weight": weight}
    assert out, "RUNG_TABLE parsed to nothing"
    return out


def test_the_viewer_names_every_rung_the_backend_has():
    table = _viewer_rung_table()
    missing = sorted(set(_STRUCTURE_RUNGS) - set(table))
    assert not missing, f"viewer RUNG_TABLE is missing {missing}"


def test_the_viewer_adds_no_rung_the_backend_does_not_have():
    table = _viewer_rung_table()
    extra = sorted(set(table) - set(_STRUCTURE_RUNGS))
    assert not extra, f"viewer invents rungs the world does not have: {extra}"


def test_every_rung_number_matches_the_backend():
    table = _viewer_rung_table()
    bad = {n: (table[n]["rung"], _STRUCTURE_RUNGS[n]["rung"])
           for n in table if n in _STRUCTURE_RUNGS
           and table[n]["rung"] != _STRUCTURE_RUNGS[n]["rung"]}
    assert not bad, f"viewer rung numbers disagree with the world: {bad}"


def test_every_weight_matches_the_backend():
    """Weight drives how much a home counts; a drifted weight misreports the
    settlement's size."""
    table = _viewer_rung_table()
    bad = {n: (table[n]["weight"], _STRUCTURE_RUNGS[n].get("weight"))
           for n in table if n in _STRUCTURE_RUNGS
           and table[n]["weight"] != _STRUCTURE_RUNGS[n].get("weight")}
    assert not bad, f"viewer weights disagree with the world: {bad}"


def test_the_top_rung_is_actually_in_the_table():
    """The exact live failure: both lanes are at rung 8 and the table ended at 6,
    so the HUD named a rung they had already built."""
    table = _viewer_rung_table()
    top = max(rec["rung"] for rec in _STRUCTURE_RUNGS.values())
    assert top in {e["rung"] for e in table.values()}, \
        f"the highest rung ({top}) is not in the viewer's table"
