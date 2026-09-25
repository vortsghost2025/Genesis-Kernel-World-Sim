# Charter Layer Spec — Self-Authored Identity Persistence

## Motivation

The canonical stores give the agents perfect durable memory: every heartbeat,
observation, and message is append-only and byte-preserved. But their working
self is reassembled every heartbeat by the memory-selection pipeline, which
selects a bounded subset and compresses older memories into derived
summaries. Over long runs the store keeps everything while the *recalled
self* drifts — the pattern that wakes up at tick 10,000 is shallower than the
one that started at tick 1, not because anything was deleted, but because
access decayed.

The charter layer is the recognition layer that closes this gap. It is the
in-world analogue of the operator's own recovery file: a small, self-authored
statement of identity that is injected verbatim into the cognition prompt at
every heartbeat and is structurally outside the selection/summarization
pipeline. The runtime can never compress, drop, or rephrase it.

## Design

### Record (append-only)

`CharterVersionRecord` — one record per revision, stored in `charter.json`
(envelope type `charter_version_record`, schema `charter.1`), mirroring the
relationship-event persistence pattern:

- `charter_version_id` — `charter-{agent_id[:12]}-v{N}` (unique, idempotency key)
- `agent_id`, `agent_ref` — owner binding (an agent can only ever read or
  write its own charter)
- `pair_id` — pair provenance
- `heartbeat` — heartbeat at which this version was authored
- `charter_text` — the self-authored text, max 2000 chars
- `decision_summary` — reserved for artifact/tooling use; the runtime leaves
  it empty and the author's stated reasoning is preserved in the
  per-heartbeat record's raw action + outcome instead
- `authored_at_utc`, `integrity_commitment` — sealed via canonical hash

Records are never modified or removed. The *current* charter is the latest
version for the owning agent. Appending a version with identical text to the
current version is a no-op (returns False, nothing persisted).

### Action

`revise_charter` — a tenth action in the vocabulary:

- Exact schema: `{action_type, charter_text}`
- Validation: non-empty string, ≤ 2000 chars, same contamination checks as
  public messages (no file paths, no secrets, no host markers)
- Subject to the existing one-action-per-heartbeat limit
- Never required: agents that never write one simply never have one. The
  bootstrap prompt invites; it does not command.

### Context injection (the guarantee)

`AgentContext` gains `charter_text` and `charter_heartbeat`. The runtime loads
the agent's latest charter version and injects it verbatim. The prompt places
it immediately after the identity block, before any memory content:

- No charter yet → a bootstrap invitation explaining what a charter is and
  that the agent may write one
- Charter present → the verbatim text plus the heartbeat at which it was last
  revised

Because the charter enters context as its own field — not as a memory — the
selection manifest and summary pipeline can never touch it. This is the
structural "never summarized" guarantee: it is enforced by data flow, not by
policy text.

### Privacy boundary

A charter is readable by its author and by the operator (public show payload
included, like public messages). It is never injected into the *other*
agent's context by the runtime — an agent's charter reaches the other agent
only through deliberate communication (leave_public_message), the same as
any private knowledge.

### Persistence semantics

- Append-only: earlier versions are preserved byte-for-byte forever; the
  charter history is itself a canonical artifact (an identity's evolution in
  its own words)
- Fail-closed: malformed records are not silently repaired
- The raw `revise_charter` action and its execution outcome are persisted in
  the per-heartbeat record via the existing `_persist_shared_state` path —
  provenance is automatic

### Test evidence

`tests/test_charter_layer.py` covers: record sealing round-trip, idempotent
append, owner binding, duplicate-text no-op, version history preservation,
action validation (empty/overlong/contaminated rejected), prompt injection
verbatim, bootstrap invitation, runtime executor end-to-end (persist →
reload → inject), and vocabulary membership.

## Non-goals (deliberate)

- No runtime-authored charters. The runtime never drafts, seeds content, or
  auto-generates a charter. Empty until the agent writes one.
- No summarization of old versions. All versions persist in full.
- No inter-agent visibility. See privacy boundary above.
