import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


from backend.daemon import agent_daemon

class FakeDaemon:
    def __init__(self, *args, **kwargs):
        self.calls = []
    def run_cycle(self, target_agent=None, target_agents=None):
        self.calls.append({'target_agent': target_agent, 'target_agents': target_agents})

def make_args(argv):
    return agent_daemon.parse_args(argv)

def test_agent_option_nonstandard_name():
    args = make_args(["--agent", "West Adam", "--once", "--dry-run", "--no-llm"])
    daemon = FakeDaemon()
    cycles = agent_daemon.run_daemon_loop(daemon, args)
    assert cycles == 1
    call = daemon.calls[0]
    assert call['target_agent'] == "West Adam"
    assert call['target_agents'] is None
