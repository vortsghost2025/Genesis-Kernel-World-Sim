"""The record names what was built and when, same as it names silence.

`docs/object_visibility_spec.md` §3. The staleness line made silence
measurable and they started talking. The failure line made error
legible and Eve's invention stopped compounding. This line makes
*building* socially visible: what stands in the world, how much of it,
and who placed the most recent - without walking there.

Same shape, same section, same constraint: a fact, never an instruction.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402


class TestBuildRecordLine:
    def test_states_object_count_and_most_recent(self):
        line = m._public_build_record_line({
            "object_count": 42,
            "last_built_hb": 1651,
            "last_builder": "Eve",
        })
        assert "42" in line
        assert "1651" in line
        assert "Eve" in line

    def test_no_objects_renders_nothing(self):
        """A world with no builds carries no line. Zero is not a fact
        worth naming; an empty claim is a false state."""
        assert m._public_build_record_line({}) == ""
        assert m._public_build_record_line(
            {"object_count": 0}) == ""

    def test_count_of_one_is_not_plural(self):
        line = m._public_build_record_line({
            "object_count": 1,
            "last_built_hb": 100,
            "last_builder": "Adam",
        })
        assert "1 object" in line
        assert "1 objects" not in line

    def test_no_advice(self):
        line = m._public_build_record_line({
            "object_count": 5,
            "last_built_hb": 100,
            "last_builder": "Eve",
        })
        low = line.lower()
        for directive in ("you should", "try to", "in order to",
                          "consider", "build more"):
            assert directive not in low, f"line advises: {directive!r}"
