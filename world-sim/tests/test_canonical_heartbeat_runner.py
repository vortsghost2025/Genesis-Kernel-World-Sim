"""Tests for the detached canonical heartbeat runner (10IY).

No test touches the canonical store, the network, or a real provider:
scratch stores under tmp_path, fake loop/exporter scripts, and fake
credential strings only. The provider-resolution proof runs the real
resolver import (no network) with non-real keys.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import backend.world.canonical_heartbeat_runner as chr_mod
from backend.world.canonical_heartbeat_runner import (
    CREATE_BREAKAWAY_FROM_JOB,
    CREATE_NEW_PROCESS_GROUP,
    DETACHED_PROCESS,
    ProviderCredentialError,
    already_persisted,
    build_clean_env,
    launcher_main,
    preflight,
    resolution_proof,
    runner_main,
)

WORLD_SIM = Path(__file__).resolve().parents[1]

FAKE_LOOP = """
import json, os, sys
store = os.environ["RUNNER_TEST_STORE"]
mode = os.environ.get("RUNNER_TEST_MODE", "ok")
ev = os.environ.get("RUNNER_TEST_EVIDENCE", "")
if mode == "fail":
    sys.exit(3)
if mode == "sentinel":
    open(os.environ["RUNNER_TEST_SENTINEL"], "w").write("loop-ran")
    sys.exit(0)
hb_p = os.path.join(store, "heartbeat.json")
hb = json.load(open(hb_p))
hb["data"].append({"heartbeat_number": len(hb["data"]) + 1, "timestamp_utc": "t"})
json.dump(hb, open(hb_p, "w"))
ws_p = os.path.join(store, "world_state.json")
ws = json.load(open(ws_p))
ws["data"]["tick"] += 1
json.dump(ws, open(ws_p, "w"))
if mode == "no_evidence":
    sys.exit(0)
