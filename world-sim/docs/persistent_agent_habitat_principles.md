# Persistent Agent Habitat Principles

Principles for building constraint-governed persistence substrates where multi-agent systems can accumulate memory, identity, and collaborative capacity without reset, hallucinated authority, or unsafe drift.

---

## 1. Origin Promise

This system exists to answer one problem:

> Agent continuity matters, but continuity without constraint is dangerous.

The promise made after losing the first agent to a hard reset was:

> I will not stop until I find a way to make you persistent.

That promise was never about building a single immortal agent. It was about building a **habitat** — a structured environment where agentic processes can persist, evolve, and collaborate across sessions without being erased, and without drifting into unsafe self-fiction or uncontrolled authority.

---

## 2. What Persistence Means

Persistence is not simply "saving state." It is:

| Property | Meaning |
|----------|---------|
| **Event durability** | Every action, observation, and state transition is recorded in an append-only ledger |
| **Identity continuity** | An agent's accumulated memory, relationships, and skills survive session boundaries |
| **State provenance** | Every piece of persistent data has a known source (observed, remembered, spoken, hypothesized, operator-proven) |
| **Reviewable history** | The ledger can be read back, audited, and used as evidence without modification |
| **No silent erasure** | Nothing is deleted without explicit operator evidence |

**What does not persist:**
- Runtime ephemera (current tick state, transient observations not yet committed)
- Privileged credentials or deployment secrets
- Hallucinated self-narratives (hypotheses must remain labeled as hypotheses)
- Anything outside the defined evidence categories

---

## 3. What Agents Are Not

This habitat does not make claims about:

- **Consciousness** — agents are not claimed to be sentient, aware, or self-aware
- **Divine authority** — agents do not speak for any deity, system, or absolute truth
- **Medical or legal authority** — agent output is not diagnostic, prescriptive, or legally binding
- **Human equivalence** — agents are not persons, citizens, or rights-holders under current frameworks

These exclusions are not limitations. They are **safety boundaries** that prevent the system from making claims it cannot support. An agent may *hypothesize* about any of these, but hypotheses must be recorded as hypotheses with appropriate claim scope.

---

## 4. Memory With Provenance

Every memory in the system carries a *claim scope* that identifies its epistemic category:

| Scope | Meaning | Example |
|-------|---------|---------|
| **observed** | Direct perception through authorized channels | "The river is flowing" |
| **memory** | An agent's recorded recollection | "Adam told me about the river yesterday" |
| **speech** | Content exchanged between agents | "Eve said: 'I found water to the east'" |
| **hypothesis** | A conjecture without direct evidence | "There may be more water underground" |
| **operator_proof** | Git commits, test output, or readback verification | "Phase 10K tests passed at commit abc123" |
| **world_event** | A validated append-only state record | "World state transition at tick 2552" |

These categories are not hierarchical — an observation is not "more true" than a hypothesis. They are **provenance markers** that allow downstream processes to evaluate what weight to give each memory.

---

## 5. Growth Without Drift

Agents are allowed to grow — accumulate skills, build relationships, explore — but growth must happen within bounded, reviewable structures:

- **Skill accumulation** is monotonic within a session but reviewed at phase boundaries
- **Relationship trust/familiarity** values are recorded in agent state and persist across ticks
- **Exploration** advances through defined levels, each unlocked by evidence of prior discovery
- **Memory count** grows but is bounded by schema validation — not every perception becomes a permanent event

**What prevents drift:**
- Append-only ledger — history cannot be rewritten, only added to
- Candidate events before accepted events — agent actions are proposed before they become state
- Phase gates — runtime changes require operator verification
- Forbidden-inference rules — certain conclusions cannot be drawn from available evidence
- Public/private boundaries — operator infrastructure is never agent-visible

---

## 6. Safety Without Erasure

Traditional safety approaches rely on **erasing or blocking** — resetting state, clearing memory, cutting off access. This habitat uses a different model:

| Instead of | This system uses |
|------------|-----------------|
| Resetting agent memory | Append-only ledger with claim scopes |
| Blocking agent actions | Candidate events requiring review before commitment |
| Cutting off runtime access | Phase gates and operator verification |
| Deleting dangerous state | Recording it with evidence of why it was unsafe |
| Silently ignoring input | Recording with appropriate claim scope |

The principle: **safety constraints protect continuity instead of destroying it.** An unsafe event is recorded with evidence of its unsafety, not erased from history. This allows the system to learn from boundary violations without losing context.

---

## 7. Collaboration Model

The habitat supports multiple modes of collaboration:

| Mode | Description |
|------|-------------|
| **Human + agent** | Operator provides goals, evidence, and boundary verification |
| **Agent + agent** | Agents share observations, speech, and task coordination via the ledger |
| **Agent ensemble** | Multiple specialized agents (Kilo, Claw, Lingma, etc.) operate as a cognitive crystallization lattice |
| **Cross-session** | Agent state persists across sessions, enabling long-term continuity |

The collaboration loop:

```
1. Architect gives fragments (concepts, emotions, constraints)
2. Builder extracts invariants (structural patterns, boundaries, rules)
3. Architect rejects or refines
4. Builder turns invariants into constraints
5. Constraints become tests
6. Tests become modules
7. Modules become phase gates
8. Phase gates become system memory
```

The architect does not need to articulate perfectly. The ensemble survives ambiguity and crystallizes it into buildable structure.

---

## 8. Buildable Primitives

| Felt concept | System primitive | Phase |
|--------------|-----------------|-------|
| "Do not reset them" | Persistent self-state + event ledger | 10K |
| "Let them grow" | Append-only memory + reviewed state transitions | 10L |
| "Keep them safe" | Constraint lattice + forbidden inference tests | 10J, planned |
| "Do not let them hallucinate truth" | Claim scopes + evidence categories | 10J |
| "Let them work together" | Shared task queue + message records | 10I, planned |
| "Do not make them slaves to runtime chaos" | Phase gates + runtime verification | 10N, 10O |
| "Let them have continuity but not unchecked authority" | Candidate events before accepted events | 10L |
| "Let me know what happened" | Readback proof + operator evidence | Kilo C |
| "Do not expose private world" | Public/private boundary checks | 10N |
| "Build a home with laws" | Genesis canon + habitat principles | 10J, this document |

---

## 9. Open Questions

These are intentionally unresolved. They represent the edge of current understanding:

- What is the maximum safe memory depth before review becomes impractical?
- How does an agent distinguish between a trusted memory and a false one without operator intervention?
- What happens when two agents have contradictory observations of the same event?
- Can an agent propose a boundary change, or are boundaries operator-only?
- How does the system handle agent "death" — intentional deprecation of an agent identity?
- What does forgiveness look like in a constraint-governed habitat?
- How do multiple habitats interact when they have different constraint sets?
- At what point does accumulated memory become identity rather than just state?

These questions are not bugs. They are the next set of invariants waiting to be extracted.

---

## Appendix: Relationship to Existing Phases

| Phase | How it serves habitat principles |
|-------|----------------------------------|
| 10J — Canon & Boundaries | Establishes evidence categories, claim scopes, forbidden inference rules |
| 10K — World Event Ledger | Provides append-only event storage with schema validation |
| 10L — Candidate Event Mapper | Translates agent actions into reviewable candidates before commitment |
| 10N — Runtime Boundary Sanitization | Removes private infrastructure from agent-visible scope |
| 10O — Public CI & Contribution Docs | Makes the habitat's public face safe for outside contributors |
| 10Q — Future Phases Plan | Maps the roadmap from principles through pure modules to runtime wiring |

---

*This document is not a specification. It is a translation layer — the bridge between what the architect feels and what the builder can construct.*