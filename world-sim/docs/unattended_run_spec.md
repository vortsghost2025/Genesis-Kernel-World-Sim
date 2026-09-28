# Unattended Run Spec — Single-Pair Chain, and the Three Defects Found by Running One

**Status:** IMPLEMENTED. Built 2026-09-28, immediately before an authorized
100-heartbeat unattended run (HB944–1043, east pair).
**Companion to:** `lockstep_chain.py`, `heartbeat_runner_integrity_spec.md`
(Defect C), `build_meaning_spec.md` (Phase B).

---

## 0. Why this document exists

Every defect below was found by **running** the thing, not by reading it. The
third was introduced by my own commit, ninety minutes earlier, and shipped
green. This is now the sixth and seventh such case this session, and the
retrospective section treats the pattern as the finding rather than any single
bug.

## 1. The capability: a single-pair chain

The chain advanced both pairs on one merged clock, hard-stopping if the two
stores disagreed. That is correct for a true lockstep run and useless for a
census that measures one pair — the west store is a deliberately dormant
comparison pair, three heartbeats behind, and it would stop every run.

```
python world-sim/scripts/lockstep_chain.py <start> <end> [pairs] [--no-snapshot]
```

- **Optional pair filter** — `east` runs a single-pair arc. An unknown pair
  name is a hard error, never a silent no-op: a typo that selected nothing
  would report success while advancing zero heartbeats.
- **The two-argument form is unchanged**, so the merged-clock path is
  byte-identical to before.
- **PREFLIGHT lines** print each pair's `count`/`tick` against the start
  heartbeat, so a misaligned start is visible before any work is done.

## 2. `--no-snapshot`: an external write, examined before shipping

The chain exports a slim snapshot and `scp`/`ssh`es it to a **public viewer**
every 10 ticks. That is not a local read and not a sim write — it *publishes*.
It was non-fatal and easy to miss, which is exactly how an undisclosed
external disclosure survives into production.

The flag defaults to **on**, preserving existing behaviour, and an unknown flag
is a hard error: a silently-ignored `--no-snapshot` would push to a public URL
the caller believed they had disabled.

**The census ran with snapshots off.** No census row needs the public show.
Consequence, stated plainly: **the public viewer will not update during
HB944–1043.** `export_viewer_snapshot.py` can be run by hand at any time.

## 3. Defect A (MINE, SHIPPED, CAUGHT IN MINUTES): `--log` killed every spawn

`1010eae` — the Defect C sibling fix — added `--log` to the **child** command:

```python
cmd = [..., "--evidence", args.evidence, "--log", str(log_path), ...]
```

`_runner_arg_parser` has **no** `--log` flag. `_launcher_arg_parser` does.
The launcher opens the log itself and redirects the child's output into it;
the runner never needed the flag.

Consequence: the launcher wrote its initial `not-started` status, spawned a
child that died at argparse, and nothing ever wrote a terminal status.
**Every heartbeat silently failed to start.**

HB943 had worked because it predated the commit. HB944 was the first spawn
after it, which is the only reason this was caught in minutes rather than at
the end of a 100-heartbeat run that reported nothing wrong.

**Fixed** by removing the flag from the child command and keeping the
launcher-side resolution (which was the actual point of the fix — a relative
`--log` landing at the repo root while its siblings resolved under the
world-sim root).

**The test I wrote asserted the bug.** It checked that the runner received an
absolute `--log`, which is precisely the wrong behaviour. It is replaced by:

- `test_launcher_resolves_the_log_itself_and_does_not_pass_it_on` — `--log`
  absent from the child command;
- `test_runner_parser_rejects_log` — a direct guard on `_runner_arg_parser`,
  not merely on the call site, so a future re-introduction fails at the parser;
- `test_launcher_creates_the_log_file_under_the_world_sim_root` — the log
  exists where it should, and **not** beside the caller.

## 4. Defect B: `wait_for_status` had no timeout

