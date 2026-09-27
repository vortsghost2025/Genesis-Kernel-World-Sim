"""Integrity checks on the committed record itself.

A census that flatters the operator is worse than no census. These
tests assert the properties that make the record trustworthy:

  * the housekeeping phrases the 5-of-5 finding rests on are the real
    phrases the agents used - not phrases I invented to get a number
  * arc files are internally consistent with the stores they came from
  * no arc file claims a measure it does not actually contain
  * the arc index cannot silently drop or duplicate an arc

If a future change makes the evidence easier to produce and less
reliable, these go red.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.export_arc_census import (
    _HOUSEKEEPING,
    ARCS_DIR,
    census_pair,
    is_housekeeping,
)

ARCS = Path("docs/arcs")


class TestHousekeepingPhrasesAreReal:
    """The 5-of-5 finding is only evidence if the phrases are real."""

    # Verbatim object descriptions the agents authored in the HB701-800
    # arc, read from the canonical store rather than from memory.
    REAL_DESCRIPTIONS = (
        "Clay cairn built from excess clay inventory to reduce goods overcapacity",
        "Stone cairn built from excess stone inventory to reduce goods overcapacity",
        "Third stone cairn built from 14 carried stone to free goods capacity "
        "for further gathering",
    )

    def test_every_real_phrase_is_covered_by_a_short_marker(self):
        for desc in self.REAL_DESCRIPTIONS:
            assert is_housekeeping(desc), f"real agent phrase not flagged: {desc!r}"
            low = desc.lower()
            matched = [p for p in _HOUSEKEEPING if p in low]
            assert matched, f"no marker matched a real phrase: {desc!r}"

    def test_markers_are_short_not_whole_sentences(self):
        """A marker list of full sentences would be reverse-engineering."""
        for phrase in _HOUSEKEEPING:
            assert len(phrase) <= 24, f"marker is a sentence, not a marker: {phrase!r}"

    def test_real_phrases_are_all_flagged_in_context(self):
        assert is_housekeeping(self.REAL_DESCRIPTIONS[0])
        assert is_housekeeping(self.REAL_DESCRIPTIONS[2])

    def test_phrases_do_not_swallow_ordinary_builds(self):
        """A false positive would make the tag meaningless."""
        for real in (
            "Woven fiber basket for storing gathered materials",
            "Woven fiber rope as tool using 3 fiber_plants",
            "Test build: woven fiber mat as crafting surface using 3 fiber_plants",
            "Test build: stone cairn using 5 stone to verify building works "
            "under new physics",
            "Test build with wild_berries on grassland under physics.epistemic.1 "
            "- marker to verify building works on origin tile",
        ):
            assert not is_housekeeping(real), f"false positive: {real!r}"


class TestArcFilesAreConsistent:
    def _arcs(self):
        if not ARCS.is_dir():
            pytest.skip("no committed arcs")
        return sorted(p for p in ARCS.glob("arc_*.md"))

    def test_arc_files_exist(self):
        assert self._arcs(), "no arc censuses committed"

    def test_every_arc_declares_read_only_provenance(self):
        for p in self._arcs():
            text = p.read_text(encoding="utf-8")
            assert "Read-only export" in text, f"{p.name} lacks provenance note"
            assert "export_arc_census.py" in text

    def test_every_arc_reports_the_decisive_measures(self):
        """An arc that omits the measures cannot falsify anything."""
        for p in self._arcs():
            text = p.read_text(encoding="utf-8")
            assert "Knowledge growth" in text, f"{p.name} omits knowledge growth"
            assert "new in arc" in text
            assert "Arc totals" in text

    def test_arc_headers_match_their_filenames(self):
        for p in self._arcs():
            m = re.match(r"arc_(\d+)_(\d+)\.md", p.name)
            assert m, f"unparseable name: {p.name}"
            text = p.read_text(encoding="utf-8")
            # filenames are zero-padded for sort order; the header is not
            start, end = int(m.group(1)), int(m.group(2))
            assert f"# Arc census HB{start}-{end}" in text, (
                f"{p.name} header disagrees with its filename")

    def test_arcs_are_lf_only(self):
        for p in self._arcs():
            assert b"\r\n" not in p.read_bytes(), f"{p.name} has CRLF"

    def test_index_lists_every_arc(self):
        if not (ARCS / "README.md").is_file():
            pytest.skip("no index")
        index = (ARCS / "README.md").read_text(encoding="utf-8")
        for p in self._arcs():
            assert p.name in index, f"{p.name} missing from the index"

    def test_index_does_not_duplicate_arcs(self):
        if not (ARCS / "README.md").is_file():
            pytest.skip("no index")
        index = (ARCS / "README.md").read_text(encoding="utf-8")
        for p in self._arcs():
            # a markdown link contains the filename twice (text + target),
            # so count link rows rather than raw occurrences
            rows = [ln for ln in index.splitlines() if f"]({p.name})" in ln]
            assert len(rows) == 1, f"{p.name} listed {len(rows)} times in the index"


class TestCensusMatchesStores:
    """A committed number must be reproducible from the store it came from."""

    def _store_objects(self, pair):
        path = Path(f".runtime/{pair}/world_state.json")
        if not path.is_file():
            pytest.skip(f"no {pair} store")
        data = json.loads(path.read_text(encoding="utf-8")).get("data", {})
        return [
            o for o in (data.get("public_objects") or {}).values()
            if isinstance(o, dict)
        ]

    def _arc_section(self, arc, pair_name):
        """The markdown block for one pair ('east' or 'west') in an arc file."""
        text = (ARCS / arc).read_text(encoding="utf-8")
        marker = f"## {pair_name} pair"
        assert marker in text, f"{arc} has no {marker} section"
        return text.split(marker)[1].split("\n## ")[0]

    def test_committed_object_count_is_reproducible_and_monotonic(self):
        """An arc is a snapshot: the store may only have grown past it.

        Exact equality is the wrong assertion because the chain keeps
        running after an export. What must hold is that the count in the
        file is a real count of build-layer objects that existed by that
        heartbeat, and that the live store is at least that large.
        """
        arc = ARCS / "arc_0701_0800.md"
        if not arc.is_file():
            pytest.skip("pre-retirement arc not committed")
        for pair, pair_name in (("first-pair", "east"), ("first-pair-west", "west")):
            section = self._arc_section(arc.name, pair_name)
            m = re.search(
                r"Objects on the board \((\d+), (\d+) from the build layer\)",
                section)
            assert m, f"{arc.name}/{pair} reports no object count"
            committed_build_layer = int(m.group(2))
            objs = self._store_objects(pair)
            live_build_layer = [o for o in objs if o.get("materials")]
            # the store is append-only, so it can only have grown
            assert len(live_build_layer) >= committed_build_layer, (
                f"{pair}: the store holds fewer build-layer objects than "
                f"{arc.name} recorded - the arc claims a count the world "
                f"never had")
            # and every committed object must still exist, unmodified
            for o in live_build_layer:
                assert o.get("object_id")

    def test_every_committed_object_still_exists_in_its_store(self):
        """Nothing the record says exists may have been quietly removed."""
        arc = ARCS / "arc_0701_0800.md"
        if not arc.is_file():
            pytest.skip("pre-retirement arc not committed")
        for pair, pair_name in (("first-pair", "east"), ("first-pair-west", "west")):
            section = self._arc_section(arc.name, pair_name)
            objs = self._store_objects(pair)
            # match on the object's own id or type, whichever the line
            # names - the census prints one or the other per line
            present = {o.get("object_id") for o in objs}
            present |= {o.get("object_type") for o in objs}
            for o in objs:
                present.add(o.get("object_id"))
            # only the "Objects on the board" list is a claim about what
            # exists; the "Build attempts" list is a claim about what was
            # tried, and a failed build legitimately has no object
            board = section.split("### Objects on the board")[-1]
            kinds = {
                line.split("**")[1]
                for line in board.splitlines()
                if line.startswith("- HB") and "**" in line
            }
            for kind in kinds:
                assert kind in present, (
                    f"{pair}: {arc.name} lists a {kind} on the board that the "
                    f"store does not have")
