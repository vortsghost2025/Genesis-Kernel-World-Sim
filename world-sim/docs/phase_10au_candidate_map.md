# Phase 10AU — Candidate Map

Three candidate directions for the next rung after 10AT.  No
implementation, no scope contract, no tests.  This document only
maps what each direction would look like so the operator and agent
can agree on one before any code is written.

All three candidates follow the established pattern: pure module,
tempdir-only tests, no runtime, no daemon, no `world-sim/data`, no
private-inference claims, and a scope contract in
`world-sim/docs/` before any code is written.

---

## Candidate A — Public Anchor / Reference Sharing

### Purpose

Formalize which public landmarks, event refs, or territory refs two
agents have each cited in their already-public surfaces.  Two agents
may share public observation of a tile *and* both reference the same
public landmark or event ref on that tile, without either agent
having private knowledge of the other.

### Inputs

- A valid 10AS two-agent public merge artifact (ok=True,
  merge_type="two_agent_public_merge", merge_schema_version="10AS.1").
- The merge already carries agent bundles with `agent_id`,
  `current_tile_id`, `known_tile_ids`, and optional route-destination
  fields.  No direct 10AP/10AQ/10AR input; 10AU reads only the 10AS
  merge.

### Outputs

A deterministic sanitized contract artifact with fields:

- `contract_id` = "10AU-" + sha256[:32] of canonical contract material
- `source_merge_id`, `source_merge_hash` — provenance from the 10AS merge
- `agent_a_id`, `agent_b_id` — sanitized agent ids
- `shared_known_tile_ids` — lifted from the 10AS merge
- `shared_public_anchor_ids` — sorted intersection of the two agents'
  **public anchor / reference ids** as reported in their 10AP
  public_state (e.g., `current_territory_ref`, `last_event_id`,
  or a future `public_anchor_ids` field if 10AP is extended)
- `shared_anchor_tile_ids` — the set of tiles those shared anchors
  belong to (derived from the 10AP public_state's territory/landmark
  mappings, which are already public)
- `agent_a_only_anchor_ids`, `agent_b_only_anchor_ids` — set
  differences
- `same_current_tile` — lifted from the 10AS merge
- `claim_scope` = "shared_public_anchors_only"

### Forbidden inferences

- "The agents share private state about these anchors."
- "The agents trust each other's anchor choices."
- "The agents are aware of each other because they cite the same
  anchor."
- "The agents can navigate to each other via shared anchors."
- Any claim that promotes a shared public anchor into a private
  relationship, shared memory, co-presence, awareness, trust,
  cooperation, conflict, or navigation claim.

### Test shape

1. Happy path: a real 10AS merge (built via 10AS creator) with two
   public_state inputs that carry matching `current_territory_ref`
   values produces `ok=True`, correct `shared_public_anchor_ids`,
   `claim_scope == "shared_public_anchors_only"`, empty errors.
2. Output has exactly the required top-level fields; no forbidden
   fields leak (`co_presence`, `trust`, `cooperation`, `conflict`,
   `awareness`, `communication`, `relationship`, `private_*`,
   `shared_private_*`).
3. `shared_public_anchor_ids` is the sorted intersection of the two
   agents' public anchor id lists; set-difference fields are correct.
4. When one agent's public_state lacks anchor ids, the contract still
   builds with empty shared/anchor-only lists and `ok=True`.
5. When neither agent's public_state carries anchor ids, the contract
   builds with empty anchor fields and `ok=True`.
6. Input mutation guard: caller's 10AS merge dict is unchanged after
   the call.
7. Non-dict / ok=False / wrong merge_type / wrong merge_schema_version
   / missing agent_a or agent_b → `ok=False` with safe errors.
8. Private markers planted in the merge (paths, secrets, IPs, agent
   traces, slash-skill refs) are redacted in the contract output and
   in the exported JSON text.
9. `contract_id` is deterministic across repeated calls and changes
   when any contract-material field changes.
