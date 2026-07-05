# Genesis Kernel World Sim

Genesis Kernel World Sim is a proof-of-concept for applying Rosetta Stone's self-correcting constraint theory to agent-based civilization simulation.

The current milestone is not autonomous civilization yet. It is the verified epistemic kernel that prevents known multi-agent failure modes before autonomy is turned loose.

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
10AV — Shared Public Event Ref Contract   (current)
10AW — Shared Public Route Destination Contract   (current)
10AX — Shared Public Territory Ref Contract
10AY — Shared Public Snapshot Hash Equality Contract   (current)
10AZ — Shared Public Tick-Range Equality Contract   (current)
10BC - Shared Public Observation Count Equality Contract   (current)
10BD - Shared Public Movement Count Equality Contract   (current)
10BE - Shared Public Accepted Event Count Equality Contract   (current)
10BF - Shared Public Ignored Event Count Equality Contract   (current)
10BG - Shared Public Last Event ID Equality Contract   (current)
10BH - Shared Public First Event ID Equality Contract   (current)
10BI - Shared Public Merge ID Equality Contract   (current)
10BJ - Shared Public Current Tile ID Equality Contract   (current)
```

Each rung of the ladder is a pure module: it consumes the previous rung's output and produces a deterministic, sanitized, replayable artifact. No rung performs true map lookup, route planning, route intent, movement execution, runtime/daemon/scheduler/provider/Docker/network activity, or `world-sim/data` access.

## Current Status

The public stack now reaches Phase 10BJ, the shared public current tile ID equality contract (10AS was the two-agent public merge; 10AU was the shared public anchor contract; 10AW was the shared public route destination contract; 10AY was the shared public snapshot hash equality contract; 10AZ through 10BI added scalar public equality contracts without crossing into co-presence, route, relationship, or timing inference).

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
- 10AV: Shared Public Event Ref Contract - deterministic sanitized public event-reference sharing contract over a valid 10AS merge artifact or caller-supplied public event ref lists; targeted tests: 26 passed; 10AI through 10AV regression: 302 passed; commit `ba3c8b6`.
- 10AW: Shared Public Route Destination Contract - deterministic sanitized public route-destination sharing contract over a valid 10AS merge artifact or caller-supplied route destination overrides; route destination fields (`route_destination_tile_id`, `route_destination_known`) compared only; `shared_route_destination_tile_id` populated only when both `route_destination_known` are True AND destinations equal; caller-supplied overrides treated as known public declarations when sanitized destination is non-empty; no path inference, no timing/window inference, no co-presence; targeted tests: 26 passed; 10AI through 10AW regression: 328 passed; commit `727f20e`.
- 10AX: Shared Public Territory Ref Contract - deterministic sanitized public territory-ref sharing contract over a valid 10AS merge artifact or caller-supplied territory ref overrides; territory ref fields (`territory_ref`) compared only; `same_territory_ref` True when both non-empty and equal; `shared_territory_ref` populated only when `same_territory_ref` is True; `agent_a_only_territory_ref` / `agent_b_only_territory_ref` populated when only one side has a non-empty ref; caller-supplied overrides treated as known public declarations when sanitized territory ref is non-empty; no proximity inference, no timing/window inference, no co-presence; targeted tests: 28 passed; 10AI through 10AX regression: 356 passed; commit `5d2600f`
- 10AY: Shared Public Snapshot Hash Equality Contract - deterministic sanitized snapshot-hash equality contract over a valid 10AS merge artifact; snapshot hash equality (`snapshot_hash`) and snapshot id fields (`snapshot_id`) compared only; `same_snapshot_hash` True when both non-empty and equal; `shared_snapshot_hash` populated only when `same_snapshot_hash` is True; `agent_a_snapshot_hash` / `agent_b_snapshot_hash` / `agent_a_snapshot_id` / `agent_b_snapshot_id` always propagated; tests inject snapshot hash/id fields into 10AS bundles after merge creation (10AS code untouched); no knowledge inference, no communication inference, no co-presence; targeted tests: 25 passed; 10AI through 10AY regression: 525 passed; commit `df25233`
- 10AZ: Shared Public Tick-Range Equality Contract - deterministic sanitized tick-range equality contract over a valid 10AS merge artifact; tick ranges (`first_tick`, `last_tick`) are caller-supplied optional arguments, not read from 10AS bundles; `same_first_tick`, `same_last_tick`, `same_tick_range` computed by pure mechanical equality only; no temporal overlap calculation, no co-presence inference, no active-at-same-time claim, no window inference; missing/None tick fields produce ok=True with None fields and equality booleans False; contract_id preserves A/B agent orientation (not sorted); targeted tests: 26 passed; 10AI through 10AZ regression: 551 passed; commit `e6ee66c`
- 10BA: Shared Public Tick Label Contract - deterministic sanitized shared-public-tick-label contract over a valid 10AS merge artifact; caller-supplied optional tick label lists (`agent_a_tick_labels`, `agent_b_tick_labels`); 10AS merge is provenance/agent identity source only; no temporal overlap, no co-presence, no ordering/sequence inference; targeted tests: 29 passed; 10AI through 10BA regression: 436 passed; commit `5b3423d`
- 10BB: Shared Public State Hash Equality Contract - deterministic sanitized shared-public-state-hash-equality contract over a valid 10AS merge artifact; caller-supplied optional public state hash strings (`agent_a_public_state_hash`, `agent_b_public_state_hash`); 10AS merge is provenance/agent identity source only; no state inference, no temporal overlap, no co-presence, no meeting/interaction inference, no relationship inference; scalar-only (no lists, no deduplication, no set algebra); targeted tests: 28 passed; 10AI through 10BB regression: 464 passed; commit `eb61ca1`
- 10BC: Shared Public Observation Count Equality Contract - deterministic sanitized shared-public-observation-count-equality contract over a valid 10AS merge artifact; caller-supplied optional observation count integers (`agent_a_observation_count`, `agent_b_observation_count`); 10AS merge is provenance/agent identity source only; 10AS bundles do not expose `observation_count`; no observation-content inference, no temporal overlap, no co-presence, no meeting/interaction inference, no relationship inference; scalar-only (no lists, no deduplication, no set algebra); targeted tests: 23 passed; 10AI through 10BC regression: 487 passed; commit `414b780`
- 10BD: Shared Public Movement Count Equality Contract - deterministic sanitized shared-public-movement-count-equality contract over a valid 10AS merge artifact; caller-supplied optional movement count integers (`agent_a_movement_count`, `agent_b_movement_count`); 10AS merge is provenance/agent identity source only; 10AS bundles do not expose `movement_count`; no movement-content inference, no temporal overlap, no co-presence, no meeting/interaction inference, no relationship inference; scalar-only (no lists, no deduplication, no set algebra); targeted tests: 23 passed; 10AI through 10BD regression: 510 passed; commit `76267b8`
- 10BE: Shared Public Accepted Event Count Equality Contract - deterministic sanitized shared-public-accepted-event-count-equality contract over a valid 10AS merge artifact; caller-supplied optional accepted event count integers (`agent_a_accepted_event_count`, `agent_b_accepted_event_count`); 10AS merge is provenance/agent identity source only; 10AS bundles do not expose `accepted_event_count`; no event-content inference, no temporal overlap, no co-presence, no meeting/interaction inference, no relationship inference; scalar-only (no lists, no deduplication, no set algebra); targeted tests: 23 passed; 10AI through 10BE regression: 533 passed; commit `4cddfe7`
- 10BF: Shared Public Ignored Event Count Equality Contract - deterministic sanitized shared-public-ignored-event-count-equality contract over a valid 10AS merge artifact; caller-supplied optional ignored event count integers (`agent_a_ignored_event_count`, `agent_b_ignored_event_count`); 10AS merge is provenance/agent identity source only; 10AS bundles do not expose `ignored_event_count`; no event-content inference, no temporal overlap, no co-presence, no meeting/interaction inference, no relationship inference; scalar-only (no lists, no deduplication, no set algebra); targeted tests: 23 passed; 10AI through 10BF regression: 556 passed; commit `9b58dbd`
- 10BG: Shared Public Last Event ID Equality Contract - deterministic sanitized shared-public-last-event-id-equality contract over a valid 10AS merge artifact; caller-supplied optional scalar string kwargs (`agent_a_last_event_id`, `agent_b_last_event_id`); 10AS bundles do not expose `last_event_id`; scalar string equality only (no lists, no deduplication, no set algebra); `contract_id` preserves A/B agent orientation (not sorted); `_sanitize_event_id` returns None for non-string, empty, or `[REDACTED`-containing values to prevent sanitizer-collapse false equality; no event-content inference, no temporal overlap, no co-presence, no meeting/interaction inference, no relationship inference; targeted tests: 23 passed; 10AI through 10BG regression: 579 passed; commit `4463045`
- 10BH: Shared Public First Event ID Equality Contract - deterministic sanitized shared-public-first-event-id-equality contract over a valid 10AS merge artifact; caller-supplied optional scalar string kwargs (`agent_a_first_event_id`, `agent_b_first_event_id`); 10AS bundles do not expose `first_event_id`; scalar string equality only (no lists, no deduplication, no set algebra); `contract_id` preserves A/B agent orientation (not sorted); `_sanitize_event_id` returns None for non-string, empty, or `[REDACTED`-containing values to prevent sanitizer-collapse false equality; no event-content inference, no temporal overlap, no co-presence, no meeting/interaction inference, no relationship inference; targeted tests: 23 passed; 10AI through 10BH regression: 602 passed; commit `af0ce11`
- 10BI: Shared Public Merge ID Equality Contract - deterministic sanitized shared-public-merge-id-equality contract over a valid 10AS merge artifact; caller-supplied optional scalar string kwargs (`agent_a_merge_id`, `agent_b_merge_id`); 10AS produces a single root-level `merge_id` for the merge artifact as a whole; it does not expose a per-agent `merge_id` field in agent bundles; scalar string equality only (no lists, no deduplication, no set algebra); `contract_id` preserves A/B agent orientation (not sorted); `_sanitize_merge_id` returns None for non-string, empty, or `[REDACTED`-containing values to prevent sanitizer-collapse false equality; no event-content inference, no temporal overlap, no co-presence, no meeting/interaction inference, no relationship inference, no same-merge-event inference; boundary: may say only "same public merge_id value"; targeted tests: 23 passed; 10AI through 10BI regression: 625 passed; commit `34b1c1d`
- 10BJ: Shared Public Current Tile ID Equality Contract - deterministic sanitized shared-public-current-tile-id-equality contract over a valid 10AS merge artifact; reads `agent_a.current_tile_id` and `agent_b.current_tile_id` from the 10AS agent bundles; scalar string equality only (no lists, no deduplication, no set algebra); `contract_id` preserves A/B agent orientation (not sorted); `_sanitize_current_tile_id` returns None for non-string, empty, or `[REDACTED`-containing values to prevent sanitizer-collapse false equality; boundary: may say only "same public current_tile_id value"; no same-place-at-same-time inference, no co-presence, no meeting/interaction/proximity/awareness inference, no route/path/destination/timing inference, no relationship/trust/cooperation/conflict inference; targeted tests: 23 passed; 10AI through 10BJ regression: 648 passed; commit `d06862d`

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
