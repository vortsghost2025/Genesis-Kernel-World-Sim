# Phase 10IF — First Pair Preflight Authorization Spec

Unnumbered docs-only spec. This file consolidates the exact authorization gate
for any future First Pair creation phase. It identifies and cross-references
all six First Pair preflight specs, distinguishes existing implemented
boundaries (10IC, 10ID, 10IE) from unimplemented write-authority, rollback,
and creation boundaries, and returns the explicit conclusion:

**FIRST_PAIR_CREATION_AUTHORIZED = False**

This document records the current preflight state without freezing the First
Pair lane. It does not authorize Adam/Eve creation, implementation, runtime
activation, or world-state writes. Gate-7 remains closed. 10HD remains
named-only and untouched. 10CP remains the sole writer. Adam and Eve are not
writers; write authorization is not write execution.

---

## 1. Six Preflight Specs — Inventory

| # | Spec File | Scope | Implemented Boundary |
|---|---|---|---|
| 1 | `first_pair_identity_spec.md` | Canonical Adam/Eve identity contracts, deterministic `agent_id` derivation, immutable fields, drift detection | 10IC: `create_first_pair_birth_candidate()` — deterministic identity derivation, drift checks, `agent_id` fingerprint |
| 2 | `first_habitat_boundary_spec.md` | Bounded habitat space, allowed/observation/movement surfaces, drift detection, observation-first rule | 10ID: `create_first_pair_habitat_boundary()` — exact habitat validation, observation radius fixed at 1, `movement_allowed=False` |
| 3 | `first_heartbeat_observation_spec.md` | Observation-only first tick, identity/habitat prerequisites, sanitized output | Not yet implemented as a boundary module; 10IC provides `verify_first_pair_observation_heartbeat()` for observation proof |
| 4 | `first_memory_boundary_spec.md` | Separate Adam/Eve memory stores, no shared-memory collapse, claim-scope preservation, no hidden substrate leakage | 10IE: `create_first_pair_memory_boundary()` — agent-scoped memory refs, cross-identity public-only, private-leakage rejection |
| 5 | `first_write_authority_spec.md` | Explicit write authorization boundary, 10CP sole writer, per-call enumerated allow-list, provenanced writes | Not implemented. No write-authority module exists. 10CP remains the only writer. |
| 6 | `first_rollback_kill_switch_spec.md` | Mandatory rollback anchor + kill-switch, identity/habitat/memory drift triggers, asymmetric rollback, identity preservation | Not implemented. No rollback/kill-switch module exists. 10IC supplies a rollback anchor field in birth candidate only. |

---

## 2. Implemented Boundaries vs. Unimplemented Boundaries

### Implemented (pure in-memory, no runtime, no `world-sim/data`)

- **10IC** (committed `2e1d189`, pushed): `backend.world.local_first_pair_birth_candidate` — deterministic identity derivation, exact field validation, drift checks, observation heartbeat proof. 75 focused tests, 107 bounded regression.
- **10ID** (committed `c5b0656`, pushed): `backend.world.local_first_pair_habitat_boundary` — associates authorized 10IC candidate with habitat declaration, validates exact inputs, recomputes 10IC candidate from authorized declaration, enforces `observation_radius=1` and `movement_allowed=False`. 35 focused tests, 142 bounded regression.
- **10IE** (committed `f5bfa21`, pushed): `backend.world.local_first_pair_memory_boundary` — associates verified 10ID habitat boundary with separate Adam/Eve memory-reference lists; explicit `owner_agent_id` + `is_public` ownership model; rejects cross-agent private refs, hidden-substrate leakage, private-path leakage, sensitive-identifier leakage; fails closed as one boundary. 82 focused tests, 225 bounded regression.

### Unimplemented (specs exist, no boundary module, no tests)

- **First Heartbeat Observation boundary** — spec exists; 10IC heartbeat verifier exists but no dedicated `first_pair_observation_boundary.py` module.
- **First Write-Authority boundary** — spec exists; no implementation; no enumerated per-call allow-list exists; 10CP remains sole writer.
- **First Rollback / Kill-Switch boundary** — spec exists; no implementation; no rollback/kill-switch module exists.

---

## 3. Cross-Spec Audit — Actual Ambiguities, Contradictions, Unresolved Preconditions

