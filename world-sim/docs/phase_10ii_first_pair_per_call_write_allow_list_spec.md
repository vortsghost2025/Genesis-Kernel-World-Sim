# Phase 10II — First Pair Per-Call Write Allow-List Specification

Numbered docs-only spec. This file defines the exact per-call write
allow-list boundary the future First Pair creation phase **must** satisfy
before any First Pair candidate material may be authorized for write. It
is **docs-only**: it implements no validator, adds no tests, performs no
write, authorizes no persistence, creates no Adam/Eve runtime entity,
does not modify 10CP, does not open Gate-7, does not implement or alter
10HD, and does not touch `world-sim/data`. 10CP remains the sole writer.
Adam and Eve never become writers. The provenance_commitment construction
remains unresolved per 10IG; the rollback last-known-good state and
`state_commitment` source envelope remain unresolved per 10IH; the
starting habitat tiles declaration remains unresolved; no phase beyond
10II/10IJ/10IK is assigned by this document.

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## A. Title and Status

- **Title**: Phase 10II — First Pair Per-Call Write Allow-List Specification.
- **Status**: Docs-only specification authorized by Sean. Repository
  documentation reserves 10II for the future First Pair per-call write
  allow-list specification. The phase is started as docs-only under
  explicit Sean authorization, recorded in Section O.
- **Phase number**: 10II. No new phase number is assigned by this
  document; 10IJ and 10IK are already named as future work in existing
  repository documentation and remain **not started**.
- **Boundary preservation**: Gate-7 remains closed. 10HD remains
  named-only and untouched. 10CP remains the sole writer.
  `world-sim/data` remains forbidden.

---

## B. Purpose

10II defines a future authorization boundary for a single bounded write
surface for First Pair candidate material. It specifies:

- an exact per-call authorization artifact envelope;
- the exact candidate-payload envelopes it permits;
- the four separate caller-supplied inputs a future pure validator must
  receive and revalidate;
- a future acceptance-test matrix for that pure validator.

It authorizes no write, performs no write, defines no writer integration,
and is a **control contract only**. A future pure validator that 10II
specifies, but does not implement, may produce a normalized allow-list
validation result. That result performs no write, no filesystem access, no
persistence, no writer call, and no
provider/model/network/daemon/scheduler/container activity.

10II only specifies the future contract. It does not implement the
validator, the inputs, the chain revalidation, or the acceptance tests.
Implementation requires a **separate phase**, **TDD**, **GPT-5.6
Sol/Luna**, and **explicit Sean approval**.

---

## C. Explicit Non-Authority Statement

- 10II is docs-only and performs no write.
- 10II defines a future authorization boundary only.
- 10II does not consume or require a 10CJ decision.
- 10II does not modify 10CP.
- Current 10CP accepts only the exact 10CN-authorized 10CJ inert audit
  surface. Current 10CP cannot consume the 10II artifact or
  First Pair candidate payload. No existing ledger path or record schema
  is inherited.
- 10CP remains the sole writer as a constitutional boundary.
- A later separately authorized First Pair adapter or 10CP-owned
  extension must be designed before any writer may consume First Pair
  candidate material. That future design requires separate docs
  authorization, implementation, TDD, GPT-5.6 Sol/Luna, and explicit
  Sean approval.
- Adam and Eve never become writers.
- `world-sim/data` remains completely forbidden.
- Gate-7 remains closed: no daemon, scheduler, network, provider,
  model, container or Docker activity is authorized.
- 10HD remains named-only and untouched.
- **FIRST_PAIR_CREATION_AUTHORIZED = False**.

---

## D. Future Validator Inputs

The future pure validator must receive four separate caller-supplied
inputs. 10II specifies the contract for each; it implements none of them.

1. **`authorization_artifact`** — the exact 25-field authorization
   artifact envelope defined in Section E.
2. **`presented_call_id`** — exact built-in `str`; must exactly equal
   `authorization_artifact.authorized_call_id`.
