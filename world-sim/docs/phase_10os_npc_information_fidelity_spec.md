# Phase 10OS — NPC Information Fidelity (Specification)

## Operator request (2026-11-07)

Operator: "do it big" on the NPC-improvement menu. This spec covers all three
measured problems at once: (A) kinder rejection messages, (B) operator-answer
pinning in prompt selection, (C) an honest resource roll-up. Docs-only;
implementation is Phase 10OU. Phase chain: 10OS (spec) → 10OT (metadata sync)
→ 10OU (implementation candidate, not started).

## Measured problems (live lanes, 2026-11-07)

- West Eve: 258 build actions today, 245 rejected, holding 124 wood / 0
  timber at tick 11152. Adam holds 204 timber, so the lane has timber —
  Eve's feedback loop is a wall, not a lesson.
- West both: 58 ask_human (Eve) + 14 (Adam) in 764 heartbeats; Eve repeated
  the stone question 5 times unheard (hb 10882–11040) after earlier answered
  stone questions. East Adam asked the collapsed-eat question 5 times across
  two days. Answers land in the operator channel but compete for prompt
  slots and fall out.
- Both lanes: `known_map_*` `observed_resources` is empty even after 100+
  visits to one tile (cont_b_gen_33_57, Eve, 103 visits). Gather only yields
  on a tile that lists the resource, so the agents forage blind. East Adam
  holds 618 stone; Eve holds 476 berries — they gather what they stumble on.

## Root causes (verified in source)

- A: `_execute_build` (first_pair_runtime.py ~2741) rejects with
  "Insufficient {kind}: need {amount}, hold {holdings}" — it names the
  shortfall but not what the agent holds overall. `_execute_gather` (~2502)
  rejects with "No {resource} available on this tile" without naming what
  the tile *does* list (`_current_tile_resources` is right there). Duplicate
  object_id rejection (~2631) names nothing about the existing object.
  `_recent_action_failure_line` (first_pair_cognition_model.py ~1120)
  surfaces the last two reasons in the prompt, truncated to 120 chars — so
  richer reasons must stay compact or they get cut.
- B: `select_human_context` (first_pair_persistence.py ~906) caps human
  context at 4 combined records, scored by active-goal text match (+100),
  pending before answered (+10), recency. Answered operator answers to
  non-goal-matched questions lose to pending questions and fall out of the
  prompt. Operator messages themselves fire once per agent (seen gate,
  first_pair_runtime.py ~1382), then vanish from the prompt unless memory
  selection keeps them — private memories are also bounded (6 recent +
  relevant), so nothing guarantees the answer stays visible.
- C: `merge_observation_into_known_map` (fog_of_war.py ~412) *does* union
  tile resources into `observed_resources`, but the live known maps are out
  of sync with that path: seeded entries start `observed_resources: []`
  (first_pair_fog_adapter.py ~186/208) and the lane maps were never
  repopulated. The prompt has no resource roll-up line at all — the agent
  never sees "tiles you have visited listed stone".

## Fix (backend, information only — no directives)

A. **Kinder rejections.**
1. Insufficient-materials: keep "need X, hold Y", append the compact full
   holdings summary ("holdings: timber 0, wood 124, stone 5") — fact, not
   advice. Must fit the 120-char failure-line window or shorten the prefix.
2. Gather on an empty tile: name the tile's actual resources
   ("No stone available on this tile; it lists: clay, wild_berries") or
   "it lists nothing gatherable" when empty.
3. Duplicate object_id: name the existing object's type and tile
   ("Duplicate object_id: X already exists as a shelter on tile Y").

B. **Operator-answer pinning.** In `select_human_context`, the most recent
   *answered* record is always selected (pin slot), even when it loses the
   goal-match scoring; the remaining 3 slots keep the existing scoring, cap
   stays 4, ordering stays deterministic. Answered operator *messages*
   (not just answered questions) that answered the agent's most recent
   question count the same way. No cap change, no prompt growth.

C. **Honest resource roll-up.**
1. Ensure `observed_resources` actually populates from observations in the
   lane runtime path (root-cause in implementation: adapter vs merge path).
2. Add one factual prompt line, e.g. "Resources observed on visited tiles:
   stone — cont_b_gen_50_46; clay — …" built from the agent's own known map
   only (never the true map), in the same register as the settlement lines.
   Absent when empty. No banned directive phrasing anywhere.

## Verification plan

1. TDD first: unit tests for each rejection string (holdings summary,
   tile resource naming, duplicate naming), for the pin (answered survives
   4 pending competitors, deterministic), for the roll-up (own-map only,
   empty-absent, no unobserved tiles).
2. Banned-phrase scan over all new strings (the Standing Rule 7 list:
   "build a", "go to", "you should", "move to", "try building", "head to").
3. Existing suites: load-bearing construction, goal hygiene, perception —
   plus the full CI list. lockstep_chain spawns fresh subprocesses per
   heartbeat, so the fix goes live with no restart.
4. Live lanes need no patch: the phase changes only feedback/selection
   strings; no capability grants, no canonical changes, no `world-sim/data`
   writes in tests (tempdir only).

## Out of scope

No taming levers (measured negative, Phase 10OD/10OF), no free timber/build
discounts, no teleport, no goal injection, no new actions, no viewer
changes, no fauna affordance resurrection. Facts only; the agents keep
choosing. A change a human operator would have to message the agents about
belongs in the operator channel, not in code.
