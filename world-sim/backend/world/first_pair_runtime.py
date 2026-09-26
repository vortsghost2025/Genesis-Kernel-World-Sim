"""Phase 10FM — First Pair Runtime Orchestrator.

Coordinates bounded heartbeat cycles for Adam and Eve. Mutations flow through
`FirstPairPersistenceStore`; the store and all its children are injected from
the outside — no module-global paths.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.world.first_pair_cognition_interface import (
    AgentContext,
    CognitionBackend,
    CognitiveCycle,
)
from backend.world.first_pair_cognition_model import (
    ModelCognitionBackend,
)
from backend.world.first_pair_cognition_stub import (
    AlternatingStubBackend,
    DeterministicStubBackend,
)
from backend.world.first_pair_persistence import (
    CapabilityGrantRecord,
    CharterVersionRecord,
    FirstPairPersistenceStore,
    GoalRecord,
    HeartbeatRecord,
    IdentityRecord,
    PublicObjectRecord,
    QuestionRecord,
    RuntimePolicyRecord,
    WorldStateRecord,
    append_charter_version,
    append_agent_question_proposal,
    append_heartbeat,
    append_memory_selection_manifest,
    append_summary,
    create_default_runtime_policy,
    derive_relationship_event_ids,
    derive_summaries_for_omitted,
    get_adjacent_tiles,
    get_persistence_root,
    initialize_first_pair_state,
    list_answered_questions_for_agent,
    list_unanswered_questions,
    load_capability_grant,
    load_charter_versions,
    load_extra_capability_grants,
    load_goals,
    load_heartbeat_history,
    load_inventory,
    add_to_inventory,
    load_latest_charter,
    load_memory,
    load_memory_selection_manifests,
    load_agent_question_proposals,
    load_operator_messages,
    load_physics_seen,
    load_questions,
    load_relationship_events,
    load_runtime_policy,
    load_summaries,
    maybe_record_relationship_event,
    record_physics_seen,
    save_goals,
    save_memory,
    save_runtime_policy,
    save_world_state,
    select_human_context,
    select_private_memories,
    validate_persistence_integrity,
)
from backend.world.question_proposal import QuestionProposal
from backend.world.world_event_sanitizer import sanitize_public_text
from backend.world.world_pressure import (
    BUILD_REJECT_FAMISHED,
    FOOD_PER_HEARTBEAT,
    PHYSICS_VERSION,
    carrying_view,
    consume_choice,
    gather_allowance,
    provisions_view,
    split_ledgers,
)
from backend.world.first_pair_fog_adapter import (
    FogAdapterError,
    cognition_safe_observation,
    derive_topology,
    fog_gate_active,
    load_known_map,
    load_true_map,
    merge_observation,
    persist_known_map,
)
from backend.world.mystery_reveal import (
    accrue_mystery_evidence,
    apply_reveal,
    project_discoveries,
    project_unsettled_reports,
)

_DEFAULT_HEARTBEAT_LIMIT = 10
_SAFE_OBJECT_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)
_ALLOWED_MUTABLE_FIELDS = frozenset({
    "public_description", "object_type", "tile_id",
})


def _is_safe_object_id(value: str) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        return False
    return all(c in _SAFE_OBJECT_ID_CHARS for c in value)


def _reflection_is_echo(memory_list: list[dict], reflection: str) -> bool:
    """True when this reflection says nothing the last reflection didn't.

    Numbers normalized, so a re-noted status line ("35+ consecutive build
    rejections... food 13/20" -> "food 14/20") is recognized as the same
    thought. Without this an agent fills its own memory with one belief
    until that belief crowds out everything else (HB701-743: 53 of 1538
    memories were the same refusal status line, three near-identical
    entries in three consecutive heartbeats).
    """
    def _norm(text: str) -> str:
        return re.sub(r"\d+", "#", (text or "").strip().lower())

    target = _norm(reflection)
    if not target:
        return False
    for entry in reversed(memory_list):
        if entry.get("type") == "reflection":
            return _norm(entry.get("content", "")) == target
    return False


class FirstPairRuntime:
    """Bounded, reproducible First Pair runtime.

    State is bound to a `FirstPairPersistenceStore` supplied at construction
    time.  Two separate memory lists (`{pair_id}_adam`, `{pair_id}_eve`) live
    inside a single shared envelope and are written atomically each tick, so
    neither agent's entries are overwritten by the other.

    Supports multiple pairs via `pair_id` (default "east"). The West pair
    uses pair_id="west" with its own store, identity, and agent refs.
    """

    def __init__(
        self,
        persistence_root: Path | None = None,
        heartbeat_limit: int = _DEFAULT_HEARTBEAT_LIMIT,
        backend: str = "stub",
        store: FirstPairPersistenceStore | None = None,
        pair_id: str = "east",
    ) -> None:
        if store is None:
            if pair_id == "east":
                store = FirstPairPersistenceStore(persistence_root)
            else:
                store = FirstPairPersistenceStore(persistence_root)
        self._store = store
        self._heartbeat_limit = heartbeat_limit
        self._backend = backend
        self._pair_id = pair_id
        self._adam_ref = f"{pair_id}_adam"
        self._eve_ref = f"{pair_id}_eve"

        self._identity_record: IdentityRecord | None = None
        self._habitat: dict | None = None
        self._world_state: WorldStateRecord | None = None
        self._goals: list[GoalRecord] = []
        self._questions: list[QuestionRecord] = []
        # Noncanonical, authority-free question proposals. Never persisted to
        # questions.json; they require a separate signed operator authorization
        # before becoming canonical.
        self._question_proposals: list[QuestionProposal] = []

        self._adam_memory: list[dict] = []
        self._eve_memory: list[dict] = []
        self._runtime_policy: RuntimePolicyRecord | None = None
        self._capability_grant: CapabilityGrantRecord | None = None

        # World pressure (docs/world_pressure_spec.md): per-agent, per-tick
        # physics state. Refreshed every heartbeat by _pressure_step before
        # context is built; gates gather caps and the famished build block.
        self._pressure_tick: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------------

    def _agent_view(self, agent_ref: str) -> dict:
        assert self._identity_record is not None
        candidate = self._identity_record.birth_candidate
        if agent_ref == self._adam_ref:
            raw = candidate["adam_identity"]
            return {
                "agent_id": self._identity_record.adam_agent_id,
                "canonical_name": raw["canonical_name"],
                "canonical_agent_ref": agent_ref,
                "other_agent_id": self._identity_record.eve_agent_id,
                "other_agent_name": candidate["eve_identity"]["canonical_name"],
                "other_agent_ref": self._eve_ref,
            }
        raw = candidate["eve_identity"]
        return {
            "agent_id": self._identity_record.eve_agent_id,
            "canonical_name": raw["canonical_name"],
            "canonical_agent_ref": agent_ref,
            "other_agent_id": self._identity_record.adam_agent_id,
            "other_agent_name": candidate["adam_identity"]["canonical_name"],
            "other_agent_ref": self._adam_ref,
        }

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _load_or_initialize(self) -> bool:
        identity, world_state = initialize_first_pair_state(self._store)

        self._identity_record = identity
        self._world_state = world_state
        self._habitat = identity.habitat_boundary["habitat"]

        memory = load_memory(self._store)
        self._adam_memory = list(memory.get(self._adam_ref, []))
        self._eve_memory = list(memory.get(self._eve_ref, []))

        self._goals = load_goals(self._store)
        self._questions = load_questions(self._store)

        self._runtime_policy = load_runtime_policy(self._store)
        self._capability_grant = load_capability_grant(self._store)

        is_fresh = (
            world_state.tick == 0
            and not self._adam_memory
            and not self._eve_memory
            and not self._goals
        )
        return is_fresh

    # ------------------------------------------------------------------
    # Cognition backends
    # ------------------------------------------------------------------

    def _get_cognition_backend(self, agent_ref: str) -> CognitionBackend:
        if self._backend == "model":
            return ModelCognitionBackend(agent_ref)
        if self._backend == "deterministic_stub":
            return DeterministicStubBackend(agent_ref)
        return AlternatingStubBackend(agent_ref)

    # ------------------------------------------------------------------
    # Movement authority
    # ------------------------------------------------------------------

    def _movement_grant_active(self) -> bool:
        """Single authoritative predicate for whether the currently loaded
        grant+policy authorize MOVEMENT.

        Fail-closed: authorized only when the grant is a granted 'movement'
        capability bound to the policy's movement_grant_ref, the policy is
        active, and the policy topology itself allows movement.
        """
        grant = self._capability_grant
        policy = self._runtime_policy
        if grant is None or policy is None:
            return False
        return (
            grant.status == "granted"
            and grant.capability_id == "movement"
            and policy.status == "active"
            and policy.topology.get("movement_allowed") is True
            and grant.grant_id == policy.movement_grant_ref
        )

    # ------------------------------------------------------------------
    # Fog integration (10JB-2): inert gate helpers
    # ------------------------------------------------------------------

    def _fog_active(self) -> bool:
        """True when per-agent known-map files exist (the fog gate)."""
        if self._store is None:
            return False
        return fog_gate_active(self._store.root, self._pair_id)

    def _get_data_root(self) -> Path:
        return Path(__file__).resolve().parents[2] / "data"

    def _mystery_step(
        self,
        known_map: dict[str, Any],
        position_tile: str,
        agent_ref: str,
        tick: int,
        true_map: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Accrue mystery evidence and apply reveals for the agent's tile.

        Spec: docs/mystery_runtime_integration_spec.md. Occupancy-only:
        only mysteries whose tile_id equals the agent's current position
        accrue — one unit per tick, per-agent (Adam's evidence gives Eve
        nothing). The true map is read-only; state lives in
        known_map['myths'] and, on reveal, known_map['known_landmarks'].
        Persist happens once, only when something changed. Fail-closed: any
        error returns the input map unchanged (no partial state handed to
        the caller, no crash; the tick is retried by the next heartbeat).
        """
        try:
            tm = true_map if true_map is not None else load_true_map(self._get_data_root())
            km = known_map
            changed = False
            for mystery in tm.get("mysteries", []):
                if not isinstance(mystery, dict) or not mystery.get("mystery_id"):
                    continue
                if mystery.get("tile_id") != position_tile:
                    continue
                km, accrued = accrue_mystery_evidence(
                    km, mystery, {"tile_id": position_tile}, tick
                )
                km, revealed = apply_reveal(km, mystery, tick)
                changed = changed or accrued or revealed is not None
            if changed:
                persist_known_map(self._store.root, agent_ref, km)
            return km
        except Exception:
            return known_map

    def _get_fog_observation(
        self, agent_ref: str, position: str, objects_here: list,
        heartbeat_number: int | None = None,
    ) -> dict[str, Any]:
        """Build a cognition-safe fog observation. Raises on fog failure.

        Mystery accrual + reveal happen here — before the observation is
        built from the just-updated known map — so hints earned this tick
        are visible to the agent in this same heartbeat's cognition
        (spec §2.1 item 7). The additive observation keys
        'unsettled_reports' and 'discoveries' are present only when the
        agent has earned them (absent otherwise).
        """
        true_map = load_true_map(self._get_data_root())
        known_map = load_known_map(self._store.root, agent_ref)
        if heartbeat_number is not None:
            known_map = self._mystery_step(
                known_map, position, agent_ref, heartbeat_number, true_map=true_map
            )
        obs = cognition_safe_observation(
            true_map, position, known_map, None, objects_here, agent_ref
        )
        reports = project_unsettled_reports(known_map)
        if reports:
            obs["unsettled_reports"] = reports
        discoveries = project_discoveries(known_map)
        if discoveries:
            obs["discoveries"] = discoveries
        return obs

    def _get_effective_adjacency(self, current_pos: str) -> list[str]:
        """Adjacent tiles from fog-derived topology or legacy policy."""
        if self._fog_active():
            true_map = load_true_map(self._get_data_root())
            known_maps = [
                load_known_map(self._store.root, ref)
                for ref in (self._adam_ref, self._eve_ref)
            ]
            topology = derive_topology(true_map, known_maps)
            for tile in topology["tiles"]:
                if tile["tile_id"] == current_pos:
                    return tile["adjacent"]
            return []
        return get_adjacent_tiles(self._runtime_policy, current_pos)

    def _get_effective_allowed_tiles(self) -> list[str]:
        """Allowed tile IDs from fog-derived topology or legacy policy."""
        if self._fog_active():
            true_map = load_true_map(self._get_data_root())
            known_maps = [
                load_known_map(self._store.root, ref)
                for ref in (self._adam_ref, self._eve_ref)
            ]
            topology = derive_topology(true_map, known_maps)
            return topology["allowed_tile_ids"]
        return self._runtime_policy.topology.get("allowed_tile_ids", [])

    def _merge_and_persist_known_map(
        self, agent_ref: str, observation: dict[str, Any], tick: int
    ) -> None:
        """Merge observation into the agent's known map and persist it."""
        if not self._fog_active():
            return
        known_map = load_known_map(self._store.root, agent_ref)
        updated = merge_observation(known_map, observation, tick)
        persist_known_map(self._store.root, agent_ref, updated)

    def _load_tile_resources(self) -> None:
        """Load gatherable resources from the true map, indexed by tile."""
        self._current_tile_resources = {}
        if not self._fog_active():
            return
        try:
            true_map = load_true_map(self._get_data_root())
            for res in true_map.get("resources", []):
                tile_id = res.get("tile_id", "")
                if not tile_id:
                    continue
                self._current_tile_resources.setdefault(tile_id, []).append(res)
        except FogAdapterError:
            self._current_tile_resources = {}

    def _get_agent_inventory(self, agent_ref: str) -> dict:
        """Return the agent's gathered-resource inventory (persisted)."""
        return dict(load_inventory(self._store).get(agent_ref, {}))

    # ------------------------------------------------------------------
    # World pressure (docs/world_pressure_spec.md)
    # ------------------------------------------------------------------

    def _reconcile_capability_requests(self) -> int:
        """Retire pending requests for capabilities already granted.

        The West pair carried 144 'pending' requests, 138 of them for
        `gather`, which the operator granted hundreds of heartbeats ago:
        the request log never reconciled, so the operator inbox's loudest
        section was stale noise. A request whose capability is now held is
        answered, not pending.
        """
        granted = {
            g.capability_id
            for g in load_extra_capability_grants(self._store)
            if g.status == "granted"
        }
        if (
            self._capability_grant is not None
            and self._capability_grant.status == "granted"
        ):
            granted.add(self._capability_grant.capability_id)
        if not granted:
            return 0
        retired = 0
        for req in self._world_state.capability_requests:
            if req.get("status") == "pending" and req.get("capability_id") in granted:
                req["status"] = "granted"
                req["retired_at_utc"] = datetime.now(timezone.utc).isoformat()
                retired += 1
        return retired

    def _pressure_step(self, agent_ref: str, heartbeat_number: int = 0) -> dict:
        """Apply this heartbeat's world physics for one agent.

        Order per spec: consume first — 1 food unit of the most-held food
        kind is decremented through the store; if no food is held the agent
        is famished this heartbeat (observable truth, gates only `build`).
        Records per-tick start-ledger totals so the gather cap rule can
        compare against them. Fail-closed: any error leaves holdings
        exactly as they were, and the state is recomputed conservatively
        from what is actually held.
        """
        state = {
            "heartbeat": heartbeat_number,
            "food_start": 0,
            "goods_start": 0,
            "consumed_kind": "",
            "famished": False,
        }
        try:
            holdings = self._get_agent_inventory(agent_ref)
            led = split_ledgers(holdings)
            state["food_start"] = led["food"]
            state["goods_start"] = led["goods"]
            kind = consume_choice(holdings)
            if kind is None:
                state["famished"] = True
            else:
                add_to_inventory(
                    self._store, agent_ref, kind, -FOOD_PER_HEARTBEAT
                )
                state["consumed_kind"] = kind
        except Exception:
            # Fail-closed: nothing (or nothing further) written. Honesty
            # rule: famished only if the agent actually holds no food.
            state["consumed_kind"] = ""
            state["famished"] = state["food_start"] == 0
        self._pressure_tick[agent_ref] = state
        return state

    def _pressure_state(self, agent_ref: str, heartbeat_number: int = 0) -> dict:
        """Current tick's pressure state, or a conservative default.

        Freshness rule: a stored state is authoritative only for the
        heartbeat it was computed in. Calls outside the heartbeat pipeline
        (direct executor invocations, other tools) get an inert default —
        never famished, start ledgers read from live holdings — so world
        pressure is only ever enforced by the real loop.
        """
        state = self._pressure_tick.get(agent_ref)
        if state is not None and state.get("heartbeat", 0) == heartbeat_number:
            return state
        led = split_ledgers(self._get_agent_inventory(agent_ref))
        return {
            "heartbeat": heartbeat_number,
            "food_start": led["food"],
            "goods_start": led["goods"],
            "consumed_kind": "",
            "famished": False,
        }

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _build_context(
        self, agent_ref: str, heartbeat_number: int
    ) -> AgentContext:
        view = self._agent_view(agent_ref)
        memory_list = (
            self._adam_memory if agent_ref == self._adam_ref else self._eve_memory
        )

        agent_goals = [g for g in self._goals if g.agent_id == view["agent_id"]]
        agent_pending_questions = [
            q
            for q in self._questions
            if q.asking_agent_id == view["agent_id"] and q.status == "pending"
        ]
        agent_answered_questions = [
            q.__dict__
            for q in self._questions
            if q.asking_agent_id == view["agent_id"] and q.status == "answered"
        ]

        position = (
            self._world_state.tile_occupancy.get(
                agent_ref,
                self._habitat["starting_tile_ids"][agent_ref],
            )
        )

        # Objects whose tile_id matches current position
        current_tile_objects = [
            obj
            for obj in self._world_state.public_objects.values()
            if isinstance(obj, dict) and obj.get("tile_id") == position
        ]

        # Fog observation when the gate is active; legacy otherwise (10JB-2)
        fog_obs_error = False
        if self._fog_active():
            try:
                observation = self._get_fog_observation(
                    agent_ref, position, current_tile_objects,
                    heartbeat_number=heartbeat_number,
                )
                visible_tiles = observation["visible_tiles"]
                available_moves = [t for t in visible_tiles if t != position]
                policy_allowed = self._get_effective_allowed_tiles()
                movement_allowed_flag = True
            except FogAdapterError:
                # Fail-closed: no fabricated observation, no legacy fallback
                fog_obs_error = True
                observation = {
                    "tile_id": position,
                    "visible_tiles": [position],
                    "objects_here": current_tile_objects,
                }
                visible_tiles = [position]
                available_moves = []
                policy_allowed = [position]
                movement_allowed_flag = False
        elif self._movement_grant_active():
            available_moves = get_adjacent_tiles(self._runtime_policy, position)
            visible_tiles = [position] + available_moves
            policy_allowed = self._runtime_policy.topology.get("allowed_tile_ids", [])
            movement_allowed_flag = True
            observation = {
                "tile_id": position,
                "visible_tiles": visible_tiles,
                "objects_here": current_tile_objects,
            }
        else:
            available_moves = []
            visible_tiles = self._habitat.get("observation_boundaries", {}).get(
                agent_ref, [position]
            )
            policy_allowed = self._habitat.get("allowed_tile_ids", [])
            movement_allowed_flag = self._habitat.get("movement_allowed", False)
            observation = {
                "tile_id": position,
                "visible_tiles": visible_tiles,
                "objects_here": current_tile_objects,
            }
        if fog_obs_error:
            observation["fog_error"] = "geography observation unavailable"

        # Visible public messages (addressed to this agent or public "all")
        visible_msgs = [
            m for m in self._world_state.public_messages
            if isinstance(m, dict) and (
                m.get("recipient") in (agent_ref, "all", "public")
                or m.get("recipient") == view["canonical_agent_ref"]
            )
        ]

        # Co-location: other agents at same tile
        other_agents_here = []
        if self._world_state.tile_occupancy:
            for ref, tid in self._world_state.tile_occupancy.items():
                if ref != agent_ref and tid == position:
                    other_view = self._agent_view(ref) if self._identity_record else {}
                    other_agents_here.append({
                        "agent_ref": ref,
                        "agent_name": other_view.get("canonical_name", ref),
                    })

        # Current runtime capabilities: the legacy movement grant plus any
        # extra operator-granted capabilities (append-only grants store)
        caps = []
        if self._movement_grant_active():
            caps.append(self._capability_grant.capability_id)
        for extra in load_extra_capability_grants(self._store):
            if extra.status == "granted" and extra.capability_id not in caps:
                caps.append(extra.capability_id)

        # --- Bounded memory selection ---
        history = load_heartbeat_history(self._store)
        recent_cutoff = max(0, heartbeat_number - 4) if history else 0

        visible_object_ids = {o.get("object_id", "") for o in current_tile_objects}
        visible_message_ids = {m.get("message_id", "") for m in visible_msgs}

        rel_events = load_relationship_events(self._store)
        rel_memory_ids = derive_relationship_event_ids(rel_events)

        # Select bounded memories with owner-bound IDs and dynamic identities
        selected_mems, sel_manifest = select_private_memories(
            memories=memory_list,
            agent_id=view["agent_id"],
            owner_agent_id=view["agent_id"],
            goals=[g.__dict__ for g in agent_goals],
            position=position,
            visible_tiles=set(visible_tiles),
            visible_object_ids=visible_object_ids,
            visible_message_ids=visible_message_ids,
            relationship_event_memory_ids=rel_memory_ids,
            recent_cutoff_hb=recent_cutoff,
            other_agent_ref=view["other_agent_ref"],
            other_agent_name=view["other_agent_name"],
        )

        sel_manifest["requesting_agent_id"] = view["agent_id"]
        sel_manifest["heartbeat"] = heartbeat_number

        # --- Bounded human context (max 4 combined) ---
        active_goal_ids = {g.goal_id for g in agent_goals if g.status == "active"}
        human_selected, human_answered_ids, human_unresolved_ids, human_omitted_count = select_human_context(
            answered_questions=agent_answered_questions,
            unresolved_questions=[q.__dict__ for q in agent_pending_questions],
            active_goal_ids=active_goal_ids,
        )
        human_answered = [r for r in human_selected if r.get("status") == "answered"]
        human_unresolved = [r for r in human_selected if r.get("status") == "pending"]

        # --- Derived summaries for older omitted memories (compute before manifest) ---
        selected_ids = {m.get("memory_id", "") for m in selected_mems}
        derived_sums, _candidate_ids = derive_summaries_for_omitted(
            memory_list=memory_list,
            selected_ids=selected_ids,
            owner_agent_id=view["agent_id"],
        )
        # Attempt validated append for each candidate; track actually persisted
        persisted_summary_ids: list[str] = []
        for ds in derived_sums:
            result = append_summary(self._store, ds, memory_list=memory_list)
            if result.get("ok"):
                persisted_summary_ids.append(ds.summary_id)

        # Load owned summaries — include only those actually persisted
        all_summaries = load_summaries(self._store)
        agent_summaries = [
            asdict(s) for s in all_summaries
            if s.owner_agent_id == view["agent_id"]
            and s.summary_id in persisted_summary_ids
        ]

        # --- Update manifest with ALL metadata, then persist once ---
        sel_manifest["summary_ids"] = persisted_summary_ids
        sel_manifest["human_context_count"] = len(human_selected)
        sel_manifest["human_context_answered_ids"] = human_answered_ids
        sel_manifest["human_context_unresolved_ids"] = human_unresolved_ids
        sel_manifest["human_context_omitted_count"] = human_omitted_count

        if self._store:
            append_memory_selection_manifest(self._store, sel_manifest)

        rel_events_export = [
            asdict(e) for e in rel_events
            if e.actor_agent_id == view["agent_id"] or e.other_agent_id == view["agent_id"]
        ]

        # --- Charter (recognition layer): latest self-authored version, verbatim ---
        latest_charter = load_latest_charter(self._store, agent_ref, view["agent_id"])
        charter_text = latest_charter.charter_text if latest_charter else ""
        charter_heartbeat = latest_charter.heartbeat if latest_charter else 0

        # --- World pressure: personal physics state (no map data) ---
        holdings_now = self._get_agent_inventory(agent_ref)
        pressure_state = self._pressure_state(agent_ref, heartbeat_number)
        famished_now = bool(pressure_state.get("famished", False))
        provisions = provisions_view(holdings_now, famished_now)
        carrying = carrying_view(holdings_now)
        observation["provisions"] = provisions
        observation["carrying"] = carrying

        # --- Physics version: can the agent notice the terms changed? ---
        # new_to_agent is True only on the first heartbeat this agent is
        # shown the current version, so the prompt can say so once.
        seen_before = load_physics_seen(self._store).get(agent_ref, {}).get("version", "")
        new_to_agent = seen_before != PHYSICS_VERSION
        observation["physics"] = {
            "version": PHYSICS_VERSION,
            "new_to_agent": new_to_agent,
        }
        try:
            record_physics_seen(self._store, agent_ref, PHYSICS_VERSION)
        except Exception:
            pass  # never fail a heartbeat over the notice

        # --- Operator messages (operator-owned; the runtime only reads) ---
        operator_messages = [
            m for m in load_operator_messages(self._store)
            if m.get("addressed_to") in ("all", agent_ref)
        ][-5:]

        return AgentContext(
            agent_id=view["agent_id"],
            canonical_name=view["canonical_name"],
            canonical_ref=agent_ref,
            heartbeat_number=heartbeat_number,
            position=position,
            observation=observation,
            memory=list(memory_list),
            goals=[g.__dict__ for g in agent_goals],
            unanswered_questions=human_unresolved,
            world_public_objects=self._world_state.public_objects,
            habitat_allowed_tiles=policy_allowed,
            habitat_movement_allowed=movement_allowed_flag,
            previous_action=None,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            other_agent_id=view["other_agent_id"],
            other_agent_name=view["other_agent_name"],
            other_agent_ref=view["other_agent_ref"],
            answered_questions=human_answered,
            available_moves=available_moves,
            current_runtime_capabilities=caps,
            current_tile_occupants=other_agents_here,
            visible_public_messages=visible_msgs,
            relevant_human_answers=human_answered,
            selected_private_memories=selected_mems,
            derived_memory_summaries=agent_summaries,
            public_relationship_events=rel_events_export,
            memory_selection_manifest=sel_manifest,
            charter_text=charter_text,
            charter_heartbeat=charter_heartbeat,
            inventory=self._get_agent_inventory(agent_ref),
            provisions=provisions,
            carrying=carrying,
            physics=dict(observation["physics"]),
            operator_messages=operator_messages,
        )

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _execute_action(self, agent_ref: str, action: dict | None, heartbeat_number: int) -> dict:
        if action is None:
            return {"status": "no_action", "detail": "No action chosen"}
        action_type = action.get("action_type")
        if action_type == "move":
            return self._execute_move(agent_ref, action)
        if action_type == "create_public_object":
            return self._execute_create_public_object(agent_ref, action, heartbeat_number)
        if action_type == "inspect_public_object":
            return self._execute_inspect_public_object(action)
        if action_type == "modify_owned_public_object":
            return self._execute_modify_owned_public_object(agent_ref, action, heartbeat_number)
        if action_type == "leave_public_message":
            return self._execute_leave_public_message(agent_ref, action, heartbeat_number)
        if action_type == "ask_human":
            return self._execute_ask_human(agent_ref, action, heartbeat_number)
        if action_type == "request_capability":
            return self._execute_request_capability(agent_ref, action, heartbeat_number)
        if action_type == "gather":
            return self._execute_gather(agent_ref, action, heartbeat_number)
        if action_type == "revise_charter":
            return self._execute_revise_charter(agent_ref, action, heartbeat_number)
        if action_type == "build":
            return self._execute_build(agent_ref, action, heartbeat_number)
        return {"status": "unknown_action", "action": action}

    def _execute_gather(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Collect a resource from the current tile."""
        resource_kind = action.get("resource_kind", "")
        if not resource_kind:
            return {"status": "rejected", "reason": "Missing resource_kind"}

        position = self._world_state.tile_occupancy.get(agent_ref)
        if not position:
            return {"status": "rejected", "reason": "No current position"}

        # Find the resource on this tile
        tile_resources = [
            r for r in self._current_tile_resources.get(position, [])
            if r.get("kind") == resource_kind and r.get("amount", 0) > 0
        ]
        if not tile_resources:
            return {"status": "rejected", "reason": f"No {resource_kind} available on this tile"}

        resource = tile_resources[0]
        available = resource.get("amount", 0)

        # World pressure: two-ledger carrying capacity, partial takes
        # (frozen reason strings — the live census and public show count
        # them verbatim).
        pressure = self._pressure_state(agent_ref, heartbeat_number)
        take, cap_reason = gather_allowance(
            resource_kind,
            self._get_agent_inventory(agent_ref),
            pressure["food_start"],
            pressure["goods_start"],
            available,
        )
        if cap_reason:
            return {"status": "rejected", "reason": cap_reason}

        resource["amount"] = available - take

        # Belongings persist: holdings live in the store, not in memory,
        # so what is gathered survives restarts.
        add_to_inventory(self._store, agent_ref, resource_kind, take)

        return {
            "status": "success",
            "resource_kind": resource_kind,
            "amount_gathered": take,
            "remaining_on_tile": resource.get("amount", 0),
        }

    def _execute_revise_charter(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Persist one self-authored charter version (append-only).

        The agent may only ever revise its own charter; ownership is bound
        to this agent's identity. A revision whose text is identical to the
        current version is a rejected no-op (nothing persisted — identity is
        not re-persisted when it has not changed). Earlier versions are
        preserved byte-for-byte forever.
        """
        view = self._agent_view(agent_ref)
        charter_text = (action.get("charter_text") or "").strip()
        if not charter_text:
            return {"status": "rejected", "reason": "Missing charter_text"}

        existing = load_latest_charter(self._store, agent_ref, view["agent_id"])
        if existing and existing.charter_text == charter_text:
            return {
                "status": "rejected",
                "reason": "charter text unchanged from current version",
                "charter_version_id": existing.charter_version_id,
            }

        versions = load_charter_versions(self._store)
        n_mine = sum(
            1 for v in versions
            if v.agent_ref == agent_ref and v.agent_id == view["agent_id"]
        )
        record = CharterVersionRecord(
            # agent_ref is unique per agent across all pairs; agent_id
            # prefixes are NOT (all genesis IDs share "genesis-agent"), so
            # the ref carries the identity here.
            charter_version_id=f"charter-{agent_ref}-v{n_mine + 1}",
            agent_id=view["agent_id"],
            agent_ref=agent_ref,
            pair_id=self._pair_id,
            heartbeat=heartbeat_number,
            charter_text=charter_text,
            decision_summary="",
        ).seal()
        if not append_charter_version(self._store, record):
            return {"status": "rejected", "reason": "charter version already persisted"}

        return {
            "status": "success",
            "charter_version_id": record.charter_version_id,
            "charter_chars": len(charter_text),
            "heartbeat": heartbeat_number,
        }

    def _execute_build(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Construct an agent-defined object from persisted holdings.

        The agent declares WHAT to make and WHAT it is made of; the runtime
        enforces placement (same rules as create_public_object), validates
        the materials declaration, checks affordability, then deducts and
        creates. No partial builds, no debt: insufficient holdings reject
        the whole build with everything untouched.
        """
        view = self._agent_view(agent_ref)
        object_id = action.get("object_id")
        object_type = action.get("object_type", "generic")
        raw_description = action.get("description", "")
        tile_id = action.get("tile_id")
        materials = action.get("materials")

        # World pressure: you cannot build on an empty stomach. Build is the
        # only action famished gates; everything else remains available.
        if self._pressure_state(agent_ref, heartbeat_number)["famished"]:
            return {"status": "rejected", "reason": BUILD_REJECT_FAMISHED}

        if not _is_safe_object_id(str(object_id or "")):
            return {"status": "rejected", "reason": "Invalid object_id"}
        if object_id in self._world_state.public_objects:
            return {"status": "rejected", "reason": f"Duplicate object_id: {object_id}"}
        current_pos = self._world_state.tile_occupancy.get(
            agent_ref, self._habitat["starting_tile_ids"][agent_ref]
        )
        if tile_id != current_pos:
            return {"status": "rejected", "reason": f"Cannot build on tile {tile_id}: you are at {current_pos}"}
        # Placement authority: you may always build on the tile you stand
        # on. Movement already governed how you got here (fog-derived
        # effective tiles grow with exploration); the old static policy
        # whitelist was never updated and refused the agent's own tile
        # after she moved (HB701-743: 26 build attempts on her own tile,
        # all refused "Tile ... not in allowed tiles").

        sanitized = sanitize_public_text(raw_description)
        if not sanitized.strip():
            return {"status": "rejected", "reason": "Empty public_description after sanitization"}

        if not isinstance(materials, dict) or not materials:
            return {"status": "rejected", "reason": "Missing or empty materials"}
        for kind, amount in materials.items():
            if not isinstance(kind, str) or not kind.strip():
                return {"status": "rejected", "reason": "Invalid material kind"}
            if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                return {"status": "rejected", "reason": f"Invalid material amount for {kind}"}

        holdings = self._get_agent_inventory(agent_ref)
        for kind, amount in materials.items():
            if holdings.get(kind, 0) < amount:
                return {
                    "status": "rejected",
                    "reason": f"Insufficient {kind}: need {amount}, hold {holdings.get(kind, 0)}",
                }

        for kind, amount in materials.items():
            add_to_inventory(self._store, agent_ref, kind, -amount)

        record = PublicObjectRecord(
            object_id=object_id,
            creator_agent_id=view["agent_id"],
            tile_id=tile_id,
            object_type=object_type,
            public_description=sanitized,
            created_heartbeat=heartbeat_number,
            materials=dict(materials),
        )
        self._world_state.public_objects[object_id] = record.to_envelope()
        return {
            "status": "success",
            "object_id": object_id,
            "tile_id": tile_id,
            "object_type": object_type,
            "materials_spent": dict(materials),
            "remaining": self._get_agent_inventory(agent_ref),
        }

    def _execute_move(self, agent_ref: str, action: dict) -> dict:
        if not self._habitat or not self._world_state:
            return {"status": "error", "reason": "Runtime not initialized"}
        if self._capability_grant is not None and self._capability_grant.status != "granted":
            return {"status": "blocked", "reason": f"Grant status is {self._capability_grant.status}"}
        if not self._movement_grant_active():
            return {"status": "blocked", "reason": "No active movement grant. Request capability from human operator."}

        target = action.get("target_tile")
        allowed = self._get_effective_allowed_tiles()
        if target not in allowed:
            return {"status": "blocked", "reason": f"Tile {target} not in runtime policy allowed tiles"}

        current_pos = self._world_state.tile_occupancy.get(agent_ref)
        if current_pos is None:
            current_pos = self._habitat["starting_tile_ids"].get(agent_ref)

        # Adjacent-only movement (fog-derived or legacy policy)
        adjacent = self._get_effective_adjacency(current_pos)
        if target not in adjacent:
            return {"status": "blocked", "reason": f"Cannot move from {current_pos} to {target}: not adjacent (adjacent: {adjacent})"}

        # Co-location is permitted on any valid traversable tile
        # (the old shared-center-only restriction was removed for the
        # expanded world; 10IZ §2.7 documented this as a near-term
        # design decision and the operator approved the generalization)

        self._world_state.tile_occupancy[agent_ref] = target
        return {"status": "success", "from": current_pos, "to": target}

    def _execute_create_public_object(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        object_id = action.get("object_id")
        object_type = action.get("object_type", "generic")
        raw_description = action.get("description", "")
        tile_id = action.get("tile_id") or self._habitat["starting_tile_ids"][agent_ref]

        if not _is_safe_object_id(str(object_id or "")):
            return {"status": "rejected", "reason": "Invalid object_id"}
        if object_id in self._world_state.public_objects:
            return {"status": "rejected", "reason": f"Duplicate object_id: {object_id}"}
        # Must place on current tile
        current_pos = self._world_state.tile_occupancy.get(
            agent_ref, self._habitat["starting_tile_ids"][agent_ref]
        )
        if tile_id != current_pos:
            return {"status": "rejected", "reason": f"Cannot place object on tile {tile_id}: you are at {current_pos}"}
        # Placement authority: the tile you stand on is always placeable
        # (same seam fix as build — movement, not a stale whitelist,
        # governs where an agent may be).

        sanitized = sanitize_public_text(raw_description)
        if not sanitized.strip():
            return {"status": "rejected", "reason": "Empty public_description after sanitization"}

        record = PublicObjectRecord(
            object_id=object_id,
            creator_agent_id=view["agent_id"],
            tile_id=tile_id,
            object_type=object_type,
            public_description=sanitized,
            created_heartbeat=heartbeat_number,
        )
        self._world_state.public_objects[object_id] = record.to_envelope()
        return {
            "status": "success",
            "object_id": object_id,
            "tile_id": tile_id,
            "object_type": object_type,
            "sanitized_description": sanitized[:200],
        }

    def _execute_inspect_public_object(self, action: dict) -> dict:
        obj_id = action.get("target_object_id")
        if not obj_id or not isinstance(obj_id, str):
            return {"status": "rejected", "reason": "Missing or invalid target_object_id"}
        obj = self._world_state.public_objects.get(obj_id)
        if obj is None or not isinstance(obj, dict):
            return {"status": "rejected", "reason": f"Object not found: {obj_id}"}
        return {"status": "success", "object": obj}

    def _execute_modify_owned_public_object(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        obj_id = action.get("target_object_id")
        if not obj_id or not isinstance(obj_id, str):
            return {"status": "rejected", "reason": "Missing or invalid target_object_id"}
        obj = self._world_state.public_objects.get(obj_id)
        if obj is None or not isinstance(obj, dict):
            return {"status": "rejected", "reason": f"Object not found: {obj_id}"}
        if obj.get("creator_agent_id") != view["agent_id"]:
            return {"status": "rejected", "reason": "Not the owner of this object"}
        modifications = action.get("modifications")
        if not isinstance(modifications, dict):
            return {"status": "rejected", "reason": "Missing or invalid modifications"}
        applied: dict[str, Any] = {}
        for key, value in modifications.items():
            if key not in _ALLOWED_MUTABLE_FIELDS:
                return {"status": "rejected", "reason": f"Cannot modify field: {key}"}
            if isinstance(value, str):
                sanitized = sanitize_public_text(value)
                if not sanitized.strip():
                    return {"status": "rejected", "reason": f"Empty text after sanitization for {key}"}
                obj[key] = sanitized
                applied[key] = sanitized
            else:
                obj[key] = value
                applied[key] = value
        obj["modified_heartbeat"] = heartbeat_number
        applied["modified_heartbeat"] = heartbeat_number
        return {
            "status": "success",
            "object_id": obj_id,
            "updates": list(modifications.keys()),
            "applied_values": applied,
        }

    def _execute_leave_public_message(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        message = action.get("message", "")
        if not isinstance(message, str) or not message.strip():
            return {"status": "rejected", "reason": "Missing or empty message"}
        sanitized = sanitize_public_text(message)
        if not sanitized.strip():
            return {"status": "rejected", "reason": "Empty after sanitization"}
        recipient = action.get("recipient", "all")
        from hashlib import sha256
        message_id = f"msg-{sha256(f'{agent_ref}{heartbeat_number}{sanitized[:50]}'.encode()).hexdigest()[:12]}"
        msg_record = {
            "message_id": message_id,
            "sender_agent_id": view["agent_id"],
            "message": sanitized[:2000],
            "recipient": recipient,
            "heartbeat": heartbeat_number,
            "sent_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self._world_state.public_messages.append(msg_record)
        return {
            "status": "success",
            "message_id": message_id,
            "message_preview": sanitized[:200],
        }

    def _execute_ask_human(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        question_id = action.get("question_id")
        question = action.get("question", "")
        reason = action.get("reason_for_asking", "")
        if not question_id or not question or not reason:
            return {"status": "rejected", "reason": "Missing question_id, question, or reason_for_asking"}
        if not _is_safe_object_id(str(question_id)):
            return {"status": "rejected", "reason": "Invalid question_id"}
        # Deduplicate against existing canonical questions AND pending
        # proposals — in memory (this process) and on disk (proposals from
        # earlier ticks; each heartbeat is a fresh process, so in-memory
        # dedupe alone let a stuck agent re-ask forever).
        for existing in self._questions:
            if existing.question_id == question_id:
                return {"status": "rejected", "reason": f"Duplicate question_id: {question_id}"}
        for existing_proposal in self._question_proposals:
            if existing_proposal.question_id == question_id:
                return {"status": "rejected", "reason": f"Duplicate question_id: {question_id}"}
        try:
            for persisted in load_agent_question_proposals(self._store):
                if persisted.get("question_id") == question_id:
                    return {"status": "rejected", "reason": f"Duplicate question_id: {question_id}"}
        except Exception:
            pass  # dedupe is best-effort; never block the ask itself
        agent_id = (
            self._identity_record.adam_agent_id
            if agent_ref == self._adam_ref
            else self._identity_record.eve_agent_id
        )
        urgency = action.get("urgency", "low")
        if urgency not in ("low", "medium", "high"):
            return {"status": "rejected", "reason": "Invalid urgency value"}
        proposal = QuestionProposal(
            question_id=question_id,
            asking_agent_id=agent_id,
            related_goal_id=action.get("related_goal_id"),
            question=question,
            reason_for_asking=reason,
            requested_human_capability=action.get("requested_human_capability", ""),
            urgency=urgency,
        )
        self._question_proposals.append(proposal)
        # Noncanonical sink: the ask is appended to agent_questions.json
        # (no authority, no signature, never questions.json) so the
        # operator can hear it. Fail-closed: a sink failure never turns a
        # heard ask into a crash or a canonical write.
        sink = "agent_questions.json"
        try:
            append_agent_question_proposal(self._store, {
                "question_id": proposal.question_id,
                "asking_agent_id": agent_id,
                "agent_ref": agent_ref,
                "pair_id": self._pair_id,
                "heartbeat": heartbeat_number,
                "question": question,
                "reason_for_asking": reason,
                "requested_human_capability": proposal.requested_human_capability,
                "urgency": urgency,
                "raised_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "unheard",
            })
        except Exception:
            sink = "memory-only"
        # No signature, no authority, no persistence to questions.json.
        return {
            "status": "proposed",
            "question_id": question_id,
            "proposal": asdict(proposal),
            "sink": sink,
        }

    def _execute_request_capability(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        cap_id = action.get("capability_id")
        cap_reason = action.get("capability_reason", "")
        if not cap_id or not isinstance(cap_id, str) or not cap_id.strip():
            return {"status": "rejected", "reason": "Missing or empty capability_id"}
        if not cap_reason or not isinstance(cap_reason, str) or not cap_reason.strip():
            return {"status": "rejected", "reason": "Missing or empty capability_reason"}
        record = {
            "capability_id": cap_id,
            "requesting_agent_id": view["agent_id"],
            "reason": cap_reason,
            "heartbeat": heartbeat_number,
            "status": "pending",
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self._world_state.capability_requests.append(record)
        return {
            "status": "success",
            "capability_id": cap_id,
            "reason": cap_reason,
        }

    def _execute_modify_world(self, agent_ref: str, action: dict) -> dict:
        return {"status": "not_implemented", "action": action}

    # ------------------------------------------------------------------
    # Cognition output application
    # ------------------------------------------------------------------

    def _apply_cognition_output(
        self, agent_ref: str, output: Any, heartbeat_number: int
    ) -> None:
        goal_updates = output.goal_updates if isinstance(output.goal_updates, list) else []
        for gu in goal_updates:
            if not isinstance(gu, dict):
                continue
            existing = next(
                (g for g in self._goals if g.goal_id == gu.get("goal_id")), None
            )
            if existing:
                existing.status = gu.get("status", existing.status)
                existing.description = gu.get("description", existing.description)
            else:
                self._goals.append(GoalRecord(
                    goal_id=gu["goal_id"],
                    agent_id=gu["agent_id"],
                    description=gu["description"],
                    status=gu.get("status", "active"),
                    created_heartbeat=gu.get("created_heartbeat", heartbeat_number),
                ))

        memory_writes = output.memory_write if isinstance(output.memory_write, list) else []
        for mw in memory_writes:
            if not isinstance(mw, dict):
                continue
            target_list = (
                self._adam_memory if agent_ref == self._adam_ref else self._eve_memory
            )
            target_list.append({
                **mw,
                "heartbeat": heartbeat_number,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            })

        questions = (
            output.questions_raised if isinstance(output.questions_raised, list) else []
        )
        for q in questions:
            if not isinstance(q, dict):
                continue
            qid = q.get("question_id")
            question_text = q.get("question")
            reason_text = q.get("reason_for_asking")
            if not isinstance(qid, str) or not qid:
                continue
            if not isinstance(question_text, str) or not question_text.strip():
                continue
            if not isinstance(reason_text, str) or not reason_text.strip():
                continue
            # Deduplicate against existing canonical questions AND proposals
            if any(existing.question_id == qid for existing in self._questions):
                continue
            if any(p.question_id == qid for p in self._question_proposals):
                continue
            agent_id = (
                self._identity_record.adam_agent_id
                if agent_ref == self._adam_ref
                else self._identity_record.eve_agent_id
            )
            proposal = QuestionProposal(
                question_id=qid,
                asking_agent_id=agent_id,
                related_goal_id=q.get("related_goal_id"),
                question=question_text,
                reason_for_asking=reason_text,
                requested_human_capability=q.get("requested_human_capability", ""),
                urgency=q.get("urgency", "low"),
            )
            self._question_proposals.append(proposal)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, start_heartbeat: int | None = None) -> dict:
        self._load_or_initialize()
        self._current_run_cognition: dict[str, dict] = {
            self._adam_ref: {"observation_summary": "", "decision_summary": "", "uncertainty": ""},
            self._eve_ref: {"observation_summary": "", "decision_summary": "", "uncertainty": ""},
        }

        history = load_heartbeat_history(self._store)
        if start_heartbeat is not None:
            current = start_heartbeat
        elif history:
            current = history[-1].heartbeat_number + 1
        else:
            current = 1

        # Capture pre-run state for evidence export
        from backend.world.first_pair_persistence import (
            load_memory_selection_manifests as _load_manifests,
            load_summaries as _load_summaries,
            load_relationship_events as _load_rel_events,
        )
        self._evidence_pre = {
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "adam_mem_before": len(self._adam_memory),
            "eve_mem_before": len(self._eve_memory),
            "cumulative_hb_before": len(history),
            "final_hb_before": history[-1].heartbeat_number if history else 0,
            "manifest_count_before": len(_load_manifests(self._store)),
            "summary_count_before": len(_load_summaries(self._store)),
            "rel_event_count_before": len(_load_rel_events(self._store)),
            "run_start_hb": current,
        }
        self._run_backend_label = self._backend

        results: dict = {"heartbeats_completed": 0, "errors": []}

        for hb in range(current, current + self._heartbeat_limit):
            adam_action: dict | None = None
            adam_outcome: dict = {}
            eve_action: dict | None = None
            eve_outcome: dict = {}
            world_mutations: list[dict] = []

            # Load gatherable resources for this heartbeat
            self._load_tile_resources()
            self._pressure_tick = {}
            self._reconcile_capability_requests()

            for agent_ref in (self._adam_ref, self._eve_ref):
                backend = self._get_cognition_backend(agent_ref)
                cycle = CognitiveCycle(backend)
                self._pressure_step(agent_ref, hb)  # physics before observation
                ctx = self._build_context(agent_ref, hb)
                output = cycle.run_cycle(ctx)
                serving = getattr(backend, "serving_provider_type", "")
                cycle_fallback_used = getattr(backend, "fallback_used", False)
                cycle_primary_failure = getattr(
                    backend, "primary_failure_reason", ""
                )
                if cycle_fallback_used and serving:
                    # A fallback lane served this cycle: sticky for the run.
                    self._fallback_used = True
                    self._serving_provider_type = serving
                elif not cycle_primary_failure and serving:
                    # Primary served this cycle; recorded only while no
                    # fallback has served any earlier cycle in this run.
                    # A cycle that failed entirely never touches serving.
                    if not getattr(self, "_fallback_used", False):
                        self._serving_provider_type = serving
                if cycle_primary_failure and not getattr(
                    self, "_primary_failure_reason", ""
                ):
                    self._primary_failure_reason = cycle_primary_failure
                outcome = self._execute_action(agent_ref, output.action, hb)

                # Fog: merge observation into known map and persist (10JB-2)
                if self._fog_active():
                    try:
                        self._merge_and_persist_known_map(
                            agent_ref, ctx.observation, hb
                        )
                    except FogAdapterError:
                        pass  # Known-map persist failure noted; don't crash the cycle

                if agent_ref == self._adam_ref:
                    adam_action = output.action
                    adam_outcome = outcome
                    self._current_run_cognition[self._adam_ref]["observation_summary"] = output.observation_summary
                    self._current_run_cognition[self._adam_ref]["decision_summary"] = output.decision_summary
                    self._current_run_cognition[self._adam_ref]["uncertainty"] = output.uncertainty
                else:
                    eve_action = output.action
                    eve_outcome = outcome
                    self._current_run_cognition[self._eve_ref]["observation_summary"] = output.observation_summary
                    self._current_run_cognition[self._eve_ref]["decision_summary"] = output.decision_summary
                    self._current_run_cognition[self._eve_ref]["uncertainty"] = output.uncertainty

                reflection = cycle.reflect(ctx, output.action, outcome)
                self._apply_cognition_output(agent_ref, output, hb)

                memory_list = (
                    self._adam_memory if agent_ref == self._adam_ref else self._eve_memory
                )
                if not _reflection_is_echo(memory_list, reflection):
                    memory_list.append({
                        "type": "reflection",
                        "content": reflection,
                        "heartbeat": hb,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    })

                # Structured mutation evidence — only actual state mutations
                if outcome.get("status") == "success":
                    action_type = (output.action or {}).get("action_type", "unknown")
                    # Only world-changing actions count as mutations
                    if action_type in (
                        "create_public_object",
                        "modify_owned_public_object",
                        "leave_public_message",
                        "request_capability",
                        "move",
                        "build",
                    ):
                        view = self._agent_view(agent_ref)
                        mutation = {
                            "acting_agent_id": view["agent_id"],
                            "heartbeat": hb,
                            "action_type": action_type,
                            "target": outcome.get("object_id") or outcome.get("target_tile") or outcome.get("message_id", ""),
                            "input": dict(output.action) if output.action else {},
                            "outcome": outcome,
                        }
                        world_mutations.append(mutation)

                    # Record social continuity event for validated public interactions
                    if action_type in (
                        "leave_public_message", "move", "create_public_object",
                        "inspect_public_object",
                    ):
                        view = self._agent_view(agent_ref)
                        other_id = view["other_agent_id"]
                        maybe_record_relationship_event(
                            self._store, hb, agent_ref,
                            view["agent_id"], other_id,
                            action_type, outcome, view,
                            self._world_state,
                        )

            # Set world_state.tick to actual heartbeat before saving
            self._world_state.tick = hb
            self._world_state.updated_at_utc = datetime.now(timezone.utc).isoformat()

            # End-of-tick persistence
            self._persist_shared_state(
                hb, adam_action, adam_outcome, eve_action, eve_outcome, world_mutations
            )
            results["heartbeats_completed"] += 1

        return results

    def _persist_shared_state(
        self,
        heartbeat_number: int,
        adam_action: dict | None = None,
        adam_outcome: dict | None = None,
        eve_action: dict | None = None,
        eve_outcome: dict | None = None,
        world_mutations: list[dict] | None = None,
    ) -> None:
        save_world_state(self._store, self._world_state)

        shared_memory = {
            self._adam_ref: list(self._adam_memory),
            self._eve_ref: list(self._eve_memory),
        }
        save_memory(self._store, shared_memory)
        save_goals(self._store, self._goals)
        self._persist_questions_without_stale_overwrite()

        actions_taken = {}
        if adam_action:
            actions_taken[self._adam_ref] = adam_action
        if eve_action:
            actions_taken[self._eve_ref] = eve_action

        action_outcomes = {}
        if adam_outcome:
            action_outcomes[self._adam_ref] = adam_outcome
        if eve_outcome:
            action_outcomes[self._eve_ref] = eve_outcome

        hb_record = HeartbeatRecord(
            heartbeat_number=heartbeat_number,
            agent_id="both",
            position="",
            observation={},
            action_taken=actions_taken if actions_taken else None,
            world_mutations=world_mutations or [],
            goals_updated=[g.goal_id for g in self._goals],
            questions_raised=[
                q.question_id for q in self._questions if q.status == "pending"
            ],
            action_outcomes=action_outcomes,
        )
        append_heartbeat(self._store, hb_record)

    def _persist_questions_without_stale_overwrite(self) -> None:
        """Reconcile canonical questions WITHOUT writing back local state.

        Canonical questions are store-owned. The runtime no longer mints
        questions (proposals are noncanonical), so it has no authority to write
        ``questions.json``. On every tick it re-syncs ``self._questions`` from the
        canonical store, guaranteeing that stale in-memory state (e.g. an old
        pending Q1) can never overwrite a newer governed answer.
        """
        self._questions = load_questions(self._store)

    # ------------------------------------------------------------------
    # Evidence / inspection
    # ------------------------------------------------------------------

    def export_evidence(self, output_path: Path, run_id: str = "") -> dict[str, Any]:
        history = load_heartbeat_history(self._store)
        process_start = datetime.now(timezone.utc)

        adam_view = self._agent_view(self._adam_ref) if self._identity_record else {}
        eve_view = self._agent_view(self._eve_ref) if self._identity_record else {}

        # --- Resolve run boundaries from pre-run state ---
        pre = getattr(self, "_evidence_pre", None)
        if pre is not None and pre.get("run_start_hb"):
            new_count = history[-1].heartbeat_number - pre["final_hb_before"] if history else 0
            start_hb = pre["run_start_hb"]
            end_hb = pre["run_start_hb"] + new_count - 1 if new_count > 0 else None
        else:
            new_count = 0
            start_hb = None
            end_hb = None

        cumulative_count = len(history)
        adam_mem_before = pre["adam_mem_before"] if pre else len(self._adam_memory)
        eve_mem_before = pre["eve_mem_before"] if pre else len(self._eve_memory)

        # --- Run-specific records (by count slicing) ---
        all_manifests = load_memory_selection_manifests(self._store)
        all_summaries = load_summaries(self._store)
        all_rel_events = load_relationship_events(self._store)

        manifest_before = pre["manifest_count_before"] if pre else len(all_manifests)
        summary_before = pre["summary_count_before"] if pre else len(all_summaries)
        rel_before = pre["rel_event_count_before"] if pre else len(all_rel_events)

        run_manifests = list(all_manifests[manifest_before:])
        run_summaries = list(all_summaries[summary_before:])
        run_rel_events = list(all_rel_events[rel_before:])

        # --- Cumulative heartbeat detail ---
        heartbeats_export: list[dict] = []
        for h in history:
            entry: dict = {"heartbeat_number": h.heartbeat_number}
            actions = h.action_taken or {}
            entry["adam_action"] = actions.get(self._adam_ref)
            entry["eve_action"] = actions.get(self._eve_ref)
            entry["questions_raised"] = h.questions_raised
            entry["goals_updated"] = h.goals_updated
            entry["world_mutations"] = [
                m for m in (h.world_mutations or [])
                if m.get("action_type") in (
                    "create_public_object", "modify_owned_public_object",
                    "leave_public_message", "request_capability", "move",
                ) and m.get("outcome", {}).get("status") == "success"
            ]
            hb_manifests = [m for m in all_manifests if m.get("heartbeat", 0) == h.heartbeat_number]
            if hb_manifests:
                entry["memory_selection_manifests"] = hb_manifests
            heartbeats_export.append(entry)

        # --- Run-specific heartbeat list ---
        run_heartbeats = [h for h in heartbeats_export
                          if start_hb is not None and end_hb is not None
                          and start_hb <= h["heartbeat_number"] <= end_hb]

        # --- Privacy manifest ---
        privacy_manifest = {
            "requesting_agent_id_adam": adam_view.get("agent_id", ""),
            "requesting_agent_id_eve": eve_view.get("agent_id", ""),
            "adam_private_memory_count": len(self._adam_memory),
            "eve_private_memory_count": len(self._eve_memory),
            "other_agent_private_memory_included": 0,
            "public_evidence_count": len(self._world_state.public_objects) + len(self._world_state.public_messages) if self._world_state else 0,
            "answered_question_count": len([q for q in self._questions if q.status == "answered"]) if self._questions else 0,
            "canonical_request_hash": hashlib.sha256(
                json.dumps({
                    "adam_mem_count": len(self._adam_memory),
                    "eve_mem_count": len(self._eve_memory),
                    "public_obj_count": len(self._world_state.public_objects) if self._world_state else 0,
                    "goal_count": len(self._goals),
                }, sort_keys=True).encode()
            ).hexdigest()[:16],
        }

        # --- Provider / backend label ---
        provider_type = ""
        model_name = ""
        backend_label = getattr(self, "_run_backend_label", self._backend)
        try:
            backend = self._get_cognition_backend(self._adam_ref)
            if hasattr(backend, "provider_type"):
                provider_type = backend.provider_type
            if hasattr(backend, "model_name"):
                model_name = backend.model_name
        except Exception:
            pass

        # Lane that actually served cognition during this run (equals
        # provider_type when no fallback lane served), plus fallback
        # provenance: the sanitized primary failure that triggered the
        # fallback is preserved even when the fallback succeeded.
        serving_provider_type = (
            getattr(self, "_serving_provider_type", "") or provider_type
        )
        fallback_used = bool(getattr(self, "_fallback_used", False))
        primary_failure_reason = getattr(self, "_primary_failure_reason", "")[:600]

        bundle: dict[str, Any] = {
            "evidence_schema_version": "10FN.2",
            "run_id": run_id,
            "backend_label": backend_label,
            "provider_type": provider_type,
            "primary_provider_type": provider_type,
            "model_name": model_name,
            "serving_provider_type": serving_provider_type,
            "fallback_used": fallback_used,
            "primary_failure_reason": primary_failure_reason,
            "root": str(self._store.root) if self._store else "",
            "process_started_at_utc": pre["started_at_utc"] if pre else "",
            "process_finished_at_utc": process_start.isoformat(),
            "start_heartbeat": start_hb,
            "end_heartbeat": end_hb,
            "new_heartbeat_count": new_count,
            "cumulative_heartbeat_count": cumulative_count,
            "initialized_or_resumed": "resumed" if cumulative_count > 1 else "initialized",
            "adam_id": adam_view.get("agent_id", ""),
            "eve_id": eve_view.get("agent_id", ""),
            "adam_memory_count_before": adam_mem_before,
            "adam_memory_count_after": len(self._adam_memory),
            "eve_memory_count_before": eve_mem_before,
            "eve_memory_count_after": len(self._eve_memory),
            "adam_selected_memory_count": len([m for m in run_manifests if m.get("requesting_agent_id") == adam_view.get("agent_id", "")]),
            "eve_selected_memory_count": len([m for m in run_manifests if m.get("requesting_agent_id") == eve_view.get("agent_id", "")]),
            "summary_count": len(all_summaries),
            "relationship_event_count": len(all_rel_events),
            "goals_before": [],
            "goals_after": [g.__dict__ for g in self._goals],
            "questions_answered_during_run": [
                q.__dict__ for q in self._questions if q.status == "answered"
            ],
            "active_capability_grants": [
                self._capability_grant.__dict__
            ] if self._capability_grant else [],
            "adam_observation_summary": getattr(self, "_current_run_cognition", {}).get(self._adam_ref, {}).get("observation_summary", ""),
            "adam_decision_summary": getattr(self, "_current_run_cognition", {}).get(self._adam_ref, {}).get("decision_summary", ""),
            "adam_uncertainty": getattr(self, "_current_run_cognition", {}).get(self._adam_ref, {}).get("uncertainty", ""),
            "eve_observation_summary": getattr(self, "_current_run_cognition", {}).get(self._eve_ref, {}).get("observation_summary", ""),
            "eve_decision_summary": getattr(self, "_current_run_cognition", {}).get(self._eve_ref, {}).get("decision_summary", ""),
            "eve_uncertainty": getattr(self, "_current_run_cognition", {}).get(self._eve_ref, {}).get("uncertainty", ""),
            # Run-specific sections
            "heartbeats": run_heartbeats,
            "memory_selection_manifests": run_manifests,
            "memory_summaries": [asdict(s) for s in run_summaries],
            "relationship_events": [asdict(e) for e in run_rel_events],
            # Cumulative state
            "cumulative": {
                "heartbeats": heartbeats_export,
                "memory_selection_manifests": all_manifests,
                "memory_summaries": [asdict(s) for s in all_summaries],
                "relationship_events": [asdict(e) for e in all_rel_events],
            },
            "privacy_manifest": privacy_manifest,
            "adam_memory": self._adam_memory,
            "eve_memory": self._eve_memory,
            "goals": [g.__dict__ for g in self._goals],
            "questions": [q.__dict__ for q in self._questions],
            "exported_at_utc": process_start.isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2, default=str, sort_keys=True)
        return bundle

    def validate_state(self) -> dict:
        return validate_persistence_integrity(self._store)


def run_first_pair_demo(
    heartbeats: int = 5,
    persistence_root: Path | None = None,
    export_path: Path | None = None,
    backend: str = "stub",
) -> dict:
    """Convenience harness — builds a fresh runtime and runs it once."""
    runtime = FirstPairRuntime(
        persistence_root=persistence_root,
        heartbeat_limit=heartbeats,
        backend=backend,
    )
    results = runtime.run()
    if export_path:
        runtime.export_evidence(export_path)
    return results