3. **`candidate_payload`** — exact built-in `dict`; schema selected by
   `authorization_artifact.target_surface`, defined in Section F.
4. **`validated_first_pair_chain`** — the already-presented
   10IC/10ID/10IE chain; must be completely reconstructed and revalidated
   by the future validator; it is **context**, not part of candidate
   payload.

The candidate payload and the validated chain are separate inputs.
Identity binding, rollback-anchor binding, and habitat binding are
derived from the revalidated chain, not from any field inside
`candidate_payload`.

10II implements none of this. It only specifies the future contract.

---

## E. Exact 25-Field Authorization Artifact

The operative authorization artifact contains **exactly 25 fields**.
Exact-key-set size: 25. Every listed field must be present. No
additional key is permitted. Any extra or missing key fails exact-key-set
validation: the result is "Invalid authorization artifact; no surface
authorized."

```python
{
    "write_authorization_schema_version": "first_pair_write_auth.1",
    "write_authorization_id": <str>,
    "authorized_call_id": <str>,
    "target_surface": <str>,
    "allowed_fields": <list[str]>,
    "payload_claim_scope": <str>,
    "payload_source_ref": <str>,
    "payload_source_schema_version": <str>,
    "payload_provenance_chain": <list[dict]>,
    "operator_approval_ref": <str>,
    "operator_approval_claim_scope": "operator_proof",
    "pair_id": "genesis-first-pair",
    "agent_id_adam": <str>,
    "agent_id_eve": <str>,
    "identity_provenance_ref": <str>,
    "rollback_anchor_ref": <str>,
    "gate_runtime_allowed": False,
    "gate_daemon_allowed": False,
    "gate_scheduler_allowed": False,
    "gate_network_allowed": False,
    "gate_provider_allowed": False,
    "gate_container_allowed": False,
    "gate_model_allowed": False,
    "gate_world_sim_data_allowed": False,
    "authorization_artifact_integrity_id": <str>,
}
```

There are exactly **eight gate flags**: `gate_runtime_allowed`,
`gate_daemon_allowed`, `gate_scheduler_allowed`, `gate_network_allowed`,
`gate_provider_allowed`, `gate_container_allowed`, `gate_model_allowed`,
`gate_world_sim_data_allowed`. Every gate flag must be the exact built-in
`bool` value `False`. Any non-`False` gate flag (including truthy
non-bool, missing, or extra) fails closed: "Invalid authorization
artifact; no surface authorized."

### E.1 Field-by-Field Specification

