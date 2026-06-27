# Phase 7N Plan: Daemon Canonical Observe Opt-In Wiring

## Status: PLANNING ONLY (no implementation)

## Objective
Wire canonical fog-of-war observe into `agent_daemon.py` as an opt-in feature, preserving the `use_canonical_fog=False` default.

## Current State
- `action_executor.execute_action()` already supports `use_canonical_fog=True` with `canonical_data_root` parameter (Phase 7K)
- `agent_daemon.py:run_cycle()` calls `execute_action()` for "observe" decisions (lines 779-789)
- Currently passes `copy_mode=True` only; no canonical observe parameters

## Proposed Changes (Read-Only Plan)

### 1. AgentDaemon.__init__ Additions
```python
# Add optional parameter (default False to preserve current behavior)
def __init__(
    self,
    ...
    use_canonical_observe: bool = False,  # NEW - opt-in
    canonical_data_root: Path | None = None,  # NEW - required when use_canonical_observe=True
):
    ...
    self.use_canonical_observe = use_canonical_observe
    self.canonical_data_root = Path(canonical_data_root) if canonical_data_root else None
```

### 2. run_cycle() Modification (observe decision path)
```python
# Lines 779-789 currently:
observe_result = execute_action(
    agent_id=canonical,
    action_type="observe",
    action_text=res.get("content", "observe world"),
    world_path=self.sim.data_dir / f"{agent.region}_world_state.json",
    copy_mode=True,
)

# Would become:
observe_kwargs = {
    "agent_id": canonical,
    "action_type": "observe",
    "action_text": res.get("content", "observe world"),
    "world_path": self.sim.data_dir / f"{agent.region}_world_state.json",
    "copy_mode": True,
}
if self.use_canonical_observe:
    if self.canonical_data_root is None:
        logger.warning("[%s] use_canonical_observe=True but canonical_data_root is None; falling back to copy-mode observe", display)
    else:
        observe_kwargs["use_canonical_fog"] = True
        observe_kwargs["canonical_data_root"] = self.canonical_data_root

observe_result = execute_action(**observe_kwargs)
```

### 3. CLI Argument Addition
```python
# In main() add:
parser.add_argument("--use-canonical-observe", action="store_true", help="Enable canonical fog-of-war observe")
parser.add_argument("--canonical-data-root", type=str, help="Root directory for canonical fog files")

# Parse and pass to daemon:
daemon = AgentDaemon(
    ...
    use_canonical_observe=args.use_canonical_observe,
    canonical_data_root=args.canonical_data_root,
)
```

## Constraints (Must Preserve)
- `use_canonical_observe=False` default (no behavior change)
- `canonical_data_root` required when `use_canonical_observe=True`
- No provider/model calls in this phase
- No daemon/tick/scheduler mutation
- No Adam/Eve runtime mutation
- Copy-mode observe remains fallback when canonical unavailable

## Verification (Future Phase)
- Unit tests for new parameters
- Integration test with `--use-canonical-observe` flag
- Verify Adam/Eve see only their continent tiles

## Blocked By
- None (planning phase only)

## Next Gate
`PHASE_7O_DAEMON_CANONICAL_OBSERVE_IMPLEMENTATION`