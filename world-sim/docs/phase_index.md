# Phase Index

Public index of implemented and planned phases for the Genesis Kernel World Sim project.

| Phase | Status | Purpose | Commit | Runtime Impact | Notes |
|---|---|---|---|---|---|
| 10I | Done | Add bounded daemon CLI controls | `ae0492c` | Daemon CLI flags and selection bounds; no change to ledger or data | Establishes that daemon commands must match authorized agent pairs; no infrastructure or provider changes |
| Kilo B | Done | Add sanitized Kilo orchestration templates | `9a64d4c` | Orchestration scaffolding only; no runtime changes | Templates for agent task definitions; not wired into daemon execution |
| Kilo C | Done | Harden council proof and output hygiene | `83302d8` | Output formatting rules enforced in council/task responses; no data writes | Bans `/skill` references, CLIXML, router noise from human-facing output; pure formatting layer |
| 10J | Done | Add Genesis canon and boundaries specification | `b3095d9` | Specification only; no runtime code or data changes | Defines evidence categories, claim scopes, founding-agent continuity, lens semantics, forbidden-inference rules, and minimum event schema for 10K |
| 10K | Done | Add pure world event ledger | `d9a2b00` | No runtime impact — module is deliberately not wired into daemon | Implements `validate_event()`, `append_event()`, `read_events()` over JSONL; enforces schema, evidence categories, claim scopes, before/after refs for mutations, and hidden-water/animal-guidance boundaries; 13 tempdir-only tests |
| 10L | Done | Add pure candidate event mapper | `9727954` | No runtime impact — returns candidate dicts only, never writes files | Translates observe/rest/gather/whisper/goal/help results into candidate events; rejects unsafe gathers and private paths; 16 tempdir-only tests pass |
| 10M | Done | Public README and phase index documentation | `b5b1b3e` | None — documentation only | Creates root README.md and this phase index; no code, test, daemon, or data changes |

## Legend

- **Done** — committed and pushed to `master`
- **In progress** — files exist in working tree but not committed
- **Planned** — agreed scope, not yet started

## Boundaries

All testable phases (10K, 10L) run against temporary directories only. No test or module in this index accesses `world-sim/data`, connects to a provider or model, runs a daemon or scheduler, or requires Docker or VPS infrastructure. A future runtime wiring phase (planned, not yet assigned a number) will document its own prerequisites before execution.