| # | Field | Built-in Type | Exact Literal or Validator | Class | Semantic Purpose | Fail-Closed Rule |
|---|-------|---------------|----------------------------|-------|------------------|-------------------|
| 1 | `write_authorization_schema_version` | `str` | exact literal `"first_pair_write_auth.1"` | control | Envelope schema version pinning | Any other value => Invalid authorization artifact; no surface authorized |
| 2 | `write_authorization_id` | `str` | `_is_safe_identifier` (1-128 chars, safe alphabet; see 10IC L387-391 / 10IH Section 4) | control | Caller-supplied safe identifier for the proposed authorization artifact | Missing/invalid/non-conforming => Invalid authorization artifact; no surface authorized |
| 3 | `authorized_call_id` | `str` | `_is_safe_identifier` | control | Exact presented-call binding | Must equal `presented_call_id` exactly; mismatch => Invalid authorization artifact; no surface authorized |
| 4 | `target_surface` | `str` | enumerated literal from Section F | control | Selects which enabled surface is authorized | Not in enabled list => Invalid authorization artifact; no surface authorized |
| 5 | `allowed_fields` | `list[str]` | exact-equal to canonical list for `target_surface` (Section F) | control | Field-level allow-list | Any deviation (order, dup, missing, extra) => Invalid authorization artifact; no surface authorized |
| 6 | `payload_claim_scope` | `str` | required literal per surface (Section F) | control | Category-specific claim_scope for payload | Missing/invalid/does not equal required => Invalid authorization artifact; no surface authorized |
| 7 | `payload_source_ref` | `str` | safe-identifier/reference rule | control | Immutable source artifact reference | Missing/invalid => Invalid authorization artifact; no surface authorized |
| 8 | `payload_source_schema_version` | `str` | non-empty, sanitized | control | Source schema/version identity | Missing/empty/unsanitized => Invalid authorization artifact; no surface authorized |
| 9 | `payload_provenance_chain` | `list[dict]` | non-empty, per-entry 3-field exact dict (Section H) | control | Provenance chain | Empty or non-conforming => Invalid authorization artifact; no surface authorized |
| 10 | `operator_approval_ref` | `str` | safe-identifier/reference rule | control | Reference to operator approval artifact | Missing/invalid => Invalid authorization artifact; no surface authorized |
| 11 | `operator_approval_claim_scope` | `str` | exact literal `"operator_proof"` | control | claim_scope for operator approval | Any other value => Invalid authorization artifact; no surface authorized |
| 12 | `pair_id` | `str` | exact literal `"genesis-first-pair"` | control | First Pair binding | Any other value => Invalid authorization artifact; no surface authorized |
| 13 | `agent_id_adam` | `str` | must exactly equal validated Adam agent ID from revalidated chain (Section G) | control | Adam identity binding | Mismatch => Invalid authorization artifact; no surface authorized |
| 14 | `agent_id_eve` | `str` | must exactly equal validated Eve agent ID from revalidated chain (Section G) | control | Eve identity binding | Mismatch => Invalid authorization artifact; no surface authorized |
| 15 | `identity_provenance_ref` | `str` | safe-identifier/reference rule (claim_scope: identity) | control | Identity provenance reference | Missing/invalid => Invalid authorization artifact; no surface authorized |
| 16 | `rollback_anchor_ref` | `str` | must exactly equal normalized `rollback_anchor_id` from revalidated chain (Section J) | control | Rollback anchor binding | Mismatch => Invalid authorization artifact; no surface authorized |
| 17 | `gate_runtime_allowed` | `bool` | exact `False` | control | Runtime gate flag | Not `False` => Invalid authorization artifact; no surface authorized |
| 18 | `gate_daemon_allowed` | `bool` | exact `False` | control | Daemon gate flag | Not `False` => Invalid authorization artifact; no surface authorized |
| 19 | `gate_scheduler_allowed` | `bool` | exact `False` | control | Scheduler gate flag | Not `False` => Invalid authorization artifact; no surface authorized |
| 20 | `gate_network_allowed` | `bool` | exact `False` | control | Network gate flag | Not `False` => Invalid authorization artifact; no surface authorized |
| 21 | `gate_provider_allowed` | `bool` | exact `False` | control | Provider gate flag | Not `False` => Invalid authorization artifact; no surface authorized |
| 22 | `gate_container_allowed` | `bool` | exact `False` | control | Container gate flag | Not `False` => Invalid authorization artifact; no surface authorized |
| 23 | `gate_model_allowed` | `bool` | exact `False` | control | Model gate flag | Not `False` => Invalid authorization artifact; no surface authorized |
| 24 | `gate_world_sim_data_allowed` | `bool` | exact `False` | control | world-sim/data gate flag | Not `False` => Invalid authorization artifact; no surface authorized |
| 25 | `authorization_artifact_integrity_id` | `str` | exact built-in `str`; exactly 64 lowercase hexadecimal characters | control | Deterministic integrity commitment over the 24-field canonical material | Missing/malformed/mismatched => Invalid authorization artifact; no surface authorized |

### E.2 `write_authorization_id` Is Not Unique

`write_authorization_id` is a caller-supplied safe identifier for the
proposed authorization artifact. Shape validation does **not** establish
uniqueness. No registry, sequence mechanism, or replay detector exists.
Duplicate reuse is **not** detected by 10II. Replay prevention is
unresolved and is separately governed (Section I).

### E.3 Excluded from the Operative Authorization Artifact

