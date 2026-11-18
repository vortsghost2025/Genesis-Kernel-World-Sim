"""Speak to Sean through his speakers — the BLOCKER channel.

Why this exists (Sean, 2026-11-18, verbatim intent):

    "you basically run the show. if you see something that needs fixing, dont
     ask me, fix it. you run into a problem... problem solve it until u hit a
     blocker you absolutly cannot bypass without me... then in those times. you
     need to run the command that speaks to me in my speakers and tells me you
     need me to absolutly do something for you"

Sean is nearly blind and works by TTS, so a spoken alert is the ONLY interruption
that reaches him. Everything else is the agent's job to finish alone.

Usage:
    python world-sim/scripts/speak.py "the message"
    python world-sim/scripts/speak.py --blocked "what only Sean can do"
    python world-sim/scripts/speak.py --text "..." --telegram   # also push it

Never raises: an alerting channel that can crash its caller is worse than none.

Note: this is deliberately NOT `backend/providers/tts.py`, which SYNTHESISES
audio to a .wav file for scene narration and never plays anything. This plays
through the default audio device via Windows SAPI.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
LOG_PATH = WORLD_SIM / ".scratch" / "speak.log"
BLOCKED_PREFIX = "Sean, I am blocked and I need you. "


def _ps_exe() -> str:
    """Windows PowerShell 5.1 carries System.Speech reliably; pwsh is the fallback."""
    for exe in ("powershell", "pwsh"):
        try:
            p = subprocess.run([exe, "-NoProfile", "-Command", "echo ok"],
                               capture_output=True, text=True, timeout=30)
            if p.returncode == 0:
                return exe
        except Exception:
            continue
    return "powershell"


def speak(text: str, repeat: int = 1, rate: int = 0, timeout: int = 180) -> dict:
    """Say `text` out loud. Returns a result dict; never raises."""
    text = (text or "").strip()
    if not text:
        return {"spoke": False, "detail": "empty text"}
    exe = _ps_exe()
    # The message goes through a temp FILE so no quoting or escaping can mangle
    # it -- a truncated or garbled blocker alert is a silent failure.
    tmp = None
    try:
        handle = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                            encoding="utf-8")
        handle.write(text)
        handle.close()
        tmp = Path(handle.name)
        script = (
            f"$t = Get-Content -Raw -LiteralPath '{tmp}'; "
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {int(rate)}; "
            f"1..{max(1, int(repeat))} | ForEach-Object {{ $s.Speak($t) }}; "
            "$s.Dispose()"
        )
        proc = subprocess.run([exe, "-NoProfile", "-Command", script],
                              capture_output=True, text=True, timeout=timeout)
        ok = proc.returncode == 0
        return {"spoke": ok, "engine": exe,
                "detail": (proc.stderr or "").strip()[:300]}
    except Exception as exc:
        return {"spoke": False, "engine": exe,
                "detail": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        try:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        except Exception:
            pass


def log(text: str, blocked: bool) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({
                "at_utc": datetime.now(timezone.utc).isoformat(),
                "blocked": blocked,
                "text": text,
            }) + "\n")
    except Exception:
        pass


def maybe_telegram(text: str) -> dict:
    """Also push to Telegram when it is configured: the speaker only reaches him
    at the machine, and a blocker may occur while he is away from it."""
    try:
        sys.path.insert(0, str(WORLD_SIM / "scripts"))
        import agent_watch  # type: ignore
        token, chat = agent_watch.telegram_config()
        if not token or not chat:
            return {"telegram": "not configured"}
        ok, detail = agent_watch.send_telegram({
            "kind": "blocker", "key": f"blocker:{int(time.time())}",
            "severity": "high", "pair": "-", "agent": "-", "heartbeat": None,
            "title": "BLOCKED - needs Sean", "body": text,
            "reply_hint": "the agent is waiting on you",
        }, token, chat)
        return {"telegram": "sent" if ok else f"failed: {str(detail)[:120]}"}
    except Exception as exc:
        return {"telegram": f"error: {type(exc).__name__}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--text", dest="text_opt", default="")
    ap.add_argument("--blocked", default="",
                    help="prefixes the message so it is unmistakably a request "
                         "for Sean; says it twice")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--rate", type=int, default=0, help="-10..10, SAPI rate")
    ap.add_argument("--telegram", action="store_true",
                    help="also push the alert to Telegram")
    ap.add_argument("--dry-run", action="store_true",
                    help="log and report without speaking")
    args = ap.parse_args()

    if args.blocked:
        text, repeat, blocked = BLOCKED_PREFIX + args.blocked.strip(), 2, True
    else:
        text, repeat, blocked = (args.text or args.text_opt).strip(), args.repeat, False

    if not text:
        print(json.dumps({"spoke": False, "detail": "no text given"}))
        return 2

    log(text, blocked)
    result = {"spoke": False, "detail": "dry run"} if args.dry_run else speak(
        text, repeat=repeat, rate=args.rate)
    result["blocked"] = blocked
    result["text"] = text
    if args.telegram:
        result.update(maybe_telegram(text))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("spoke") or args.dry_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