The status wait polled `while True`. Combined with Defect A it produced the
worst behaviour available to an unattended run: the chain **looked alive,
reported nothing, and never stopped**. I spent four minutes of Sean's
departure window watching a run that had already failed.

An unattended process must be able to distinguish *working* from *dead*.

```
STATUS_TIMEOUT_S = 600
```

Ten minutes per heartbeat — generous for a free-tier model, finite. A timeout
is **retryable** (the store check still governs, and a retry can succeed)
rather than fatal, and after `MAX_RETRIES` the chain hard-stops as it always
did. The timeout message names the last status it saw, because a silent
timeout is undiagnosable.

## 5. Verification

| check | result |
|---|---|
| `test_lockstep_pair_filter.py` | 18 passed |
| `test_lockstep_chain_timeout.py` | 9 passed |
| `test_canonical_heartbeat_runner.py` | 33 passed |
| full working set | 360 passed, 11 skipped |
| **HB944 real launch** | **landed; store 943 → 944** |
| runner log location | `.scratch/lockstep/`, not repo root |
| provider policy | both lanes `:free` (`nemotron-3-super…:free`, `glm-5.2:free`) |
| east store after the stuck run | untouched at 943 — no corruption |

## 6. The sixth false claim: I nearly "fixed" working code

Checking the Phase B anchors against live data, I compared
`creator_agent_id` to the literal `'east_adam'`, saw 0 anchors, and concluded
the feature was dead. Before changing anything I read how `agent_id` is
constructed: it is the **hashed canonical form**, `genesis-agent-<64 hex>`, and
`creator_agent_id` is the same form. The comparison in the shipped code was
correct; my **verification script** was wrong.

I was one edit away from breaking a working feature to satisfy a bad
measurement.

The durable fix is in the test suite, not the code:
`TestCanonicalAgentIdForm` asserts the canonical ids do not equal the short
refs, that anchors resolve under the canonical form, and that a short-ref
creator does **not** anchor. The original fixtures used
`creator_agent_id="east_adam"` — self-consistent, all green, and structurally
unable to detect a mismatch with the real store.

**A test that cannot fail on real data is not evidence.**

## 7. Phase B first live result — the decisive row is answered

Rendered from the real store at HB944:

```
REAL-DATA anchor count for Adam: 19
- [meeting-stone-center] on public-shared-center (heartbeat 10):
  Adam & Eve founded on contact, cooperation, and shared ground.
  The center is our meeting point. …
```

**`anchors per agent`: 0 → 19 each.** The census's decisive row flipped on the
first heartbeat. A statement written at heartbeat 10 and invisible to its
author for 934 heartbeats is now in front of him, verbatim.

**An honest counterweight, visible in the same render:** 18 of Adam's 19
anchors are `Test build: …` strings. The build history is mostly testing, plus
one real statement of shared ground. So the mechanism works and the *content*
is thin. That is a finding about what the agents chose to record, not about
whether they can.

## 8. What remains unproven

- 99 of the 100 heartbeats are unrun. One heartbeat is not a census; the trend
  rows (does the anchor count rise, do moves hold, do reachability blocks stay
  at 0) are still open.
- `anchors > 0` tests that agents *can* use the slot. It does not test that
  they *will*. The honest prior is unchanged.
- The bridge has never fired on a real signal. It is proven only against an
  injected probe and a hash-verified restore.
- The chain may hard-stop unattended on a store mismatch or three timeouts. It
  will now *say so* in the log rather than spin — but a stopped chain is still a
  stopped chain, and only a human will notice.

## 9. Retrospective

Seven claims this session, seven falsified by measurement, six of them mine.
The causes are always the same two:

1. **Reasoning about code without executing it** (the weather source, the stale
   snapshot, the move rule, `--log`'s parser contract).
2. **Testing against a fixture I invented rather than the data that exists**
   (the agent-id form, the anchor region slice, the `--log` assertion).

The second is the cheaper lesson and the more portable one. A test written to
match my idea of the data validates my idea. Only a fixture lifted from the
store can tell me the idea was wrong — and the one time I checked live, the
code was right and the check was wrong.