- `expiration`, `consumed`, `sequence`, previous-artifact reference,
  clock dependency, replay detector, persistent consumption registry are
  **absent** from the operative schema. Any input containing one of those
  unknown fields fails exact-key-set validation.
- Ledger path, authorized ledger path, 10CJ decision reference,
  `equality_signal_value` are **excluded**; handled by separate specs.
  Their presence in a 10II artifact is rejected as an extra key.

---

## F. Exact Two Candidate Payload Envelopes

The exact enabled target surfaces remain only:

1. `sanitized_proof_reference`
2. `sanitized_observation_evidence_reference`

### F.1 Surface 1: `sanitized_proof_reference`

`candidate_payload` must be an exact built-in `dict` containing exactly:

```python
{
    "source_proof_ref": <exact str>,
    "source_schema_version": <exact str>,
    "claim_scope": "proof"
}
```

Canonical `allowed_fields`:

```python
[
    "source_proof_ref",
    "source_schema_version",
    "claim_scope"
]
```

Required `payload_claim_scope`: `"proof"`.

### F.2 Surface 2: `sanitized_observation_evidence_reference`

`candidate_payload` must be an exact built-in `dict` containing exactly:

```python
{
    "source_observation_ref": <exact str>,
    "source_schema_version": <exact str>,
    "claim_scope": "observed"
}
```

Canonical `allowed_fields`:

```python
[
    "source_observation_ref",
    "source_schema_version",
    "claim_scope"
]
```

Required `payload_claim_scope`: `"observed"`. Restricted to sanitized
observe-only First Pair heartbeat evidence.

### F.3 Cross-Binding Rules

For both surfaces:

- `candidate_payload` exact-key-set enforcement: no extra or missing
  fields; exact built-in string values.
- Source reference must pass the approved safe-reference rule.
- `source_schema_version` must be non-empty and sanitized.
- `authorization_artifact.allowed_fields` must exactly equal the relevant
  canonical list: exact built-in list; exact built-in string entries;
  exact order; no duplicates; no missing item; no additional item.
- `authorization_artifact.payload_claim_scope` must equal
  `candidate_payload.claim_scope`.
- `authorization_artifact.payload_source_ref` must equal the relevant
  candidate payload source reference.
- `authorization_artifact.payload_source_schema_version` must equal the
  candidate payload `source_schema_version`.

No agent ID, tick, tile ID, observation contents, world data, or identity
material may appear in `candidate_payload`. The authorization surface
carries references only, not the source artifact's contents.

### F.4 Disabled Target Surfaces (Named, No Authority)

The following surface names are recognized but disabled. They receive no
authority. Any `target_surface` not in the enabled list fails closed.

- `identity_provenance_reference` - disabled
- `speech_reference` - disabled
- `hypothesis_reference` - disabled
- `world_ledger_material` - disabled (future-disabled category only; no
  authority)
- `persistent_memory_material` - disabled (future-disabled category only;
  no authority)
- `world_state_mutation` - disabled
- `rollback_state_material` - disabled
- `hidden_true_map` - always forbidden
- `raw_transcripts` - always forbidden
- `private_paths` - always forbidden
- `secrets` - always forbidden
- `provider_model_config` - always forbidden

World-ledger and persistent-memory categories may be named as future
disabled categories only. They receive no authority. A future adapter or
10CP-owned extension must be **separately authorized** before any of
those categories may be enabled or consumed.

---

## G. Required Control Context

### G.1 Identity Binding

Identity is mandatory control context. The future validator must:

- reconstruct and validate the complete 10IC/10ID/10IE chain from
  `validated_first_pair_chain`;
- obtain the canonical Adam and Eve agent IDs from that validated chain;
- require `authorization_artifact.agent_id_adam` to exactly equal the
  validated Adam agent ID;
- require `authorization_artifact.agent_id_eve` to exactly equal the
  validated Eve agent ID;
- require `pair_id` exact equality with `"genesis-first-pair"`;
- verify `identity_provenance_ref` against the validated identity
  context;
