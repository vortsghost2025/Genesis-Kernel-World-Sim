# Genesis Kernel World Sim

A civilization-simulation kernel that models persistent agents, their perceptions, memories, actions, and the evidence-backed world events they produce.

This project is a **simulation engine**, not a real-world claim. The founding agents — Adam and Eve — are simulation entities with canonical identities, continuity across cycles, and bounded perception. They are not religious figures, real-world authorities, or conscious beings.

## Core Principle

**A claim is not a fact unless backed by accepted evidence.**

The system distinguishes several categories of information, each with different epistemic weight:

| Category | Description |
|---|---|
| **Observation** | Direct perception of world state through authorized channels |
| **Memory** | Persistent record of what an agent has perceived, done, or believed |
| **Speech** | Content of messages or whispers exchanged between agents |
| **Hypothesis** | A conjecture not yet supported by direct evidence |
| **Operator Proof** | Git commits, test output, or readback verification produced by the operator |
| **World Event** | An append-only record of a state change, action result, or social consequence |

Every event in the world ledger carries a `claim_scope` that identifies which of these categories it belongs to. The system enforces that hypotheses are labeled as hypotheses, that speech is recorded as speech (not fact), and that world mutations require before/after evidence.

## Architecture

Simulation output follows a pipeline:

```
daemon/action output
    → candidate event mapper
    → ledger validator
    → append-only ledger
```

- **Action executor** produces raw results from agent decisions (observe, rest, gather, whisper, goal, help).
- **Candidate event mapper** (Phase 10L) translates those results into candidate ledger entries without writing files.
- **Ledger validator** (Phase 10K) checks each candidate against the Genesis canon schema — required fields, valid evidence categories, private-path rejection, hidden-water and animal-guidance boundaries.
- **Append-only ledger** (Phase 10K) stores validated events as JSONL, preserving history immutably.

The ledger and mapper are currently **pure modules** — they can be imported, tested, and validated without a running simulation or any infrastructure.

## Public Phase Ladder

```
10AM — bounded heartbeat sequence
10AN — ledger/export bridge (sequence -> verified temp ledger)
10AO — replay custody trail (audit summary)
10AP — current public state read model (public_state projection)
10AQ — known map snapshot export (portable sanitized snapshot)
10AR — route intent contract (deterministic sanitized intent artifact)
10AS — two-agent public merge
10AT — Shared Public Observation Contract
10AU — Shared Public Anchor Contract   (current)
```

Each rung of the ladder is a pure module: it consumes the previous rung's output and produces a deterministic, sanitized, replayable artifact. No rung performs true map lookup, route planning, route intent, movement execution, runtime/daemon/scheduler/provider/Docker/network activity, or `world-sim/data` access.

## Current Status

The public stack now reaches Phase 10AU, the shared public anchor contract (10AT was the shared public observation contract; 10AS was the two-agent public merge; 10AR was the route intent contract).

