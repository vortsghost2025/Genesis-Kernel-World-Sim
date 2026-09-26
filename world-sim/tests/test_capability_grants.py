"""Extra capability grants — operator answers to agent capability requests.

The legacy capability system stores a SINGLE grant per store
(capability_grant.json, currently the movement grant). Overwriting it to
acknowledge a new capability would destroy movement. This layer adds an
append-only additional-grants store (capability_grants.json) so the operator
can answer request_capability requests without touching the legacy record.

See the 2026-09-25 operator decision: the West pair requested 'gather' 135
times, received silence, and gathered anyway (the runtime never required
permission — the agents only lacked acknowledgment).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.world.first_pair_persistence import (
    CapabilityGrantRecord,
    FirstPairPersistenceStore,
    append_capability_grant,
    load_capability_grant,
    load_extra_capability_grants,
)
from backend.world.first_pair_runtime import FirstPairRuntime


def _fresh_store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / ".runtime" / "first-pair")


def _grant(capability_id: str, grant_id: str) -> CapabilityGrantRecord:
    return CapabilityGrantRecord(
        grant_id=grant_id,
        capability_id=capability_id,
        scope="resources visible on the agent's current tile",
        reason="operator answer to repeated capability requests",
        operator_provenance="sean-operator-2026-09-25",
    ).seal()


class TestExtraCapabilityGrants:
    def test_append_and_load(self, tmp_path):
        store = _fresh_store(tmp_path)
        g = _grant("gather", "grant-gather-west-001")
        assert append_capability_grant(store, g) is True
        loaded = load_extra_capability_grants(store)
        assert len(loaded) == 1
        assert loaded[0].capability_id == "gather"
        assert loaded[0].status == "granted"
        assert loaded[0].integrity_commitment == g.integrity_commitment

    def test_idempotent_by_grant_id(self, tmp_path):
        store = _fresh_store(tmp_path)
        g = _grant("gather", "grant-gather-west-001")
        assert append_capability_grant(store, g) is True
        assert append_capability_grant(store, g) is False
        assert len(load_extra_capability_grants(store)) == 1

    def test_multiple_capabilities_coexist(self, tmp_path):
        store = _fresh_store(tmp_path)
        assert append_capability_grant(store, _grant("gather", "grant-gather-west-001"))
        assert append_capability_grant(store, _grant("craft", "grant-craft-west-001"))
        caps = [g.capability_id for g in load_extra_capability_grants(store)]
        assert caps == ["gather", "craft"]

    def test_legacy_grant_file_untouched(self, tmp_path):
        """The movement grant in capability_grant.json is never modified."""
        store = _fresh_store(tmp_path)
        # seed a legacy movement grant exactly like grant_capability does
        legacy = CapabilityGrantRecord(
            grant_id="grant-movement-west-001",
            capability_id="movement",
            scope="topology",
            reason="activation",
            operator_provenance="seed",
        ).seal()
        store._atomic_write(store._path("capability_grant.json"), legacy.to_envelope())
        before = (store._path("capability_grant.json")).read_bytes()

        append_capability_grant(store, _grant("gather", "grant-gather-west-001"))

        after = (store._path("capability_grant.json")).read_bytes()
        assert after == before
        loaded_legacy = load_capability_grant(store)
        assert loaded_legacy is not None
        assert loaded_legacy.capability_id == "movement"
        assert loaded_legacy.integrity_commitment == legacy.integrity_commitment

    def test_empty_store_loads_empty(self, tmp_path):
        store = _fresh_store(tmp_path)
        assert load_extra_capability_grants(store) == []

    def test_revoked_grants_not_active(self, tmp_path):
        store = _fresh_store(tmp_path)
        g = _grant("gather", "grant-gather-west-001")
        g.status = "revoked"
        append_capability_grant(store, g)
        active = [x for x in load_extra_capability_grants(store) if x.status == "granted"]
        assert active == []


class TestRuntimeContextIncludesExtraGrants:
    def _runtime(self, store) -> FirstPairRuntime:
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        return rt

    def test_caps_include_extra_grants(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        assert append_capability_grant(store, _grant("gather", "grant-gather-west-001"))
        ctx = rt._build_context("east_adam", 2)
        assert "gather" in ctx.current_runtime_capabilities

    def test_caps_unchanged_without_extra_grants(self, tmp_path):
        """Regression: no extra grants file -> context caps are exactly the
        legacy behavior (empty in a fresh store with no movement grant)."""
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        ctx = rt._build_context("east_adam", 2)
        assert ctx.current_runtime_capabilities == []
