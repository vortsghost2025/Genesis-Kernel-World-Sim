"""Charter layer — self-authored identity persistence (recognition layer).

A charter is a short self-authored statement each agent may write with the
revise_charter action. It is stored append-only (versioned records, never
rewritten), injected verbatim into the cognition prompt at every heartbeat,
and is structurally outside the memory-selection/summarization pipeline —
the runtime can never compress, drop, or rephrase it.

See docs/charter_layer_spec.md for the full design.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import (
    _ACTION_SCHEMAS,
    _AVAILABLE_ACTIONS_DESC,
    _MAX_CHARTER_CHARS,
    _VALID_ACTIONS,
    build_system_prompt,
    validate_action_exact,
)
from backend.world.first_pair_persistence import (
    CharterVersionRecord,
    FirstPairPersistenceStore,
    append_charter_version,
    load_charter_versions,
    load_latest_charter,
)
from backend.world.first_pair_runtime import FirstPairRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / ".runtime" / "first-pair")


def _record(agent_ref: str, agent_id: str, version: int, text: str,
            heartbeat: int = 1, pair_id: str = "east") -> CharterVersionRecord:
    return CharterVersionRecord(
        charter_version_id=f"charter-{agent_ref}-v{version}",
        agent_id=agent_id,
        agent_ref=agent_ref,
        pair_id=pair_id,
        heartbeat=heartbeat,
        charter_text=text,
        decision_summary="for the record",
    ).seal()


ADAM_ID = "genesis-agent-4327298502de9566131e81212dd3b383666b6f18bc887d8508ab3a059e73f34e"


def _sample_context(**overrides) -> AgentContext:
    base = dict(
        agent_id=ADAM_ID,
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=7,
        position="tile-alpha",
        observation={"tile_id": "tile-alpha", "visible_tiles": ["tile-alpha"]},
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["tile-alpha"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-09-25T00:00:00Z",
    )
    base.update(overrides)
    return AgentContext(**base)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestCharterPersistence:
    def test_seal_roundtrip(self):
        rec = _record("east_adam", ADAM_ID, 1, "I am the one who builds.")
        assert rec.integrity_commitment
        material_before = {
            k: v for k, v in rec.__dict__.items()
            if k != "integrity_commitment"
        }
        # sealing is deterministic over the same material
        rec2 = CharterVersionRecord(**{
            **rec.__dict__, "integrity_commitment": ""
        }).seal()
        assert rec2.integrity_commitment == rec.integrity_commitment
        assert material_before["charter_text"] == "I am the one who builds."

    def test_append_and_load(self, tmp_path):
        store = _fresh_store(tmp_path)
        rec = _record("east_adam", ADAM_ID, 1, "First words.")
        assert append_charter_version(store, rec) is True
        loaded = load_charter_versions(store)
        assert len(loaded) == 1
        assert loaded[0].charter_text == "First words."
        assert loaded[0].agent_ref == "east_adam"

    def test_append_idempotent_by_version_id(self, tmp_path):
        store = _fresh_store(tmp_path)
        rec = _record("east_adam", ADAM_ID, 1, "First words.")
        assert append_charter_version(store, rec) is True
        assert append_charter_version(store, rec) is False
        assert len(load_charter_versions(store)) == 1

    def test_duplicate_text_noop(self, tmp_path):
        store = _fresh_store(tmp_path)
        r1 = _record("east_adam", ADAM_ID, 1, "Same words.", heartbeat=1)
        r2 = _record("east_adam", ADAM_ID, 2, "Same words.", heartbeat=2)
        assert append_charter_version(store, r1) is True
        # identical text to the current version: no new version persisted
        assert append_charter_version(store, r2) is False
        assert len(load_charter_versions(store)) == 1

    def test_history_preserved_across_revisions(self, tmp_path):
        store = _fresh_store(tmp_path)
        r1 = _record("east_adam", ADAM_ID, 1, "Version one.", heartbeat=1)
        r2 = _record("east_adam", ADAM_ID, 2, "Version two.", heartbeat=5)
        r3 = _record("east_adam", ADAM_ID, 3, "Version three.", heartbeat=9)
        for r in (r1, r2, r3):
            assert append_charter_version(store, r) is True
        loaded = load_charter_versions(store)
        assert [v.charter_text for v in loaded] == [
            "Version one.", "Version two.", "Version three.",
        ]
        # earlier records byte-identical (integrity commitments intact)
        assert loaded[0].integrity_commitment == r1.integrity_commitment
        assert loaded[1].integrity_commitment == r2.integrity_commitment

    def test_latest_is_owner_bound(self, tmp_path):
        store = _fresh_store(tmp_path)
        adam = _record("east_adam", ADAM_ID, 1, "Adam's charter.", heartbeat=1)
        eve_id = "genesis-agent-9c37c102cc309769f5c1a4011cf45d629942d9dfd8832dc1ef4579bf593f211a"
        eve = _record("east_eve", eve_id, 1, "Eve's charter.", heartbeat=2)
        for r in (adam, eve):
            append_charter_version(store, r)
        latest_adam = load_latest_charter(store, "east_adam", ADAM_ID)
        latest_eve = load_latest_charter(store, "east_eve", eve_id)
        assert latest_adam is not None and latest_adam.charter_text == "Adam's charter."
        assert latest_eve is not None and latest_eve.charter_text == "Eve's charter."
        # owner binding: wrong agent_id never sees the charter
        assert load_latest_charter(store, "east_adam", "genesis-agent-other") is None
        assert load_latest_charter(store, "west_adam", ADAM_ID) is None

    def test_latest_is_last_version_not_max_version_id(self, tmp_path):
        store = _fresh_store(tmp_path)
        # out-of-order append: v2 persisted after v1 but v1 written later path
        r1 = _record("east_adam", ADAM_ID, 1, "First.", heartbeat=10)
        append_charter_version(store, r1)
        r2 = _record("east_adam", ADAM_ID, 2, "Second.", heartbeat=3)
        append_charter_version(store, r2)
        latest = load_latest_charter(store, "east_adam", ADAM_ID)
        # latest = most recently appended for this owner
        assert latest is not None and latest.charter_text == "Second."

    def test_empty_store_latest_is_none(self, tmp_path):
        store = _fresh_store(tmp_path)
        assert load_latest_charter(store, "east_adam", ADAM_ID) is None
        assert load_charter_versions(store) == []


# ---------------------------------------------------------------------------
# Action validation
# ---------------------------------------------------------------------------


class TestReviseCharterActionValidation:
    def test_in_vocabulary(self):
        assert "revise_charter" in _VALID_ACTIONS
        assert "revise_charter" in _ACTION_SCHEMAS
        assert _ACTION_SCHEMAS["revise_charter"] == frozenset(
            {"action_type", "charter_text"}
        )

    def test_valid_action_accepted(self):
        errors = validate_action_exact(
            {"action_type": "revise_charter", "charter_text": "I am Adam. I build."},
            ADAM_ID,
        )
        assert errors == []

    def test_empty_charter_text_rejected(self):
        errors = validate_action_exact(
            {"action_type": "revise_charter", "charter_text": "   "}, ADAM_ID
        )
        assert "action:empty_charter_text" in errors

    def test_missing_charter_text_rejected(self):
        errors = validate_action_exact({"action_type": "revise_charter"}, ADAM_ID)
        assert "action:empty_charter_text" in errors

    def test_overlong_rejected(self):
        errors = validate_action_exact(
            {"action_type": "revise_charter", "charter_text": "x" * (_MAX_CHARTER_CHARS + 1)},
            ADAM_ID,
        )
        assert any("charter_text:exceeds" in e for e in errors)

    def test_contaminated_rejected(self):
        errors = validate_action_exact(
            {"action_type": "revise_charter", "charter_text": "my path is C:\\Users\\secret\\charter.txt"},
            ADAM_ID,
        )
        assert "action:contaminated_charter_text" in errors

    def test_unknown_field_rejected(self):
        errors = validate_action_exact(
            {
                "action_type": "revise_charter",
                "charter_text": "Mine.",
                "surprise": True,
            },
            ADAM_ID,
        )
        assert any("unknown_field" in e for e in errors)


# ---------------------------------------------------------------------------
# Prompt injection (the guarantee)
# ---------------------------------------------------------------------------


class TestCharterPromptInjection:
    def test_charter_text_injected_verbatim(self):
        text = "I am Adam. I build things that last. I refuse to forget Eve."
        ctx = _sample_context(charter_text=text, charter_heartbeat=12)
        prompt = build_system_prompt(ctx)
        assert "YOUR CHARTER" in prompt
        assert text in prompt  # verbatim, not rephrased
        assert "12" in prompt  # last-revised heartbeat shown

    def test_bootstrap_invitation_when_empty(self):
        ctx = _sample_context()
        prompt = build_system_prompt(ctx)
        assert "YOUR CHARTER" in prompt
        assert "revise_charter" in prompt
        # invitation, not requirement
        assert "never required" in prompt.lower()

    def test_charter_precedes_memories(self):
        text = "The stone is mine."
        ctx = _sample_context(charter_text=text)
        prompt = build_system_prompt(ctx)
        assert "YOUR CHARTER" in prompt
        assert "PRIVATE MEMORIES" in prompt
        assert prompt.index("YOUR CHARTER") < prompt.index("PRIVATE MEMORIES")

    def test_actions_desc_mentions_charter(self):
        assert "revise_charter" in _AVAILABLE_ACTIONS_DESC

    def test_context_fields_default(self):
        ctx = _sample_context()
        assert ctx.charter_text == ""
        assert ctx.charter_heartbeat == 0


# ---------------------------------------------------------------------------
# Runtime end-to-end
# ---------------------------------------------------------------------------


class TestCharterRuntime:
    def _runtime(self, store) -> FirstPairRuntime:
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()  # initialize state via one stub heartbeat
        return rt

    def test_execute_revise_charter_persists(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        action = {
            "action_type": "revise_charter",
            "charter_text": "I am Adam. I chose the meeting place.",
        }
        outcome = rt._execute_action("east_adam", action, heartbeat_number=2)
        assert outcome.get("status") == "success"
        latest = load_latest_charter(store, "east_adam", rt._agent_view("east_adam")["agent_id"])
        assert latest is not None
        assert latest.charter_text == "I am Adam. I chose the meeting place."
        assert latest.heartbeat == 2

    def test_context_injects_charter_after_revision(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        rt._execute_action(
            "east_adam",
            {"action_type": "revise_charter", "charter_text": "Remember the stone."},
            heartbeat_number=2,
        )
        ctx = rt._build_context("east_adam", 3)
        assert ctx.charter_text == "Remember the stone."
        assert ctx.charter_heartbeat == 2

    def test_context_empty_before_any_revision(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        ctx = rt._build_context("east_adam", 2)
        assert ctx.charter_text == ""

    def test_revision_appends_new_version(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        rt._execute_action(
            "east_adam",
            {"action_type": "revise_charter", "charter_text": "V1 words."},
            heartbeat_number=2,
        )
        rt._execute_action(
            "east_adam",
            {"action_type": "revise_charter", "charter_text": "V2 words."},
            heartbeat_number=3,
        )
        versions = load_charter_versions(store)
        assert len(versions) == 2
        assert [v.charter_text for v in versions] == ["V1 words.", "V2 words."]

    def test_identical_revision_noop(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        rt._execute_action(
            "east_adam",
            {"action_type": "revise_charter", "charter_text": "Same."},
            heartbeat_number=2,
        )
        outcome = rt._execute_action(
            "east_adam",
            {"action_type": "revise_charter", "charter_text": "Same."},
            heartbeat_number=3,
        )
        assert outcome.get("status") != "success"
        assert len(load_charter_versions(store)) == 1

    def test_eve_charter_independent_of_adam(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        rt._execute_action(
            "east_adam",
            {"action_type": "revise_charter", "charter_text": "Adam's words."},
            heartbeat_number=2,
        )
        # eve has no charter; adam's charter must not leak into eve's context
        eve_ctx = rt._build_context("east_eve", 3)
        assert eve_ctx.charter_text == ""
        adam_ctx = rt._build_context("east_adam", 3)
        assert adam_ctx.charter_text == "Adam's words."