Completed locally (mixed pure modules and harness proof):
- 10K: pure world event ledger
- 10L: pure candidate event mapper
- 10T: pure event verifier
- 10U: pure event aggregator
- 10V: pure event exporter
- 10Y: single-tick event-ingress harness – the first executable heartbeat proof (observe → verifier → temporary ledger append → read‑back → exporter)
- 10AA: two-agent echo harness – the first executable remembered-heartbeat proof (Adam observe → Eve speech echo → provenance-preserving export)
- 10AB: two-agent echo rejection guardrails – rejects whispered claims of observed scope, missing agent_speech or world_event provenance, and observed_world_fact truth-transfer attempts
- 10AC: replay/audit harness – proves replay order stability, event ID distinctness, claim-scope preservation, world_event provenance resolution, no observed-truth inheritance, deterministic export across repeated reads, and stable aggregator summaries
- 10AD: pure public egress sanitizer – deterministic regex-based redaction of Windows paths, credentials, IPs/runtime markers, agent trace markers, and slash-skill contamination; recursive mapping with dict-key sanitization; 32 tempdir-only tests
- 10AE: public egress boundary harness – proves exported world-event output (JSON/JSONL/CSV) passes through the egress sanitizer; plants harmless fake leak markers and proves them redacted; proves all five redaction markers appear, world terms survive, idempotent, no mutation, and both pre-export and post-export sanitization eliminate leaks; 18 tempdir-only tests
- 10AF: hidden planet substrate contract – proves a hidden true_map (3 regions, 3 tiles, 3 landmarks, resources, hazards) exists behind fog-of-war; agent at Misty Vale observes only the local slice; ledger records only observed data; hidden region/landmark/resource names absent from JSON/JSONL/CSV export; sanitizer redacts fake leak markers in observed data while preserving world language; full pipeline proof (observe→ledger→export→sanitize) with and without leaks; 41 tempdir-only tests
- 10AG: observed slice event bridge – converts a fog-of-war `build_local_observation()` result into a world event candidate via `candidate_from_observe_result()`, bridging the hidden planet substrate into the event system through verifier, ledger, export, and sanitizer without leaking hidden substrate; 28 tempdir-only tests
- 10AH: observed slice bridge hardening – hardens bridge/verifier seam: tick required (ValueError for None/negative); explicit claim_scope="observed" passed through mapper; duplicate key includes territory_ref enabling same-tick cross-region observations; input validation rejects malformed observation dicts; 19 tempdir-only tests
- 10AI: local movement contract – proves an agent can move locally inside the hidden planet substrate; `resolve_local_move()` supports 8 directions, `destination_tile_id`, coordinate adjacency (Manhattan ≤ 1), `blocks_travel` rejection, tick validation, and `before_ref`/`after_ref` as `"tile:<id>"`; `candidate_from_move_result()` bridges move result into candidate event; 38 tempdir-only tests covering movement, candidate mapping, verifier, ledger, post-move observation, and full pipeline
- 10AJ: known-map accumulation contract – proves an agent can accumulate and retain known_map data across ticks; `known_map` persists across moves, enabling map building; contract implementation and candidate mapping; 27 tests passed; regression suite 209 passed; safety scan PASS; network scan PASS; commit `5b6c13d Phase 10AJ: add known-map accumulation contract`
- 10AK: multi-tick exploration loop contract – proves an agent can perform multi-tick exploration, gather observations across successive ticks, and integrate them into a coherent world event; pure modules only, no runtime, daemon, provider, or Docker impact; 13 tests passed; regression suite 222 passed; cached diff check PASS; commit `7c57efc Phase 10AK: add multi-tick exploration loop contract`
- 10AL: tiny local heartbeat harness – a small, bounded harness that drives one heartbeat boundary at a time; it is not a daemon, not a scheduler, and not a runtime loop; it calls the 10AK multi-tick exploration loop once per heartbeat boundary and stops; pure local execution only, no daemon, scheduler, provider, Docker, or runtime loop; 10AL tests: 8 passed; 10AL + regression: 230 passed; diff check PASS; cached diff check PASS; safety scan PASS; network scan PASS; commit `e56ad8b Phase 10AL: add tiny local heartbeat harness`
- 10AM: bounded heartbeat sequence runner – chains a finite heartbeat plan through 10AL, advancing across ordered heartbeat boundaries until the plan is exhausted, then stops; it is not a daemon, not a scheduler, not a runtime, and not an infinite loop; it calls the 10AL tiny local heartbeat harness once per boundary in the plan and terminates when the plan ends; pure local execution only, no daemon, scheduler, provider, Docker, or runtime loop; 10AM tests: 12 passed; 10AM + 10AL + 10AK + 10AJ + 10AI regression: 98 passed; cached diff check PASS; safety scan PASS; network scan PASS; commit `57797d1 Phase 10AM: add bounded heartbeat sequence runner`
- 10AN: bounded sequence-to-ledger bridge – transforms public 10AM heartbeat sequence output into verified temp-ledger events and sanitized export proof; it never accepts, reads, returns, exports, or infers hidden true_map; ledger path is caller-supplied temp directory only; pure local execution only, no daemon, scheduler, provider, Docker, runtime, network, or live data; 10AN tests: 11 passed; 10AN + 10AM + 10AL + 10AK + 10AJ + 10AI regression: 109 passed; diff check PASS; contamination scan PASS; network/runtime scan PASS; commit `883115d Phase 10AN: add bounded sequence-to-ledger bridge`
- 10AO: ledger replay verifier – deterministic replay summary from accepted public ledger events; audit replay only, not state projection, not memory export; derives agent_id, final public position, observed tile ids, movement chain, tick range, accepted/ignored counts, and safe errors from accepted ledger events; 10AO tests: 19 passed; 10AO + 10AN + 10AM + 10AL + 10AK + 10AJ + 10AI regression: 128 passed; diff check PASS; forbidden marker/runtime scan PASS; commit `b2bd52e Phase 10AO: add ledger replay verifier`
- 10AP: Public State Projector – accepted public ledger events -> current public world-state read model; projector/read model only, not memory export, not known_map rebuild, not route planning, not runtime, not daemon, not multi-agent merge; 10AP targeted tests: 16 passed; 10AP + 10AO + 10AN + 10AM + 10AL + 10AK + 10AJ + 10AI regression: 144 passed; diff check PASS; forbidden marker/runtime scan PASS; commit `0c8a604 Phase 10AP: add public state projector`
- 10AQ: Known Map Snapshot Export – consumes the 10AP public_state projection and exports a deterministic, sanitized, portable known-map snapshot; pure transform only — no true map lookup, no route planning, no route intent, no movement execution, not runtime/daemon/scheduler/provider/Docker/network, not diff functions, not `world-sim/data`; canonical sanitized projection JSON hashed via sha256 to produce `source_projection_hash`; `snapshot_id = "10AQ-" + hash[:32]`; `known_tile_ids = sorted(union(observed_tile_ids, visited_tile_ids))`; public functions `create_known_map_snapshot(public_state)`, `export_known_map_snapshot(snapshot)`, `snapshot_ledger_file(ledger_path)`; 10AQ targeted tests: 15 passed; 10AQ + 10AP + 10AO + 10AN + 10AM + 10AL + 10AK + 10AJ + 10AI regression: 159 passed; diff check PASS; forbidden marker/runtime scan PASS; commit `e35b844 Phase 10AQ: add known map snapshot export`
- 10AR: Route Intent Contract – consumes a 10AQ known-map snapshot and emits a deterministic, sanitized route-intent contract artifact; contract only — no path, no route steps, no route edges, no adjacency inference, no pathfinding, no movement execution, no ledger write, no candidate-event mapping, no verifier dependency, no mapper dependency, no true map lookup, no runtime/daemon/scheduler/provider/Docker/network, no `world-sim/data`; validates `destination_tile_id ∈ known_tile_ids` → `destination_known`; sanitizes `destination_tile_id` before any use; `claim_scope = "intent_only"`; canonical intent material `{source_snapshot_hash, agent_id, from_tile_id, destination_tile_id, claim_scope, reason?}` hashed via sha256 to produce `intent_id = "10AR-" + hash[:32]`; public functions `create_route_intent_contract(snapshot, destination_tile_id, *, reason=None)`, `export_route_intent_contract(contract)`, `contract_snapshot_file(snapshot_json_path, destination_tile_id, *, reason=None)`; tests: `world-sim/tests/test_phase10ar_route_intent_contract.py`; 10AR targeted tests: 17 passed; 10AR + 10AQ + 10AP + 10AO + 10AN + 10AM + 10AL + 10AK + 10AJ + 10AI regression: 176 passed; diff check PASS; forbidden marker/runtime scan PASS; commit `d19225d Phase 10AR: add route intent contract`,
- 10AS: Two-Agent Public Merge – combines two agents' already-public surfaces (10AP public_state + 10AQ known-map snapshot + optional 10AR route-intent contract, per agent) into a deterministic sanitized two-agent public merge artifact; targeted tests: 30 passed; regression stack: 206 passed; public functions `create_two_agent_public_merge(public_state_a, snapshot_a, public_state_b, snapshot_b, route_intent_a=None, route_intent_b=None)`, `export_two_agent_public_merge(merge)`, `merge_public_surface_files(public_state_a_path, snapshot_a_path, public_state_b_path, snapshot_b_path, route_intent_a_path=None, route_intent_b_path)`; canonical merge material hashed via sha256 to produce `merge_id = "10AS-" + hash[:32]`; `claim_scope = "public_only"`; agent bundles include `agent_id`, `public_state_hash`, `snapshot_id`, `snapshot_hash`, `current_tile_id`, `known_tile_ids`, `route_intent_id`, `route_destination_tile_id`, `route_destination_known`; allowed comparisons `shared_known_tile_ids`, `agent_a_only_known_tile_ids`, `agent_b_only_known_tile_ids`, `same_current_tile`, `both_have_route_intent`; strict route-intent validation requires `ok=True`, `intent_type="route_intent_contract"`, matching `agent_id`, matching `source_snapshot_id`, `claim_scope="intent_only"`, and `destination_known=True`; invalid or internally inconsistent route intents return `ok=False` with safe errors; all inputs deep-copied before reading; all inputs sanitized via `sanitize_public_mapping`; route destination fields sanitized before output; private markers must never reach merge output or exported JSON; boundary: 10AS may say "These two public surfaces overlap on tiles X/Y/Z.", but 10AS may not say "The agents know each other, met, communicated, trust each other, cooperate, conflict, are aware of each other, or can travel between those tiles."; commit `afc79f7`

