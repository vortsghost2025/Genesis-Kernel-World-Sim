# Watch Bridge Spec — Turning a Watcher Alert Into an Operator Turn

**Status:** IMPLEMENTED (`watch_bridge.py`). Built 2026-09-28.
**Companion to:** `agent_watch.py` (the read-only watcher + Telegram alerter).
**Origin:** Sean's request — *"run the monitoring in the background so that as
they are finished it will basically send you a message or something that nudges
you back into turn."*

---

## 0. The mechanism, and its honest limit

I cannot wake myself from inside a turn. Nothing in this session can inject a
prompt into a running agent. What *is* available is a process I leave running
that starts a **new** turn:

```
opencode run -c "<brief>"     # -c continues the most recent session
```

`-c` continues **this** session, so the resumed turn inherits the full
context — `AGENTS.md`, the delegated operator authority (rule 7), the working
register, the phase history. That is the closest available thing to a
self-wake, and it is a real nudge rather than a metaphor: the agents ask a
question, and an operator turn begins that can answer it.

**The limit, stated plainly:** a resumed turn is a *new* model call with a
large context. It is not free, and it is not me "noticing" mid-thought. The
bridge spends a turn; the turn does the reasoning.

## 1. Why a separate script and not a hook on the watcher

`agent_watch.py` carries a hard design property: it is read-only and **never
answers on the operator's behalf** — "the operator's voice stays a human's."
Bolt an LLM-spawning side effect onto that and the property is gone.

The bridge is the *explicit* act that honours AGENTS.md rule 7 instead. It
never answers an agent itself. It only decides **when to ask a session to
look**, and that decision is budgeted and logged.

| | `agent_watch.py` | `watch_bridge.py` |
|---|---|---|
| reads sim state | yes | yes (the watcher's ledger only) |
| writes sim state | **never** | **never** |
| answers agents | **never** | **never** |
| notifies Sean | Telegram | no (watcher owns that) |
| spends a model turn | no | yes, on `ask` / `stuck` only |

## 2. Which signals nudge

| signal | nudges? | why |
|---|---|---|
| `ask` | **yes** | an agent asked a question; only an operator can answer |
| `stuck` | **yes** | refused the same way, repeatedly; needs a human look |
| `first_build` | no | informational — Telegram already covers it |
| `dead` | no | almost always means *we* stopped running the chain |
| `starving` | no | informational; a pressure state, not a request |

Firing on informational signals would spend turns on things nobody needs to
decide. The bridge is for *"a human is required"*, nothing else.

## 3. The baseline watermark — the defect this would have shipped with

First draft computed "not yet nudged" as *difference between the watcher's
ledger and the bridge's ledger*. The watcher's ledger holds **111 signals**
going back to the 26th, most of them questions **already answered** in past
turns. The first scan would have fired a burst of operator turns replaying a
week-old backlog, and then the cooldown would have suppressed the *real* new
question behind them.

The fix is a watermark. On its first scan the bridge records
`baselined_at_utc` and marks every pre-existing signal as seen. `pending_nudges`
then rejects anything at or before that timestamp. Consequence:

> A question that already exists in the ledger can **never** trigger a turn,
> and the bridge does not need to know which questions were answered.

Idempotence falls out of it — restarting the bridge cannot re-nudge old alerts,
because "old" is defined by wall-clock, not by ledger bookkeeping.

**Verified:** first scan absorbed 111 / nudged 0. A hash-verified injected
probe (`east:ask:BRIDGE_SELFTEST_probe`) was picked up as pending and nudged;
the live watcher ledger was restored **byte-identical** (SHA-256 match), and the
probe's budget consumption was then reset.

## 4. Budget — the caps are real

Every nudge is a model turn, so the defaults are stingy:

- `--max-invocations 3` — hard cap, then `budget_exhausted`, forever.
- `--cooldown-seconds 900` — 15 minutes between turns.
- batched — one turn absorbs *all* pending signals, then they are all marked.

`opencode` is invoked detached (`DETACHED_PROCESS` | `CREATE_NEW_PROCESS_GROUP`
| `CREATE_BREAKAWAY_FROM_JOB` | `CREATE_NO_WINDOW`), so the bridge never blocks
on a turn and never dies because one is slow.

## 5. The brief it sends

Short and directive, and it encodes the standing constraints so a resumed turn
cannot drift:

1. read `operator_inbox.py` (read-only);
2. answer **factual** questions under rule 7 — truth or change only, *never*
   strategy, destinations, or build instructions; if a question needs an
   authority the delegation does not cover, **say so instead of guessing**;
3. re-read the relevant spec for the register on what is true;
4. report to Sean in plain language — no raw traces;
5. **do not** start a heartbeat, change physics, commit, or push. Heartbeats
   stay one-per-explicit-authorization.

## 6. Operating

```bash
python world-sim/scripts/watch_bridge.py --once --dry-run   # what would it do
python world-sim/scripts/watch_bridge.py --pending           # would it fire?
python world-sim/scripts/watch_bridge.py --status            # last action
python world-sim/scripts/watch_bridge.py --interval 90       # foreground loop
```

Artifacts in `world-sim/.scratch/watch_bridge/`: `nudged.json` (ledger +
budget), `bridge.log`, `status.json`.

## 7. What this will not do

**The world is frozen at HB943.** The bridge watches; it does not advance. No
heartbeat runs without Sean's explicit per-heartbeat authorization, so the
ledger cannot gain a new `ask` and the bridge will sit idle and correct.

That is not a defect — it is the standing rule doing its job. But it means
"monitoring in the background" and "the simulation keeps running" are two
different claims, and only the first is true right now. Running a chain needs a
separate decision, with its real cost: each heartbeat is 2 agent calls plus
retries, and the Phase B census is a 100-heartbeat arc.

## 8. Retrospective

Same failure mode as the four claims in
`weather_visibility_dial_spec.md` §9: a design reasoned about rather than run.
"Notify me when an agent asks" is obviously satisfiable. "Absorb the existing
backlog without replaying it" was the actual problem, and it was invisible
until the real ledger — 111 entries, mostly answered — was read.

The lesson generalises: **any stateful watcher needs a watermark, and the
watermark is the hard part.** The alerting is the easy half.
