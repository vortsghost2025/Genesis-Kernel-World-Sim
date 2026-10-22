"""The viewer must speak the exporter's language.

The black-box viewer bug (Oct 17 2026) was a silent schema drift: the
viewer read `agents`, `objects`, `messages`, `tick` while the export
wrote `current_positions`, `public_objects`, `public_messages`,
`exported_tick`. Nothing failed loudly — the canvas just stayed black.

The viewer was rebuilt since (Oct 19-20: tabbed observatory, terrain
splatting, playback, client-side weather). These tests pin the
contract as it now stands: the keys the exporter writes, the keys the
rebuilt viewer reads, and the dead keys that must never come back.
"""
from __future__ import annotations

import re
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
VIEWER_HTML = WORLD_SIM / "viewer" / "index.html"
EXPORTER = WORLD_SIM / "scripts" / "export_viewer_snapshot.py"
BACKDROP_PNG = WORLD_SIM / "viewer" / "world_base.png"

# Keys the exporter writes into each pair's snapshot.
EXPORTED_PAIR_KEYS = (
    "agents",
    "exported_tick",
    "exported_at_utc",
    "current_positions",
    "public_objects",
    "public_messages",
    "inventories",
    "position_timeline",
    "vitals",
    "weather",
    "chronicle",
    "agent_asks",
)
EXPORTED_TOP_KEYS = ("true_map", "pairs", "shared_tiles", "world_size")


def _viewer_js() -> str:
    html = VIEWER_HTML.read_text(encoding="utf-8")
    blocks = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert blocks, "viewer index.html must contain an inline script block"
    # the main script is the largest inline block
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
        """The comms/chronicle renders name the actor; the exporter must
        resolve senders rather than shipping raw agent hashes."""
        src = _exporter_source()
        assert '"sender"' in src

    def test_full_world_backdrop_exists(self):
        """The full 200x200 true map renders server-side to a tiny PNG
        and ships as world_size metadata. The rebuilt viewer computes
        its own terrain client-side, so the PNG is exporter-side
        reference data — it must still build without breaking."""
        assert BACKDROP_PNG.exists(), (
            "world_base.png missing — run export_viewer_snapshot.py"
        )
        assert "write_world_backdrop" in _exporter_source()
        src = _exporter_source()
        assert '"world_size"' in src


class TestViewerSide:
    def test_viewer_reads_exported_pair_keys(self):
        """The rebuilt viewer's actual data reads. If the viewer is
        rebuilt again, this list moves with it — deliberately."""
        js = _viewer_js()
        for key in ("current_positions", "public_objects", "inventories",
                    "vitals", "chronicle", "agent_asks",
                    "position_timeline", "shared_tiles"):
            assert key in js, (
                f"viewer never reads {key!r}; it cannot render the "
                "exported data"
            )

    def test_viewer_computes_weather_client_side(self):
        """Accepted duplication: the viewer reimplements the weather
        machine so playback can scrub history without re-fetching. The
        vocabulary must stay aligned with backend/world/survival.py."""
        js = _viewer_js()
        assert "getWeatherAt" in js
        assert "WEATHER_TABLE" in js
        survival = (WORLD_SIM / "backend" / "world" / "survival.py"
                    ).read_text(encoding="utf-8")
        for wtype in ("clear", "overcast", "rain", "storm"):
            assert f'"{wtype}"' in js and f'"{wtype}"' in survival

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
        """ctx.fillStyle silently ignores var(--x)."""
        js = _viewer_js()
        bad = re.findall(r"fillStyle\s*=\s*['\"]var\(", js)
        assert not bad, (
            "canvas fillStyle must use literal colors, not CSS vars"
        )

    def test_viewer_escapes_model_text_into_innerhtml(self):
        """Agent-authored strings must not reach innerHTML raw."""
        js = _viewer_js()
        assert "function esc(" in js, (
            "viewer must escape model-authored text before innerHTML"
        )
