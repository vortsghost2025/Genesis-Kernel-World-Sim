# Survival Physics — "you have a body now" (epistemic.4)

**Date:** 2026-10-18 · **Physics version:** `epistemic.4` · **Module:** `backend/world/survival.py` · **Tests:** `tests/test_survival_physics.py`, `tests/test_survival_runtime_wiring.py`

## Why

Sean, watching the sim at heartbeat ~3,850: *"they don't build shelter cause there is no environment, it's not cold or hot, they don't have to worry about animals, they don't get hungry, so there's no incentive to figure out fire, food, storage, defenses, things that force them to build shelter not just wander aimlessly."*

He named the design flaw exactly. An unpressured world produces wandering and philosophy, because those are rational responses to a world that asks nothing.

## What the board said first

`scripts/audit_tile_resources.py` (the standing guard the retired model left us): 21,358 berry tiles, 4,278 mushroom, 2,596 edible-roots, 1,806 fish, 1,126 shellfish. **The world is an abundant garden.** Food scarcity must not be the pressure — that is the exact rock pressure-v1 died on (income == consumption pinned `east_adam` at zero for 100+ heartbeats; he reported it as a bug and was right; the East pair's 0% build rate was correct refusal, misread as apathy).

The scarce resources are **time, warmth, and safety**. That is what epistemic.4 taxes.

## The body

Three vital tracks per agent, in `world_state.vitals[agent_ref]`, shown every heartbeat in the observation under `self_body`:

| track | behavior |
|---|---|
| `hunger` | +1.4/heartbeat, capped 100. Eating (new `eat` action) consumes 1 unit of carried food and subtracts its satisfaction. Raw berries 18, mushrooms 14, roots 22, fish 26, shellfish 20; **cooked ×2.5** (fire matters). |
| `warmth` | drifts toward ambient temperature (10%/heartbeat of the gap). Ambient = seasonal base + day/night sine (72 heartbeats/day; spring 55, summer 72, autumn 46, winter 26, ±13 swing). **Fire within 3 tiles: +9/heartbeat toward 100.** Shelter adjacent: cold drain ×0.45 (shelter holds warmth; it does not create it). |
| `vitality` | −0.6/hb while hunger ≥ 88; −0.8/hb while warmth ≤ 20; +0.5/hb while fed (≤45) and warm (≥50). At 0 → **collapse**: downed, all actions refused except a cry for help; passive recovery 0.15/hb capped at 12 (the stand threshold); food eaten while down still satisfies. Collapse is recoverable — the stake is the story, not permadeath. |

Time of day, season, and temperature ride in every observation under `environment`, along with `by_fire` / `sheltered` flags.

## The invariants the old model violated

1. **Slack.** From fed (18), ~50 heartbeats before weakening. A gather trip (walk + 2–3 gathers ≈ 12 heartbeats) nets 1.5× its hunger cost on any healthy tile. Expeditions pay. Tested: `test_a_gather_trip_nets_more_than_it_costs`.
2. **No impossible boards.** Hunger caps at 100 and only *weakens* — it never zeroes the ability to walk to food. The v1 trap (income == consumption → correct refusal misread as apathy) is structurally unreachable.
3. **No accountant minds.** No caps on holdings, no overcapacity goods. Pressure is on the *body*, not the ledger.
4. **Migration without famine.** Existing agents seed at hunger 18 / warmth 82 / vitality 100. They learn the new terms from the epistemic.4 changelog (delivered once via the existing terms gate), not by waking mid-crisis.

## Deliberately not in v1

- **Predators / night threats** — the defense chain. Comes as phase 2, after settlement behavior exists to defend. A threat system built now would punish camps that don't exist yet.
- **Cooking** — the `cooked_meal` satisfaction key exists; the smelt/craft recipe that produces it comes with the first campfire, so cooking is *discovered*, not announced.
- **Farming** — tiles deplete (measured: `GATHER_YIELD=1` against finite tile pools); if depletion outranges walking, planting becomes the next mechanic. Not scheduled. Let the world ask first.

## The chain this buys

hunger → gather → **storage** (depleted tiles + night trips make stockpiles rational) · night cold → **fire** → fuel gathering · warmth drain → **shelter** · vitality collapse → **rescue** (a downed agent eats from their tile; the partner decides whether to bring food) · seasons → **planning** (winter is survivable; unprepared winter is not comfortable).

Nothing in the changelog tells the agents what to do about any of this. The world imposes; they discover.
