# Signed Answer Authority V1 — External Operator Signer Interface

Authoritative reference for the ONE-SHOT external operator signer and the
Genesis consumer (verifier) side of single-question answer authority.

**Status:** interface contract only. The production signer is NOT implemented
in Genesis (by design). Genesis is verify-only.

## 1. Trust model

- The operator holds a single Ed25519 key pair, shared with question-creation
  authority (same key, distinct domains).
- The **private key never exists anywhere inside Genesis**: not in the repo,
  not in `backend/world`, not in any Genesis environment variable, not in
  canonical `.runtime`, not in any receipt, not in any test fixture.
- Genesis knows only:
  1. the **signed envelope** (JSON), and
  2. the **trusted public key** via `GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX`.
- Transport/storage of the signed envelope need not be trusted: Genesis
  independently re-verifies the signature before any canonical mutation.

## 2. Domains (strict separation)

Answer authority uses a domain/action strictly DISTINCT from question-creation,
so a creation signature can never replay as an answer signature and vice versa.

| Contract | Value |
|---|---|
| `schema` | `single_question_answer_authorization.ed25519.1` |
| `domain` | `GENESIS_FIRST_PAIR_SINGLE_QUESTION_ANSWER_AUTH_ED25519_V1` |
| `action` | `single_question_answer` |

Question-creation uses a different `domain`/`schema`/`action`
(`GENESIS_FIRST_PAIR_SINGLE_QUESTION_CREATE_AUTH_ED25519_V1` /
`single_question_creation_authorization.ed25519.1` / `single_question_create`);
it must remain distinct and is NOT interchangeable.

## 3. Envelope shape

The signed answer envelope is a flat JSON object. Keys excluded from the signed
payload (metadata carried outside the signature):

- `signature` (hex, 64-byte Ed25519)
- `public_key_hex` (optional, never trusted for verification)
- `public_key_id` (optional, never trusted for verification)

Signed payload keys (everything else is signed):

| Key | Meaning |
|---|---|
| `schema` | answer schema literal above |
| `domain` | answer domain literal above |
| `action` | answer action literal above |
| `question_id` | the exact question being answered |
| `asking_agent_id` | the exact asker (owner binding) |
| `formatted_answer_hash` | sha256(canonical `{"answer_material":"<stripped answer>"}`) |
| `max_writes` | must equal `1` |
| `nonce` | non-empty string; freshness / replay identity |
| `issued_at_utc` | timezone-aware UTC ISO-8601 (e.g. `2026-08-24T00:00:00Z`) |
| `expires_at_utc` | timezone-aware UTC ISO-8601, `> issued` |
| `operator_proof_ref` | optional audit/claim reference (NOT cryptographic authority) |

The signature signs the canonical JSON of the entire signed payload:

```
sort_keys=True, separators=(",", ":"), ensure_ascii=False
```

`authorization_id` is **derived** (never written into the envelope):

```
authorization_id = "auth-" + sha256_hex(canonical_json(unsigned_payload))[:16]
```

where `unsigned_payload` is the envelope minus `signature`/`public_key_hex`/
`public_key_id`.

## 4. Signer I/O contract (external, one-shot)

**Input** (to the signer): the unsigned answer-authorization material exactly as
in §3 (schema, domain, action, question_id, asking_agent_id, formatted_answer_hash,
max_writes=1, nonce, issued_at_utc, expires_at_utc, optional operator_proof_ref).

**Process**: requires explicit operator invocation/approval (a human confirms the
exact question/agent/answer to authorize). The signer signs the canonical JSON
of the unsigned payload with the operator private key.

**Output**: the complete signed answer envelope JSON (unsigned payload +
`signature` hex).

**Constraints the signer MUST honor**:
- It is a one-shot interactive tool, never a daemon, never an unattended API.
- Genesis must have NO ability to call it automatically to obtain authority.
- It must not expose the private key in its output.

## 5. Genesis consumer (verify-only)

Genesis verifies on every consumption:

1. signature over the canonical unsigned payload against `GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX`
   (env-only; absent → `operator_public_key_unconfigured`; malformed → fail-closed);
2. exact `schema`/`domain`/`action` answer literals;
3. `max_writes == 1`;
4. `nonce` present;
5. `issued_at_utc <= expires_at_utc`, both timezone-aware, `expires > now`;
6. recompute `authorization_id` and require exact match with the consumed receipt's identity;
7. signed `question_id == requested`, signed `asking_agent_id == canonical owner`,
   signed `formatted_answer_hash == hash(answer being applied)`.

Then it persists a **consumed authority receipt** storing the full signed
envelope, and only the locked answer transaction may perform the canonical
`pending -> answered` mutation — re-verifying the stored envelope again under
the store lock.

## 6. Authority evidence vs audit evidence

- **Authority predicate** = valid signed envelope stored in
  `answer-authorization-receipts/auth-<id>.consumed.json`, re-verified against
  the env trust root.
- **Audit evidence only** = `provenance.jsonl`
  `single_question_answer_consumed` / `single_question_answer_applied` lines.
  These grant ZERO authority and may be forged without consequence.

## 7. Known separate authority debt (NOT in scope of this module)

Goal authorization (`local_single_goal_write.seal_authorization`) and
goal-status authorization (`local_single_goal_status_update.seal_goal_status_authorization`)
still use the unsigned/self-consistent-hash `seal_*` pattern. This module closes
**answer** authority only. Project-wide operator authority is NOT yet fully
cryptographically closed until those domains receive the same signed treatment.