10. Boundary scan: the 10AU module contains no forbidden imports (no
    10AS/10AR/10AQ/10AP creators, no ledger writers, no projectors,
    no network/process/runtime tools, no `world-sim/data`).
11. Module source does not call `create_two_agent_public_merge(` or
    any other upstream creator.
12. Boundary smoke: the full happy-path contract text carries no
    relationship, trust, cooperation, conflict, awareness,
    co-presence, or communication tokens.
13. Saturation: all three public functions exercised
    (`create_shared_public_anchor_contract`, `export_…`,
    `contract_shared_anchor_file`).
14. `contract_shared_anchor_file` reads an exported 10AS merge JSON
    from a tempdir path and builds a contract.
15. `same_current_tile` and `shared_known_tile_ids` lifted from the
    10AS merge remain correctly propagated.

All tests are tempdir-only.  No test writes to `world-sim/data`, no
test connects to a provider, runs a daemon, or requires Docker.

---

## Candidate B — Observation Depth Contract

### Purpose

Formalize how deeply each agent *observed* shared tiles, without
exposing the agent's private observation process or the hidden true
map.  Two agents may share public observation of tile X, and both
may have observed tile X at different depths (e.g., Adam observed
tile X via a short-radius observe, Eve via a long-radius observe),
but neither agent's private observation parameters may ever reach
the contract output.

### Inputs

- A valid 10AS two-agent public merge artifact.
- Each agent bundle in the 10AS merge already carries
  `known_tile_ids` (the union of `observed_tile_ids` and
  `visited_tile_ids`).  10AU does **not** import 10AP directly; it
  reads only the 10AS merge bundles.

### Outputs

A deterministic sanitized contract artifact with fields:

- `contract_id` = "10AU-" + sha256[:32] of canonical contract material
- `source_merge_id`, `source_merge_hash` — provenance
- `agent_a_id`, `agent_b_id` — sanitized agent ids
- `shared_known_tile_ids` — lifted from the 10AS merge
- `shared_observed_tile_ids` — sorted intersection of the two
  agents' `observed_tile_ids` (these are **public** in 10AP
  public_state; 10AU never reads the hidden true map or the agent's
  private `build_local_observation()` result)
- `agent_a_observation_depth` — derived from the public
  `observation_count` and `observed_tile_ids` in agent_a's 10AP
  public_state (e.g., `len(observed_tile_ids)`); a public scalar,
  not a private process description
- `agent_b_observation_depth` — same for agent_b
- `depth_delta` — absolute difference between the two depths
- `agent_a_only_observed_tile_ids`, `agent_b_only_observed_tile_ids`
  — set differences
- `same_current_tile` — lifted from the 10AS merge
- `claim_scope` = "shared_public_observation_depth_only"

### Forbidden inferences

- "Agent A observed tile X more thoroughly than Agent B, so Agent A
  knows more about tile X." (depth delta is a public scalar
  comparison only; it does not imply differential private knowledge)
- "Agent B missed something on tile X that Agent A saw." (10AU never
  reads the hidden true map; it cannot know what was missed)
- "The agents' observation depths imply they used different equipment,
  strategies, or abilities." (no equipment/strategy/ability claims)
- "Agent A's observation depth on tile X implies Agent A has private
  knowledge Agent B lacks." (depth is a public scalar; private
  knowledge transfer is never inferable)
- Any claim that promotes depth comparison into a trust, cooperation,
  conflict, awareness, co-presence, or relationship claim.

### Test shape

1. Happy path: 10AS merge with agents that have different
   `observed_tile_ids` lengths produces `ok=True`, correct
   `shared_observed_tile_ids`, `agent_a_observation_depth`,
   `agent_b_observation_depth`, `depth_delta`, and
   `claim_scope == "shared_public_observation_depth_only"`.
2. Output has exactly the required top-level fields; no forbidden
   fields leak.
