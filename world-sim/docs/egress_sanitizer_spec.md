# Phase 10W: Egress Sanitizer Specification

Docs-only specification for a future pure public-egress safety layer.

---

## 1. Purpose

The egress sanitizer protects the public event surface from non-public data.
It does not decide whether an event is true, does not upgrade `claim_scope`,
does not serialize output, and does not write ledger events. Its job is
limited to public egress safety.

## 2. Placement in pipeline

The sanitizer runs after event verification and before any public export
surface.

A typical flow is:

```text
candidate mapper -> verifier -> egress sanitizer -> exporter -> public egress
```

If a future export path builds a projected event dict before serialization,
the same sanitizer rules apply to that projected dict immediately before
public egress.

## 3. What the sanitizer receives

The sanitizer receives one of the following:

- an event-shaped dict using the current public event fields, or
- a projected event dict derived from those same fields for a public export
  profile

The sanitizer may receive extra non-public fields that should not cross the
public boundary. It does not require daemon objects, scheduler state, runtime
state, or any external service.

## 4. What the sanitizer returns

The sanitizer returns either:

- a sanitized event-shaped dict, or
- a sanitized projected event dict, or
- a rejection result for the entire event

The sanitizer does not serialize the result. Serialization remains the
exporter's responsibility.

## 5. Allowed event schema surface

The public event surface is limited to these fields:

| Field | Type | Notes |
|---|---|---|
| `event_id` | string | Stable event identifier |
| `schema_version` | string | Event schema version |
| `tick` | integer or null | At least one of `tick` or `timestamp_utc` must be present |
| `timestamp_utc` | string or null | At least one of `tick` or `timestamp_utc` must be present |
| `actor_id` | string | Acting agent identifier |
| `lens` | string | Perspective or region label |
| `territory_ref` | string | Territory reference |
| `action_type` | string | Event action label |
| `summary` | string | Human-readable event summary |
| `evidence_refs` | list of dict | Each item must include `category` and either `ref` or `reference` |
| `claim_scope` | string | One of `observed`, `memory`, `speech`, `hypothesis`, `operator_proof`, `unknown` |
| `before_ref` | string or null | May be null or empty for non-mutating events |
| `after_ref` | string or null | May be null or empty for non-mutating events |
| `affected_agents` | list | Affected agent identifiers |
| `artifacts_created_or_changed` | list | Artifact references or identifiers |
| `relationship_delta` | structured value | Event-carried relationship change data |
| `consequence` | string | Human-readable consequence text |
| `verification_status` | string | Verification state |

Allowed `evidence_refs.category` values are:

- `observed_world_fact`
- `agent_memory`
- `agent_speech`
- `agent_action`
- `artifact_record`
- `territory_record`
- `relationship_record`
- `operator_proof`
- `world_event`

A public export profile may use any subset of the fields above, but it may not
introduce new public fields outside this surface.

## 6. Forbidden public egress categories

The sanitizer must reject public egress when allowed fields contain any of the
following categories of content:

- credential material
- connection details
- operator-only diagnostics
- private implementation details
- malformed evidence entries
- evidence categories outside the allowed list
- non-serializable structured values in a public payload

These categories are defined generically on purpose. This specification does
not include concrete machine-specific or service-specific values.

## 7. Reject vs strip behavior

| Situation | Action |
|---|---|
| Extra top-level field that is not part of the public schema surface and is not itself sensitive | Strip |
| Extra nested field inside an otherwise valid public structure and not itself sensitive | Strip |
| Allowed field contains credential material, connection details, operator-only diagnostics, or private implementation details | Reject the event |
| Evidence entry is malformed or uses a category outside the allowed list | Reject the event |
| Public field value is structurally unsafe for export | Reject the event |
| Event is already public-safe and contains only allowed fields | Pass through unchanged |

The sanitizer should prefer stripping only when the extra content is clearly
non-public but not sensitive. It should reject when the content itself would be
unsafe to expose.

## 8. Examples of accepted payloads

Accepted example with no extra fields:

```json
{
  "event_id": "evt_10w_example_001",
  "schema_version": "10K.1",
  "tick": 42,
  "timestamp_utc": null,
  "actor_id": "east_adam",
  "lens": "east",
  "territory_ref": "territoryA",
  "action_type": "observe",
  "summary": "Water is visible at the basin edge.",
  "evidence_refs": [
    {
      "category": "observed_world_fact",
      "ref": "world.observe.example"
    }
  ],
  "claim_scope": "observed",
  "before_ref": null,
  "after_ref": null,
  "affected_agents": [
    "east_adam"
  ],
  "artifacts_created_or_changed": [],
  "relationship_delta": [],
  "consequence": "Observation recorded.",
  "verification_status": "candidate"
}
```

Accepted example that becomes safe after stripping a benign extra field:

```json
{
  "event_id": "evt_10w_example_002",
  "schema_version": "10K.1",
  "tick": 43,
  "timestamp_utc": null,
  "actor_id": "east_adam",
  "lens": "east",
  "territory_ref": "territoryA",
  "action_type": "observe",
  "summary": "Tracks are visible near the reeds.",
  "evidence_refs": [
    {
      "category": "observed_world_fact",
      "ref": "world.observe.reeds"
    }
  ],
  "claim_scope": "observed",
  "before_ref": null,
  "after_ref": null,
  "affected_agents": [
    "east_adam"
  ],
  "artifacts_created_or_changed": [],
  "relationship_delta": [],
  "consequence": "Observation recorded.",
  "verification_status": "candidate",
  "display_hint": "compact"
}
```

In the second example, `display_hint` is stripped before public export.

## 9. Examples of rejected payloads

Rejected example with placeholder-only unsafe content:

```json
{
  "event_id": "evt_10w_example_reject_001",
  "schema_version": "10K.1",
  "tick": 44,
  "timestamp_utc": null,
  "actor_id": "east_adam",
  "lens": "east",
  "territory_ref": "territoryA",
  "action_type": "observe",
  "summary": "Observation included <private implementation detail>.",
  "evidence_refs": [
    {
      "category": "observed_world_fact",
      "ref": "world.observe.example"
    }
  ],
  "claim_scope": "observed",
  "before_ref": null,
  "after_ref": null,
  "affected_agents": [
    "east_adam"
  ],
  "artifacts_created_or_changed": [],
  "relationship_delta": [],
  "consequence": "Observation withheld from public egress.",
  "verification_status": "candidate"
}
```

This event is rejected because an allowed field contains private implementation
detail text.

Rejected example with a malformed public evidence entry:

```json
{
  "event_id": "evt_10w_example_reject_002",
  "schema_version": "10K.1",
  "tick": 45,
  "timestamp_utc": null,
  "actor_id": "east_adam",
  "lens": "east",
  "territory_ref": "territoryA",
  "action_type": "observe",
  "summary": "A reflection was seen on the water.",
  "evidence_refs": [
    {
      "category": "not_allowed_here",
      "ref": "world.observe.example"
    }
  ],
  "claim_scope": "observed",
  "before_ref": null,
  "after_ref": null,
  "affected_agents": [
    "east_adam"
  ],
  "artifacts_created_or_changed": [],
  "relationship_delta": [],
  "consequence": "Observation withheld from public egress.",
  "verification_status": "candidate"
}
```

This event is rejected because the evidence category is outside the allowed
public surface.

## 10. Relationship to candidate mapper, verifier, exporter

| Component | Relationship to the sanitizer |
|---|---|
| Candidate mapper | Produces event-shaped dicts and may already remove some obviously unsafe material before verification |
| Verifier | Checks schema, consistency, and provenance; it is not a public egress safety layer |
| Exporter | Serializes only sanitized events or sanitized projections; it does not decide public safety on its own |

## 11. Open questions for runtime wiring

- Should the sanitizer be a standalone pure module or a small layer around export orchestration?
- Should rejected events return a structured reason object, or should rejection stay opaque at the public edge?
- Should public export profiles define field subsets in one central allowlist or per-export target?
- Should nested public projections of `evidence_refs` be normalized further before serialization?
- What is the smallest pure test matrix that proves strip vs reject behavior without depending on runtime infrastructure?

---

This specification is intentionally pure and implementation-agnostic. A future
phase may turn it into code, but 10W itself is docs-only.
