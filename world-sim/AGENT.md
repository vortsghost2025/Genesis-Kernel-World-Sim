# Canonical Runtime / Host Map

This project has multiple valid environments. Do not treat “a shell somewhere” as canonical runtime access.

### WE — Windows local host

- Hostname: `WE`
- User: `we\seand`
- Role: Sean’s Windows workstation / local working copy
- Canonical local repo path:
  - `S:\Genesis Kernel World Sim\world-sim`
- Notes:
  - Windows Docker Desktop may be unavailable.
  - If hostname is `WE`, this is not the VPS2 runtime host.
  - Do not run runtime-provider gates from WE.
  - Do not attempt to rename or “correct” WE to `srv1756620`.

### GitHub

- Repo:
  - `vortsghost2025/Genesis-Kernel-World-Sim`
- Default branch:
  - `master`
- Repo path convention:
  - GitHub root contains `world-sim/...`
- Current required closure commit after Phase 6V:
  - `32dacbf Phase 6V closure: Adam provider re-entry verified`
- Notes:
  - GitHub verifies tracked code/continuity.
  - Runtime JSON files may be untracked and must be verified on the runtime substrate.

### VPS1 — federation-vps

- SSH alias:
  - `federation-vps`
- Hostname:
  - `srv1345984`
- Role:
  - Federation containers / federation-game host
- Important:
  - This is not the Genesis Kernel World Sim runtime host for 6W gates.
  - If hostname is `srv1345984`, abort Genesis runtime verification.

### VPS2 — canonical Genesis runtime host

- SSH alias may be:
  - `vps2`
- Hostname:
  - `srv1756620`
- Role:
  - Canonical Genesis Kernel World Sim runtime host
- Required host identity:
  - `hostname = srv1756620`
- Required runtime containers:
  - `deploy-shim-world-sim-1` = running
  - `deploy-shim-sim-tick-1` = exited
- Required bind mounts:
  - `/app -> /srv/genesis`
  - `/app/data -> /srv/genesis/data`
- Canonical in-container working directory:
  - `/app`
- Canonical in-container data root:
  - `/app/data`

### Headless Ubuntu laptop

- SSH alias:
  - `headless`
- Role:
  - Separate Ubuntu laptop / lane-worker / repo host
- Important:
  - Not the canonical VPS2 runtime host for 6W provider gates.
  - If hostname is not `srv1756620`, abort Genesis runtime verification.

## Runtime Verification Rule

Before any Genesis runtime phase, provider phase, daemon phase, tick phase, or dual-agent phase, prove canonical identity first.

Required proof:

```text
hostname = srv1756620
deploy-shim-world-sim-1 = running
deploy-shim-sim-tick-1 = exited
docker inspect proves /app -> /srv/genesis
docker inspect proves /app/data -> /srv/genesis/data
```

If the agent cannot prove this, return only:

```text
PHASE_TOOLING_LOST_CANONICAL_RUNTIME_CONTEXT
PHASE_TOOLING_ACCESS_GAP_RUNTIME_NOT_VERIFIED
```

Do not ask Sean to manually compensate.

## Phase 6W Correct Baseline Map

Do not compare `ACTIVE_STATE.md` to the world-state MD5.

Correct map:

```text
/app/data/east_world_state.json
MD5 = 8b8c61d10a0540f7249beaa553a3a31f

/app/data/agents/east_eve/self_state.json
MD5 = 9da86704f734a5b31011c5f834b6d3c5

/app/data/memories/east_eve_memories.json
MD5 = 16f94246e78edd9d3acd9aa685eb79c7

/app/data/agents/east_adam/self_state.json
MD5 = b1fa70b17563ed584fc411a97f7e37f8

/app/data/memories/east_adam_memories.json
MD5 = 9bd0edf50bc8057d184ea385366fe156

/app/data/proposals/model_calls.jsonl
MD5 = 67b774875fbcef6ea14fb4d2f5f5f95e
lines = 2

/app/data/continuity/ACTIVE_STATE.md
expected: exists and contains Phase 6V closure markers
assigned MD5 baseline: none for 6W-A
```

Semantic checks:

```text
Eve unread = []
Adam unread = []
No daemon/tick/provider process running
```

## Hard Abort Rules

Abort if any of these are true:

```text
hostname != srv1756620
Docker host cannot inspect deploy-shim-world-sim-1
/app mount cannot be proven
/app/data mount cannot be proven
baseline file-to-MD5 map is mixed up
agent is running from WE, srv1345984, headless, or an unknown host
```

Forbidden without explicit phase authorization:

```text
No Eve.
No Adam.
No provider.
No dual-provider.
No daemon.
No tick.
No scheduler.
No Docker start/stop.
No copy/restore/manual injection.
No commit/push.
```