3. `shared_observed_tile_ids` is the sorted intersection of the two
   agents' `observed_tile_ids` lists as carried in the 10AS bundles.
4. When agents have equal observation depth, `depth_delta` is 0.
5. When one agent observed a tile the other did not, it appears in
   the agent-only observed list, not in the shared list.
6. When neither agent's bundle carries `observed_tile_ids` (edge
   case), the contract builds with empty observed fields and
   `ok=True`.
7. Input mutation guard.
8. Non-dict / ok=False / wrong type / wrong version / missing bundle
   / empty agent ids → `ok=False` with safe errors.
9. Private markers redacted in contract and export.
10. `contract_id` deterministic and collision-resistant.
11. Boundary scan: no forbidden imports or creator calls in the 10AU
    module.
12. Boundary smoke: full happy-path contract text carries no
    relationship/trust/cooperation/conflict/awareness/co-presence
    tokens.
13. Saturation: all three public functions exercised.
14. File helper reads exported 10AS merge JSON from tempdir.
15. `same_current_tile` and `shared_known_tile_ids` lifted from the
    10AS merge remain correctly propagated.

All tests are tempdir-only.  No `world-sim/data`, no daemon, no
provider, no Docker.

---

## Candidate C — Shared Observation Timeline Summary

### Purpose

Formalize a **time-windowed** shared-observation summary: not just
*where* two agents' public surfaces overlap, but *when* (across
which ticks) those overlaps occurred.  This is the temporal
dimension that 10AT does not cover.  10AU-C does not produce a
timeline of the agents' private actions; it only summarizes which
public ticks both agents' public surfaces report as active, and
whether shared-tile observations occurred on the same or different
ticks.

### Inputs

- A valid 10AS two-agent public merge artifact.
- Each agent bundle in the 10AS merge already carries `first_tick`,
  `last_tick`, `accepted_event_count`, and (if the 10AP public_state
  carries it) a per-tile observation tick list.  10AU-C reads only
  the 10AS merge; it does not import 10AP, 10AQ, 10AR, or any
  earlier creator.

### Outputs

A deterministic sanitized contract artifact with fields:

- `contract_id` = "10AU-" + sha256[:32] of canonical contract material
- `source_merge_id`, `source_merge_hash` — provenance
- `agent_a_id`, `agent_b_id` — sanitized agent ids
- `shared_known_tile_ids` — lifted from the 10AS merge
- `agent_a_active_tick_range` — `(first_tick, last_tick)` derived
  from the public bundle fields; a public scalar pair
- `agent_b_active_tick_range` — same for agent_b
- `shared_active_tick_count` — count of ticks in the overlap of the
  two active ranges (inclusive); a public scalar
- `shared_known_tile_ids_observed_in_same_tick_window` — the subset
  of `shared_known_tile_ids` where both agents' public surfaces
  report observation activity within the shared active-tick window
  (this is a public-surface comparison only; 10AU-C never reads the
  hidden true map or any agent's private tick log)
- `shared_known_tile_ids_observed_in_different_tick_windows` — the
  complement subset (public surface only)
- `same_current_tile` — lifted from the 10AS merge
- `claim_scope` = "shared_public_timeline_only"

### Forbidden inferences

- "The agents were active at the same time, so they could have met."
  (shared active ticks are a public-surface scalar; co-presence is
  never inferable from overlapping tick ranges)
- "Agent A observed tile X at tick N and Agent B observed tile X at
  tick N, so they were at tile X together." (10AU-C never reads
  private position logs; public-surface tick overlap is not
  co-presence)
- "The agents' observation timelines imply a shared schedule or
  coordination." (no coordination, planning, or schedule claims)
- "Agent B's lack of observation on tile X at tick N means Agent B
  missed something Agent A saw." (10AU-C never reads the hidden true
  map; it cannot know what was missed)
- Any claim that promotes timeline overlap into a trust, cooperation,
  conflict, awareness, co-presence, relationship, or communication
  claim.

