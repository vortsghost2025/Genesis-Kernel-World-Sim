# Contributing

## Phase-Gated Workflow

This project uses a phase-gated development model. Each phase is a small, scoped change with a defined purpose:

- A phase adds or modifies a specific capability (ledger, mapper, documentation, CI)
- A phase does not wire into runtime unless that is its explicit purpose
- A phase is not committed until its tests pass and its proof is accepted

If you want to contribute, review `world-sim/docs/phase_index.md` to understand what phases exist and what is planned.

## Pure Modules and Safe Tests

All backend modules in `world-sim/backend/world/` are currently **pure** — they can be imported, tested, and validated without a running simulation or any infrastructure.

Tests use temporary directories only. They do not:

- Write to `world-sim/data`
- Connect to any provider or model
- Start daemon, tick, or scheduler processes
- Access the network
- Require Docker or a VPS

Run the pure-module test suite with:

```bash
cd world-sim
python -m pytest tests/test_phase10k_world_event_ledger_append_only.py \
                 tests/test_phase10k_world_event_ledger_boundaries.py \
                 tests/test_phase10k_world_event_ledger_schema.py \
                 tests/test_phase10l_candidate_mapper_observe_rest.py \
                 tests/test_phase10l_candidate_mapper_gather.py \
                 tests/test_phase10l_candidate_mapper_social.py \
                 tests/test_phase10l_candidate_mapper_boundaries.py \
                 -v
```

Do not run broad `pytest tests/` unless a specific phase authorizes it.

## Evidence and Proof Discipline

Every world event carries a `claim_scope` that identifies the epistemic category:

- **observed** — direct perception through authorized channels
- **memory** — an agent's recorded recollection
- **speech** — content exchanged between agents
- **hypothesis** — a conjecture without direct evidence
- **operator_proof** — git commits, test output, or readback verification
- **world_event** — a validated append-only state record

Hypotheses must be labeled as hypotheses. Speech must be recorded as speech. World mutations require before/after evidence. Code changes that touch the ledger or mapper must include corresponding test updates.

## Public / Private Boundary

This repository explicitly excludes certain information from agent-visible simulation scope:

- Machine identifiers, remote access labels, deployment host details, and runtime infrastructure
- API keys, provider routes, billing, and credentials
- Git remotes, commits, branch state, and local operator workflow
- Private configuration files and personal details
- Operator-only safety gates and internal runtime notes

Do not submit pull requests that contain private infrastructure details, runtime baselines, hostnames, credentials, or local machine paths.

Documentation may use placeholders such as `<CANONICAL_RUNTIME_NODE>` where real values would be private.

## Runtime Phases

Runtime phases (daemon, provider, tick, dual-agent) require explicit operator verification on the canonical runtime host. They are not part of public CI and must not be executed from an unverified environment. Do not add runtime wiring to a phase unless that phase explicitly authorizes it.

## Before Submitting

- Ensure all existing pure-module tests pass
- Add tests for new mapper or ledger functionality
- Ensure no private or runtime infrastructure details are committed
- Ensure no broad `pytest tests/` commands are added
- Confirm `git diff --check` reports no trailing whitespace