- reject any identity drift.

The provenance_commitment construction remains unresolved per 10IG
Section 8. The final literal agent IDs **cannot** be approved independently of
their validated identity material. 10II does not hard-code Adam or Eve
agent IDs; they are bound from the revalidated chain.

Identity immutable fields (`canonical_name`, `pair_id`,
`founding_role`, `provenance_commitment` per the Identity spec Section 3) are
**never writable** as payload. Any identity field appearing in
`allowed_fields` fails closed: "Invalid authorization artifact; no
surface authorized."

### G.2 Rollback-Anchor Binding

`rollback_anchor_ref` is a mandatory control field, not a payload
surface. The future validator must:

- reconstruct and revalidate the complete 10IC/10ID/10IE chain from
  `validated_first_pair_chain`;
- obtain the complete normalized rollback-anchor envelope from that
  chain;
- confirm `rollback_anchor_valid` is exact `bool True`;
- confirm `rollback_anchor_ref` exactly equals the normalized
  `rollback_anchor_id`;
- compare the complete normalized anchor material carried by the
  validated chain rather than trusting an isolated caller-supplied anchor
  ID;
- confirm exact habitat binding (the anchor's `habitat_id` equals the
  validated habitat stem's `habitat_id`).

The `validated_first_pair_chain` is a separate validator input. 10II
does **not** add a new rollback-envelope field to the operative
authorization artifact. See Section J for the complete rollback limitations.

### G.3 Mandatory Control Fields (Never Payload)

Every 10II authorization artifact must contain all of the following;
they are never part of any surface's `allowed_fields`:

- `operator_approval_ref` (field 10)
- `operator_approval_claim_scope` (field 11; exact literal
  `"operator_proof"`)
- `authorized_call_id` (field 3)
- `pair_id` (field 12; exact literal `"genesis-first-pair"`)
- `agent_id_adam` (field 13)
- `agent_id_eve` (field 14)
- `identity_provenance_ref` (field 15)
- `rollback_anchor_ref` (field 16)
- All 8 gate flags (fields 17-24; each exact `bool False`)
- `authorization_artifact_integrity_id` (field 25; exact 64-character
  lowercase hex; mandatory)

### G.4 Operator-Approval Semantics

`operator_approval_ref` is a caller-supplied reference to a separately
governed operator-approval artifact. Safe-reference validation establishes
shape only. `operator_approval_claim_scope` = `"operator_proof"` is a
claim classification only. Presence of the reference and claim_scope does
not independently prove that operator approval occurred.

10II defines no operator-approval artifact schema. The four current
future-validator inputs contain no independently validated operator-
approval artifact. Operator-approval artifact verification therefore
remains unresolved and separately governed. No validator operating only
on the four 10II inputs may conclude that a write surface is
operator-authorized.

---

## H. Provenance Rules

`payload_provenance_chain` (field 9) must be a **non-empty exact
built-in list**.

Every entry must be an exact built-in `dict` containing **exactly** three
fields:

```python
{
    "claim_scope": <str>,
    "source_ref": <str>,
    "source_schema_version": <str>,
}
```

### H.1 Rules

- No extra or missing entry fields.
- All three values must be exact built-in strings.
- `source_ref` must satisfy the approved safe-identifier/reference rule.
- `source_schema_version` must be non-empty and sanitized.
- Every entry `claim_scope` must be recognized (taxonomy: `proof`,
  `observed`, `identity`, `operator_proof`).
- At least one entry must match `payload_claim_scope` and
  `payload_source_ref`.
- Duplicate three-field entries are rejected.
- List order is preserved.
- **No universal `source_record_hash` is required.**

A `source_record_hash` may exist only inside or beside a referenced
artifact when that artifact's own schema defines one (e.g., a 10CP ledger
record has `record_hash` per its own schema). It is **not** added to
this baseline envelope. It is **not** a universal field.

### H.2 Required Payload Item Properties

Every accepted payload item must carry:

- its required category-specific `claim_scope` (`proof` or `observed`
  for the enabled surfaces);
- an immutable source artifact or decision reference (`source_ref`);
- its required provenance chain (`payload_provenance_chain`);
- source schema/version identity where applicable
  (`source_schema_version`).

The `authorization_artifact_integrity_id` is a separate deterministic
commitment over the authorization envelope. It proves envelope integrity
only and does not prove operator approval.

---

## I. Exact-Call and Replay Limitations

The operative authorization artifact has **no**:

- expiration timestamp;
- consumed flag;
- sequence number;
- previous-artifact reference;
- clock dependency;
- persistent consumption registry;
- replay detector.

Instead:

- Those fields are **absent** from the operative schema.
- Any input containing one of those unknown fields fails exact-key-set
  validation: "Invalid authorization artifact; no surface authorized."
- `authorized_call_id` must match `presented_call_id` **exactly**.
- Exact call matching is **not** durable replay detection.
- Replay prevention remains unresolved and is separately governed. 10II
  does not reserve or name another phase number for replay prevention.
  That is an operator decision required before any future phase.

---

## J. Complete Rollback Binding and Limitations

10IH is a docs-only specification describing the anchor already carried
by 10IC. Do **not** call this an accepted "10IH anchor." The future
validator revalidates the **complete 10IC/10ID/10IE chain**, not 10IH in
isolation.

### J.1 Future Validator Steps

The future validator must:

- reconstruct and revalidate the complete 10IC/10ID/10IE chain;
- obtain the complete normalized rollback-anchor envelope from that
  chain;
- confirm `rollback_anchor_valid` is exact `bool True`;
- confirm `rollback_anchor_ref` exactly equals the normalized
  `rollback_anchor_id`;
- compare the complete normalized anchor material carried by the
  validated chain rather than trusting an isolated caller-supplied anchor
  ID;
- confirm exact habitat binding.

### J.2 Explicit Limitations

- `rollback_anchor_id` uniqueness is not enforced.
- Replay detection does not exist.
- No anchor fingerprint exists.
- Anchor acceptance is not rollback authorization.
- Rollback authorization is not rollback execution.
- No executor exists.
- No actual reversibility is claimed.
- `state_commitment` construction and last-known-good state remain
  unresolved per 10IH Section 12.

The `validated_first_pair_chain` is a separate validator input. 10II does
**not** add a new rollback-envelope field to the operative authorization
artifact.

---

## K. Relationship to Current 10CP

- 10II is docs-only and performs no write.
- 10II defines a future authorization boundary only.
- 10II does not consume or require a 10CJ decision.
- 10II does not modify 10CP.
- Current 10CP accepts only the exact 10CN-authorized 10CJ inert audit
  surface.
- Current 10CP cannot consume the 10II artifact or First Pair
  candidate payload.
- No current ledger path or record schema is inherited.
- 10CP remains the sole writer as a constitutional boundary.
- A later separately authorized First Pair adapter or 10CP-owned
  extension must be designed before any writer may consume First Pair
  candidate material.
- That future design requires separate docs authorization,
  implementation, TDD, GPT-5.6 Sol/Luna, and explicit Sean approval.
- Adam and Eve never become writers.

Do **not** say that current 10CP executes when given a 10II artifact.
Current 10CP cannot consume a 10II artifact.

---

## L. Acceptance Tests Specified for a Later Pure Validator

**Acceptance tests specified by 10II for a later pure validator
implementation.** 10II adds no test code. 10II adds no validator. It
defines a future acceptance-test matrix only. Any implementation
requires a separate phase, TDD, GPT-5.6 Sol/Luna, and explicit Sean
approval.