### Test shape

1. Happy path: 10AS merge with agents carrying `first_tick` /
   `last_tick` produces `ok=True`, correct active tick ranges,
   `shared_active_tick_count`, correct
   `shared_known_tile_ids_observed_in_same_tick_window` /
   `…_different_tick_windows`, `claim_scope ==
   "shared_public_timeline_only"`.
2. Output has exactly the required top-level fields; no forbidden
   fields leak.
3. When active tick ranges overlap partially, `shared_active_tick_count`
   reflects the inclusive overlap count.
4. When active tick ranges do not overlap, `shared_active_tick_count`
   is 0 and both `…_same_tick_window` /
   `…_different_tick_windows` lists reflect the public-surface state.
5. `same_current_tile` and `shared_known_tile_ids` lifted from the
   10AS merge remain correctly propagated regardless of tick-window
   results.
6. When neither agent's bundle carries tick-range fields, the
   contract builds with empty/None tick fields and `ok=True`.
7. Input mutation guard.
8. Non-dict / ok=False / wrong type / wrong version / missing bundle
   / empty agent ids → `ok=False` with safe errors.
9. Private markers redacted in contract and export.
10. `contract_id` deterministic and collision-resistant.
11. Boundary scan: no forbidden imports or creator calls in the 10AU
    module.
12. Boundary smoke: full happy-path contract text carries no
    relationship/trust/cooperation/conflict/awareness/co-presence
    tokens.
13. Saturation: all three public functions exercised.
14. File helper reads exported 10AS merge JSON from tempdir.
15. `shared_active_tick_count` correctly handles edge cases:
    single-tick overlap, full containment, zero overlap, identical
    ranges.

All tests are tempdir-only.  No `world-sim/data`, no daemon, no
provider, no Docker.

---

## Recommendation

**Candidate A (Public Anchor / Reference Sharing) is the
recommended next direction.**

Reasoning:

- It is the smallest semantic extension beyond 10AT.  10AT formalized
  *where* two agents' public surfaces overlap; Candidate A adds *what
  public landmarks and event refs both agents cite* on those shared
  tiles.  The public-state fields already exist in 10AP
  (`current_territory_ref`, `last_event_id`) and are carried forward
  through 10AQ, 10AR, and 10AS.  No new public-state fields need to be
  invented; 10AU-A can build immediately on the current stack.

- Candidate B (Observation Depth) is viable but requires a judgment
  call about what "depth" means publicly.  The `observation_count`
  scalar is already public in 10AP, but extending 10AU-B into a
  richer depth vocabulary (tile-level observation radii, observation
  quality markers) would need a separate scope contract to avoid
  accidentally surfacing private observation parameters.  Candidate B
  is a good 10AU+1 after A.

- Candidate C (Shared Observation Timeline) is the most complex of
  the three.  Tick-range overlap is a legitimate public-surface
  comparison, but the "same tick window" subset logic risks sliding
  into co-presence inference if the contract's claim-scope wording is
  not extremely careful.  Candidate C is best reserved for 10AU+2,
  after A and B have established the pattern for safe public-surface
  temporal comparisons.

**Next step if Candidate A is chosen:**

1. Write `world-sim/docs/phase_10au_public_anchor_contract_spec.md`
   as the scope contract (following the 10AT spec's template).
2. Implement
   `world-sim/backend/world/local_shared_public_anchor_contract.py`
   with public functions `create_shared_public_anchor_contract`,
   `export_shared_public_anchor_contract`, and
   `contract_shared_anchor_file`.
3. Write `world-sim/tests/test_phase10au_shared_public_anchor_contract.py`
   following the test shape above.
4. Run targeted 10AU tests, regression 10AI → 10AU, then commit
   implementation/spec/test together.
5. Sync README.md and phase_index.md, commit docs-only, then push.

**No implementation until the operator confirms the chosen direction
and the scope contract is written and reviewed.**
