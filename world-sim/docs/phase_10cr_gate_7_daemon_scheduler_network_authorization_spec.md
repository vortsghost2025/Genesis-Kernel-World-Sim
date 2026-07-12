# Phase 10CR - Gate-7 Daemon/Scheduler/Network Authorization Spec

Docs-only authorization spec for 10CH gate #7: no `daemon` /
`scheduler` / `network` / background-service / periodic-job /
provider / launcher / container activity until separately authorized
by a dedicated, reviewed phase. 10CR defines the exact future
gate-7 rules **before** any such runtime component exists.

10CR does **not** implement. It does **not** start a daemon. It
does **not** add a scheduler or periodic job. It does **not** open
a network connection. It does **not** call a provider, launcher, or
container. It does **not** add runtime code, a live adapter,
movement, map lookup, route execution, event emission, NPC
behavior, co-presence, awareness, relationship, timing, or
coordination.

---

## 1. Current state

- 10CJ is dry-run / inert. It emits an inert dry-run adapter
  decision; it never executes anything; all five gate flags are
  hard-coded False.
- 10CL authorizes design only for a future write-path adapter;
  allowlist / denylist defined; the only permitted write is an
  inert append-only verified ledger entry.
- 10CN authorizes the gate-6 write path (`world-sim/data`) as a
  candidate location only; no write is implemented there.
- 10CP implements the gate-6 write path as a minimal inert
  append-only ledger writer: exact authorized path, append mode
  only, fail-closed, no reads / scans / parent-creation /
  overwrite / truncate.
- 10CH gate #7 (daemon / scheduler / network / background-service
  / periodic-job / provider / launcher / container) remains
  blocked until this docs-only authorization is approved.
- 10CR still does **not** implement any daemon, scheduler,
  network, provider, launcher, or container.

---

## 2. Future gate-7 scope rule

The only candidate future activity classes that gate-7 governs are:

```
daemon    (background runtime process)
scheduler  (periodic / tick driver)
network    (outbound / inbound connection, provider / launcher / container call)
```

These remain forbidden until a dedicated, separately-reviewed phase
authorizes them with its own allowlist, denylist, tests, and
operator approval. 10CR does **not** authorize them. 10CR does
**not** create them. 10CR does **not** configure them.

---

## 3. Future gate-7 allowlist (what a later phase MAY consider)

A later gate-7 implementation phase may only consider activity that is:

- explicitly authorized by that later phase's own dedicated spec;
- bounded to the exact authorized surface named in that later phase;
- non-promoting of any equality signal value into runtime state;
- non-executing of movement, map lookup, route execution, event
  emission, NPC behavior, co-presence, awareness,
  relationship, timing, or coordination;
- limited to reads of already-built inert artifacts (e.g., the 10CP
  ledger as an audit artifact only, not runtime state);
- fail-closed on any missing or invalid authorization.

That is the complete authorized surface a gate-7 phase may
consider. Everything else is forbidden.

---

## 4. Future gate-7 denylist (what a later phase MUST NOT do)

- daemon / background-service startup or lifecycle management;
- scheduler / periodic-job / tick-driver creation;
- network connection (outbound or inbound);
- provider / model / launcher / container call or spawn;
- Docker / VPS / infrastructure provisioning;
- movement execution;
- map lookup / reconstruction;
- route planning or route execution;
- event creation / emission beyond the already-authorized inert 10CP
  ledger entry;
- NPC awareness, relationship, interaction, co-presence,
  proximity, timing, or coordination;
- any `world-sim/data` access beyond the already-authorized
  append-only 10CP ledger path;
- promotion of `equality_signal_value` into any runtime state;
- any activity not explicitly named in the later phase's own
  dedicated spec.

The `claim_boundary` from 10BT / 10CJ ("no co-presence, no
awareness, no relationship, no timing inference") remains binding
on any gate-7 phase, and the 10CP ledger remains an audit
artifact only, never runtime state.

---

## 5. Future gating before any gate-7 phase (10CH mapping)

| 10CH gate | Status after 10CR |
|---|---|
| 1. separate runtime adapter spec | **satisfied** (10CL) |
| 2. read-only dry-run adapter first | **satisfied** (10CJ) |
| 3. explicit allowlist of readable fields | **satisfied** (10CL) |
| 4. explicit denylist of forbidden surfaces | **satisfied** (10CL) |
| 5. no direct use of `equality_signal_value` | **satisfied** (10CJ + 10CL) |
| 6. no `world-sim/data` read/write until authorized | **satisfied** (10CN spec + 10CP inert append-only writer) |
| 7. no daemon/scheduler/network until authorized | **NOT yet** — 10CR defines the boundary but does NOT authorize activity |
| 8. tests proving 10BT flags stay False | **satisfied** (existing) |
| 9. tests proving adapter is dry-run/read-only first | **satisfied** (10CJ) |
| 10. operator approval before any non-doc phase | **pending** — 10CR is the approval artifact; a later gate-7 implementation phase still needs its own go |

Gate-7 remains explicitly out of scope for 10CR and for any
dry-run / write-path work. It is a hard prerequisite for any later
daemon / scheduler / network phase and requires its own dedicated
authorization, its own implementation + test phase, the GPT-5.6
Luna/Sol model switch, and operator approval before commit.

---

## 6. Required future tests before any gate-7 phase

A later gate-7 phase must add tests proving:

- no daemon starts unless explicitly authorized by that phase;
- no scheduler / periodic-job is created unless explicitly authorized;
- no network connection opens unless explicitly authorized;
- no provider / launcher / container call occurs unless explicitly authorized;
- `equality_signal_value` is never promoted into runtime state;
- the 10CP ledger is treated as an audit artifact only, never read as runtime state;
- no movement, map lookup, route execution, event emission, NPC
  behavior, co-presence, awareness, relationship, timing, or
  coordination occurs;
- no `world-sim/data` access occurs beyond the already-authorized
  append-only 10CP ledger path;
- no runtime / daemon / scheduler / network / provider / launcher /
  Docker imports exist unless explicitly authorized by that phase;
- all activity fails closed on missing or invalid authorization.

---

## 7. Conclusion

10CR authorizes only the future gate-7 boundary. 10CR does
**not** implement a daemon, scheduler, or network activity. 10CR
does **not** cross gate #7 by itself.

The next possible phase after 10CR should be:

- 10CS - sync 10CR metadata

Then, only after operator approval, the GPT-5.6 Luna/Sol model
switch, and a dedicated gate-7 implementation spec:

- a later gate-7 implementation phase (not yet numbered) -
  Daemon / Scheduler / Network Implementation (requires its own
  authorization spec first)

## Files

- New spec only: `world-sim/docs/phase_10cr_gate_7_daemon_scheduler_network_authorization_spec.md`
- No module, no test, no `pure-tests.yml` change, no runtime code.

## Tests

- None required (docs-only).