| Test | Requirement |
|------|-------------|
| Envelope exact-key-set validation (25 fields) | Valid allow-list structure; operator authorization not independently verified; any extra/missing key => Invalid authorization artifact; no surface authorized |
| Schema version literal enforcement | != `"first_pair_write_auth.1"` => Invalid authorization artifact; no surface authorized |
| Target surface enumeration | Only enabled surfaces accepted; disabled => Invalid authorization artifact; no surface authorized |
| `allowed_fields` exact-equal | Order, duplicates, missing, extras => Invalid authorization artifact; no surface authorized |
| `candidate_payload` exact-key-set | Extra/missing fields => Invalid authorization artifact; no surface authorized |
| Payload `claim_scope` binding | Does not equal required per surface => Invalid authorization artifact; no surface authorized |
| Payload source cross-binding | `payload_source_ref` does not equal candidate source reference, or `payload_source_schema_version` does not equal candidate version => Invalid authorization artifact; no surface authorized |
| Provenance chain structure | Non-empty; 3-field exact dicts; duplicates => Invalid authorization artifact; no surface authorized |
| Provenance match rule | At least one entry matches `payload_claim_scope` + `payload_source_ref` |
| Operator approval `claim_scope` | != `"operator_proof"` => Invalid authorization artifact; no surface authorized |
| `pair_id` literal | != `"genesis-first-pair"` => Invalid authorization artifact; no surface authorized |
| Validated-chain Adam/Eve agent_id binding | `agent_id_adam` / `agent_id_eve` does not equal validated chain IDs => Invalid authorization artifact; no surface authorized |
| Identity provenance reference | Invalid / drift => Invalid authorization artifact; no surface authorized |
| Complete rollback-anchor binding | Cross-validated chain anchor comparison; `rollback_anchor_ref` does not equal normalized ID => Invalid authorization artifact; no surface authorized |
| Habitat binding | Anchor `habitat_id` does not equal validated habitat stem `habitat_id` => Invalid authorization artifact; no surface authorized |
| Gate flag enforcement | Any of 8 gate flags not exact `False` => Invalid authorization artifact; no surface authorized |
| Identity field payload denial | Identity field in `allowed_fields` => Invalid authorization artifact; no surface authorized |
| world-sim/data denial | Any reference => Invalid authorization artifact; no surface authorized |
| Unknown field rejection | Expiration/consumed/sequence/previous/clock/replay/etc. => Invalid authorization artifact; no surface authorized |
| Exact call matching | `authorized_call_id` does not equal `presented_call_id` => Invalid authorization artifact; no surface authorized |
| `validated_first_pair_chain` revalidation | Chain must be completely reconstructed and revalidated; failure => Invalid authorization artifact; no surface authorized |
| Integrity ID shape | `authorization_artifact_integrity_id` missing, not exactly 64 lowercase hex characters, or malformed => Invalid authorization artifact; no surface authorized |
| Integrity ID recomputation | Reconstructed canonical material SHA-256 does not equal `authorization_artifact_integrity_id` => Invalid authorization artifact; no surface authorized |

A future validator may produce a normalized allow-list validation result.
It performs:

- no write;
- no filesystem access;
- no persistence;
- no writer call;
- no provider/model/network/daemon/scheduler/container activity.

A structurally valid allow-list candidate remains non-executable and
non-authorizing until a separately specified and independently validated
operator-approval artifact is bound to the exact artifact and call.

---

## M. Authorization Conclusion

The Phase 10II contract defines a future authorization boundary and
acceptance-test matrix only. It does not authorize creation. It does not
implement tests or a validator. It does not modify 10CP. It does not
open Gate-7. It does not assign a phase number beyond 10II. It does not
resolve the unresolved preconditions identified by 10IF (write allow-list
enumeration itself is now specified; all other open preconditions
remain). It does not authorize any persistent write.

The later pure validator specified by 10II may establish only exact
envelope shape, exact payload surface and field binding, provenance
structure, exact-call matching, validated-chain identity binding,
validated-chain rollback-anchor binding, all-False gates, and
deterministic integrity-ID equality. It must not return an authorized
result solely from these four inputs. A structurally valid allow-list
candidate remains non-executable and non-authorizing until a separately
specified and independently validated operator-approval artifact is bound
to the exact artifact and call.

