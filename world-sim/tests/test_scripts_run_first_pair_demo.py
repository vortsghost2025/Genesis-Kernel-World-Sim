"""Focused smoke tests for the operator script.

Does not duplicate the runtime suite — validates only script-level plumbing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_first_pair_demo.py"


class TestScriptHelp:
    def test_help_flag(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "--heartbeats" in result.stdout
        assert "--root" in result.stdout
        assert "--export" in result.stdout
        assert "--questions" in result.stdout


class TestScriptRun:
    def test_default_heartbeats(self, tmp_path: Path) -> None:
        root = tmp_path / "test-default"
        result = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--heartbeats", "1",
             "--root", str(root)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "initialised" in result.stdout
        assert "Adam ID:" in result.stdout
        assert "Eve ID:" in result.stdout

    def test_resume_detected(self, tmp_path: Path) -> None:
        root = tmp_path / "test-resume"
        subprocess.run(
            [sys.executable, str(SCRIPT),
             "--heartbeats", "1",
             "--root", str(root)],
            capture_output=True,
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--heartbeats", "1",
             "--root", str(root)],
            capture_output=True, text=True,
        )
        assert "resumed" in result.stdout

    def test_export_flag(self, tmp_path: Path) -> None:
        root = tmp_path / "test-export"
        export = tmp_path / "export-evidence.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--heartbeats", "1",
             "--root", str(root),
             "--export", str(export)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert export.exists()
        assert "Evidence:" in result.stdout

    def test_questions_flag(self, tmp_path: Path) -> None:
        root = tmp_path / "test-questions"
        result = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--heartbeats", "1",
             "--root", str(root),
             "--questions"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "Pending questions:" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
