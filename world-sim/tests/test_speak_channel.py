"""The blocker channel: the one way the agent interrupts Sean.

Sean is nearly blind and works by TTS, so a SPOKEN alert is the only interruption
that reaches him. Everything else is the agent's job to finish alone. These tests
never make noise -- the speaking path is exercised only through its guards and
the dry run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import speak as sp  # noqa: E402


def test_empty_text_speaks_nothing_and_does_not_raise():
    r = sp.speak("")
    assert r["spoke"] is False
    assert "empty" in r["detail"]


def test_whitespace_only_is_treated_as_empty():
    assert sp.speak("   \n  ")["spoke"] is False


def test_the_blocked_phrase_marks_it_as_a_request_for_sean(tmp_path):
    assert sp.BLOCKED_PREFIX.startswith("Sean, I am blocked")
    assert "need you" in sp.BLOCKED_PREFIX


def test_it_logs_every_alert(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sp, "LOG_PATH", tmp_path / "speak.log")
    monkeypatch.setattr(sys, "argv", [
        "speak.py", "--blocked", "only Sean can rotate the key", "--dry-run"])
    code = sp.main()
    assert code == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["blocked"] is True
    assert out["text"].startswith(sp.BLOCKED_PREFIX)
    lines = (tmp_path / "speak.log").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["blocked"] is True
    assert "only Sean can rotate the key" in rec["text"]


def test_no_text_is_an_error_code_and_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sp, "LOG_PATH", tmp_path / "speak.log")
    monkeypatch.setattr(sys, "argv", ["speak.py"])
    assert sp.main() == 2
    assert not (tmp_path / "speak.log").exists()


def test_the_message_never_goes_through_shell_quoting(tmp_path, monkeypatch):
    """The text is handed to PowerShell through a FILE, so quotes, $ and ; in a
    blocker message cannot mangle or truncate it -- a garbled alert is a silent
    failure."""
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["kw"] = kw

        class P:
            returncode = 0
            stderr = ""
            stdout = ""
        return P()

    monkeypatch.setattr(sp.subprocess, "run", fake_run)
    r = sp.speak('he said "stop"; cost $5 & done')
    assert r["spoke"] is True
    script = captured["cmd"][-1]
    assert 'he said "stop"' not in script, "the text must not be inline in the script"
    assert "speechsynthesizer" in script.lower()
    assert "Get-Content -Raw -LiteralPath" in script