- 10AT: Shared Public Observation Contract - deterministic sanitized time-windowed public observation contract over a valid 10AS two-agent public merge artifact; consumes 10AS merge + shared_window + optional public anchors/refs only; no 10AP/10AQ/10AR direct inputs, no parent-body rehashing, no full route-intent revalidation, no meeting/awareness/co-presence/relationship/route inference; 10AT targeted tests: 44 passed; 10AI through 10AT regression: 250 passed; diff check PASS; commit `5177342 Phase 10AT: add shared public observation contract`
- 10AU: Shared Public Anchor Contract - deterministic sanitized public anchor/reference sharing contract over a valid 10AS merge artifact or caller-supplied public anchor lists.

Documentation/spec phases:
- 10M: public README and phase index
- 10N: public runtime‑boundary sanitization
- 10O: public CI/security/contribution docs
- 10W: egress sanitizer specification
- 10X: runtime wiring pilot spec / first‑heartbeat contract
- 10Z: first remembered‑heartbeat contract (docs‑only/spec‑only)
- 10Q–10S: future plan, persistent habitat principles, and runtime wiring architecture

CI status: GitHub Actions may show pending or failed while account-level restrictions prevent CI runners from starting. Pure-module tests are designed to run locally without runtime infrastructure.

## Safe Local Verification

