"""The viewer must speak the exporter's language.

The black-box viewer bug (Oct 17 2026) was a silent schema drift: the
viewer read `agents`, `objects`, `messages`, `tick` while the export
wrote `current_positions`, `public_objects`, `public_messages`,
`exported_tick`. Nothing failed loudly — the canvas just stayed black.

These tests pin the contract from both sides: the keys the exporter
writes, the keys the viewer reads, and the dead keys that must never
come back.
"""
from __future__ import annotations

import re
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
VIEWER_HTML = WORLD_SIM / "viewer" / "index.html"
EXPORTER = WORLD_SIM / "scripts" / "export_viewer_snapshot.py"

# Keys the exporter actually writes into VIEWER_DATA (verified against
# build_pair_snapshot / main in export_viewer_snapshot.py).
EXPORTED_PAIR_KEYS = (
    "agents",
    "exported_tick",
    "exported_at_utc",
    "current_positions",
    "public_objects",
    "public_messages",
    "inventories",
    "position_timeline",
)
EXPORTED_TOP_KEYS = ("true_map", "pairs", "shared_tiles", "world_size")
BACKDROP_PNG = WORLD_SIM / "viewer" / "world_base.png"


def _viewer_js() -> str:
    html = VIEWER_HTML.read_text(encoding="utf-8")
    blocks = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert blocks, "viewer index.html must contain an inline script block"
    # the main script is the largest inline block (a tiny cache-buster
    # script tag sits ahead of it)
    return max(blocks, key=len)


def _exporter_source() -> str:
    return EXPORTER.read_text(encoding="utf-8")


class TestExporterSide:
    def test_exporter_writes_every_key_the_contract_names(self):
        src = _exporter_source()
        for key in EXPORTED_PAIR_KEYS:
            assert f'"{key}"' in src, (
                f"exporter no longer writes pair key {key!r}; update "
                "EXPORTED_PAIR_KEYS and the viewer together"
            )
        for key in EXPORTED_TOP_KEYS:
            assert f'"{key}"' in src, (
                f"exporter no longer writes top-level key {key!r}"
            )

    def test_public_messages_carry_a_resolved_sender(self):
        """The viewer renders m.sender; the exporter must resolve it."""
        src = _exporter_source()
        assert '"sender"' in src, (
            "exporter must add a resolved 'sender' field to public_messages"
        )

    def test_full_world_backdrop_exists(self):
        """The unexplored world must have presence: the exporter renders
        the full true map to a 1px/tile PNG that the viewer draws dim.
        Without it the map is sparse dots on void."""
        assert BACKDROP_PNG.exists(), (
            "world_base.png missing — run export_viewer_snapshot.py"
        )
        assert BACKDROP_PNG.stat().st_size > 10_000, (
            "world_base.png suspiciously small for a 200x200 world"
        )
        assert "write_world_backdrop" in _exporter_source()
        # the viewer must read world_size from the snapshot root and
        # reference the backdrop by name
        js = _viewer_js()
        assert "D.world_size" in js, (
            "viewer must use the snapshot's full-world frame"
        )
        assert 'src = "world_base.png"' in js, (
            "viewer must draw the ghost backdrop"
        )


class TestViewerSide:
    def test_viewer_reads_exported_pair_keys(self):
        js = _viewer_js()
        for key in ("current_positions", "public_objects",
                    "public_messages", "exported_tick", "inventories"):
            assert key in js, (
                f"viewer never reads {key!r}; it cannot render the "
                "exported data"
            )

    def test_viewer_does_not_read_dead_keys(self):
        """The exact patterns that produced the silent black canvas."""
        js = _viewer_js()
        dead = [
            r"pairData\.objects\b",
            r"pd\.objects\b",
            r"\bpd\.messages\b",
            r"\bD\.tick\b",
            r"\bpdata\.tick\b",
            r"pairData\.tick\b",
            r"D\.generated_at",
            r"info\.tile_id\s*\|\|\s*info\.position",
        ]
        for pattern in dead:
            assert not re.search(pattern, js), (
                f"viewer references dead key pattern {pattern!r}; the "
                "exporter never wrote it"
            )

    def test_viewer_has_no_canvas_var_fillstyle(self):
        """ctx.fillStyle silently ignores var(--x) — walls rendered in
        the previous fill color instead of the wall color."""
        js = _viewer_js()
        bad = re.findall(r"fillStyle\s*=\s*['\"]var\(", js)
        assert not bad, (
            "canvas fillStyle must use literal colors, not CSS vars"
        )

    def test_viewer_escapes_agent_text_into_innerhtml(self):
        js = _viewer_js()
        assert "function esc(" in js, (
            "viewer must escape model-authored text before innerHTML"
        )
        assert "${esc(m.message" in js, (
            "public message bodies must go through esc() — they are "
            "model-authored strings"
        )
