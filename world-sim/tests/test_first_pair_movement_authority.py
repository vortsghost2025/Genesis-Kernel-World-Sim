"""Focused movement-authority predicate tests.

One authoritative movement predicate must gate both model-facing context
advertisement and movement execution. Every unauthorized combination must
fail closed: no capability/move advertisement, no prompt "active grant"
claim, and no successful move.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest

from backend.world.first_pair_cognition_model import build_system_prompt
from backend.world.first_pair_persistence import (
    CapabilityGrantRecord,
    FirstPairPersistenceStore,
    create_default_runtime_policy,
    grant_capability,
)
from backend.world.first_pair_runtime import FirstPairRuntime


@pytest.fixture()
def tmp_path():
    """Sandbox-safe tmp_path: pytest's built-in mkdtemp dirs are ACL-locked
    in this environment; plain os.makedirs/os.mkdir under the workspace work."""
    base = Path(__file__).resolve().parent.parent / ".tmp-movauth"
    base.mkdir(exist_ok=True)
    d = base / f"case-{uuid.uuid4().hex[:12]}"
    os.mkdir(d)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _fresh_store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / ".runtime" / "first-pair")


def _grant(**overrides) -> CapabilityGrantRecord:
    fields = {
        "grant_id": "grant-movement-001",
        "capability_id": "movement",
        "scope": "first-pair-shared-habitat",
        "reason": "Operator-approved movement",
        "status": "granted",
    }
    fields.update(overrides)
    return CapabilityGrantRecord(**fields)


_NEGATIVE_CASES = {
    # 1. no grant (policy present)
    "no_grant": {"grant": None, "policy": "default"},
    # 2. grant present but status not granted
    "grant_status_revoked": {
        "grant": _grant(status="revoked"),
        "policy": "default",
    },
    # 3. wrong capability_id (unrelated granted capability; grant_id still
    #    matches policy ref so only the capability binding is isolated)
    "wrong_capability_id": {
        "grant": _grant(capability_id="modify_habitat_movement_allowed"),
        "policy": "default",
    },
    # 4. missing runtime policy
    "missing_policy": {"grant": _grant(), "policy": None},
    # 5. policy status not active
    "policy_inactive": {
        "grant": _grant(),
        "policy": "default",
        "policy_mutations": {"status": "inactive"},
    },
    # 6. topology movement_allowed is False
    "movement_allowed_false": {
        "grant": _grant(),
        "policy": "default",
        "policy_mutations": {"topology_override": {"movement_allowed": False}},
    },
    # 7. grant id does not match policy movement_grant_ref
    "mismatched_grant_ref": {
        "grant": _grant(grant_id="grant-unrelated-001"),
        "policy": "default",
    },
}


def _runtime(tmp_path: Path, spec: dict) -> FirstPairRuntime:
    store = _fresh_store(tmp_path)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt.run()
    grant = spec.get("grant")
    if spec.get("policy") == "default":
        policy = create_default_runtime_policy()
        for k, v in spec.get("policy_mutations", {}).items():
            if k == "topology_override":
                for tk, tv in v.items():
                    policy.topology[tk] = tv
            else:
                setattr(policy, k, v)
        policy.seal()
    else:
        policy = None
    rt._capability_grant = grant
    rt._runtime_policy = policy
    return rt


@pytest.mark.parametrize("name", sorted(_NEGATIVE_CASES.keys()))
def test_unauthorized_context_and_prompt_fail_closed(tmp_path: Path, name: str) -> None:
    rt = _runtime(tmp_path, _NEGATIVE_CASES[name])
    ctx = rt._build_context("east_adam", 2)

    assert ctx.available_moves == [], (
        f"{name}: advertised moves without movement authority"
    )
    assert ctx.current_runtime_capabilities == [], (
        f"{name}: advertised capability without movement authority"
    )
    assert ctx.habitat_movement_allowed is False, (
        f"{name}: habitat flag should reflect the historical no-grant boundary"
    )

    prompt = build_system_prompt(ctx)
    assert "A bounded runtime movement grant is active" not in prompt, (
        f"{name}: prompt falsely claims an active movement grant"
    )


@pytest.mark.parametrize("name", sorted(_NEGATIVE_CASES.keys()))
def test_unauthorized_move_is_blocked(tmp_path: Path, name: str) -> None:
    rt = _runtime(tmp_path, _NEGATIVE_CASES[name])
    outcome = rt._execute_move(
        "east_adam", {"action_type": "move", "target_tile": "public-shared-center"}
    )
    assert outcome["status"] == "blocked", (
        f"{name}: move succeeded without movement authority: {outcome}"
    )
    assert rt._world_state.tile_occupancy.get("east_adam") == "public-start-adam", (
        f"{name}: tile occupancy mutated without movement authority"
    )


def test_authorized_movement_positive(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt.run()
    grant = grant_capability(
        store, "movement", "first-pair-shared-habitat", "Operator-approved movement"
    )
    policy = create_default_runtime_policy()
    rt._capability_grant = grant
    rt._runtime_policy = policy

    ctx = rt._build_context("east_adam", 2)
    assert ctx.current_runtime_capabilities == ["movement"]
    assert ctx.available_moves == ["public-shared-center"]

    prompt = build_system_prompt(ctx)
    assert "A bounded runtime movement grant is active" in prompt

    outcome = rt._execute_move(
        "east_adam", {"action_type": "move", "target_tile": "public-shared-center"}
    )
    assert outcome["status"] == "success", f"Got: {outcome}"
    assert rt._world_state.tile_occupancy["east_adam"] == "public-shared-center"
