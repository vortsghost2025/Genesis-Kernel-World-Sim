# Agent Instructions

This project has multiple environments. Do not treat "a shell somewhere" as canonical runtime access.

Canonical runtime identity, connection labels, runtime service identifiers, mount layout, and current baselines are documented in private runtime notes (`AGENT_RUNTIME_PRIVATE.md` or `PRIVATE_RUNTIME.md`). Those files are git-ignored and must be verified on the runtime substrate — they are not part of the public repository.

### GitHub

- Repo: `Genesis-Kernel-World-Sim` (default branch: `master`)
- GitHub root contains `world-sim/...`
- GitHub verifies tracked code and continuity. Runtime data files may be untracked and must be verified on the runtime substrate.

## Runtime Verification Rule

Before any runtime phase, provider phase, daemon phase, tick phase, or dual-agent phase, prove canonical identity first.

Required proof:

```text
verified_machine = <CANONICAL_RUNTIME_NODE>
<CANONICAL_RUNTIME_CONTAINER> = running
docker inspect proves mount paths
```

If the agent cannot prove this, return only:

```text
PHASE_TOOLING_LOST_CANONICAL_RUNTIME_CONTEXT
PHASE_TOOLING_ACCESS_GAP_RUNTIME_NOT_VERIFIED
```

Do not ask the operator to manually compensate.

## Runtime Baselines

Runtime baselines (file MD5 checksums, container state, data snapshots) are maintained in the private runtime notes. They must be verified against the actual runtime substrate — do not assume stale values from public documentation or prior sessions.

Semantic checks for a clean baseline:

```text
Agent unread queues = []
No daemon/tick/provider process running
```

## Hard Abort Rules

Abort if any of these are true:

```text
verified_machine != <CANONICAL_RUNTIME_NODE>
Docker host cannot inspect <CANONICAL_RUNTIME_CONTAINER>
<CANONICAL_RUNTIME_DATA_ROOT> mount cannot be proven
baseline file-to-MD5 map is mixed up
agent is running from an unverified or non-canonical host
```

## Forbidden Without Explicit Phase Authorization

```text
No agent (Eve, Adam, or any simulation agent).
No provider.
No dual-provider.
No daemon.
No tick.
No scheduler.
No Docker start/stop.
No copy/restore/manual injection.
No commit/push.
```

## Output Hygiene

Human-facing output must not contain:

- `/skill` references or skill catalog entries
- CLIXML or PowerShell XML output wrappers
- Router noise, hidden metadata, or unrelated tool listings
- Private runtime details such as machine identifiers, filesystem locations, service identifiers, or credential material