# Genesis Kernel World Sim

A civilization-simulation kernel that models persistent agents, their perceptions, memories, actions, and the evidence-backed world events they produce.

This project is a **simulation engine**, not a real-world claim. The founding agents — Adam and Eve — are simulation entities with canonical identities, continuity across cycles, and bounded perception. They are not religious figures, real-world authorities, or conscious beings.

## Core Principle

**A claim is not a fact unless backed by accepted evidence.**

The system distinguishes several categories of information, each with different epistemic weight:

| Category | Description |
|---|---|
| **Observation** | Direct perception of world state through authorized channels |
| **Memory** | Persistent record of what an agent has perceived, done, or believed |
| **Speech** | Content of messages or whispers exchanged between agents |
| **Hypothesis** | A conjecture not yet supported by direct evidence |
| **Operator Proof** | Git commits, test output, or readback verification produced by the operator |
| **World Event** | An append-only record of a state change, action result, or social consequence |

Every event in the world ledger carries a `claim_scope` that identifies which of these categories it belongs to. The system enforces that hypotheses are labeled as hypotheses, that speech is recorded as speech (not fact), and that world mutations require before/after evidence.

## Architecture

Simulation output follows a pipeline:

```
daemon/action output
    → candidate event mapper
    → ledger validator
    → append-only ledger
```

- **Action executor** produces raw results from agent decisions (observe, rest, gather, whisper, goal, help).
- **Candidate event mapper** (Phase 10L) translates those results into candidate ledger entries without writing files.
- **Ledger validator** (Phase 10K) checks each candidate against the Genesis canon schema — required fields, valid evidence categories, private-path rejection, hidden-water and animal-guidance boundaries.
- **Append-only ledger** (Phase 10K) stores validated events as JSONL, preserving history immutably.

The ledger and mapper are currently **pure modules** — they can be imported, tested, and validated without a running simulation or any infrastructure.

## Current Status

**Phase 10L complete.** The stack up through the pure candidate event mapper has been implemented, tested (16 passing tests, all tempdir-only, no runtime dependencies), and pushed.

**Phase 10M in progress.** Public documentation only — this README and the phase index. No code changes. No daemon changes.

A later planned phase may connect the ledger and mapper into daemon and action-execution paths. That work is not part of this documentation phase.

## Safe Local Verification

You can run the pure-module tests for the completed ledger and mapper phases without any daemon, provider, tick, or runtime infrastructure:

```bash
cd world-sim
python -m pytest tests/test_phase10k_world_event_ledger_schema.py tests/test_phase10k_world_event_ledger_append_only.py tests/test_phase10k_world_event_ledger_boundaries.py tests/test_phase10l_candidate_mapper_observe_rest.py tests/test_phase10l_candidate_mapper_gather.py tests/test_phase10l_candidate_mapper_social.py tests/test_phase10l_candidate_mapper_boundaries.py -v
```

All tests use temporary directories only. They do not:
- Write to `world-sim/data/`
- Connect to any provider or model
- Start daemon, tick, or scheduler processes
- Access network or infrastructure
- Require Docker or a VPS

## Runtime Warning

Do not run daemon, provider, tick, or dual-agent phases unless you have verified that you are on the canonical runtime host with the correct container and mount configuration. Running these phases from an unverified host, workstation, or non-canonical environment may produce incorrect state or data loss.

## Project Boundaries

This repository explicitly excludes the following from agent-visible simulation scope:

- Hostnames, SSH targets, VPS details, and deployment infrastructure
- API keys, provider routes, billing, and credentials
- Git remotes, commits, branch state, and local operator workflow
- Private configuration files and personal family details
- Operator-only safety gates and internal runtime notes

Agents may not act on outside-world information unless a future phase deliberately translates it into an in-world artifact or event.