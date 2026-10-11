"""A route health check before a run prevents the frozen-heartbeat pattern.

Three freezes now (Sept 30, Oct 2, Oct 10): the configured model died
upstream and every heartbeat ran inert until the frozen-detection killed
the chain. The net catches you after you've fallen; the preflight is
not walking onto the ice.

The check is one tiny request per lane. If both primary and fallback
answer, the run starts. If the primary is dead but the fallback answers,
the run starts with a warning - the fallback will serve. If both are
dead, the run refuses to start and says so, because 100 inert heartbeats
is not a result.

Unit under test: the decision, as a pure function.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import lockstep_chain as lc  # noqa: E402


class TestRouteHealthVerdict:
    def test_both_alive_means_go(self):
        v = lc.route_health_verdict(primary_ok=True, fallback_ok=True)
        assert v["action"] == "go"

    def test_primary_dead_fallback_alive_means_go_with_warning(self):
        v = lc.route_health_verdict(primary_ok=False, fallback_ok=True)
        assert v["action"] == "go"
        assert "fallback" in v["note"].lower()

    def test_both_dead_means_refuse(self):
        v = lc.route_health_verdict(primary_ok=False, fallback_ok=False)
        assert v["action"] == "refuse"
        assert "both" in v["note"].lower() or "dead" in v["note"].lower()

    def test_primary_alive_fallback_dead_means_go(self):
        v = lc.route_health_verdict(primary_ok=True, fallback_ok=False)
        assert v["action"] == "go"


class TestRefusalIsLoud:
    def test_refusal_names_the_condition_not_a_guess(self):
        v = lc.route_health_verdict(primary_ok=False, fallback_dead_reason="404",
                                    fallback_ok=False)
        assert "404" in v["note"]