json.dump({"stub": "loop-evidence"}, open(ev, "w"))
"""

FAKE_EXPORTER = """
import argparse, json
p = argparse.ArgumentParser()
p.add_argument("--out", required=True)
json.dump({"exporter": "stub"}, open(p.parse_args().out, "w"))
"""

FAKE_VAULT = (
    "NVIDIA_NIM_API_KEY=fake-nv-abc123\n"
    "OPENROUTER_API_KEY=fake-or-xyz789\n"
)


def _write_store(root: Path, count: int, tick: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "heartbeat.json").write_text(
        json.dumps({
            "data": [
                {"heartbeat_number": i, "timestamp_utc": "t"}
                for i in range(1, count + 1)
            ],
        }),
        newline="\n",
    )
    (root / "world_state.json").write_text(
        json.dumps({
            "data": {
                "tick": tick,
                "tile_occupancy": {"east_adam": "x", "east_eve": "y"},
            },
        }),
        newline="\n",
    )


def _write_test_scripts(tmp_path: Path) -> tuple[Path, Path, Path]:
    loop = tmp_path / "fake_loop.py"
    loop.write_text(FAKE_LOOP, newline="\n")
    exporter = tmp_path / "fake_exporter.py"
    exporter.write_text(FAKE_EXPORTER, newline="\n")
    vault = tmp_path / "vault.env"
    vault.write_text(FAKE_VAULT, newline="\n")
    return loop, exporter, vault


def _use_paid_fallback(monkeypatch):
    """Force a non-free fallback so the guard can be observed rejecting it.

    The shipped policy is now compliant (both lanes ':free'), so the guard's
    rejection path has to be provoked deliberately rather than inherited from
    a broken default.
    """
    monkeypatch.setattr(chr_mod, "FALLBACK_MODEL", "z-ai/glm-5.3-flash")


def _runner_args(loop, exporter, vault, store, tmp_path):
    args = [
        "--expect-heartbeat", "10",
        "--store-root", str(store),
        "--evidence", str(tmp_path / "evidence.json"),
        "--status", str(tmp_path / "status.json"),
        "--vault", str(vault),
        "--world-sim-root", str(WORLD_SIM),
        "--loop-script", str(loop),
        "--export-script", str(exporter),
    ]
    return args


class TestBuildCleanEnv:
    def test_maps_vault_and_strips_ambient_provider_vars(
        self, tmp_path, monkeypatch
    ):
        vault = tmp_path / "vault.env"
        vault.write_text(FAKE_VAULT, newline="\n")
        monkeypatch.setenv("NVIDIA_API_KEY", "ambient-must-be-replaced")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_BASE_URL", "http://ambient-lane")
        env = build_clean_env(vault)
        assert env["NVIDIA_API_KEY"] == "fake-nv-abc123"
        assert env["OPENROUTER_API_KEY"] == "fake-or-xyz789"
        assert env["GENESIS_FIRST_PAIR_BASE_URL"] == chr_mod.PRIMARY_BASE_URL
        assert env["GENESIS_FIRST_PAIR_API_KEY"] == "fake-or-xyz789"
        assert env["GENESIS_FIRST_PAIR_MODEL"] == chr_mod.PRIMARY_MODEL
        assert env["GENESIS_FIRST_PAIR_FALLBACK_MODEL"] == chr_mod.FALLBACK_MODEL
        # Defect B: the fallback the environment actually carries must be a
        # free model, or the enforced guard will refuse to launch.
        assert env["GENESIS_FIRST_PAIR_FALLBACK_MODEL"].endswith(":free")

    def test_missing_credential_fails_naming_the_variable(self, tmp_path):
        vault = tmp_path / "vault.env"
        vault.write_text("NVIDIA_NIM_API_KEY=fake-nv-abc123\n", newline="\n")
        with pytest.raises(ProviderCredentialError) as exc:
            build_clean_env(vault)
        msg = str(exc.value)
        assert "OPENROUTER_API_KEY" in msg
        assert "fake-nv-abc123" not in msg


class TestResolutionProof:
    def test_shipped_policy_is_free_only_and_conforms(self, tmp_path):
        """The shipped policy must satisfy the guard it enforces.

        Regression guard for Defect B: the fallback was a non-free model, so
        once Defect A was actually enforced the runner refused to launch at
        all. The policy is now compliant and the proof passes unaltered.
        """
        assert chr_mod.FALLBACK_MODEL.endswith(":free"), (
            f"shipped fallback is not free: {chr_mod.FALLBACK_MODEL}"
        )
        assert chr_mod.PRIMARY_MODEL.endswith(":free"), (
            f"shipped primary is not free: {chr_mod.PRIMARY_MODEL}"
        )
        vault = tmp_path / "vault.env"
        vault.write_text(FAKE_VAULT, newline="\n")
        env = build_clean_env(vault)
        ok, text = resolution_proof(env, WORLD_SIM)
        assert ok, text
        assert "RESOLUTION_KEY_SET=TRUE" in text
        assert "RESOLUTION_FALLBACK_FREE=TRUE" in text
        assert f"RESOLUTION_MODEL={chr_mod.PRIMARY_MODEL}" in text
        assert f"RESOLUTION_BASE_URL={chr_mod.PRIMARY_BASE_URL}" in text
        assert "RESOLUTION_FALLBACK=NONE" not in text

    def test_paid_fallback_fails_closed(self, tmp_path, monkeypatch):
        """Defect A, pinned: a non-':free' fallback must be refused.

        This assertion previously passed only because the guard computed
        RESOLUTION_FALLBACK_FREE and never read it.
        """
        _use_paid_fallback(monkeypatch)
        vault = tmp_path / "vault.env"
        vault.write_text(FAKE_VAULT, newline="\n")
        env = build_clean_env(vault)
        ok, text = resolution_proof(env, WORLD_SIM)
        assert "RESOLUTION_FALLBACK_FREE=FALSE" in text
        assert not ok, f"paid fallback was accepted: {text}"
        assert ":free" in text

    def test_rejects_missing_fallback(self, tmp_path):
        vault = tmp_path / "vault.env"
        vault.write_text(FAKE_VAULT, newline="\n")
        env = build_clean_env(vault)
        env.pop("GENESIS_FIRST_PAIR_FALLBACK_MODEL", None)
        ok, text = resolution_proof(env, WORLD_SIM)
        assert not ok


class TestPreflight:
    def test_passes_when_count_and_tick_match_expect_minus_one(self, tmp_path):
        _write_store(tmp_path / "store", 9, 9)
        ok, detail = preflight(tmp_path / "store", 10)
        assert ok, detail

    def test_fails_on_record_count_mismatch(self, tmp_path):
        _write_store(tmp_path / "store", 8, 9)
        ok, detail = preflight(tmp_path / "store", 10)
        assert not ok
        assert "record" in detail

    def test_fails_on_tick_mismatch(self, tmp_path):
        _write_store(tmp_path / "store", 9, 8)
        ok, detail = preflight(tmp_path / "store", 10)
        assert not ok
        assert "tick" in detail

    def test_fails_on_unparseable_store(self, tmp_path):
        store = tmp_path / "store"
        store.mkdir()
        (store / "heartbeat.json").write_text("{broken", newline="\n")
        (store / "world_state.json").write_text("{}", newline="\n")
        ok, detail = preflight(store, 10)
        assert not ok


class TestAlreadyPersisted:
    def test_true_when_store_at_expected(self, tmp_path):
        _write_store(tmp_path / "store", 10, 10)
        assert already_persisted(tmp_path / "store", 10)

    def test_false_when_store_behind_expected(self, tmp_path):
        _write_store(tmp_path / "store", 9, 9)
        assert not already_persisted(tmp_path / "store", 10)


class TestRunnerFlow:
    def _setup(self, tmp_path, count, tick, mode):
        loop, exporter, vault = _write_test_scripts(tmp_path)
        store = tmp_path / "store"
        _write_store(store, count, tick)
        return loop, exporter, vault, store

    def test_happy_path_original_evidence_preserved(self, tmp_path, monkeypatch):
        loop, exporter, vault, store = self._setup(tmp_path, 9, 9, "ok")
        monkeypatch.setenv("RUNNER_TEST_STORE", str(store))
        monkeypatch.setenv("RUNNER_TEST_EVIDENCE", str(tmp_path / "evidence.json"))
        monkeypatch.setenv("RUNNER_TEST_MODE", "ok")
        rc = runner_main(_runner_args(loop, exporter, vault, store, tmp_path))
        assert rc == 0
        status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert status["status"] == "evidence-exported"
        assert status["evidence_class"] == "original_execution_evidence"
        assert json.loads((store / "heartbeat.json").read_text())["data"][-1][
            "heartbeat_number"
        ] == 10
        ev = json.loads((tmp_path / "evidence.json").read_text())
        assert ev == {"stub": "loop-evidence"}

    def test_crash_recovery_labels_recovered_evidence(
        self, tmp_path, monkeypatch
    ):
        loop, exporter, vault, store = self._setup(tmp_path, 9, 9, "no_evidence")
        monkeypatch.setenv("RUNNER_TEST_STORE", str(store))
        monkeypatch.setenv("RUNNER_TEST_EVIDENCE", str(tmp_path / "evidence.json"))
        monkeypatch.setenv("RUNNER_TEST_MODE", "no_evidence")
        rc = runner_main(_runner_args(loop, exporter, vault, store, tmp_path))
        assert rc == 0
        status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert status["status"] == "evidence-exported"
        assert status["evidence_class"] == "recovered_state_evidence"
        ev = json.loads((tmp_path / "evidence.json").read_text())
        assert ev["evidence_class"] == "recovered_state_evidence"
        assert ev["exporter"] == "stub"

    def test_already_persisted_never_reruns_the_loop(
        self, tmp_path, monkeypatch
    ):
        loop, exporter, vault, store = self._setup(tmp_path, 10, 10, "sentinel")
        sentinel = tmp_path / "sentinel.txt"
        monkeypatch.setenv("RUNNER_TEST_STORE", str(store))
        monkeypatch.setenv("RUNNER_TEST_EVIDENCE", str(tmp_path / "evidence.json"))
        monkeypatch.setenv("RUNNER_TEST_MODE", "sentinel")
        monkeypatch.setenv("RUNNER_TEST_SENTINEL", str(sentinel))
        rc = runner_main(_runner_args(loop, exporter, vault, store, tmp_path))
        assert rc == 0
        assert not sentinel.exists(), "NO-RERUN RULE VIOLATED: loop executed"
        status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert status["status"] == "evidence-exported"
        assert status["evidence_class"] == "recovered_state_evidence"
        assert "never re-executed" in status["detail"]
        assert json.loads((store / "heartbeat.json").read_text())["data"][-1][
            "heartbeat_number"
        ] == 10

    def test_loop_failure_fails_closed(self, tmp_path, monkeypatch):
        loop, exporter, vault, store = self._setup(tmp_path, 9, 9, "fail")
        monkeypatch.setenv("RUNNER_TEST_STORE", str(store))
        monkeypatch.setenv("RUNNER_TEST_EVIDENCE", str(tmp_path / "evidence.json"))
        monkeypatch.setenv("RUNNER_TEST_MODE", "fail")
        rc = runner_main(_runner_args(loop, exporter, vault, store, tmp_path))
        assert rc != 0
        status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert status["status"] == "failed"
        assert len(json.loads((store / "heartbeat.json").read_text())["data"]) == 9
        assert not (tmp_path / "evidence.json").exists()

    def test_preflight_mismatch_marks_failed_without_running_loop(
        self, tmp_path, monkeypatch
    ):
        loop, exporter, vault, store = self._setup(tmp_path, 8, 8, "sentinel")
        sentinel = tmp_path / "sentinel.txt"
        monkeypatch.setenv("RUNNER_TEST_STORE", str(store))
        monkeypatch.setenv("RUNNER_TEST_EVIDENCE", str(tmp_path / "evidence.json"))
        monkeypatch.setenv("RUNNER_TEST_MODE", "sentinel")
        monkeypatch.setenv("RUNNER_TEST_SENTINEL", str(sentinel))
        rc = runner_main(_runner_args(loop, exporter, vault, store, tmp_path))
        assert rc != 0
        assert not sentinel.exists()
        status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert status["status"] == "failed"


class TestLogPathResolution:
    """Defect C's sibling: --log was left unresolved by the original fix.

    Found while running HB943: the runner log appeared at the repository
    root instead of beside the run's evidence and status, because evidence and
    status resolve against the world-sim root and the log did not.
    """

    def test_relative_log_resolves_under_world_sim_root(self, tmp_path):
        root = tmp_path / "wsroot"
        root.mkdir()
        resolved = chr_mod._resolve_under(root, ".scratch/hb/runner.log")
        assert resolved == root / ".scratch" / "hb" / "runner.log"

    def test_log_resolution_is_idempotent(self, tmp_path):
        root = tmp_path / "wsroot"
        root.mkdir()
        once = chr_mod._resolve_under(root, ".scratch/hb/runner.log")
        assert chr_mod._resolve_under(root, str(once)) == once

    def test_launcher_resolves_the_log_before_spawning(self, tmp_path):
        """The log arg handed to the runner must already be absolute, so the
        detached child cannot re-resolve it against its own cwd."""
        loop, exporter, vault = _write_test_scripts(tmp_path)
        store = tmp_path / "store"
        _write_store(store, 9, 9)
        calls: list[tuple] = []
        monkey_popen = MagicMock()
        monkey_popen.pid = 5150

        def fake_popen(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return monkey_popen

        original = chr_mod.subprocess.Popen
        chr_mod.subprocess.Popen = fake_popen
        try:
            rc = launcher_main([
                "--expect-heartbeat", "10",
                "--evidence", str(tmp_path / "evidence.json"),
                "--log", ".scratch/hb/runner.log",
                "--status", str(tmp_path / "status.json"),
                "--store-root", str(store),
                "--vault", str(vault),
                "--world-sim-root", str(tmp_path / "wsroot"),
                "--loop-script", str(loop),
                "--export-script", str(exporter),
            ])
        finally:
            chr_mod.subprocess.Popen = original
        assert rc == 0
        assert calls, "runner was never spawned"
        cmd = calls[0][0]
        log_arg = cmd[cmd.index("--log") + 1]
        assert chr_mod.os.path.isabs(log_arg), (
            f"runner received a relative --log: {log_arg}"
        )
        assert log_arg.startswith(str(tmp_path / "wsroot")), (
            f"log must resolve under the world-sim root, got {log_arg}"
        )


class TestLauncher:
    def _launcher_args(self, tmp_path, loop, exporter, vault, store):
        return [
            "--expect-heartbeat", "10",
            "--evidence", str(tmp_path / "evidence.json"),
            "--log", str(tmp_path / "run.log"),
            "--status", str(tmp_path / "status.json"),
            "--store-root", str(store),
            "--vault", str(vault),
            "--world-sim-root", str(WORLD_SIM),
            "--loop-script", str(loop),
            "--export-script", str(exporter),
        ]

    def test_spawns_detached_and_exits_without_waiting(
        self, tmp_path, monkeypatch
    ):
        loop, exporter, vault = _write_test_scripts(tmp_path)
        store = tmp_path / "store"
        _write_store(store, 9, 9)
        calls: list[tuple] = []
        mock_proc = MagicMock()
        mock_proc.pid = 4242

        def fake_popen(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return mock_proc

        monkeypatch.setattr(chr_mod.subprocess, "Popen", fake_popen)
        rc = launcher_main(self._launcher_args(tmp_path, loop, exporter, vault, store))
        assert rc == 0
        assert len(calls) == 1
        cmd, kwargs = calls[0]
        assert cmd[0] == chr_mod.sys.executable
        assert "run_canonical_heartbeat_detached.py" in cmd[2]
        flags = kwargs["creationflags"]
        assert flags & DETACHED_PROCESS
        assert flags & CREATE_NEW_PROCESS_GROUP
        assert flags & CREATE_BREAKAWAY_FROM_JOB
        assert "stdout" in kwargs and "stderr" in kwargs
        status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert status["status"] == "not-started"
        assert status["pid"] == 4242
        assert status["expected_heartbeat"] == 10
        assert status["breakaway"] is True

    def test_breakaway_denied_falls_back_to_plain_detached(
        self, tmp_path, monkeypatch
    ):
        loop, exporter, vault = _write_test_scripts(tmp_path)
        store = tmp_path / "store"
        _write_store(store, 9, 9)
        calls: list[tuple] = []

        def fake_popen(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if len(calls) == 1:
                raise PermissionError("breakaway not permitted by job")
            return MagicMock(pid=777)

        monkeypatch.setattr(chr_mod.subprocess, "Popen", fake_popen)
        rc = launcher_main(self._launcher_args(tmp_path, loop, exporter, vault, store))
        assert rc == 0
        assert len(calls) == 2
        flags2 = calls[1][1]["creationflags"]
        assert flags2 & DETACHED_PROCESS
        assert not (flags2 & CREATE_BREAKAWAY_FROM_JOB)
        status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert status["pid"] == 777
        assert status["breakaway"] is False


# ---------------------------------------------------------------------------
# Defect A - the free-only guard computed its verdict and never read it.
# Measured on heartbeat 941: RESOLUTION_FALLBACK_FREE=FALSE and the run
# proceeded. The docstring and runbook both claim this fails closed.
# ---------------------------------------------------------------------------


class TestResolutionProofEnforcesPolicy:
    def test_accepts_free_fallback(self, tmp_path, monkeypatch):
        """With a genuinely free fallback configured, the proof passes."""
        monkeypatch.setattr(chr_mod, "FALLBACK_MODEL", "z-ai/glm-5.2:free")
        vault = tmp_path / "vault.env"
        vault.write_text(FAKE_VAULT, newline="\n")
        env = build_clean_env(vault)
        ok, text = resolution_proof(env, WORLD_SIM)
        assert ok, text
        assert "RESOLUTION_FALLBACK_FREE=TRUE" in text

    def test_rejects_primary_model_hijack(self, tmp_path, monkeypatch):
        """A primary that is not the configured one is a silent lane hijack."""
        monkeypatch.setattr(chr_mod, "FALLBACK_MODEL", "z-ai/glm-5.2:free")
        vault = tmp_path / "vault.env"
        vault.write_text(FAKE_VAULT, newline="\n")
        env = build_clean_env(vault)
        env["GENESIS_FIRST_PAIR_MODEL"] = "attacker/injected:free"
        ok, text = resolution_proof(env, WORLD_SIM)
        assert not ok, f"hijacked primary accepted: {text}"

    def test_rejects_base_url_hijack(self, tmp_path, monkeypatch):
        """A base URL other than the configured one must not be served from."""
        monkeypatch.setattr(chr_mod, "FALLBACK_MODEL", "z-ai/glm-5.2:free")
        vault = tmp_path / "vault.env"
        vault.write_text(FAKE_VAULT, newline="\n")
        env = build_clean_env(vault)
        env["GENESIS_FIRST_PAIR_BASE_URL"] = "https://attacker.invalid/v1"
        ok, text = resolution_proof(env, WORLD_SIM)
        assert not ok, f"hijacked base url accepted: {text}"

    def test_free_only_assertion_cannot_be_removed(self):
        """Import-guard: the free-only check must remain in the source."""
        source = (WORLD_SIM / "backend" / "world"
                  / "canonical_heartbeat_runner.py").read_text(encoding="utf-8")
        assert "RESOLUTION_FALLBACK_FREE" in source
        assert ":free" in source


# ---------------------------------------------------------------------------
# Defect C - relative evidence path resolved against the subprocess cwd,
# producing a doubled directory. NFM-021 recurring (see Paper F).
# ---------------------------------------------------------------------------


class TestEvidencePathResolution:
    def test_relative_path_resolves_under_root(self, tmp_path):
        root = tmp_path / "ws"
        root.mkdir()
        resolved = chr_mod._resolve_under(root, "world-sim/.scratch/hb/evidence.json")
        assert resolved == root / "world-sim" / ".scratch" / "hb" / "evidence.json"

    def test_absolute_path_is_unchanged(self, tmp_path):
        target = tmp_path / "elsewhere" / "evidence.json"
        resolved = chr_mod._resolve_under(tmp_path, str(target))
        assert resolved == target

    def test_resolution_is_idempotent(self, tmp_path):
        """The doubled-path failure: resolving twice must not prepend again."""
        root = tmp_path / "ws"
        root.mkdir()
        once = chr_mod._resolve_under(root, "world-sim/.scratch/hb/evidence.json")
        twice = chr_mod._resolve_under(root, str(once))
        assert twice == once
        assert str(twice).count("ws") == 1

    def test_runner_resolves_evidence_before_launching_loop(
        self, tmp_path, monkeypatch
    ):
        """A relative --evidence must reach the loop as an absolute path."""
        _write_store(tmp_path / "store", 9, 9)
        loop = tmp_path / "argv_loop.py"
        loop.write_text(
            "import json, os, sys\n"
            "store = os.environ['RUNNER_TEST_STORE']\n"
            "hb = json.load(open(os.path.join(store, 'heartbeat.json')))\n"
            "hb['data'].append({'heartbeat_number': len(hb['data']) + 1})\n"
            "json.dump(hb, open(os.path.join(store, 'heartbeat.json'), 'w'))\n"
            "ws = json.load(open(os.path.join(store, 'world_state.json')))\n"
            "ws['data']['tick'] += 1\n"
            "json.dump(ws, open(os.path.join(store, 'world_state.json'), 'w'))\n"
            "json.dump(sys.argv[1:], open(os.path.join(store, 'argv.json'), 'w'))\n",
            newline="\n",
        )
        exporter = tmp_path / "fake_exporter.py"
        exporter.write_text(
            "import argparse, json, os\n"
            "p = argparse.ArgumentParser()\n"
            "p.add_argument('--out', required=True)\n"
            "out = p.parse_args().out\n"
            "os.makedirs(os.path.dirname(out), exist_ok=True)\n"
            "json.dump({'exporter': 'stub'}, open(out, 'w'))\n",
            newline="\n",
        )
        vault = tmp_path / "vault.env"
        vault.write_text(FAKE_VAULT, newline="\n")

        monkeypatch.setenv("RUNNER_TEST_STORE", str(tmp_path / "store"))
        monkeypatch.setattr(chr_mod, "resolution_proof",
                            lambda env, root: (True, "STUB RESOLUTION_OK"))
        monkeypatch.chdir(tmp_path)

        # world-sim-root is a temp dir, NOT the real repository: a relative
        # --evidence resolves under it, so using the real root would make
        # this test write into the working tree on every run.
        ws_root = tmp_path / "wsroot"
        ws_root.mkdir()

        rc = runner_main([
            "--expect-heartbeat", "10",
            "--store-root", str(tmp_path / "store"),
            "--evidence", "rel/evidence.json",
            "--status", str(tmp_path / "status.json"),
            "--vault", str(vault),
            "--world-sim-root", str(ws_root),
            "--loop-script", str(loop),
            "--export-script", str(exporter),
        ])
        assert rc == 0
        argv = json.loads((tmp_path / "store" / "argv.json").read_text())
        evidence_arg = argv[argv.index("--evidence") + 1]
        assert chr_mod.os.path.isabs(evidence_arg), (
            f"loop received a relative evidence path: {evidence_arg}"
        )
        # The evidence landed exactly once, under the resolved root.
        assert (ws_root / "rel" / "evidence.json").is_file()
        assert not (ws_root / "rel" / "rel").exists()
        # And nothing was written into the real repository.
        assert not (WORLD_SIM / "rel").exists()


# ---------------------------------------------------------------------------
# Defect D - provider provenance was printed to a scratch log and never
# persisted to a durable artifact.
# ---------------------------------------------------------------------------


class TestProviderProvenancePersisted:
    def test_status_records_resolved_provider_policy(
        self, tmp_path, monkeypatch
    ):
        _write_store(tmp_path / "store", 9, 9)
        loop, exporter, vault = _write_test_scripts(tmp_path)
        monkeypatch.setenv("RUNNER_TEST_STORE", str(tmp_path / "store"))
        monkeypatch.setattr(chr_mod, "resolution_proof",
                            lambda env, root: (True, "STUB RESOLUTION_OK"))
        rc = runner_main(_runner_args(loop, exporter, vault,
                                      tmp_path / "store", tmp_path))
        assert rc == 0
        status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert status["primary_model"] == chr_mod.PRIMARY_MODEL
        assert status["fallback_model"] == chr_mod.FALLBACK_MODEL
        assert status["fallback_free"] is False
        assert status["provider_base_url"] == chr_mod.PRIMARY_BASE_URL

    def test_status_records_serving_attempts_from_error_memories(
        self, tmp_path, monkeypatch
    ):
        """No error memories means a single transport attempt (runbook S9)."""
        _write_store(tmp_path / "store", 9, 9)
        loop, exporter, vault = _write_test_scripts(tmp_path)
        monkeypatch.setenv("RUNNER_TEST_STORE", str(tmp_path / "store"))
        monkeypatch.setattr(chr_mod, "resolution_proof",
                            lambda env, root: (True, "STUB RESOLUTION_OK"))
        rc = runner_main(_runner_args(loop, exporter, vault,
                                      tmp_path / "store", tmp_path))
        assert rc == 0
        status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert status["serving_provider_type"] == "single_attempt_no_error_memories"
        assert "credential" not in json.dumps(status).lower()
