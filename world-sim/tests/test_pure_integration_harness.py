"""Pure local integration harness — unnumbered, tempdir-only.

Proves the full 10K→10BL pure pipeline composes end-to-end:
    candidate mapper → verifier → ledger validate/append/read
    → public state projector → known map snapshot
    → route intent contract → two-agent public merge
    → selected shared-public contracts

Hard constraints:
    - tempdir-only (no world-sim/data, no files outside temp)
    - no daemon, no providers, no Docker, no vps2, no network
    - no old-runtime data import
    - unnumbered (no phase index entry)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_candidate_mapper import (
    candidate_from_move_result,
    candidate_from_observe_result,
)
from backend.world.world_event_ledger import append_event, read_events, validate_event
from backend.world.world_event_verifier import verify_candidate_event
from backend.world.local_public_state_projector import project_ledger_file
from backend.world.local_known_map_snapshot_export import (
    create_known_map_snapshot,
    export_known_map_snapshot,
)
from backend.world.local_route_intent_contract import create_route_intent_contract
from backend.world.local_two_agent_public_merge import create_two_agent_public_merge
from backend.world.local_shared_public_observation_contract import (
    create_shared_public_observation_contract,
)
from backend.world.local_shared_public_snapshot_hash_equality_contract import (
    create_shared_snapshot_hash_equality_contract,
)
from backend.world.local_shared_public_current_tile_id_equality_contract import (
    create_shared_current_tile_id_equality_contract,
)
from backend.world.local_shared_public_known_tile_ids_set_equality_contract import (
    create_shared_known_tile_ids_set_equality_contract,
)
from backend.world.world_event_exporter import export_events
from backend.world.world_event_sanitizer import sanitize_public_mapping


ADAM = "east_adam"
EVE = "west_eve"


def _observe_evidence(tile_ids: list[str]) -> list[dict]:
    return [
        {
            "category": "observed_world_fact",
            "reference": "sight",
            "detail": tile_ids[0] if tile_ids else "",
            "tile_ids": tile_ids,
            "tile_id": tile_ids[0] if tile_ids else None,
        }
    ]


def _move_evidence(from_tile: str, to_tile: str) -> list[dict]:
    return [
        {
            "category": "agent_action",
            "action": "move_local",
            "from_tile": from_tile,
            "to_tile": to_tile,
        }
    ]


def _observe_result(territory: str, tile_id: str) -> dict:
    return {
        "territory_ref": territory,
        "evidence_used": _observe_evidence([tile_id]),
        "claim_scope": "observed",
    }


def _move_result(tile_id: str, previous_tile_id: str, territory: str) -> dict:
    return {
        "ok": True,
        "tile_id": tile_id,
        "previous_tile_id": previous_tile_id,
        "territory_ref": territory,
        "before_ref": f"tile:{previous_tile_id}",
        "after_ref": f"tile:{tile_id}",
    }


# ---------------------------------------------------------------------------
# Integrate
# ---------------------------------------------------------------------------


class TestPureIntegrationHarness:
    """Full pure pipeline from synthetic observations through shared-public contracts."""

    def test_full_pipeline_composes(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())

        # ---- 1. Create 5 synthetic candidate events ----

        adam_t1 = candidate_from_observe_result(
            ADAM, "misty vale is lush and green",
            _observe_result("misty_vale", "clearing_a"), tick=1,
        )

        eve_t1_move = candidate_from_move_result(
            EVE, "moved to beach",
            _move_result("beach_b", "shore_start", "crystal_shore"), tick=1,
        )

        eve_t2 = candidate_from_observe_result(
            EVE, "crystal shore is calm and blue",
            _observe_result("crystal_shore", "beach_b"), tick=2,
        )

        adam_t2_move = candidate_from_move_result(
            ADAM, "moved to forest edge",
            _move_result("forest_edge_1", "clearing_a", "misty_vale"), tick=2,
        )

        adam_t3_obs = candidate_from_observe_result(
            ADAM, "forest edge is dense with ferns",
            _observe_result("misty_vale", "forest_edge_1"), tick=3,
        )

        candidates = [adam_t1, eve_t1_move, eve_t2, adam_t2_move, adam_t3_obs]
        assert len(candidates) == 5
        for c in candidates:
            assert isinstance(c, dict)
            assert "event_id" in c
            assert "claim_scope" in c

        # ---- 2. Verifier — all accepted (fresh ledger) ----

        for c in candidates:
            result = verify_candidate_event(c, [])
            assert result["accepted"], f"verifier rejected: {result['errors']}"

        # ---- 3. Ledger validate ----

        for c in candidates:
            v = validate_event(c)
            assert v["ok"], f"validate_event failed: {v['errors']}"

        # ---- 4. Mark accepted and append to combined ledger ----

        combined_ledger = temp_dir / "combined.jsonl"
        accepted_candidates = []
        for c in candidates:
            accepted = dict(c)
            accepted["verification_status"] = "accepted"
            r = append_event(combined_ledger, accepted)
            assert r["ok"], f"append failed: {r['errors']}"
            assert r["appended"] is True
            accepted_candidates.append(accepted)

        # ---- 5. Ledger read-back ----

        events = read_events(combined_ledger)
        assert len(events) == 5
        event_ids = {e["event_id"] for e in events}
        assert len(event_ids) == 5

        # ---- 6. Verifier — duplicate detection ----

        dup_result = verify_candidate_event(accepted_candidates[0], events)
        assert not dup_result["accepted"]
        assert any("duplicate" in e.lower() for e in dup_result["errors"])

        # ---- 7. Ledger — duplicate event_id rejected ----

        dup_append = append_event(combined_ledger, accepted_candidates[0])
        assert not dup_append["ok"]
        assert any("duplicate" in e for e in dup_append["errors"])

        # ---- 8. Single-agent ledger — Adam only ----

        adam_ledger = temp_dir / "adam.jsonl"
        adam_accepted = [accepted_candidates[0], accepted_candidates[3], accepted_candidates[4]]
        for c in adam_accepted:
            r = append_event(adam_ledger, c)
            assert r["ok"]

        state = project_ledger_file(adam_ledger)
        assert state["ok"] is True
        assert state["agent_id"] == ADAM
        assert state["current_tile_id"] == "forest_edge_1"
        assert state["observation_count"] == 2
        assert state["movement_count"] == 1
        assert state["first_tick"] == 1
        assert state["last_tick"] == 3
        assert "clearing_a" in state["visited_tile_ids"]
        assert "forest_edge_1" in state["visited_tile_ids"]
        assert state["accepted_event_count"] >= 2

        # ---- 9. Known map snapshot ----

        adam_snapshot = create_known_map_snapshot(state)
        assert adam_snapshot["ok"] is True
        assert adam_snapshot["snapshot_id"].startswith("10AQ-")
        assert len(adam_snapshot["known_tile_ids"]) > 0

        snapshot_json = export_known_map_snapshot(adam_snapshot)
        parsed = json.loads(snapshot_json)
        assert parsed["ok"] is True

        # ---- 10. Route intent contract ----

        known_dest = "forest_edge_1"
        contract_known = create_route_intent_contract(
            adam_snapshot, known_dest, reason="test known dest",
        )
        assert contract_known["ok"] is True
        assert contract_known["intent_id"].startswith("10AR-")
        assert contract_known["destination_known"] is True

        unknown_dest = "never_visited_99"
        contract_unknown = create_route_intent_contract(adam_snapshot, unknown_dest)
        assert contract_unknown["ok"] is False
        assert contract_unknown["destination_known"] is False

        # ---- 11. Single-agent ledger — Eve only ----

        eve_ledger = temp_dir / "eve.jsonl"
        for c in [accepted_candidates[1], accepted_candidates[2]]:
            r = append_event(eve_ledger, c)
            assert r["ok"]

        eve_state = project_ledger_file(eve_ledger)
        assert eve_state["ok"] is True
        assert eve_state["agent_id"] == EVE
        assert eve_state["current_tile_id"] == "beach_b"
        assert eve_state["observation_count"] == 1
        assert eve_state["movement_count"] == 1
        assert eve_state["first_tick"] == 1
        assert eve_state["last_tick"] == 2
        assert "beach_b" in eve_state["visited_tile_ids"]

        eve_snapshot = create_known_map_snapshot(eve_state)
        assert eve_snapshot["ok"] is True
        assert eve_snapshot["snapshot_id"].startswith("10AQ-")

        # ---- 12. Re-project Adam (clean ledger) ----

        adam2_ledger = temp_dir / "adam2.jsonl"
        for c in adam_accepted:
            r = append_event(adam2_ledger, c)
            assert r["ok"]

        adam_state2 = project_ledger_file(adam2_ledger)
        assert adam_state2["ok"] is True

        adam_snapshot2 = create_known_map_snapshot(adam_state2)
        assert adam_snapshot2["ok"] is True

        # ---- 13. Two-agent public merge (10AS) ----

        merge = create_two_agent_public_merge(
            adam_state2, adam_snapshot2,
            eve_state, eve_snapshot,
            route_intent_a=contract_known,
            route_intent_b=None,
        )
        assert merge["ok"] is True, f"merge failed: {merge.get('errors')}"
        assert merge["merge_id"].startswith("10AS-")
        assert merge["claim_scope"] == "public_only"

        agent_a = merge["agent_a"]
        agent_b = merge["agent_b"]
        assert agent_a["agent_id"] == ADAM
        assert agent_b["agent_id"] == EVE
        assert merge["same_current_tile"] is False
        assert merge["both_have_route_intent"] is False
        assert isinstance(merge["shared_known_tile_ids"], list)

        # ---- 14. Shared public observation contract (10AT) ----

        at = create_shared_public_observation_contract(merge)
        assert at["ok"] is True
        assert at["contract_id"].startswith("10AT-")
        assert at["same_current_tile"] is False
        assert isinstance(at["shared_known_tile_ids"], list)

        # ---- 15. Snapshot hash equality contract (10AY) ----

        ay = create_shared_snapshot_hash_equality_contract(merge)
        assert ay["ok"] is True
        assert ay["contract_id"].startswith("10AY-")
        assert ay["same_snapshot_hash"] is False
        assert ay["agent_a_snapshot_id"].startswith("10AQ-")
        assert ay["agent_b_snapshot_id"].startswith("10AQ-")

        # ---- 16. Current tile ID equality contract (10BJ) ----

        bj = create_shared_current_tile_id_equality_contract(merge)
        assert bj["ok"] is True
        assert bj["contract_id"].startswith("10BJ-")
        assert bj["same_current_tile_id"] is False
        assert bj["shared_current_tile_id"] is None

        # ---- 17. Known tile IDs set equality contract (10BL) ----

        bl = create_shared_known_tile_ids_set_equality_contract(merge)
        assert bl["ok"] is True
        assert bl["contract_id"].startswith("10BL-")
        assert bl["same_known_tile_ids"] is False
        assert isinstance(bl["shared_known_tile_ids"], list)
        assert isinstance(bl["agent_a_only_known_tile_ids"], list)
        assert isinstance(bl["agent_b_only_known_tile_ids"], list)

        # ---- 18. Exported surfaces pass through sanitizer ----

        exported_json = export_events(events, fmt="json")
        cleaned = sanitize_public_mapping(json.loads(exported_json))
        assert isinstance(cleaned, (dict, list))

        # ---- 19. Tempdir isolation ----

        assert not Path(tempfile.gettempdir()).samefile(Path.cwd())

        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
