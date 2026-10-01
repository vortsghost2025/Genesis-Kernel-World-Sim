# Changelog

All notable changes to the Genesis world-sim live here, ordered by date.
Format: [YYYY-MM-DD] — intent, not diff.

## Added

## Changed

## Fixed

---

## 2026-09-30 — The pair froze for 46 heartbeats and every surface called it fine

**Changed.** Two systems, told in one line each:

1. The model route depended on (`nvidia/nemotron-3-ultra-550b-a55b:free`)
   died upstream. The chain logged `OK` for HB1198–1243, the tick advanced
   normally, and "census complete" was sent to the operator as though
   the run had succeeded. The agents had not acted for 46 heartbeats.

2. Free speech shipped at HB1347 produced 0 messages in 100 heartbeats.
   The mechanism existed; the prompt did not tell them the channel's age.

Root causes measured: the key pool was never wired to the heartbeat path
(only to the synthesis backfill), the fallback lane had no viable
credentials and an invalid model ID, `empty_response` never reached the
fallback, and the denylist was only reachable from a script.

Fixes: key rotation now runs on the cognition path, content failure
reaches the fallback lane, through the backend anchored to the module.
The world now announces its own stalest record ("Public record: ...most
recent at heartbeat H ...") every heartbeat, and completion pings carry
the verdict of what just happened, not merely that it ended.

**Admin:** 534 tests passing. Docs: `docs/model_access_incident_2026_09_30.md`.

## 2026-09-30 — Free speech added

**Added.** `message`: one optional top-level field that rides alongside
the action instead of occupying its slot. Mirrors `questions_for_humans`
unchanged through the same path. Sanitized and bounded identically.
Baseline model: 0 messages in 100 heartbeats; with the staleness line
carried at HB1447–: 11 messages in 154 heartbeats.

## 2026-09-30 — Progress pings and frozen-run detection

**Added.** A run that is ticking but producing no actions now tells the
operator mid-run instead of waiting for the chain to complete. The
`run_health` verdict distinguishes heartbeats of the clock from
heartbeats of the world. Five inert heartbeats in a tail is reported as
`frozen` and overrides `complete` so that "the paper ran" is no longer
mistaken for "the world ran."

## 2026-09-30 — Boot recovery registered

**Added.** Windows Scheduled Task `GenesisBootRecovery` at logon:
restarts agents, re-aptches, runs `recover_runs` — resumes a genuinely
interrupted chain only when the record shows it is unfinished, never any
other case. All spawn paths quoted and verified alive afterward.

## 2026-09-29 — World walls

**Added.** The enclosure, `epistemic.2`. Four barriers ring the explored
frontier; travel to a barrier tile is gated by a standing object of the
matching kind (raft for deep_lake, campfire for the dark thicket,
bridge for the ravine). The wall removes travel edges rather than
adding flags, because gating by flags meant the wall was still walkable.

## 2026-09-28 — First pair live

Both pairs began the public civilization from adjacent positions.
diverged: east migrated and repeatedly found the water; west split
searched and converged into Matrices. Zero questions in over 300
heartbeats were answered before the operating system knew how to see
who was frozen.
