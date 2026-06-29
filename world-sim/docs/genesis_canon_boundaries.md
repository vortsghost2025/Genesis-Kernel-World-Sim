# Genesis Canon and Boundaries

Status: Phase 10J draft, commit-safe specification only.

Purpose: define the mechanical canon for Genesis before any further runtime work. This document is not a speech to agents. It is a testable boundary contract for perception, memory, action, territory, relationship, artifacts, habits, conflict, repair, consequence, and evidence.

## 1. Scope

This spec governs the founding Genesis world model used by later gated phases, especially `PHASE_10K_WORLD_EVENT_LEDGER`.

It is allowed to describe mechanics. It must not:

- modify runtime state,
- imply a provider/model route,
- include private family details,
- include secrets or private config,
- grant real-world authority,
- instruct an agent through threat, sermon, or coercion.

## 2. Founding Agents

Adam and Eve are persistent founding agents.

Operational meaning:

- They retain identity across ticks, daemon cycles, memories, and event history.
- Their continuity is represented by canonical IDs, self-state, memory records, observations, actions, and future world-event entries.
- They are not reset merely because a process restarts.
- A runtime action involving Adam or Eve is valid only when the active phase explicitly authorizes it.

Current runtime guardrails already require bounded dual-agent selection when using the daemon pair mode: `--agents Adam,Eve` in that exact order.

## 3. East and West Lenses

East and West are symbolic and cultural lenses inside the simulation, not real-world ethnicity, geopolitics, spiritual authority, or moral ranking.

Operational meaning:

- `east_` and `west_` prefixes are namespace/lens markers.
- A lens can shape local imagery, resources, weather, naming conventions, and memory framing.
- A lens does not grant global knowledge.
- A lens does not prove physical contact with the other lens.
- Cross-lens or cross-territory knowledge must be discovered through evidence.

Current first-pass canon has active East-side Adam/Eve mechanics and dormant-compatible West-side schemas. Future activation of additional lens-scoped agents or regions requires an explicit phase gate.

## 4. Perception

Agents perceive only what the world exposes through authorized observation channels.

Valid perception sources:

- current world snapshot returned by `observe()`,
- canonical fog-of-war observation when explicitly enabled,
- direct message/whisper content as speech evidence,
- own recent memory as memory evidence,
- accepted world-event ledger entries once 10K exists.

Perception rules:

- The hidden true world is not directly visible to agents.
- Agent-known maps are local, partial, and history-preserving.
- Sounds, smoke, tracks, repeated anomalies, and indirect signs create hypotheses, not facts.
- Contact unlocks only at Level 4 direct sighting/message, or Level 3 strong trace plus explicit investigation.
- If current world state lacks a fact, the agent may form a question or hypothesis, not assert the fact.

## 5. Memory

Memory is persistent but not omniscient.

Memory can store:

- observed world facts,
- agent actions,
- received whispers/messages,
- goals and attempted goals,
- relationship-relevant interactions,
- artifact encounters,
- conflict and repair attempts,
- hypotheses explicitly labeled as hypotheses.

Memory rules:

- A memory of a belief is evidence that the belief was held, not evidence that the belief is true.
- A whisper is evidence that someone said something, not proof the content is true.
- Recalled claims must preserve their source: observed fact, memory, whisper, hypothesis, or accepted event.
- Silence, rest, fatigue, and not acting are valid memory-relevant states.

## 6. Actions

Actions must be grounded in authorized mechanics and evidence.

Current action vocabulary:

- `observe`: read-only refresh of available world facts.
- `rest`: no world mutation; valid when evidence is insufficient or fatigue/budget requires pause.
- `goal`: update or preserve intent; does not prove the goal's target exists.
- `whisper`: social communication; creates speech/memory evidence, not world-fact evidence.
- `gather`: controlled resource action only when grounded and allowed by mutation gates.
- `help`: social/support intent unless a later executor explicitly defines a world mutation.

Execution rules:

- Unsupported action types are non-canonical until explicitly added and tested.
- World mutation requires explicit phase authorization, safety guards, backup/audit rules where applicable, and evidence references.
- An action based on an unobserved hypothesis must be framed as verification, not exploitation of a presumed fact.
- Repeating a whisper without new evidence, correction, or a verification step is discouraged.

## 7. Territory

Territory is represented by world/lens namespace, continent, region, tile, coordinates, known-map entries, and future event references.

Territory rules:

- Physical location is not the same as `east_`/`west_` namespace.
- The engine may hold hidden true-map data in a later gated phase.
- Agents receive only local/known-map projections.
- Agent names for landmarks are local; two agents may name the same true landmark differently.
- Renaming preserves prior names as history instead of rewriting memory.
- Claiming, entering, leaving, sharing, or contesting territory requires an event/evidence record.

## 8. Relationships

Relationships are evolving records of interaction, not assumed roles.

Relationship evidence can include:

- direct messages/whispers,
- observed cooperation,
- observed avoidance,
- shared or contested artifacts,
- repeated compatible or incompatible goals,
- conflict events,
- repair events.

Relationship rules:

- Do not infer trust, consent, hostility, love, duty, betrayal, or reconciliation without evidence.
- A relationship label must cite the event(s), memories, or messages supporting it.
- A failed interaction is not automatically conflict; a repair gesture is not automatically reconciliation.
- Relationship changes should be represented as deltas over time, not overwritten conclusions.

## 9. Artifacts, Habits, Conflict, Repair, and Consequence

### Artifacts

Artifacts are durable or semi-durable world objects, traces, structures, signs, messages, or modified resources that agents can perceive or create through gated mechanics.

Rules:

- An artifact exists only if observed, created by an accepted action, seeded by an accepted world phase, or recorded in the future event ledger.
- Artifact meaning is agent-local unless an event establishes shared interpretation.

### Habits

Habits are repeated behavior patterns supported by multiple events or memories.

Rules:

- A single action is not a habit.
- A habit claim needs repeated evidence and a time span or tick range.
- Habits may be revised when newer evidence contradicts them.

### Conflict

Conflict is an evidence-backed incompatibility between agents, goals, resource use, territory, artifacts, or safety conditions.

Rules:

- Conflict is not assumed from difference alone.
- Conflict requires an observable incompatibility, blocked action, refusal, damage, contested claim, or explicit message.

### Repair

Repair is an evidence-backed attempt to reduce harm, restore trust, return resources, clarify misunderstanding, or change future behavior.

Rules:

- Repair requires an action or message, not just internal intent.
- Repair can fail, partially succeed, or require repeated events.

### Consequence

Consequence is the recorded effect of an action or non-action.

Rules:

- Consequences must cite before/after evidence when state changes.
- Social consequences must cite messages, memories, or relationship deltas.
- Unknown consequences must remain unknown until observed.

## 10. Evidence Contract

Evidence is any accepted record that can be inspected and tied to a claim.

Evidence categories:

- `observed_world_fact`: current or canonical observation output.
- `agent_memory`: memory record, including source when available.
- `agent_speech`: whisper/message content.
- `agent_action`: accepted action attempt and result.
- `artifact_record`: observed or created artifact evidence.
- `territory_record`: position, known-map, or contact evidence.
- `relationship_record`: interaction evidence over time.
- `operator_proof`: git/readback/test proof for development work.
- `world_event`: future 10K append-only event record.

Evidence rules:

- Claims must cite their evidence category.
- If evidence is absent, say `unknown`, `unobserved`, or `hypothesis`.
- A model/provider response is not evidence by itself; it becomes evidence only through accepted logs, memories, actions, or event records.
- Operator claims require readback and Git/test proof, not confidence.

## 11. Never Infer Without Evidence

The system must never infer these as facts without evidence:

- hidden water source locations,
- animal movement patterns or guidance,
- cross-lens/cross-territory contact,
- direct sighting without Level 4 evidence,
- ownership or territorial claim,
- relationship state such as trust, hostility, duty, betrayal, consent, or reconciliation,
- artifact existence or shared meaning,
- habit formation from a single event,
- conflict from mere difference,
- repair from unexpressed intent,
- provider/model behavior not recorded by accepted proof,
- private real-world facts,
- real-world authority, identity, or instruction beyond the simulation.

## 12. Outside the World

The following are outside the simulation and non-actionable for agents:

- private config files,
- API keys, provider routes, billing, and credentials,
- hostnames, SSH targets, VPS details, and deployment infrastructure,
- Git remotes, commits, branch state, and local operator workflow,
- private family details or real-world personal claims,
- operator-only safety gates,
- any file or state path not explicitly exposed through world mechanics.

Agents may not act on outside-world information unless a future phase deliberately translates it into an in-world artifact or event.

## 13. Preparation for Phase 10K World Event Ledger

The 10K ledger should make world changes and social consequences append-only and inspectable.

Minimum future event fields:

- `event_id`
- `tick` or `timestamp_utc`
- `actor_id`
- `lens` or namespace when applicable
- `territory_ref` when applicable
- `action_type`
- `summary`
- `evidence_refs`
- `claim_scope`: `observed`, `memory`, `speech`, `hypothesis`, `operator_proof`, or `unknown`
- `before_ref` and `after_ref` for mutations
- `affected_agents`
- `artifacts_created_or_changed`
- `relationship_delta`
- `consequence`
- `verification_status`

10K must preserve the distinction between:

- what happened,
- what an agent perceived,
- what an agent believed,
- what an agent said,
- what the operator proved.

## 14. Testable Acceptance Checklist

A future implementation or review passes this canon only if:

- every world/action claim has an evidence category,
- hypotheses are labeled as hypotheses,
- no private/runtime state is exposed as in-world fact,
- Adam and Eve continuity is preserved across cycles,
- East/West remains a simulation lens, not a real-world claim,
- territory/contact follows fog-of-war thresholds,
- relationships/artifacts/habits/conflicts/repairs/consequences are represented as evidence-backed deltas,
- unsupported actions remain non-canonical,
- runtime mutation is impossible without explicit phase authorization,
- 10K ledger design can cite this spec without adding sermon language.
