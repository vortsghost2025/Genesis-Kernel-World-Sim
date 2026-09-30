"""Human-friendly watcher alerts + test-build coalescing.

The operator's Telegram received 27 near-identical [HIGH] "Test build:"
alerts in one hour when West Eve ran a material-combination matrix during
her catch-up run. The signal was real and remarkable (an agent running a
controlled experiment) but the delivery was a firehose of key=value noise.

Two fixes, both tested here:

  * RENDER: plain sentences for humans. No `pair=west agent=unknown hb=968`
    telemetry line, no raw materials dict. The durable log keeps full
    fidelity; Telegram gets the readable version.
  * COALESCE: builds whose description opens with "Test build" are science,
    not show moments. They summarize: one alert per window per pair, with
    count and heartbeat range. Real builds (a charter stone, a meeting
    house, anything not prefixed Test) stay per-object and high — those
    ARE the show.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import agent_watch as aw  # noqa: E402


def _sig(**over):
    base = {
        "kind": "first_build",
        "key": "west:build:obj1",
        "severity": "high",
        "pair": "west",
        "agent": "Eve",
        "heartbeat": 968,
        "title": "west pair built: storage",
        "body": "Test build: mixed-material storage using clay and fiber.",
        "reply_hint": "object_id=obj1 materials={'clay': 1, 'fiber_plants': 1}",
    }
    base.update(over)
    return base


class TestRenderHumanFriendly:
    def test_no_key_value_telemetry_line(self):
        text = aw.render(_sig())
        assert "pair=" not in text
        assert "agent=" not in text
        assert "hb=" not in text

    def test_no_severity_bracket_noise(self):
        text = aw.render(_sig())
        assert "[HIGH]" not in text

    def test_names_agent_and_heartbeat_in_plain_words(self):
        text = aw.render(_sig())
        assert "Eve" in text
        assert "hb 968" in text or "heartbeat 968" in text

    def test_materials_dict_not_dumped(self):
        text = aw.render(_sig())
        assert "materials=" not in text
        assert "{'clay'" not in text

    def test_body_survives_verbatim(self):
        text = aw.render(_sig())
        assert "Test build: mixed-material storage" in text

    def test_render_survives_missing_optional_keys(self):
        """chain_watch sends its own shapes; render must not KeyError."""
        text = aw.render({
            "severity": "info",
            "title": "run monitor",
            "pair": "-",
            "agent": "-",
            "heartbeat": "-",
            "body": "channel works",
        })
        assert "run monitor" in text

    def test_severity_worded_not_shouted(self):
        low = aw.render(_sig(severity="low"))
        high = aw.render(_sig(severity="high"))
        assert "high" in high.lower()
        assert "high" not in low.lower()


class TestIsTestBuild:
    def test_test_prefix_is_science(self):
        assert aw._is_test_build(
            {"public_description": "Test build: clay and stone matrix."})

    def test_real_build_is_show(self):
        assert not aw._is_test_build(
            {"public_description": "A meeting house for us both."})

    def test_empty_description_is_not_test(self):
        assert not aw._is_test_build({"public_description": ""})


class TestCoalescedTestBuilds:
    def test_one_summary_per_window_not_per_object(self, tmp_path):
        store = tmp_path / "store"
        store.mkdir()
        objs = {}
        for i in range(5):
            objs[f"o{i}"] = {
                "object_type": "storage",
                "public_description": f"Test build: combo {i}",
                "materials": {"stone": 1},
                "created_heartbeat": 960 + i,
            }
        (store / "world_state.json").write_text(
            '{"data": {"public_objects": ' + repr(objs).replace("'", '"')
            + ', "tick": 965}}', encoding="utf-8")
        sigs = aw.scan_first_build("west", store)
        # The five test builds coalesce into ONE summary signal.
        assert len(sigs) == 1, sigs
        summary = sigs[0]
        assert summary["kind"] == "build_tests"
        assert "5" in summary["body"]
        assert "960" in summary["body"] and "964" in summary["body"]

    def test_real_build_stays_individual_and_high(self, tmp_path):
        store = tmp_path / "store"
        store.mkdir()
        objs = {
            "real1": {
                "object_type": "landmark",
                "public_description": "A meeting stone, founded on contact.",
                "materials": {"stone": 2},
                "created_heartbeat": 10,
            },
        }
        (store / "world_state.json").write_text(
            '{"data": {"public_objects": ' + repr(objs).replace("'", '"')
            + ', "tick": 11}}', encoding="utf-8")
        sigs = aw.scan_first_build("east", store)
        assert len(sigs) == 1
        assert sigs[0]["severity"] == "high"
        assert sigs[0]["kind"] == "first_build"

    def test_mixed_objects_split_correctly(self, tmp_path):
        store = tmp_path / "store"
        store.mkdir()
        objs = {
            "t1": {"object_type": "tool", "public_description": "Test build: x",
                   "materials": {"wood": 1}, "created_heartbeat": 100},
            "t2": {"object_type": "tool", "public_description": "Test build: y",
                   "materials": {"wood": 1}, "created_heartbeat": 101},
            "real": {"object_type": "shelter", "public_description": "Our house.",
                     "materials": {"wood": 3}, "created_heartbeat": 102},
        }
        (store / "world_state.json").write_text(
            '{"data": {"public_objects": ' + repr(objs).replace("'", '"')
            + ', "tick": 102}}', encoding="utf-8")
        sigs = aw.scan_first_build("east", store)
        kinds = sorted(s["kind"] for s in sigs)
        assert kinds == ["build_tests", "first_build"], kinds


class TestSummaryKeyStability:
    def test_window_key_is_stable_within_bucket(self):
        k1 = aw._test_window_key("west", 960)
        k2 = aw._test_window_key("west", 964)
        assert k1 == k2

    def test_window_key_moves_across_buckets(self):
        assert aw._test_window_key("west", 949) != aw._test_window_key(
            "west", 950)

    def test_keys_differ_by_pair(self):
        assert aw._test_window_key("east", 100) != aw._test_window_key(
            "west", 100)


class TestAgentResolution:
    def test_creator_resolved_to_name(self, tmp_path):
        store = tmp_path / "store"
        store.mkdir()
        adam_id = "genesis-agent-aaa"
        (store / "identity.json").write_text(
            '{"data": {"adam_agent_id": "genesis-agent-aaa", '
            '"eve_agent_id": "genesis-agent-bbb", "birth_candidate": {}}}',
            encoding="utf-8")
        objs = {
            "r1": {"object_type": "shelter",
                   "public_description": "Our house.",
                   "materials": {"wood": 3}, "created_heartbeat": 5,
                   "creator_agent_id": adam_id},
        }
        (store / "world_state.json").write_text(
            '{"data": {"public_objects": ' + repr(objs).replace("'", '"')
            + ', "tick": 6}}', encoding="utf-8")
        sigs = aw.scan_first_build("east", store)
        assert sigs[0]["agent"] == "Adam"

    def test_unresolvable_creator_falls_back_gracefully(self, tmp_path):
        store = tmp_path / "store"
        store.mkdir()
        objs = {
            "r1": {"object_type": "shelter", "public_description": "House.",
                   "materials": {"wood": 1}, "created_heartbeat": 5,
                   "creator_agent_id": "someone-else"},
        }
        (store / "world_state.json").write_text(
            '{"data": {"public_objects": ' + repr(objs).replace("'", '"')
            + ', "tick": 6}}', encoding="utf-8")
        sigs = aw.scan_first_build("east", store)
        assert sigs[0]["agent"] in ("someone", "unknown")
        assert sigs[0]["agent"] != ""