**FIRST_PAIR_CREATION_AUTHORIZED = False**

---

## N. Integrity ID as Mandatory Control Field

Field 25 is the approved deterministic integrity commitment.

### N.1 Field

`authorization_artifact_integrity_id`

### N.2 Type and Shape

- exact built-in `str`;
- exactly 64 lowercase hexadecimal characters;
- required, not optional.

### N.3 Canonical Integrity Material

The deterministic integrity hash is computed over exactly the original
24 baseline fields and no others.

Call this:

canonical_integrity_material

It is not itself the complete presented authorization artifact.

### N.4 Derivation

1. Take all 24 baseline authorization-artifact fields and no others.
2. Serialize using:

   ```python
   json.dumps(
       canonical_integrity_material,
       sort_keys=True,
       separators=(",", ":"),
       ensure_ascii=False,
   )
   ```

3. Encode the resulting string as UTF-8.
4. Hash using `hashlib.sha256`.
5. Return the full lowercase 64-character hexdigest.
6. No truncation.

The operative authorization artifact contains exactly 25 fields.

Fields 1 through 24 remain unchanged.

Field 25 is `authorization_artifact_integrity_id`.

The future validator must:

- reconstruct the exact 24-field canonical_integrity_material;
- recompute the SHA-256 value;
- require exact equality with field 25;
- fail closed when field 25 is missing, malformed or mismatched.

The integrity ID proves only envelope integrity.

It does **not** prove:

- operator approval;
- authority;
- uniqueness;
- freshness;
- non-replay;
- consumption;
- execution.

---

## O. Operator Decisions — Approved by Sean Before 10II Began

Sean approved the following three decisions during a read-only design
review that preceded this docs-only phase. The phase author records them
here; the phase author did not grant them independently.

### Decision 1 (Sean approval recorded)

Approve the initial enabled candidate payload categories as only:

- sanitized proof references;
- sanitized observe-only evidence references.

**Decision recorded**: Approved by Sean before 10II began.

### Decision 2 (Sean approval recorded)

Approve operator approval, exact-call binding, validated-chain identity
binding, and complete validated-chain rollback-anchor binding as
mandatory control context, never writable payload.

**Decision recorded**: Approved by Sean before 10II began.

### Decision 3 (Sean approval recorded)

Approve the deterministic `authorization_artifact_integrity_id` as
field 25 of the operative authorization artifact, with the explicit rule
that it proves envelope integrity only and does not prove operator
approval, authority, uniqueness, freshness, non-replay, consumption, or
execution.

**Decision recorded**: Approved by Sean before 10II began.

These recorded approvals authorize 10II as a docs-only phase only. They
do not authorize implementation, a validator, tests, Adam/Eve creation,
persistence, world-sim/data access, writer integration, autonomous
runtime, or Gate-7 activity. `FIRST_PAIR_CREATION_AUTHORIZED` remains
`False`.

---

## P. Forbidden Actions (Repeated for Emphasis)

Under this spec and all six preflight specs, the following are forbidden
and must fail closed:

- Creating Adam or Eve runtime entities
- Opening Gate-7 (no network egress/ingress, no daemon, no scheduler, no
  provider, no container, no Docker)
- Writing to `world-sim/data`
- Implementing, altering, or recurring into 10HD (10HD remains
  named-only and untouched; the recursion spine is separate)
- Granting write authority to Adam, Eve, or any new writer (10CP remains
  the sole writer)
- Model/provider autonomy (no model may choose actions, writes, or
  ticks)
- Runtime self-scheduling (no self-initiated ticks)
- Any write without an explicit per-call allow-list and provenance chain
- Modifying the 10IC implementation, 10ID, or 10IE
- Implementing a validator or tests under 10II

---

## Q. Phase Index

The 10II phase row is added to `phase_index.md` only after the phase
documentation commit is pushed. The row records that pushed phase
commit's real short SHA. The metadata update is an unnumbered
documentation correction. It does not start 10IJ or 10IK.
