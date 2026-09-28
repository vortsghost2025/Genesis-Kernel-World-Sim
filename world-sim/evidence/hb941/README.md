# Heartbeat 941 — Recovered State Evidence

Durable preservation of the state evidence for canonical heartbeat 941
(`east` pair), run 2026-09-28T01:38Z, store tick advanced 940 → 941.

## What this file is

`state_evidence.json` is the **recovered state evidence** for heartbeat 941,
regenerated read-only from the authoritative store by
`scripts/export_first_pair_state_evidence.py`. Per the no-rerun rule in
`docs/canonical_heartbeat_runbook.md` §8, the heartbeat was **never
re-executed** — the store had already persisted tick 941, and recovery means
read-only evidence regeneration only.

The file's own `evidence_class` and `recovery_note` fields record this
provenance; they were written by the runner's
`label_recovered_evidence()` and are preserved verbatim here.

- SHA-256: `52d4c201f849d3ae33aae9504c2e8d4cf2d06fe7cf18daec1170e3ab1dfd99c2`
- Size: 133,769 bytes
- Exported at: `2026-09-28T01:39:50Z` (per the file's `exported_at_utc`)

## Why it was copied to this path

The original export landed at a **doubled path**:

```
S:\Genesis Kernel World Sim\world-sim\world-sim\.scratch\hb941\evidence.json
```

The runner was invoked with a relative `--evidence` path and the loop script
resolved it against its own `cwd`, producing a doubled directory. The runner
then failed to find the evidence at the path it expected and reported
`recovery evidence export: evidence export exited 0` — misreporting a success
return code as a failure.

This is **Defect C** in `docs/heartbeat_runner_integrity_spec.md` and
**NFM-021** in Paper F (relative path resolution failure), recurring in a
second codebase.

The file is preserved here at a durable, tracked path so the record survives
the gitignored `.scratch/` tree. The doubled-path original was left in place,
untouched, as the literal artifact of the defect; removing it is an operator
decision, not an automated cleanup.

## Status of the run itself

The heartbeat **succeeded**: store persisted tick 941, 941 heartbeat records,
both agents acted (east_adam moved to a hill tile, east_eve gathered clay).
The run's `status.json` reported `failed` only because of the evidence-path
defect above. Two further defects found in the same run — the unenforced
free-only provider guard and the unpersisted provider provenance — are
documented in the spec alongside this one.