You can run the mixed local verification suite—including the completed pure‑module tests, the Phase 10Y single‑tick ingress harness, and the Phase 10AA two‑agent echo harness—without any daemon, provider, tick, or runtime infrastructure:

```bash
cd world-sim
python -m pytest \
    tests/test_phase10k_world_event_ledger_schema.py \
    tests/test_phase10k_world_event_ledger_append_only.py \
    tests/test_phase10k_world_event_ledger_boundaries.py \
    tests/test_phase10l_candidate_mapper_observe_rest.py \
    tests/test_phase10l_candidate_mapper_gather.py \
    tests/test_phase10l_candidate_mapper_social.py \
    tests/test_phase10l_candidate_mapper_boundaries.py \
    tests/test_phase10t_event_verifier_duplicate.py \
    tests/test_phase10t_event_verifier_contradiction.py \
    tests/test_phase10t_event_verifier_reference.py \
    tests/test_phase10t_event_verifier_consistency.py \
    tests/test_phase10t_event_verifier_accept.py \
    tests/test_phase10u_event_aggregator.py \
    tests/test_phase10v_event_exporter.py \
    tests/test_phase10y_single_tick_ingress.py \
    tests/test_phase10aa_two_agent_echo_harness.py \
    tests/test_phase10ab_two_agent_echo_rejections.py \
    tests/test_phase10ac_replay_audit_harness.py \
    tests/test_phase10ad_public_egress_sanitizer.py \
    tests/test_phase10ae_public_egress_boundary_harness.py \
    tests/test_phase10af_hidden_planet_substrate.py \
    tests/test_phase10ag_observed_slice_mapper.py \
    tests/test_phase10ah_observed_slice_bridge_hardening.py \
    tests/test_phase10ai_local_movement_contract.py -v
```

All tests use temporary directories only. They do not:
- Write to `world-sim/data/`
- Connect to any provider or model
- Start daemon, tick, or scheduler processes
- Access network or infrastructure
- Require Docker or a VPS

## Runtime Warning

Do not run daemon, provider, tick, or dual-agent phases unless you have verified that you are on the canonical runtime host with the correct container and mount configuration. Running these phases from an unverified host, workstation, or non-canonical environment may produce incorrect state or data loss.

## Project Boundaries

This repository explicitly excludes the following from agent-visible simulation scope:

- Hostnames, remote access targets, VPS details, and deployment infrastructure
- API keys, provider routes, billing, and credentials
- Git remotes, commits, branch state, and local operator workflow
- Private configuration files and household operator details
- Operator-only safety gates and internal runtime notes

Agents may not act on outside-world information unless a future phase deliberately translates it into an in-world artifact or event.
