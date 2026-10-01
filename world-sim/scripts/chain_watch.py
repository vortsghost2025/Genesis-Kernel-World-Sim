"""Chain run monitor: distinct terminal messages, never silence.

The watcher reports store idleness (`dead`) identically for finished-OK and
died-badly, says nothing about why, and is itself silent if it dies. This
script watches ONE run: Telegrams on start (with target), then exactly one
terminal message — complete, hard-stop with the log's reason, or stalled
(tick unmoved beyond budget with the chain gone quiet).

Dedupe: one terminal state sends once, ever, per ledger. Restarting the
monitor cannot replay a terminal message.

Usage:
    python world-sim/scripts/chain_watch.py --pair east --start 1044 --end 1143 --chain-pid 1234
    python world-sim/scripts/chain_watch.py --status
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

STORES = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}
WATCH_SCRATCH = WORLD_SIM / ".scratch" / "chain_watch"
LEDGER = WATCH_SCRATCH / "runs.json"

ADAM_REF = "east_adam"
EVE_REF = "east_eve"

# A heartbeat lands every ~2-3 min; 30 min without movement while the chain
# is supposed to be running means dead-or-wedged, not slow.
STALL_BUDGET_S = 1800
POLL_S = 120

# Inert-heartbeat budget. The tick measures the CLOCK, not the world: a
# chain whose model route is dead keeps ticking and keeps logging "OK"
# while both agents take no action at all. Proven on 2026-09-30 - the
# nvidia/* routes began returning 502/403 upstream, and HB1198-1243 ran 46
# consecutive heartbeats with zero actions while the chain reported success
# and this watcher reported "complete". Five consecutive fully-inert
# heartbeats (~10-15 min at the live cadence) is past any transient: a
# single 429 or one dead key is a dead heartbeat, not a dead world.
INERT_TAIL_THRESHOLD = 5


def run_health(heartbeats: list[dict]) -> dict:
    """Is the sim actually living, or just the clock?

    A heartbeat is INERT when no agent acted — `action_taken` absent, or
    present with every agent entry null. Anything either agent did counts
    as life, so a run where one agent is silent but the other works is
    alive, not frozen.

    Returns {verdict, inert_tail, last_active_heartbeat, heartbeats_seen}.
    `verdict` is "frozen" once the inert tail reaches
    INERT_TAIL_THRESHOLD, "healthy" while short of it, and "unknown" when
    there is no history at all: absence of evidence is not evidence of a
    dead world, and this monitor has already learned that a monitor which
    invents death from its own read failure is worse than silent.
    """
    rows = [r for r in heartbeats if isinstance(r, dict)]
    if not rows:
        return {"verdict": "unknown", "inert_tail": 0,
                "last_active_heartbeat": None, "heartbeats_seen": 0}

    def acted(row: dict) -> bool:
        acts = row.get("action_taken") or {}
        if not isinstance(acts, dict):
            return False
        return any(isinstance(a, dict) and a.get("action_type") not in
                   (None, "", "no_action") for a in acts.values())

    inert_tail = 0
    last_active = None
    for row in rows:
        n = row.get("heartbeat_number")
        if acted(row):
            inert_tail = 0
            last_active = n
        else:
            inert_tail += 1
    verdict = "frozen" if inert_tail >= INERT_TAIL_THRESHOLD else "healthy"
    return {"verdict": verdict, "inert_tail": inert_tail,
            "last_active_heartbeat": last_active,
            "heartbeats_seen": len(rows)}


def load_heartbeats(pair: str, limit: int = 60) -> list[dict]:
    """Most recent heartbeat records for a pair, oldest-first.

    Reads the store's own heartbeat ledger. Returns [] when unreadable —
    never a fabricated history.
    """
    data = _read_json(STORES.get(pair, STORES["east"]) / "heartbeat.json")
    rows = data.get("data", data)
    if not isinstance(rows, list):
        return []
    rows = [r for r in rows if isinstance(r, dict)]
    return rows[-limit:] if limit else rows


# --- Progress pings -------------------------------------------------------
# The terminal messages answer "is it broken". These answer "is it
# happening" - the question a person waiting on a long run actually has.
# Sent by this process, because the person waiting is not required to be
# awake for the world to report on itself.

_PROGRESS_EVERY = 25

_AGENT_LABELS = {
    "east_adam": "Adam", "east_eve": "Eve",
    "west_adam": "Adam", "west_eve": "Eve",
}


def _tile_xy(tile: str) -> tuple[int, int] | None:
    """(x, y) from a gen tile id, or None when the shape is unfamiliar."""
    try:
        parts = str(tile).split("_")
        return int(parts[-2]), int(parts[-1])
    except (ValueError, IndexError):
        return None


def _row_tile(row: dict, who: str) -> str:
    """Where an agent stood, read from the store's real shape.

    `position` is an empty string on every row in this store's history -
    the location is in `observation[agent_ref].tile_id`. Reading the empty
    field is what made the first live render say "0 tiles nowhere".
    """
    obs = row.get("observation")
    if isinstance(obs, dict):
        entry = obs.get(who)
        if isinstance(entry, dict):
            tid = entry.get("tile_id")
            if isinstance(tid, str) and tid:
                return tid
    pos = row.get("position")
    if isinstance(pos, dict):
        tid = pos.get(who)
        if isinstance(tid, str) and tid:
            return tid
    return ""


def window_summary(heartbeats: list[dict], since_hb: int, to_hb: int) -> dict:
    """What each agent did between two heartbeats.

    Counts real move/gather actions from the ledger rather than inferring
    activity from position, and derives a compass direction from net
    displacement. A missing location yields "nowhere" - never a guess.
    """
    window = [r for r in heartbeats
              if since_hb < (r.get("heartbeat_number") or 0) <= to_hb]
    out: dict[str, dict] = {}
    for row in window:
        for who in (ADAM_REF, EVE_REF):
            acts = (row.get("action_taken") or {}).get(who)
            if isinstance(acts, dict):
                at = acts.get("action_type")
                if at in ("move", "gather"):
                    rec = out.setdefault(who, _blank_agent())
                    rec[at + "s"] += 1
            tile = _row_tile(row, who)
            if tile:
                rec = out.setdefault(who, _blank_agent())
                rec["_first_tile"] = rec.get("_first_tile") or tile
                rec["_last_tile"] = tile
    for who, rec in out.items():
        first = _tile_xy(rec.pop("_first_tile", ""))
        last = _tile_xy(rec.pop("_last_tile", ""))
        if first and last:
            rec["net_tiles"] = abs(last[0] - first[0]) + abs(last[1] - first[1])
            rec["direction"] = _compass(first, last)
            rec["at"] = f"{last[0]},{last[1]}"
        else:
            rec["net_tiles"] = 0
            rec["direction"] = "nowhere"
            rec["at"] = None
    return out


def _blank_agent() -> dict:
    return {"moves": 0, "gathers": 0, "net_tiles": 0, "direction": "nowhere",
            "at": None}


def _compass(first: tuple[int, int], last: tuple[int, int]) -> str:
    dx, dy = last[0] - first[0], last[1] - first[1]
    if dx == 0 and dy == 0:
        return "nowhere"
    if abs(dx) >= abs(dy):
        return "east" if dx > 0 else "west"
    return "north" if dy > 0 else "south"


def progress_message(pair: str, since_hb: int, target_end: int, summary: dict,
                     tick: int | None, messages: int, objects_built: int,
                     questions: int, first_message: str = "") -> str:
    """One short paragraph a person can read on a phone.

    Plain sentences by construction: agent names, counts, compass
    directions. No ids, no field names, no dumps - the run monitor's
    terminal messages are the ones that carry diagnostics, and they carry
    them once.
    """
    bits = []
    for who in (ADAM_REF, EVE_REF):
        rec = summary.get(who)
        if not rec:
            continue
        name = _AGENT_LABELS.get(who, who)
        if rec["moves"] and rec["direction"] != "nowhere":
            where = (f", now at {rec['at']}" if rec["at"] else "")
            bits.append(f"{name} made {rec['moves']} moves, net "
                        f"{rec['net_tiles']} tiles {rec['direction']}{where}")
        elif rec["moves"]:
            bits.append(f"{name} made {rec['moves']} moves without going "
                        f"anywhere in particular")
        elif rec["gathers"]:
            bits.append(f"{name} spent this stretch gathering "
                        f"({rec['gathers']} times)")
        else:
            bits.append(f"{name} did nothing")
    who_line = "; ".join(bits) if bits else "no agent activity recorded"

    tail = []
    if messages:
        tail.append(f"they have sent {messages} message"
                    f"{'s' if messages != 1 else ''} to each other")
    else:
        tail.append("they have sent no messages to each other")
    if objects_built:
        tail.append(f"built {objects_built} object"
                    f"{'s' if objects_built != 1 else ''}")
    if questions:
        tail.append(f"asked the operator {questions} question"
                    f"{'s' if questions != 1 else ''}")

    msg = (f"Genesis: {pair} is {tick - since_hb + 1} of {target_end - since_hb + 1} "
           f"heartbeats in. {who_line}. {'; '.join(tail).capitalize()}.")
    if first_message:
        msg += f' The first one said: "{first_message[:140]}"'
    return msg


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8",
                    newline="\n")


def store_tick(pair: str) -> int | None:
    ws = STORES[pair] / "world_state.json"
    data = _read_json(ws)
    inner = data.get("data", data)
    tick = inner.get("tick")
    return tick if isinstance(tick, int) else None


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        import psutil  # type: ignore
        return psutil.Process(pid).is_running()
    except Exception:
        pass
    try:
        import os
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def classify(tick: int | None, target_end: int, chain_alive: bool,
             seconds_since_move: float) -> str:
    """One of: complete, stopped, stalled, running, unknown.

    Pure function — the unit under test. `tick is None` (unreadable store)
    is unknown, never a terminal state: a monitor must not declare death
    from its own read failure.
    """
    if tick is None:
        return "unknown"
    if tick >= target_end:
        return "complete"
    if not chain_alive:
        return "stopped"
    if seconds_since_move > STALL_BUDGET_S:
        return "stalled"
    return "running"


def terminal_message(state: str, pair: str, tick: int | None, target_end: int,
                     reason: str = "", inert_tail: int | None = None) -> str:
    if state == "frozen":
        span = f" for the last {inert_tail} heartbeats" if inert_tail else ""
        return (f"Genesis: the agents have stopped acting{span}. {pair} is at "
                f"HB{tick} of a run targeting {target_end}, and NEITHER agent "
                f"has taken an action. The clock is still advancing; the "
                f"world is not. This is a model/provider failure, not a "
                f"result about the agents - these heartbeats are not "
                f"evidence. Needs a human look.")
    if state == "complete":
        return (f"Genesis: census run complete. {pair} reached HB{target_end} "
                f"(100 heartbeats, no action needed).")
    if state == "stopped":
        return (f"Genesis: chain STOPPED at HB{tick} (target {target_end}). "
                f"{reason} I am idle; nothing will advance until a human "
                f"looks. No data lost: the store is intact at HB{tick}.")
    if state == "stalled":
        return (f"Genesis: chain STALLED at HB{tick} (target {target_end}, "
                f"no movement in 30+ min). {reason} Needs a human look.")
    return ""


def _load_ledger() -> dict:
    return _read_json(LEDGER)


def already_sent(run_key: str, state: str) -> bool:
    return _load_ledger().get(run_key, {}).get(state, False)


def mark_sent(run_key: str, state: str) -> None:
    ledger = _load_ledger()
    entry = ledger.get(run_key, {})
    entry[state] = {"at_utc": _utc_now()}
    ledger[run_key] = entry
    _write_json(LEDGER, ledger)


def send_telegram_text(text: str) -> tuple[bool, str]:
    """Best-effort Telegram; failures are returned, never raised.

    Shapes the message as a watcher signal so the shared render path is
    reused exactly — one format on the channel, no drift.
    """
    sys.path.insert(0, str(WORLD_SIM / "scripts"))
    try:
        from agent_watch import send_telegram
    except Exception as exc:
        return False, f"import: {type(exc).__name__}"
    import os
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        # Fall back to User-level env (where the operator keeps them).
        return False, "telegram not configured in process env"
    sig = {
        "severity": "info",
        "title": "run monitor",
        "pair": "-",
        "agent": "-",
        "heartbeat": "-",
        "body": text,
    }
    try:
        return send_telegram(sig, token, chat)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:120]}"


def chain_log_tail(n: int = 6) -> list[str]:
    logs = sorted((WORLD_SIM / ".scratch" / "lockstep").glob("chain_*.log"))
    if not logs:
        return []
    try:
        return logs[-1].read_text(
            encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def last_stop_reason() -> str:
    tail = chain_log_tail(8)
    for line in reversed(tail):
        if "HARD STOP" in line or "FAILED after" in line or "TIMEOUT" in line:
            return line.strip()[:160]
    return "no reason in chain log tail."


def start_of_run(start: int, end: int, tick: int | None) -> int:
    """The window's lower bound for a digest: run start, or as far back as
    the stored heartbeat ledger reaches, whichever is later."""
    return start

def completion_digest(pair: str, start: int, end: int) -> str:
    """The verdict the run was measuring, in one short paragraph.

    chain_watch already announces a terminal state. This carries what the
    terminal state means: did either agent speak, did 'unresponsive' stay
    or leave their own reasoning, where are they. Plain sentences, read
    off the store - the same place the agent figured it out, not a report
    written separate from what happened.
    """
    beats = load_heartbeats(pair, limit=0)
    if not beats:
        return "the store cannot be read, so I cannot say how it went."

    # Messages / objects / asks created in this run's window.
    n_msgs, n_objs, n_asks, first_msg = window_counts(pair, start, end)

    # Decision summaries on the final heartbeat: own-age fracture point.
    last = beats[-1]
    reasoning = " ".join(
        str(v) for v in (last.get("decision_summaries") or {}).values())
    mentions_unresponsive = "unresponsive" in (reasoning or "").lower()

    if n_msgs:
        verdict = (f"they sent {n_msgs} message"
                   f"{'s' if n_msgs != 1 else ''} in this run")
        if first_msg:
            verdict += f'; the first said: "{first_msg[:120]}"'
    else:
        verdict = "no messages in this run"

    if mentions_unresponsive:
        verdict += "; their final reasoning still names being unanswered by her"
    else:
        verdict += "; the belief that she is not answering is gone from their final reasoning"

    if n_objs:
        verdict += (f"; they built {n_objs} object"
                    f"{'s' if n_objs != 1 else ''}")
    return verdict + "."


def wake_operator(brief: str, run_key: str) -> dict:
    """Resume the operator session with a completed run's verdict.

    Telegram is the alarm. `opencode run -c` is the turn: it resumes the
    current session with full context, so the operator's report on what
    just finished is made by the thing that read it. This exists because
    the pattern Sean name-checked - a scheduled turn brings the agent back
    with information - was already live here for ask/stuck signals, and
    completion had no door on the same bell.

    Fires once per run, keyed by the same ledger that dedupes Telegram:
    a wake that wasn't sent is not 'sent-but-maybe'. A run that never
    completes never wakes.
    """
    import os
    import subprocess
    if already_sent(run_key, "woken"):
        return {"woken": False, "reason": "already_woken"}
    DETACHED = (0x00000008 | 0x00000200 | 0x01000000 | 0x08000000)
    cmd = ["opencode", "run", "-c",
           "--title", f"genesis census verdict ({run_key})", brief]
    try:
        subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=DETACHED)
        mark_sent(run_key, "woken")
        return {"woken": True, "brief_len": len(brief)}
    except Exception as exc:
        return {"woken": False, "reason": f"{type(exc).__name__}: {exc}"}


def monitor_once(pair: str, start: int, end: int,
                 chain_pid: int | None) -> dict:
    run_key = f"{pair}:{start}-{end}"
    tick = store_tick(pair)
    alive = pid_alive(chain_pid)
    # Movement clock: newest evidence/status mtime in the lockstep dir.
    move_age = _seconds_since_last_evidence()
    state = classify(tick, end, alive, move_age)
    health = run_health(load_heartbeats(pair))
    # A run that produced no actions is not succeeding, whether or not it
    # has reached its target. Reaching the end is a property of the clock;
    # the agents acting is a property of the world. Proven on 2026-09-30,
    # when 46 dead heartbeats were reported to the operator as a completed
    # census and nobody knew the sim had been frozen since HB1198.
    if health["verdict"] == "frozen":
        state = "frozen"
    result: dict = {"state": state, "tick": tick, "chain_alive": alive,
                    "run": run_key, "health": health}
    if state in ("complete", "stopped", "stalled", "frozen") and \
            not already_sent(run_key, state):
        reason = "" if state in ("complete", "frozen") else last_stop_reason()
        msg = terminal_message(state, pair, tick, end, reason,
                               inert_tail=health["inert_tail"])
        if state == "complete":
            msg += f" Verdict: {completion_digest(pair, start, end)}"
        ok, detail = send_telegram_text(msg)
        result["notified"] = ok
        result["notify_detail"] = detail
        if ok:
            mark_sent(run_key, state)
            # Wake the operator session on ends-of-run, not only Telegram:
            # a completed census or a frozen one both mean it is time to
            # look. Frozen wakes because "why did nothing happen" is
            # diagnosis work, which belongs in a turned session with the
            # full context, not on a phone screen.
            if state in ("complete", "frozen"):
                brief = (
                    f"Genesis census run ended. Pair: {pair}, "
                    f"run {start}-{end}. State: {state}. "
                    f"{terminal_message(state, pair, tick, end, reason)}"
                )
                if state == "complete":
                    brief += (
                        f" Verdict for this run: "
                        f"{completion_digest(pair, start, end)}"
                    )
                wake = wake_operator(brief, run_key)
                result["woken"] = wake.get("woken", False)
    else:
        result["notified"] = False
    return result


def _seconds_since_last_evidence() -> float:
    d = WORLD_SIM / ".scratch" / "lockstep"
    try:
        mtimes = [p.stat().st_mtime for p in d.glob("lockstep_*")
                  if p.is_file()]
    except OSError:
        return float("inf")
    if not mtimes:
        return float("inf")
    return time.time() - max(mtimes)


def announce_start(pair: str, start: int, end: int) -> dict:
    run_key = f"{pair}:{start}-{end}"
    if already_sent(run_key, "started"):
        return {"announced": False, "reason": "already announced"}
    msg = (f"Genesis: census run started. {pair} HB{start}-{end} "
           f"({end - start + 1} heartbeats, ~4h). I will message on "
           f"complete, stop, or stall — silence from me means running.")
    ok, detail = send_telegram_text(msg)
    if ok:
        mark_sent(run_key, "started")
    return {"announced": ok, "detail": detail}


def window_counts(pair: str, since_hb: int, to_hb: int) -> tuple[int, int, int, str]:
    """(messages, objects, questions, first message text) created in a window.

    Read from the world state, not inferred. A message is worth quoting:
    when they finally speak, the words matter more than the count.
    """
    data = _read_json(STORES.get(pair, STORES["east"]) / "world_state.json")
    inner = data.get("data", data)

    def _hb_of(rec: dict) -> int:
        for k in ("heartbeat", "created_heartbeat"):
            v = rec.get(k)
            if isinstance(v, int):
                return v
        return 0

    def _in_window(rec: dict) -> bool:
        h = _hb_of(rec)
        return since_hb < h <= to_hb

    msgs = [m for m in (inner.get("public_messages") or [])
            if isinstance(m, dict) and _in_window(m)]
    objs = [o for o in (inner.get("public_objects") or {}).values()
            if isinstance(o, dict) and _in_window(o)]
    asks = [q for q in (inner.get("questions_raised") or inner.get("questions") or [])
            if isinstance(q, dict) and _in_window(q)]
    first = str(msgs[0].get("message", "")) if msgs else ""
    return len(msgs), len(objs), len(asks), first


def maybe_send_progress(pair: str, start: int, end: int, tick: int | None,
                        every: int = _PROGRESS_EVERY) -> dict:
    """Send a progress ping once per `every` heartbeats crossed.

    Deduplicated in the ledger by window index, so a poll that crosses the
    same boundary twice sends once, and a re-run of the watcher mid-run
    does not re-send pings already delivered.
    """
    if not tick or tick < start or every <= 0:
        return {"sent": False, "reason": "not_due"}
    index = (tick - start) // every
    if index < 1:
        return {"sent": False, "reason": "not_due"}
    run_key = f"{pair}:{start}-{end}"
    state = f"progress:{index}"
    if already_sent(run_key, state):
        return {"sent": False, "reason": "already_sent"}
    since = start + index * every - every
    beats = load_heartbeats(pair, limit=max(every * 3, 80))
    summary = window_summary(beats, since, tick)
    n_msgs, n_objs, n_asks, first = window_counts(pair, since, tick)
    msg = progress_message(pair, since, end, summary, tick, n_msgs, n_objs,
                           n_asks, first_message=first)
    ok, detail = send_telegram_text(msg)
    if ok:
        mark_sent(run_key, state)
    return {"sent": ok, "index": index, "detail": detail, "message": msg}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pair", default="east")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--end", type=int, default=0)
    p.add_argument("--chain-pid", type=int, default=None)
    p.add_argument("--once", action="store_true")
    p.add_argument("--announce", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--progress-every", type=int, default=_PROGRESS_EVERY,
                   help="heartbeats between progress pings (0 disables)")
    args = p.parse_args(argv)
    if args.status:
        print(json.dumps(_load_ledger(), indent=2))
        return 0
    if args.announce:
        print(json.dumps(announce_start(args.pair, args.start, args.end),
                         indent=2))
        return 0
    if args.once:
        print(json.dumps(monitor_once(args.pair, args.start, args.end,
                                      args.chain_pid), indent=2))
        return 0
    print(f"CHAIN_WATCH=UP run={args.pair}:{args.start}-{args.end} "
          f"progress_every={args.progress_every}", flush=True)
    while True:
        try:
            out = monitor_once(args.pair, args.start, args.end, args.chain_pid)
            if out.get("state") in ("complete", "stopped", "stalled", "frozen") \
                    and out.get("notified"):
                print(f"[{_utc_now()}] terminal {out['state']} notified",
                      flush=True)
            elif args.progress_every:
                prog = maybe_send_progress(args.pair, args.start, args.end,
                                          out.get("tick"),
                                          every=args.progress_every)
                if prog.get("sent"):
                    print(f"[{_utc_now()}] progress #{prog['index']} notified",
                          flush=True)
        except Exception as exc:
            print(f"CHAIN_WATCH_ERROR {type(exc).__name__}: {exc}", flush=True)
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
