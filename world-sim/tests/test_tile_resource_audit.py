"""Tile resource audit - the standing guard that the board is not rigged.

TDD suite for scripts/audit_tile_resources.py (§3.4 of
docs/epistemic_pressure_spec.md).

This exists because two pressure phases were designed by reasoning about
what agents would find interesting, and both were wrong in ways one
table of resource data would have shown: east_adam's home tile yields
exactly 1 wild_berry per heartbeat, which the consumption rule removed
again every heartbeat, pinning his food at 0 for 100+ ticks. He reported
it as a bug (HB797). Nobody read the table first.

The audit answers one question for every tile an agent can occupy: can
they actually acquire anything here, and if not, why not?
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_tile_resources import (
    ACCEPTED_FINDINGS,
    audit_true_map,
    render_audit,
    tile_offer_health,
)


def _resources(entries):
    return [
        {"tile_id": t, "kind": k, "amount": a, "renewable": r}
        for (t, k, a, r) in entries
    ]


class TestTileOfferHealth:
    def test_healthy_when_yield_exceeds_consumption(self):
        health = tile_offer_health(
            _resources([("t1", "stone", 5, False)]), consumption_per_tick=1
        )
        assert health["status"] == "healthy"
        assert health["net_gain"] == 4
        assert health["findings"] == []

    def test_deadlock_when_yield_equals_consumption(self):
        """The exact east_adam case: 1 berry offered, 1 consumed."""
        health = tile_offer_health(
            _resources([("t1", "wild_berries", 1, True)]), consumption_per_tick=1
        )
        assert health["status"] == "deadlock"
        assert health["net_gain"] == 0
        assert any("exactly cancelled" in f for f in health["findings"])

    def test_deadlock_when_consumption_exceeds_yield(self):
        health = tile_offer_health(
            _resources([("t1", "wild_berries", 1, True)]), consumption_per_tick=3
        )
        assert health["status"] == "deadlock"
        assert health["net_gain"] == -2

    def test_barren_when_no_resources(self):
        """The exact public-shared-center case: no resource records at all."""
        health = tile_offer_health([], consumption_per_tick=0)
        assert health["status"] == "barren"
        assert any("no resources" in f for f in health["findings"])

    def test_zero_amount_is_barren_not_healthy(self):
        health = tile_offer_health(
            _resources([("t1", "stone", 0, False)]), consumption_per_tick=0
        )
        assert health["status"] == "barren"

    def test_malformed_record_is_reported_never_skipped(self):
        bad = [{"tile_id": "t1", "kind": "stone"},  # no amount
               {"tile_id": "t1", "kind": "clay", "amount": "x"}]
        health = tile_offer_health(bad, consumption_per_tick=0)
        assert health["status"] == "malformed"
        # reported as a count, and never silently dropped
        assert any("2 malformed" in f for f in health["findings"])

    def test_no_consumption_is_never_a_deadlock(self):
        """After retirement nothing is removed, so a 1-berry tile is fine."""
        health = tile_offer_health(
            _resources([("t1", "wild_berries", 1, True)]), consumption_per_tick=0
        )
        assert health["status"] == "healthy"
        assert health["net_gain"] == 1

    def test_non_integer_consumption_treated_as_zero(self):
        health = tile_offer_health(
            _resources([("t1", "stone", 1, False)]), consumption_per_tick=None
        )
        assert health["status"] == "healthy"


class TestAuditTrueMap:
    def _map(self, entries):
        return {
            "tiles": [{"tile_id": "t1", "continent_id": "cont_a"}],
            "resources": entries,
        }

    def test_reports_only_requested_tiles(self):
        result = audit_true_map(
            self._map(_resources([("t1", "stone", 3, False), ("t2", "clay", 2, False)])),
            occupy=["t1"],
            consumption_per_tick=0,
        )
        assert [r["tile_id"] for r in result["tiles"]] == ["t1"]
        assert result["blocking"] == 0

    def test_counts_blocking_findings(self):
        result = audit_true_map(
            self._map(_resources([("t1", "stone", 3, False)])),
            occupy=["t1", "t_missing"],
            consumption_per_tick=0,
        )
        assert result["blocking"] == 1
        assert result["tiles"][1]["status"] == "barren"

    def test_deadlock_is_blocking_under_consumption(self):
        result = audit_true_map(
            self._map(_resources([("t1", "wild_berries", 1, True)])),
            occupy=["t1"],
            consumption_per_tick=1,
        )
        assert result["blocking"] == 1
        assert result["tiles"][0]["status"] == "deadlock"

    def test_known_finding_is_not_counted_as_new_blocking(self):
        """An operator-accepted finding is reported but not re-litigated."""
        base = self._map(_resources([("t1", "stone", 3, False)]))
        unaccepted = audit_true_map(base, occupy=["t1", "t_accepted"])
        assert unaccepted["blocking"] == 1
        accepted = audit_true_map(
            base,
            occupy=["t1", "t_accepted"],
            accepted={"t_accepted:barren": "operator accepted: barren post"},
        )
        assert accepted["blocking"] == 0
        assert accepted["accepted_count"] == 1
        # and it is still reported, not hidden
        assert accepted["tiles"][1]["status"] == "barren"


class TestRender:
    def test_render_names_every_finding(self):
        result = audit_true_map(
            {"tiles": [], "resources": _resources([("t1", "stone", 3, False)])},
            occupy=["t1", "t_barren"],
            consumption_per_tick=0,
        )
        text = render_audit(result)
        assert "t1" in text
        assert "t_barren" in text
        assert "barren" in text


class TestLiveBoard:
    """The real board, measured. This is the guard that would have caught it."""

    def _live_map(self):
        p = Path("data/world/true_map.json")
        if not p.is_file():
            pytest.skip("true map not present")
        return json.loads(p.read_text(encoding="utf-8"))

    def _occupied(self):
        tiles = []
        for pair in ("first-pair", "first-pair-west"):
            ws = Path(".runtime") / pair / "world_state.json"
            if not ws.is_file():
                continue
            data = json.loads(ws.read_text(encoding="utf-8")).get("data", {})
            tiles.extend((data.get("tile_occupancy") or {}).values())
            habitat = data.get("habitat") or {}
            tiles.extend((habitat.get("starting_tile_ids") or {}).values())
        return sorted(set(tiles))

    def test_every_occupied_tile_is_gatherable_after_retirement(self):
        result = audit_true_map(
            self._live_map(),
            occupy=self._occupied(),
            consumption_per_tick=0,
            accepted=ACCEPTED_FINDINGS,
        )
        unexpected = [
            f"{t['tile_id']}:{t['status']}"
            for t in result["tiles"]
            if t["status"] != "healthy"
            and f"{t['tile_id']}:{t['status']}" not in ACCEPTED_FINDINGS
        ]
        assert not unexpected, (
            "occupied tiles are un-gatherable and not operator-accepted: "
            + ", ".join(unexpected)
        )

    def test_east_adam_home_is_no_longer_a_deadlock(self):
        """The regression that motivated the whole audit."""
        result = audit_true_map(
            self._live_map(),
            occupy=["public-start-adam"],
            consumption_per_tick=0,
        )
        assert result["tiles"][0]["status"] == "healthy"

    def test_public_shared_center_is_known_and_accepted(self):
        """Eve's post genuinely has no resources. Recorded, not hidden."""
        result = audit_true_map(
            self._live_map(),
            occupy=["public-shared-center"],
            consumption_per_tick=0,
        )
        tile = result["tiles"][0]
        if tile["status"] != "healthy":
            assert "public-shared-center:barren" in ACCEPTED_FINDINGS
