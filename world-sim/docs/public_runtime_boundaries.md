# Public Runtime Boundaries

This document describes what is safe to run on any machine and what requires the canonical runtime host.

## Public-Safe (Any Machine)

The following can be run from any clone of this repository without special infrastructure:

- **Pure-module tests**: the 10K and 10L test suite (7 files, 29 tests total). These use temporary directories only, require no network, no Docker, no VPS, and no credentials.
- **Code review and spec review**: all backend modules in `world-sim/backend/world/` and all documentation in `world-sim/docs/` are safe to read, analyze, and modify.
- **Phase index and README**: public documentation can be updated without runtime access.

Commands that are always safe:

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

## Requires Canonical Runtime Host

The following require the canonical runtime host, its verified container and mount configuration, and the operator's explicit authorization:

- Daemon phases (10I and later daemon wiring)
- Provider phases (any that call an LLM or model)
- Tick and scheduler phases
- Dual-agent phases
- Any phase that reads or writes `world-sim/data`
- Any phase that starts or stops Docker containers

Documentation may refer to the canonical runtime host using the placeholder `<CANONICAL_RUNTIME_NODE>` and to runtime services using `<CANONICAL_RUNTIME_CONTAINER>` and `<CANONICAL_RUNTIME_DATA_ROOT>`. These are not real values — they must be replaced with the operator's private runtime notes before execution.

## Private Runtime Notes

The actual runtime identity, connection labels, service identifiers, mount layout, and current baselines are maintained in git-ignored private runtime notes:

- `AGENT_RUNTIME_PRIVATE.md`
- `PRIVATE_RUNTIME.md`
- `runtime-private.md`

These files are not part of the public repository. They must be verified against the actual runtime substrate and should never be committed.

## CI Boundaries

The public CI workflow runs only pure-module tests. It does not:

- Access any network beyond standard GitHub Actions setup steps
- Require secrets or credentials
- Run daemon, provider, tick, or scheduler processes
- Require Docker or a VPS
- Touch `world-sim/data`