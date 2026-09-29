"""Runner for phased memory-synthesis backfill.

`docs/memory_synthesis_spec.md` §5: synthesis never runs in the heartbeat
path. This script is the background cadence — plan coverage, call the model
once per group, validate, append. Fail-closed per group, bounded per run.

Default is dry-run (plan only): no model calls, no writes. `--apply`
performs the pass and still requires the vault + the free-only proof.

No test here touches the network, wall-clock time, or `world-sim/data`.
Live-store runs are an explicitly authorized operation, never a test.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

runner = importlib.import_module("run_memory_synthesis")

ADAM_ID = "genesis-agent-aaa"


def _mem(heartbeat: int, content: str) -> dict:
    return {"heartbeat": heartbeat, "content": content, "type": "reflection"}


def _seeded_store(tmp_path, owner_ref="east_adam", n=10):
    from backend.world.first_pair_persistence import (
        FirstPairPersistenceStore,
        save_memory,
    )

    store = FirstPairPersistenceStore(tmp_path / "store")
    save_memory(store, {
        owner_ref: [
            _mem(hb, f"event {hb} at cont_a_gen_1_2 with wild_berries")
            for hb in range(1, n + 1)
        ],
        "east_eve" if owner_ref == "east_adam" else "east_adam": [],
    })
    return store


def _good_synth(covered: list[dict], owner_id: str) -> dict:
    hbs = sorted(m["heartbeat"] for m in covered)
    return {
        "text": f"Heartbeat {hbs[0]}-{hbs[-1]}: surveyed cont_a_gen_1_2 and gathered wild_berries.",
        "salient_entities": ["cont_a_gen_1_2", "wild_berries"],
    }


class TestPromptBuilder:
    def test_prompt_contains_every_covered_content(self):
        mems = [_mem(1, "alpha marker"), _mem(2, "beta marker")]
        prompt = runner.build_synthesis_prompt(mems, "east_adam")
        assert "alpha marker" in prompt
        assert "beta marker" in prompt

    def test_prompt_forbids_invention_and_demands_json(self):
        prompt = runner.build_synthesis_prompt([_mem(1, "x")], "east_adam")
        lowered = prompt.lower()
        assert "json" in lowered
        assert "salient_entities" in prompt
        assert "only" in lowered and "appear" in lowered

    def test_prompt_bans_thinking_out_loud(self):
        """Measured failure: the model preambles, burns tokens, and the JSON
        truncates. The prompt must forbid preamble explicitly."""
        prompt = runner.build_synthesis_prompt([_mem(1, "x")], "east_adam")
        assert "nothing else" in prompt.lower()
        assert "preamble" in prompt.lower()

    def test_no_preamble_rule_opens_the_prompt(self):
        """Measured failure continued: a ban at the bottom was talked past.
        The rule leads, not just closes — primacy and recency."""
        prompt = runner.build_synthesis_prompt([_mem(1, "x")], "east_adam")
        head = "\n".join(prompt.splitlines()[:4]).lower()
        assert "entire reply" in head
        assert "json" in head


class TestResponseParser:
    def test_valid_response_parses(self):
        payload, errors = runner.parse_synthesis_response(
            '{"text": "surveyed the hills.", "salient_entities": ["hills"]}'
        )
        assert errors == []
        assert payload["text"] == "surveyed the hills."

    def test_fenced_response_parses(self):
        payload, errors = runner.parse_synthesis_response(
            '```json\n{"text": "t", "salient_entities": []}\n```'
        )
        assert errors == []
        assert payload["text"] == "t"

    def test_garbage_is_an_error_not_an_exception(self):
        payload, errors = runner.parse_synthesis_response("not json at all {{{")
        assert payload is None
        assert errors

    def test_missing_keys_are_an_error(self):
        payload, errors = runner.parse_synthesis_response('{"text": "t"}')
        assert payload is None
        assert errors

    def test_wrong_types_are_an_error(self):
        payload, errors = runner.parse_synthesis_response(
            '{"text": 42, "salient_entities": "hills"}'
        )
        assert payload is None
        assert errors

    def test_prose_wrapped_json_is_unwrapped(self):
        payload, errors = runner.parse_synthesis_response(
            'Here is the rollup:\n{"text": "surveyed.", '
            '"salient_entities": []}\nHope that helps.'
        )
        assert errors == []
        assert payload["text"] == "surveyed."

    def test_prose_without_json_still_fails(self):
        payload, errors = runner.parse_synthesis_response(
            "I cannot comply with that request."
        )
        assert payload is None
        assert errors


class TestEmptyResponseRetry:
    """200 with no choices: retryable transient, then success."""

    def _client(self, replies):
        class Msg:
            def __init__(self, content):
                self.content = content

        class Choice:
            def __init__(self, content):
                self.message = Msg(content)

        class Resp:
            def __init__(self, contents):
                self._contents = contents

            @property
            def choices(self):
                if self._contents is None:
                    return None
                return [Choice(c) for c in self._contents]

        class Client:
            def __init__(self):
                self.calls = 0
                self.chat = self
                self.completions = self

            def create(self, **kwargs):
                self.calls += 1
                return Resp(replies[min(self.calls - 1, len(replies) - 1)])

        return Client()

    def _patched_synth(self, monkeypatch, clients):
        import openai
        made = {"n": 0}

        def fake_openai(**kwargs):
            client = clients[min(made["n"], len(clients) - 1)]
            made["n"] += 1
            return client

        monkeypatch.setattr(openai, "OpenAI", fake_openai)
        return runner._live_synthesizer(["k1"] * len(clients),
                                        "https://x", "m")

    def test_empty_then_valid_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setattr(runner.time, "sleep", lambda s: None)
        store = _seeded_store(tmp_path, n=8)
        client = self._client([
            None,  # first call: empty choices
            ['{"text": "surveyed cont_a_gen_1_2.", "salient_entities": ["cont_a_gen_1_2"]}'],
        ])
        synth = self._patched_synth(monkeypatch, [client])
        mems = [{"heartbeat": 1, "content": "surveyed cont_a_gen_1_2",
                 "type": "reflection"}]
        out = synth(mems, ADAM_ID)
        assert out["text"] == "surveyed cont_a_gen_1_2."
        assert client.calls == 2

    def test_persistent_empty_fails_closed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(runner.time, "sleep", lambda s: None)
        client = self._client([None, None, None, None])
        synth = self._patched_synth(monkeypatch, [client])
        mems = [{"heartbeat": 1, "content": "x", "type": "reflection"}]
        with pytest.raises(Exception):
            synth(mems, ADAM_ID)
        assert client.calls == 2, "bounded retries, then stop"

    def test_unparseable_failure_carries_raw_snippet(self, tmp_path,
                                                    monkeypatch):
        monkeypatch.setattr(runner.time, "sleep", lambda s: None)
        client = self._client([["sorry, cannot do that"]])
        synth = self._patched_synth(monkeypatch, [client])
        mems = [{"heartbeat": 1, "content": "x", "type": "reflection"}]
        with pytest.raises(ValueError) as exc:
            synth(mems, ADAM_ID)
        assert "raw:" in str(exc.value)
        assert "sorry" in str(exc.value)


class TestFreeLaneGate:
    def test_pinned_primary_with_free_fallback_passes(self):
        from backend.world.canonical_heartbeat_runner import (
            PRIMARY_MODEL,
            PRIMARY_BASE_URL,
        )

        ok, _ = runner.free_lane_ok(PRIMARY_MODEL, PRIMARY_BASE_URL,
                                    "someone/glm:free")
        assert ok

    def test_paid_fallback_fails(self):
        from backend.world.canonical_heartbeat_runner import (
            PRIMARY_MODEL,
            PRIMARY_BASE_URL,
        )

        ok, reason = runner.free_lane_ok(PRIMARY_MODEL, PRIMARY_BASE_URL,
                                         "someone/glm:paid")
        assert not ok
        assert "free" in reason.lower()

    def test_wrong_primary_model_fails(self):
        from backend.world.canonical_heartbeat_runner import PRIMARY_BASE_URL

        ok, _ = runner.free_lane_ok("evil/model", PRIMARY_BASE_URL,
                                    "someone/glm:free")
        assert not ok

    def test_wrong_base_url_fails(self):
        from backend.world.canonical_heartbeat_runner import PRIMARY_MODEL

        ok, _ = runner.free_lane_ok(PRIMARY_MODEL, "https://evil.example/v1",
                                    "someone/glm:free")
        assert not ok


class TestDryRunDefault:
    def test_without_apply_nothing_is_called_or_written(self, tmp_path, capsys):
        store = _seeded_store(tmp_path)
        calls: list = []

        def spy(covered: list[dict], owner_id: str) -> dict:
            calls.append((covered, owner_id))
            return _good_synth(covered, owner_id)

        rc = runner.main([
            "--store", str(tmp_path / "store"),
            "--owner-ref", "east_adam",
            "--owner-id", ADAM_ID,
            "--max-rollups", "2",
        ])
        assert rc == 0
        assert calls == [], "dry-run must not call the synthesizer"
        from backend.world.first_pair_persistence import load_summaries
        assert load_summaries(store) == [], "dry-run must not write"
        out = capsys.readouterr().out
        assert "DRY-RUN" in out


class TestLivePass:
    def test_bounded_pass_appends_valid_records(self, tmp_path):
        store = _seeded_store(tmp_path, n=10)
        report = runner.run_synthesis_pass(
            store, "east_adam", ADAM_ID, _good_synth,
            max_rollups=2, group_size=4,
        )
        assert report["appended"] == 2
        assert report["failed"] == []
        from backend.world.first_pair_persistence import load_summaries
        sums = [s for s in load_summaries(store) if s.owner_agent_id == ADAM_ID]
        assert len(sums) == 2
        assert all(s.derivation_method == "model_synthesized_v1" for s in sums)

    def test_second_pass_is_idempotent(self, tmp_path):
        store = _seeded_store(tmp_path, n=10)
        first = runner.run_synthesis_pass(store, "east_adam", ADAM_ID,
                                          _good_synth, max_rollups=4,
                                          group_size=4)
        assert first["appended"] >= 1
        second = runner.run_synthesis_pass(store, "east_adam", ADAM_ID,
                                           _good_synth, max_rollups=4,
                                           group_size=4)
        assert second["appended"] == 0
        assert second["skipped_covered"] >= 1

    def test_invalid_synthesis_is_skipped_not_stored(self, tmp_path):
        store = _seeded_store(tmp_path, n=8)

        def liar(covered: list[dict], owner_id: str) -> dict:
            return {"text": "Found gold at el_dorado.",
                    "salient_entities": ["el_dorado"]}

        report = runner.run_synthesis_pass(store, "east_adam", ADAM_ID, liar,
                                           max_rollups=2, group_size=4)
        assert report["appended"] == 0
        assert len(report["failed"]) == 2
        from backend.world.first_pair_persistence import load_summaries
        assert load_summaries(store) == []

    def test_synthesizer_crash_fails_the_group_not_the_run(self, tmp_path):
        store = _seeded_store(tmp_path, n=8)
        calls = {"n": 0}

        def flaky(covered: list[dict], owner_id: str) -> dict:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return _good_synth(covered, owner_id)

        report = runner.run_synthesis_pass(store, "east_adam", ADAM_ID, flaky,
                                           max_rollups=2, group_size=4)
        assert report["appended"] == 1
        assert len(report["failed"]) == 1

    def test_respects_max_rollups(self, tmp_path):
        store = _seeded_store(tmp_path, n=40)
        report = runner.run_synthesis_pass(store, "east_adam", ADAM_ID,
                                           _good_synth, max_rollups=1,
                                           group_size=4)
        assert report["appended"] == 1

    def test_report_is_json_serializable(self, tmp_path):
        store = _seeded_store(tmp_path, n=8)
        report = runner.run_synthesis_pass(store, "east_adam", ADAM_ID,
                                           _good_synth, max_rollups=1,
                                           group_size=4)
        json.dumps(report)

    def test_ratio_passthrough_orders_newest_first(self, tmp_path):
        store = _seeded_store(tmp_path, n=12)
        report = runner.run_synthesis_pass(store, "east_adam", ADAM_ID,
                                           _good_synth, max_rollups=3,
                                           group_size=2, newest_first_ratio=2)
        assert report["appended"] == 3
        from backend.world.first_pair_persistence import load_summaries
        ranges = sorted(
            tuple(s.covered_heartbeat_range)
            for s in load_summaries(store) if s.owner_agent_id == ADAM_ID
        )
        # Newest groups first: [11,12],[9,10] then oldest [1,2].
        assert ranges == [(1, 2), (9, 10), (11, 12)], ranges