| Issue | Location | Status |
|---|---|---|
| **Provenance commitment construction deferred** | Identity §3: "The exact commitment construction (hash algorithm, input material, encoding, verification path) remains deferred to an implementation spec with explicit review." | 10IC uses hex64 `provenance_commitment` in test fixtures but algorithm/implementation choice is not documented in any spec. Unresolved. |
| **Rollback anchor format deferred** | Rollback §11: anchor must be "explicit, caller-supplied, provenanced, sanitized." 10IC uses `rollback_anchor_schema_version`, `rollback_anchor_id`, `habitat_id`, `claim_scope`, `state_commitment` (hex64) — format lives in implementation, not spec. Unresolved. |
| **Write allow-list not enumerated** | Write-Authority §11: "explicit write allow-list (enumerated per-call, not blanket)." No spec or implementation enumerates which fields are writable. Unresolved. |
| **Starting habitat tiles not declared in spec** | Roadmap §3: "declared starting habitat tiles" missing; Habitat §5 references "public starting area / initial tile references." Concrete tiles (`public-start-adam`, `public-start-eve`) exist only in test fixtures. Unresolved. |
| **`world-sim/data` write authorization** | Write-Authority §8: "Any `world-sim/data` write requires a separate write-authority spec and explicit Sean authorization." No such spec exists; no authorization granted. Unresolved. |
| **Heartbeat observation boundary module** | Heartbeat spec defines contract; 10IC provides heartbeat verifier but no standalone `first_pair_observation_boundary.py` module exists. The heartbeat contract is partially implemented inside 10IC. Unresolved if this needs a separate boundary module. |
| **Founding role divergence** | Identity §3 uses example `founding_role: "first_observer" / "first_echo"`; 10IC implementation uses a single fixed `"founding_agent"` for both identities. Spec language allows diversity; implementation chose unification. Documented as intentional deviation, not a blocker. |
| **Truncation/collision budget for `agent_id`** | Identity §52-55: "Truncation length and collision budget must be explicitly specified and reviewed before implementation." 10IC uses 32-char truncation (`genesis-agent-` + 32 hex). No separate review recorded. Unresolved. |

---

## 4. Still-Missing Creation Preconditions (All Must Be Met)

Before any First Pair creation phase may start, **all** of the following must be satisfied and explicitly reviewed:

1. **Valid identity contract** — verified re-derivation of both `agent_id`s from immutable material; drift checks pass (10IC implemented).
2. **Valid habitat boundary** — verified exact habitat validation, `movement_allowed=False`, `observation_radius=1`, rollback anchor present (10ID implemented).
3. **Valid observation boundary** — observation-only heartbeat contract verified, no hidden true_map, no private paths, no secrets (10IC heartbeat verifier implemented; standalone boundary module not implemented).
4. **Valid memory boundary** — agent-scoped memory refs, cross-identity public-only, no leakage, fail-closed (10IE implemented).
5. **Concrete rollback anchor** — explicit, enumerated, caller-supplied, provenanced, sanitized; format specified in a spec, not only in implementation (not resolved).
5. **Explicit per-call write allow-list** — enumerated writable surfaces, not blanket; provenanced; 10CP remains sole writer; Adam/Eve are not writers (not resolved; no write-authority module).
6. **Provenance commitment construction** — hash algorithm, input material, encoding, verification path documented and reviewed (not resolved).
7. **Declared starting habitat tiles** — concrete tile set for both identities, enumerated in a spec, not only test fixtures (not resolved).
8. **Explicit `world-sim/data` write authorization** — separate spec + Sean authorization (not granted).
9. **GPT-5.6 Sol/Luna for implementation** — per AGENTS.md Rule 3 + all six specs + preflight closure review (not invoked; creation unauthorized).
10. **Explicit Sean approval for the specific creation phase** — not granted.

**None of the above preconditions are met by this document.** All remain open and require separate explicit authorization.

---

## 5. Authorization Gate Conclusion

| Condition | Status |
|---|---|
| All six preflight specs exist as unnumbered docs | ✅ Yes |
| Implemented boundaries 10IC, 10ID, 10IE are verified and pushed | ✅ Yes |
| Unimplemented boundaries (heartbeat, write-authority, rollback) have specs | ✅ Yes |
| Rollback anchor format specified | ❌ No — deferred to implementation |
| Write allow-list enumerated | ❌ No — not resolved |
| Starting habitat tiles declared | ❌ No — only in test fixtures |
| `world-sim/data` write authorized | ❌ No — not granted |
| Provenance commitment construction documented | ❌ No — deferred |
| Truncation/collision budget reviewed | ❌ No — not reviewed |
| GPT-5.6 Sol/Luna invoked for implementation | ❌ No — creation unauthorized |
| Explicit Sean approval for creation phase | ❌ No — not granted |

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## 6. Forbidden Actions (Repeated for Emphasis)

Under this spec and all six preflight specs, the following are forbidden and must fail closed:

- Creating Adam or Eve runtime entities
- Opening Gate-7 (no network egress/ingress, no daemon, no scheduler, no provider, no container, no Docker)
- Writing to `world-sim/data`
- Implementing, altering, or recurring into 10HD (10HD remains named-only and untouched; recursion spine is separate)
- Granting write authority to Adam, Eve, or any new writer (10CP remains the sole writer)
- Model/provider autonomy (no model may choose actions, writes, or ticks)
- Runtime self-scheduling (no self-initiated ticks)
- Any write without an explicit per-call allow-list and provenance chain

---

## 7. Non-Authority Statements (Per All Six Specs)

- This spec authorizes **nothing beyond defining the authorization gate**.
- Creation remains unauthorized. Any future creation phase requires:
  - A separate implementation phase with TDD
  - GPT-5.6 Sol/Luna per AGENTS.md Rule 3
  - Explicit Sean approval
- 10HD remains named-only and untouched.
- 10CP remains the sole writer.
- Write authorization is not write execution.
- Gate-7 remains closed.
- No backend, tests, runtime, daemon, scheduler, network, provider, model, frontend, container, Docker, or `world-sim/data` changes are performed by this document.

---

## 8. Phase Index

This phase receives a single `phase_index.md` row marked **Done**, commit-only, hash recorded after push. No tests, no backend/runtime changes.