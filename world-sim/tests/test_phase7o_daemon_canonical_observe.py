"""
Phase 7O tests: Daemon canonical observe opt-in wiring.

Tests that the AgentDaemon correctly passes canonical observe parameters
to execute_action when use_canonical_observe is enabled.

No runtime, no provider calls, no daemon mode.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from unittest.mock import MagicMock, patch

from backend.daemon.agent_daemon import AgentDaemon


class TestDaemonCanonicalObserveInit:
    """Test AgentDaemon.__init__ with canonical observe parameters."""

    def test_default_values(self):
        """Default values should be False/None (no behavior change)."""
        daemon = AgentDaemon(no_llm=True)
        assert daemon.use_canonical_observe is False
        assert daemon.canonical_data_root is None

    def test_canonical_observe_true_requires_root(self):
        """use_canonical_observe=True with canonical_data_root set."""
        daemon = AgentDaemon(
            no_llm=True,
            use_canonical_observe=True,
            canonical_data_root="/tmp/test_data",
        )
        assert daemon.use_canonical_observe is True
        assert daemon.canonical_data_root == Path("/tmp/test_data")

    def test_canonical_observe_false_ignores_root(self):
        """use_canonical_observe=False should ignore canonical_data_root."""
        daemon = AgentDaemon(
            no_llm=True,
            use_canonical_observe=False,
            canonical_data_root="/tmp/test_data",
        )
        assert daemon.use_canonical_observe is False
        assert daemon.canonical_data_root == Path("/tmp/test_data")

    def test_canonical_data_root_string_converted_to_path(self):
        """canonical_data_root string should be converted to Path."""
        daemon = AgentDaemon(
            no_llm=True,
            canonical_data_root="some/string/path",
        )
        assert isinstance(daemon.canonical_data_root, Path)
        assert "some" in str(daemon.canonical_data_root)
        assert "string" in str(daemon.canonical_data_root)
        assert "path" in str(daemon.canonical_data_root)

    def test_canonical_observe_with_none_root(self):
        """use_canonical_observe=True with canonical_data_root=None."""
        daemon = AgentDaemon(
            no_llm=True,
            use_canonical_observe=True,
            canonical_data_root=None,
        )
        assert daemon.use_canonical_observe is True
        assert daemon.canonical_data_root is None


class TestDaemonObservePathCanonicalParams:
    """Test run_cycle observe decision path with canonical params."""

    @patch("backend.daemon.agent_daemon.AgentDaemon._load_awareness")
    @patch("backend.daemon.agent_daemon.AgentDaemon._load_registry")
    @patch("backend.daemon.agent_daemon.ModelCallLedger")
    def test_observe_without_canonical_flag_calls_copy_mode_only(
        self, mock_ledger_class, mock_registry, mock_aware
    ):
        """Without --use-canonical-observe, observe should use copy_mode=True only."""
        mock_ledger = MagicMock()
        mock_ledger.budget_exhausted.return_value = False
        mock_ledger_class.from_data_dir.return_value = mock_ledger

        mock_aware.return_value = {"universal": "", "east": "", "west": ""}
        mock_registry.return_value = {
            "Adam": {"canonical_id": "east_adam", "display_name": "East Adam", "self_state_path": "data/agents/east_adam/self_state.json"},
        }

        daemon = AgentDaemon(no_llm=True, dry_run=True)
        daemon.sim.east.agents["Adam"].persistent_memory = MagicMock()
        daemon.sim.east.agents["Adam"].persistent_memory.get_unread_whispers.return_value = []
        daemon.sim.east.agents["Adam"].persistent_memory.get_recent.return_value = []
        daemon.sim.east.agents["Adam"].tick = 100

        with patch.object(daemon, 'try_reflect', return_value={"decision": "observe", "canonical_id": "east_adam"}):
            with patch("backend.daemon.agent_daemon.execute_action") as mock_exec:
                mock_exec.return_value = {"ok": True, "world_changed": False}
                daemon.run_cycle(target_agent="Adam")

                call_kwargs = mock_exec.call_args[1]
                assert call_kwargs["copy_mode"] is True
                assert "use_canonical_fog" not in call_kwargs
                assert "canonical_data_root" not in call_kwargs

    @patch("backend.daemon.agent_daemon.AgentDaemon._load_awareness")
    @patch("backend.daemon.agent_daemon.AgentDaemon._load_registry")
    @patch("backend.daemon.agent_daemon.ModelCallLedger")
    def test_observe_with_canonical_flag_and_root(
        self, mock_ledger_class, mock_registry, mock_aware
    ):
        """With --use-canonical-observe and canonical_data_root, should pass canonical params."""
        mock_ledger = MagicMock()
        mock_ledger.budget_exhausted.return_value = False
        mock_ledger_class.from_data_dir.return_value = mock_ledger

        mock_aware.return_value = {"universal": "", "east": "", "west": ""}
        mock_registry.return_value = {
            "Adam": {"canonical_id": "east_adam", "display_name": "East Adam", "self_state_path": "data/agents/east_adam/self_state.json"},
        }

        daemon = AgentDaemon(
            no_llm=True, dry_run=True,
            use_canonical_observe=True,
            canonical_data_root="/app/data",
        )
        daemon.sim.east.agents["Adam"].persistent_memory = MagicMock()
        daemon.sim.east.agents["Adam"].persistent_memory.get_unread_whispers.return_value = []
        daemon.sim.east.agents["Adam"].persistent_memory.get_recent.return_value = []
        daemon.sim.east.agents["Adam"].tick = 100

        with patch.object(daemon, 'try_reflect', return_value={"decision": "observe", "canonical_id": "east_adam"}):
            with patch("backend.daemon.agent_daemon.execute_action") as mock_exec:
                mock_exec.return_value = {"ok": True, "world_changed": False}
                daemon.run_cycle(target_agent="Adam")

                call_kwargs = mock_exec.call_args[1]
                assert call_kwargs["copy_mode"] is True
                assert call_kwargs["use_canonical_fog"] is True
                assert call_kwargs["canonical_data_root"] == Path("/app/data")

    @patch("backend.daemon.agent_daemon.AgentDaemon._load_awareness")
    @patch("backend.daemon.agent_daemon.AgentDaemon._load_registry")
    @patch("backend.daemon.agent_daemon.ModelCallLedger")
    def test_observe_with_flag_but_no_root_falls_back(
        self, mock_ledger_class, mock_registry, mock_aware
    ):
        """With --use-canonical-observe but no canonical_data_root, should fall back."""
        mock_ledger = MagicMock()
        mock_ledger.budget_exhausted.return_value = False
        mock_ledger_class.from_data_dir.return_value = mock_ledger

        mock_aware.return_value = {"universal": "", "east": "", "west": ""}
        mock_registry.return_value = {
            "Adam": {"canonical_id": "east_adam", "display_name": "East Adam", "self_state_path": "data/agents/east_adam/self_state.json"},
        }

        daemon = AgentDaemon(
            no_llm=True, dry_run=True,
            use_canonical_observe=True,
            canonical_data_root=None,
        )
        daemon.sim.east.agents["Adam"].persistent_memory = MagicMock()
        daemon.sim.east.agents["Adam"].persistent_memory.get_unread_whispers.return_value = []
        daemon.sim.east.agents["Adam"].persistent_memory.get_recent.return_value = []
        daemon.sim.east.agents["Adam"].tick = 100

        with patch.object(daemon, 'try_reflect', return_value={"decision": "observe", "canonical_id": "east_adam"}):
            with patch("backend.daemon.agent_daemon.execute_action") as mock_exec:
                mock_exec.return_value = {"ok": True, "world_changed": False}
                with patch("backend.daemon.agent_daemon.logger") as mock_logger:
                    daemon.run_cycle(target_agent="Adam")

                    mock_logger.warning.assert_called()
                    warning_msg = mock_logger.warning.call_args[0][0]
                    assert "use_canonical_observe=True but canonical_data_root is None" in warning_msg

                    call_kwargs = mock_exec.call_args[1]
                    assert call_kwargs["copy_mode"] is True
                    assert "use_canonical_fog" not in call_kwargs
                    assert "canonical_data_root" not in call_kwargs