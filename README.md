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

## Current Status

The public stack now reaches Phase 10AE, the public egress boundary harness that proves exported world-event output passes through the sanitizer before becoming public-facing text.

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
    tests/test_phase10ae_public_egress_boundary_harness.py -v
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
