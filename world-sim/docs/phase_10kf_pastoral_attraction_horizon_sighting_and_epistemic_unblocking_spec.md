# Phase 10KF Specification: Pastoral Attraction Dynamics, Horizon Sighting & Epistemic Unblocking

> **Phase Chain:** 10KD (audit, Done `cf4e55b`) -> 10KE (metadata sync, Done `17d0be5`, hash-corrected `cc3c95a`) -> 10KF (specification, this document) -> 10KG (metadata sync) -> 10KH (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10KH following explicit operator authorization.

---

## 1. Overview & Problem Statement

Phase 10KD established, from direct measurement of the live canonical stores, that the absence of animal domestication is **not** a cognitive refusal, a food shortage, or a missing prompt affordance. It is a spatial horizon disconnect:

1. **Perception horizon is tiny.** `FirstPairRuntime._fauna_visible` (`backend/world/first_pair_runtime.py:1405`) filters fauna strictly to Chebyshev distance `<= 6` and returns `{"nearby": [...]}`. Any animal 7+ tiles away yields an empty list.
2. **Fauna spawn far and drift far.** `fauna.spawn_fauna` places cows and horses at distance 4-14 (`FAUNA_MIN_SPAWN_DISTANCE = 4`, `FAUNA_MAX_SPAWN_DISTANCE = 14`), and untamed grazers execute a uniform 8-neighbourhood random walk (`_free_drift_step`) across a 200x200 continent.
3. **The result is a lottery, not ecology.** In West Dawn, `cow-6864-0` drifted to 33 tiles and `horse-6866-1` to 42 tiles. Across hundreds of heartbeats, neither West agent ever had a domestic animal inside the 6-tile window, so the `offer_food` / `milk_animal` affordance lines shipped in Phase 10JR were never emitted.
4. **One lane is paralyzed on top of that.** West Dawn holds 6 active goals, all `await operator direction`, and 148 of 233 recent actions (63.5%) are `ask_human`. West stopped exploring precisely when the animals drifted away.

Phase 10KF specifies two mechanical corrections and one epistemic one.

---

## 2. Scope

### 2.1 In Scope (Phase 10KH Candidate)

1. **Pastoral Attraction Dynamics** — bias untamed grazer drift toward active settlement signal (fire, occupation) within a bounded pastoral radius, replacing the uniform random-walk lottery with a graded attraction gradient that is still fully deterministic.
2. **Distant Horizon Sighting** — extend `_fauna_visible` to return a `distant` list for animals at distance 7-15, and render a corresponding environmental-awareness line in the cognition prompt, giving agents an epistemic reason to travel toward fauna before entering the interaction bubble.
3. **Epistemic Unblocking Harness** — formalize the operator-statement delivery path for West Dawn through `scripts/operator_say.py`, plus post-delivery state verification that the lane resumes autonomous action.
4. **Regression-Gate Hardening** — replace the substring assertions in `tests/test_viewer_fidelity.py` with structural assertions that exercise real code paths.

### 2.2 Out of Scope

- Any change to taming thresholds, trust deltas, or `ANIMAL_FOOD_TRUST` values (Phase 10JN owns those).
- Horse riding, mounted movement, or carrying capacity.
- New fauna species, or fauna spawning during night/rain/storm/blizzard (the existing gate at `spawn_fauna` is correct and stays).
- Any edit to live stores (`.runtime/`) outside the authorized operator-message path.
- Changing the RNG seed derivation (`heartbeat_number * 31 + (crc32(pair_id) % 100000)`) or the pure/deterministic contract of `fauna.py`.

---

## 3. Design Invariants

1. **Preserved Determinism.** `fauna.py` is a pure module: every function is `(state) -> state'` with the RNG injected. Attraction may reweight which neighbour is chosen, but the RNG stream and call order must remain identical so that a given `(pair_id, heartbeat_number)` reproduces byte-identical results. Attraction must be expressed as a *reordering of the existing candidate set*, never as extra `rng` draws.
2. **Gradated, Not Inevitable.** Attraction is a bias, not a tractor beam. A grazer inside the pastoral radius may still move away. Design goal is a strong statistical pull (empirically, mean approach toward signal), not guaranteed capture.
3. **No New Perception for Free.** Horizon sighting changes only what is *reported* to the agent, not what the agent can act on. Interaction still requires `dist <= 1` for `offer_food` / `milk_animal`, enforced by the existing fail-closed reach check.
4. **Hazard Precedence.** Snakes keep their existing behaviour exactly (`_snake_step` already avoids fire and sheltered tiles). Attraction applies only to `_free_drift_step`, which is the cow and non-fleeing horse path.
5. **Existing Plumbing Reused.** `move_fauna` already receives `fire_xys: list[tuple[int, int]]`. The attraction gradient is derived from these coordinates plus agent occupation; **no signature change to `move_fauna` is required.** Only `_free_drift_step` gains parameters.
6. **Operator Voice Discipline.** Any operator statement is strictly factual: it states what is true about the world, never strategy, destinations, or build instructions (Standing Rule 7).

---

## 4. Architectural Specifications

### 4.1 Pastoral Attraction in `backend/world/fauna.py`

Current state (verified, `fauna.py:253-278`):

```python
def _free_drift_step(entity: dict, tile: tuple[int, int],
                     rng: random.Random) -> tuple[int, int]:
    if entity.get("tamed"):
        return _bounded_anchor_step(entity, tile, rng)
    options = _neighbors(tile)
    return rng.choice(options)


def _horse_step(entity: dict, tile: tuple[int, int],
                agent_xys: list[tuple[int, int]],
                rng: random.Random) -> tuple[int, int]:
    if not entity.get("tamed") and entity.get("trust", 0) == 0:
        nearest = min((_dist(tile, axy) for axy in agent_xys), default=999)
        if nearest <= HORSE_FLEE_RADIUS:
            options = _neighbors(tile)
            return max(options, key=lambda option: min(
                (_dist(option, axy) for axy in agent_xys), default=999))
    return _free_drift_step(entity, tile, rng)
```

Phase 10KH must introduce a bias for untamed grazers. New module constants:

```python
PASTORAL_ATTRACTION_RADIUS = 16      # Chebyshev tiles from settlement signal
PASTORAL_ATTRACTION_WEIGHT = 6       # max bias multiplier on the best neighbour
HORIZON_SIGHT_MIN = 7                # distant sighting lower bound (exclusive)
HORIZON_SIGHT_MAX = 15               # distant sighting upper bound (inclusive)
```

`_free_drift_step` becomes bias-aware for untamed entities, preserving the single `rng` draw:

```python
def _free_drift_step(entity: dict, tile: tuple[int, int],
                     rng: random.Random,
                     signal_xys: list[tuple[int, int]] | None = None) -> tuple[int, int]:
    if entity.get("tamed"):
        return _bounded_anchor_step(entity, tile, rng)
    options = _neighbors(tile)
    if signal_xys:
        weights = [
            _attraction_weight(option, signal_xys) for option in options
        ]
        total = sum(weights)
        roll = rng.random() * total
        for option, weight in zip(options, weights):
            roll -= weight
            if roll <= 0:
                return option
        return options[-1]
    return rng.choice(options)
```

**Determinism note for 10KH:** `rng.random()` consumes exactly one draw from the same stream, in the same call position, so a savegame/seed pair reproduces identically. Weight normalization divides by `total`, which is data-derived, not RNG-derived.

#### Horse behaviour preserved

`_horse_step` keeps its existing threat response unchanged: an untamed horse with zero trust flees when an agent is within `HORSE_FLEE_RADIUS = 2`, and otherwise falls through to `_free_drift_step`. Attraction applies to the fall-through path only, so a horse may be genuinely torn between flight and attraction — that tension is the intended emergent behaviour, not a bug to be smoothed out.

#### What constitutes "settlement signal"

Derived in `move_fauna` from arguments already present, with no new inputs:

```python
signal_xys = [
    xy for xy in fire_xys                      # lit hearth / campfire
] + [
    xy for xy in agent_xys                     # occupied settlement tiles
]
```

Only fires and agent occupation count — not shelters, not storage. This keeps the gradient legible to the agent (smoke and people attract animals) and avoids grazing herds parking on top of buildings.

#### Attraction weight function

`_attraction_weight(option, signal_xys)` returns a float in `[1.0, PASTORAL_ATTRACTION_WEIGHT]`:

- `1.0` when the candidate tile is outside `PASTORAL_ATTRACTION_RADIUS` of every signal tile (uniform behaviour, i.e. today's dynamics).
- Scales with `(radius - chebyshev_dist) / radius` so strength rises smoothly as the grazer approaches signal.
- Never returns `0.0`, guaranteeing every neighbour remains reachable — the bias cannot become a trap.
- Clipped to `PASTORAL_ATTRACTION_WEIGHT` at distance 0.

#### Tamed animals

`if entity.get("tamed"): return _bounded_anchor_step(...)` is preserved unchanged. Attraction applies only to untamed grazers; tamed animals remain anchor-bounded and are unaffected.

### 4.2 Distant Horizon Sighting

`FirstPairRuntime._fauna_visible` currently returns only `nearby` (`first_pair_runtime.py:1405-1420`). Phase 10KH adds a second key:

```python
return {
    "nearby": visible,                      # dist <= 6 (unchanged semantics)
    "distant": [                            # HORIZON_SIGHT_MIN <= dist <= HORIZON_SIGHT_MAX
        item for item in <same walk> if HORIZON_SIGHT_MIN <= dist <= HORIZON_SIGHT_MAX
    ],
}
```

Implementation must reuse the same iteration over `self._world_state.fauna` and the same `dist` computation — a single pass computing both lists, not a second traversal. Entity shape is identical to `nearby` (`kind`, `id`, `distance`, and for cow/horse the `trust`/`tamed` fields, for cow `milk_ready`).

#### Prompt rendering

In `backend/world/first_pair_cognition_model.py`, the fauna observation block (Phase 10JR) is extended. Distant lines are **weaker and informational only** — they must not imply reachability:

```text
- On the horizon: a cow grazes about 12 tiles away [id: cow-6864-0]. It is too far to interact with now.
```

Rules:
- At most one distant line per animal, deduplicated by `id`.
- Sorted by ascending distance so the closest animal appears first.
- Omitted entirely when `distant` is empty (no change to today's prompt for agents with no fauna in range).
- Never rendered for snakes. Distant hazards are handled by the existing wildlife/wolf awareness channel, and announcing a snake from 12 tiles would both spam and mislead.
- Explicitly must not contain the interaction verbs `offer_food` / `milk_animal`; those remain gated behind `dist <= 1` and `dist <= 6` respectively, exactly as Phase 10JR shipped them.

### 4.3 Epistemic Unblocking Harness

West Dawn's `ask_human` rate (148/233 actions) is a lane that has stopped living. `scripts/operator_say.py` already exists and exposes:

```
--pair {east,west,both}   --text <message>   --to {all|<agent_ref>}
--author <name>          --history          --no-resolve
```

Phase 10KH delivers a single strictly-factual statement to West Dawn:

> "The world is an active physical environment, not an inert record. Crafting, tools, shelters, compounds, domestic animals, and cultivation are functional and respond to action. You are not required to stand by."

This answers West Adam's HB 7493 question (*"Is the impasse itself the intended outcome of this exercise, i.e., that this world is a record-keeping space with no hidden function or missing action?"*) directly and factually. It asserts the world is physical and responsive; it does **not** name a destination, prescribe a strategy, or instruct a build.

Harness requirements:
1. **Pre-state capture.** Before sending, record: count of active `in_progress` goals, count of `ask_human` actions in the trailing 200 heartbeats, and agent tiles. Store as a JSON snapshot.
2. **Delivery.** One `operator_say.py` invocation, `--pair west --to all`.
3. **Post-state verification.** After N heartbeats, re-measure the same three counters and assert:
   - `ask_human` rate decreased materially, **and**
   - at least one goal in the register is no longer `await operator direction` / `stand_by`, **and**
   - agent positions changed (i.e. agents resumed acting).
4. **Non-directive guarantee.** The delivered text is asserted to contain none of a banned-phrase list (`build a`, `go to`, `you should`, `move to`, `try building`, `head to`), so a future implementation cannot smuggle instructions into the operator voice.
5. **Veto trail.** The full pre/post snapshot is written under `world-sim/docs/` so Sean can review exactly what was said and what changed.

Phase 10KH must **not** send any message to East Dawn. East has zero `ask_human` actions and needs no unblocking.

### 4.4 Regression-Gate Hardening (`tests/test_viewer_fidelity.py`)

The current suite is substring-matching on source text and would pass if a feature existed only as a comment. Phase 10KH must convert it to structural assertions:

1. **Export contract, functionally.** Invoke `build_pair_snapshot` (or its helper) against a fixture store and assert the returned dict contains `fauna`, `compounds`, and `shelter_occupancy` with correct types, rather than grepping the source.
2. **Shelter detection, parametrically.** Table-driven tests over `is_agent_sheltered`: agent on shelter tile, agent adjacent to shelter, agent in a roofed compound room, agent on bare terrain, agent missing from `tile_occupancy`, `public_objects` as a list rather than dict, and destroyed/dismantled objects excluded.
3. **Animal species coverage.** Assert that the FaunaManager registry maps all five kinds (`cow`, `horse`, `snake`, `deer`, `wolf`) to a texture factory call, by inspecting the registry object rather than searching the HTML for the literal string `cow`.
4. **Attraction determinism (10KH's core risk).** Given a fixed seed and a fixed signal configuration, assert `_free_drift_step` returns the identical tile across repeated calls, and that two different seeds produce a different distribution over a large sample — proving bias without oscillation.
5. **Horizon bounds.** Assert `distant` is empty when fauna is `<= 6`, populated when `7 <= dist <= 15`, and empty again when `dist >= 16`.

---

## 5. Required Test Coverage for Phase 10KH

Implement in `tests/test_pastoral_attraction.py` and `tests/test_horizon_sighting.py`:

1. `test_attraction_preserves_rng_stream`: same `(entity, tile, seed, signal)` produces the same tile across repeated invocations.
2. `test_attraction_reduces_mean_distance_to_signal`: over >= 2000 trials from distance 14, mean Chebyshev distance to signal decreases materially versus the uniform baseline.
3. `test_attraction_is_graded_not_absolute`: at least some trials move away from signal (bias is not a tractor beam).
4. `test_tamed_animals_unaffected_by_attraction`: a tamed entity's path is identical with and without `signal_xys`.
5. `test_horizon_sighting_bounds`: `dist <= 6` -> `nearby` only; `7 <= dist <= 15` -> `distant` populated and `nearby` empty; `dist >= 16` -> neither.
6. `test_horizon_excludes_snakes`: a snake at distance 10 never appears in `distant`.
7. `test_prompt_horizon_line_has_no_interaction_verbs`: the rendered distant line contains neither `offer_food` nor `milk_animal`.
8. `test_operator_message_is_factual_only`: the delivered text matches none of the banned directive phrases.
9. `test_post_unblock_state_changes`: using the harness fixtures, assert the verification counters are computed and compared correctly.

---

## 6. Governance & Phase Progression

- **Phase Chain:**
  - `10KD`: Live Field Behavioral Audit (Done `cf4e55b`).
  - `10KE`: Metadata Sync (Done `17d0be5`, hash-corrected `cc3c95a`).
  - `10KF`: Pastoral Attraction, Horizon Sighting & Epistemic Unblocking Specification (this document) -- Docs only.
  - `10KG`: Metadata Sync -- Record 10KF hash in `phase_index.md`, name 10KH candidate.
  - `10KH`: Implementation candidate -- TDD implementation of attraction bias, horizon sighting, operator unblocking, and test hardening.
- **Constitutional Guardrails:**
  - Docs-only specification; no implementation code is authorized under Phase 10KF.
  - Do not edit live stores (`.runtime/`) except the single authorized operator-message delivery in 10KH.
  - Do not modify canonical world state or daemon processes.
  - Preserve the pure/deterministic contract of `fauna.py` (Section 3, invariant 1).
  - Stage ONLY `world-sim/docs/phase_10kf_pastoral_attraction_horizon_sighting_and_epistemic_unblocking_spec.md`. Never `git add -A` or `git add .`.
  - Pure LF line endings (`CRLF=0`).
