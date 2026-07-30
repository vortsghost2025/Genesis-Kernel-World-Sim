# Phase 10IF — First Pair Preflight Authorization Spec

Numbered docs-only authorization spec. This file consolidates the exact authorization gate
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
| **Provenance commitment construction (docs-level)** | Identity §3: "The exact commitment construction (hash algorithm, input material, encoding, verification path) remains deferred to an implementation spec with explicit review." | 10IL ("First Pair Provenance Commitment Source-Envelope Specification") now defines the source-envelope schema, canonical serialization, SHA-256 commitment derivation, and a 40-item acceptance-test table. **Docs-level design complete. Runtime implementation not performed.** 10IC still validates only hex64 shape. Operator-approval binding remains unresolved. |
| **Rollback anchor envelope format documented** | Rollback §11: anchor must be "explicit, caller-supplied, provenanced, sanitized." | Phase 10IH now documents the exact five-field envelope format and validation rules enforced by 10IC. Phase 10IN specifies the state_commitment source-envelope schema and commitment derivation (docs-level design). Rollback execution, authorization, replay prevention, and runtime source-envelope validator remain unresolved. |
| **Write allow-list design completed** | Write-Authority §11: "explicit write allow-list (enumerated per-call, not blanket)." | Phase 10II now specifies the 25-field authorization artifact design and two enabled candidate surfaces. The pure runtime validator, operator-approval artifact verification, replay prevention, freshness, and 10CP consumption remain unresolved. |
| **Starting habitat tiles not declared in spec** | Roadmap §3: "declared starting habitat tiles" missing; Habitat §5 references "public starting area / initial tile references." Concrete tiles (`public-start-adam`, `public-start-eve`) exist only in test fixtures. | 10IJ is a protected uncommitted draft, not authoritative or closed. No tiles are declared in any committed spec. Unresolved. |
| **`world-sim/data` write authorization** | Write-Authority §8: "Any `world-sim/data` write requires a separate write-authority spec and explicit Sean authorization." No such spec exists; no authorization granted. Unresolved. |
| **Heartbeat observation boundary module** | Heartbeat spec defines contract; 10IC provides heartbeat verifier but no standalone `first_pair_observation_boundary.py` module exists. The heartbeat contract is partially implemented inside 10IC. Unresolved if this needs a separate boundary module. |
| **Founding role divergence** | Identity §3 uses example `founding_role: "first_observer" / "first_echo"`; 10IC implementation uses a single fixed `"founding_agent"` for both identities. Spec language allows diversity; implementation chose unification. Documented as intentional deviation, not a blocker. |
| **Truncation/collision budget for `agent_id`** | Identity §52-55: "Truncation length and collision budget must be explicitly specified and reviewed before implementation." 10IC uses the full 64-character SHA-256 digest (`genesis-agent-<full 64-char hex>`, verified at `local_first_pair_birth_candidate.py:208,314`; `_ID_DERIVATION_VERSION = "sha256-full-v1"`). The docs-only Phase 10IK specification (now on master) records that decision: full-digest preservation, no truncation authorized, and seven conditions any future truncation must satisfy. **Docs-level decision recorded; runtime behavior unchanged.** Unresolved items remain: (1) 10IC performs no Adam-vs-Eve `agent_id` equality comparison; the first duplicate-ID check is in 10ID `local_first_pair_habitat_boundary.py:161-162` returning `duplicate_identity`; identity-layer collision detection inside 10IC is recorded as an unresolved future implementation requirement, not implemented. (2) `provenance_commitment` receives hex64 shape validation only; cross-domain source rejection is deferred until the source envelope is specified. (3) The truncation/collision **runtime behavior** has not been audited by GPT-5.6 Sol/Luna, which is a separate implementation-phase requirement. **Docs-level review recorded (10IK); runtime-implementation review NOT performed.** |

---

## 4. Still-Missing Creation Preconditions (All Must Be Met)

Before any First Pair creation phase may start, **all** of the following must be satisfied and explicitly reviewed:

1. **Valid identity contract** — verified re-derivation of both `agent_id`s from immutable material; drift checks pass (10IC implemented).
2. **Valid habitat boundary** — verified exact habitat validation, `movement_allowed=False`, `observation_radius=1`, rollback anchor present (10ID implemented).
3. **Valid observation boundary** — observation-only heartbeat contract verified, no hidden true_map, no private paths, no secrets (10IC heartbeat verifier implemented; standalone boundary module not implemented).
4. **Valid memory boundary** — agent-scoped memory refs, cross-identity public-only, no leakage, fail-closed (10IE implemented).
5. **Rollback anchor envelope format documented** — five-field envelope, exact validation rules, claim classification semantics, habitat binding documented by Phase 10IH (docs-level design complete; rollback execution, authorization, replay prevention, and state_commitment source-envelope runtime validator remain unresolved).
6. **Per-call write allow-list design documented** — 25-field authorization artifact, two enabled candidate surfaces, provenance rules, gate flag contract documented by Phase 10II (docs-level design complete; runtime validator, operator-approval artifact verification, replay prevention, freshness, exact-call binding, and 10CP consumption remain unresolved).
7. **Provenance commitment source-envelope construction documented** — schema, serialization, commitment hash, verification rules specified in a reviewed document (10IL design complete; runtime validator not implemented).
8. **Provenance commitment runtime validator implemented** — the source-envelope is presented and verified for Adam and Eve by a factory-trained runtime module (not implemented; requires separate phase + GPT-5.6 Sol/Luna).
9. **Rollback state-commitment runtime validator implemented** — the state-envelope is presented and verified for the rollback anchor by a factory-trained runtime module (not implemented; requires separate phase + GPT-5.6 Sol/Luna).
10. **Declared starting habitat tiles** — concrete tile set for both identities, enumerated in a spec, not only test fixtures (not resolved).
11. **Explicit `world-sim/data` write authorization** — separate spec + Sean authorization (not granted).
12. **GPT-5.6 Sol/Luna for implementation** — per AGENTS.md Rule 3 + all six specs + preflight closure review (not invoked; creation unauthorized).
13. **Explicit Sean approval for the specific creation phase** — not granted.

This document grants no new authority. The implemented 10IC, 10ID, and 10IE boundaries remain verified, while the unresolved creation prerequisites identified above remain open and require separate review and explicit authorization.

---

## 5. Authorization Gate Conclusion

| Condition | Status |
|---|---|
| All six preflight specs exist as unnumbered docs | ✅ Yes |
| Implemented boundaries 10IC, 10ID, 10IE are verified and pushed | ✅ Yes |
| Unimplemented boundaries (heartbeat, write-authority, rollback) have specs | ✅ Yes |
| Rollback anchor envelope format documented | ✅ Yes — by Phase 10IH (five-field envelope, validation rules; execution/authorization/replay remain unresolved) |
| Rollback state_commitment source-envelope documented | ✅ Yes — by Phase 10IN (source-envelope schema, commitment derivation; runtime validator remains unresolved) |
| Rollback anchor execution and authorization implemented | ❌ No — not implemented; requires separate phase + GPT-5.6 Sol/Luna |
| Write allow-list design documented | ✅ Yes — by Phase 10II (25-field authorization artifact, two enabled surfaces; runtime validator, operator approval, replay prevention, freshness, 10CP consumption remain unresolved) |
| Write allow-list runtime validator implemented | ❌ No — not implemented; requires separate phase + GPT-5.6 Sol/Luna |
| Starting habitat tiles declared | ❌ No — 10IJ is a protected uncommitted draft, not authoritative or closed |
| `world-sim/data` write authorized | ❌ No — not granted |
| Provenance commitment source-envelope documented | ✅ Yes — 10IL docs-only spec on master defines source-envelope schema, validation rules, and 40-item acceptance-test table |
| Provenance commitment runtime validator implemented | ❌ No — not implemented; 10IC validates only hex64 shape; requires separate phase + GPT-5.6 Sol/Luna |
| Operator-approval independently verified for a specific envelope | ❌ No — not resolved; 10IL's `operator_approval_ref` is shape-only, proves no approval |
| Truncation/collision budget docs-level decision recorded | ✅ Yes — 10IK docs-only spec on master preserves full 64-char SHA-256 digest |
| Truncation/collision runtime-implementation review | ❌ No — not performed; requires separate implementation phase + GPT-5.6 Sol/Luna |
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
