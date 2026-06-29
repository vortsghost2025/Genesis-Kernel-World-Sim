import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from backend.daemon import agent_daemon

class FakeDaemon:
    def __init__(self, *args, **kwargs):
        self.calls = []
    def run_cycle(self, target_agent=None, target_agents=None):
        self.calls.append({'target_agent': target_agent, 'target_agents': target_agents})


def make_args(argv):
    return agent_daemon.parse_args(argv)


def test_agents_option_success():
    args = make_args(["--agents", "Adam,Eve", "--once", "--dry-run", "--no-llm"])
    daemon = FakeDaemon()
    cycles = agent_daemon.run_daemon_loop(daemon, args)
    assert cycles == 1
    call = daemon.calls[0]
    assert call['target_agent'] is None
    assert call['target_agents'] == ["Adam", "Eve"]


def test_agent_option_success():
    args = make_args(["--agent", "Adam", "--once", "--dry-run", "--no-llm"])
    daemon = FakeDaemon()
    cycles = agent_daemon.run_daemon_loop(daemon, args)
    assert cycles == 1
    call = daemon.calls[0]
    assert call['target_agent'] == "Adam"
    assert call['target_agents'] is None


def test_invalid_agent_in_agents():
    with pytest.raises(SystemExit):
        make_args(["--agents", "Adam,West Eve"])


def test_unknown_agent_in_agents():
    with pytest.raises(SystemExit):
        make_args(["--agents", "Adam,Unknown"])

def test_agents_missing_eve_rejected():
    with pytest.raises(SystemExit):
        make_args(["--agents", "Adam"])


def test_mutually_exclusive_agent_and_agents():
    with pytest.raises(SystemExit):
        make_args(["--agent", "Adam", "--agents", "Adam,Eve"])


def test_agents_wrong_order():
    with pytest.raises(SystemExit):
        make_args(["--agents", "Eve,Adam"])

def test_pre_cycle_runtime_stop():
    # Mock monotonic to return start=0, then 2.0 for pre‑cycle check
    calls = [0.0, 2.0]
    def fake_monotonic():
        return calls.pop(0) if calls else 2.0
    def fake_sleep(sec):
        pass  # should not be called
    args = make_args(["--agents", "Adam,Eve", "--max-runtime-seconds", "1.5", "--dry-run", "--no-llm"])
    daemon = FakeDaemon()
    cycles = agent_daemon.run_daemon_loop(daemon, args, monotonic=fake_monotonic, sleep=fake_sleep)
    assert cycles == 0
    assert len(daemon.calls) == 0


def test_post_cycle_runtime_stop():
    # Mock monotonic to allow one cycle then exceed runtime bound
    calls = [0.0, 0.5, 2.0]
    def fake_monotonic():
        return calls.pop(0) if calls else 2.0
    def fake_sleep(sec):
        # Should not be called because loop breaks before sleeping
        raise AssertionError("sleep should not be called in post‑cycle stop test")
    args = make_args(["--agents", "Adam,Eve", "--max-runtime-seconds", "1.5", "--dry-run", "--no-llm"])
    daemon = FakeDaemon()
    cycles = agent_daemon.run_daemon_loop(daemon, args, monotonic=fake_monotonic, sleep=fake_sleep)
    assert cycles == 1
    assert len(daemon.calls) == 1


def test_max_cycles():
    # Test that --max-cycles limits the loop without sleeping (using injected fake sleep).
    sleep_calls = []
    def fake_sleep(seconds):
        sleep_calls.append(seconds)
    args = make_args(["--agents", "Adam,Eve", "--max-cycles", "2", "--dry-run", "--no-llm"])
    daemon = FakeDaemon()
    cycles = agent_daemon.run_daemon_loop(daemon, args, sleep=fake_sleep)
    assert cycles == 2
    # Ensure two cycles were executed.
    assert len(daemon.calls) == 2
    # Sleep should have been called after first cycle only (since after second it breaks before sleep).
    # The interval defaults to 60, so we expect one sleep call.
    assert sleep_calls == [agent_daemon.DEFAULT_WAKE_INTERVAL]


def test_dry_run_help_text(capsys):
    # Capture stdout from argparse help; should include the updated dry‑run description.
    with pytest.raises(SystemExit):
        agent_daemon.parse_args(["--dry-run", "--help"])
    out, err = capsys.readouterr()
    # Normalize whitespace to avoid line‑wrapping issues in help output.
    normalized = " ".join(out.split())
    # Verify the dry‑run help mentions that it does not disable model/provider calls
    # and that '--no-llm' should be used for that purpose.
    assert "does not disable model/provider calls" in normalized
    assert "--no-llm" in normalized

