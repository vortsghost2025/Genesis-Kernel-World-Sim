# First-Pair Human-Answer Round-Trip — Governance Seam Spec

Read-only source audit + minimal design. NOT committed; NOT implemented.

**FIRST_PAIR_CREATION_AUTHORIZED = False**
**GATE_7_OPENED = False**

---

## PURPOSE

Close the single source-proven gap in the already-existing

`ask_human → QuestionRecord → operator answer → answered-question re-entry → next cognition`

round trip: the **operator-answer write is raw and ungoverned**. Everything else
is already implemented and wired in committed source. This spec describes the
**smallest governed seam** around the dangerous middle mutation, reusing all
existing persistence and re-entry machinery.

---

## EXISTING_COMPONENTS (all committed, source-proven)

| Component | Location | State |
|---|---|---|
| `ask_human` action routing | `first_pair_runtime._execute_action` → `_execute_ask_human` | wired |
| Pending `QuestionRecord` creation (action route) | `_execute_ask_human` (validates id/question/reason/urgency, dedup, appends pending) | wired |
| Pending `QuestionRecord` creation (cognition `questions_raised` route, 2nd path) | `_apply_cognition_output` question branch (dedup, pending) | wired |
| Question persistence | `_persist_shared_state` → `save_questions` → `questions.json` | wired |
| Raw answer mutation | `mark_question_answered` (`first_pair_persistence.py:1473`) | wired but **ungoverned** |
| Answered-question selection / owner filter | `first_pair_runtime._build_context`: `asking_agent_id == current AND status == "answered"` → `select_human_context` | wired |
| `AgentContext` re-entry fields | `answered_questions` and `relevant_human_answers` both set to selected answered records | wired |
| Model prompt exposure | `build_system_prompt` renders both "Human answers you have received" and "Answers you have received" | wired (intentional dual exposure, retained) |
| Operator CLI answer entry | `world-sim/scripts/run_first_pair_demo.py` `--answer/--answer_text` → raw writer, `provenance="operator_script"` | wired, raw |

---

## THE ONE MISSING COMPONENT

A **bounded governed operator-answer seam** that provides the governed path
around the raw `mark_question_answered` mutation for canonical/governed
operations, adding the same safety properties the committed single-goal writers
(`local_single_goal_write.py`, `local_single_goal_status_update.py`) already have.
It reuses lower-level existing primitives (`load_questions` / `save_questions` /
`store._append_provenance`) rather than wrapping the raw writer (see Decision).

Concretely, the missing seam provides a **single-use operator-grounded
authorization** bound to an exact `(question_id, asking_agent_id, answer)`, and
applies it fails-closed with replay rejection before any durable mutation.

---

## QUESTION_LIFECYCLE (existing, unchanged)

1. Agent cognition emits `ask_human` action (or a `questions_for_humans` entry).
2. Runtime appends a `QuestionRecord(status="pending")` to `self._questions`.
3. End-of-tick `_persist_shared_state` calls `save_questions` → `questions.json`.
4. Question stays `pending` until an operator answer marks it `answered`.

Note: Adam's validated real-model output (`proposed_action = ask_human`,
`questions_for_humans = []`) **would** create one durable pending question via
the action route — the `questions_raised`/`questions_for_humans` path is a
second, independent creation vector, not a prerequisite.

The two creation routes are **NOT equivalent at the runtime boundary**:

- `_execute_ask_human` (action route) runtime-enforces: required `question_id`,
  required `question`, required `reason_for_asking`, safe `question_id`,
  duplicate-`question_id` rejection, and `urgency` in `{low, medium, high}`
  before appending the `QuestionRecord`.
- `_apply_cognition_output(... questions_raised ...)` primarily reads
  `q["question_id"]`, deduplicates by `question_id`, and constructs the
  `QuestionRecord` directly — it does **not** independently repeat the
  safe-id/urgency/required-field runtime checks at that boundary.
- Nuance: `ModelCognitionBackend.validate_model_output` DOES validate
  `questions_for_humans` upstream (required fields, safe IDs, lengths, urgency,
  related goal ID) before those values become `CognitionOutput`. So a
  model-backed `questions_for_humans` entry carries upstream schema validation;
  only a generic arbitrary `CognitionBackend`'s `questions_raised` is trusted
  substantially more at the runtime boundary.

This asymmetry is an EXISTING_SEPARATE_RISK and a NON-GOAL for the operator-answer
seam (not fixed here). Adam's actual output is unaffected: his `proposed_action`
passed Genesis validation, so `ADAM_EXACT_OUTPUT_WOULD_CREATE_DURABLE_QUESTION = YES`
stands, creating exactly one question (no duplicate).

---

## ANSWER_LIFECYCLE (missing governance added around existing persistence)

**Existing raw sequence (`mark_question_answered`):**

```
load_questions
→ find by question_id
→ status = "answered"
→ provenance["answer"] = answer
→ provenance["answered_at_utc"] = now
→ provenance["operator_provenance"] = provenance
→ save_questions                       (STEP 1)
→ append_provenance("answer_question") (STEP 2)
```

**Missing additions (the governed seam):**

1. **Pending-only precondition** — a question already `answered` must reject a
   re-answer (immutable first-answer).
2. **Single-use authorization artifact** — an operator-sealed token binding
   `(question_id, asking_agent_id, answer_material)`; consumed exactly once,
   owned by the operator (Sean), never self-authorized.
3. **Expected-owner binding** — the intended `asking_agent_id` is part of the
   authorization material, so an authorization issued for one question/agent
   cannot be redirected to another.
4. **Consume-first commit point** — burn/consume the authorization in
   `provenance.jsonl` **before** `save_questions`, mirroring the goal-status
   writer's consume-first ordering.
5. **Inbound-appropriate answer validation** — NOT `sanitize_public_text`
   (that helper is a public-egress / world-facing redactor; see below).
6. **Provenance failure handling (failure window)** — see below.

**Answer validation (inbound context) — do NOT reuse `sanitize_public_text`:**

`sanitize_public_text` (world_event_sanitizer.py) is a **public egress / world-
facing** releaser that *rewrites* content — it deliberately redacts filesystem
paths, `.env`, credentials, localhost/IPv4, SSH/HostingEr/Tailscale infra names,
model/trace markers, and more. An operator answer is **inbound private cognition
context**, and blindly running it through this redactor could corrupt legitimate
information intentionally given to Adam (e.g. an answer containing
"The service is available at 127.0.0.1").

The governed seam therefore uses a minimal **bounded-text validity** check, no
semantic rewriting:

- must be `str`
- strip and reject empty after stripping
- deterministic maximum length, using a source-supported bound (the model layer
  already bounds question text at `_MAX_QUESTION_CHARS = 1000` /
  `_MAX_REASON_CHARS = 1000`; the same char-bound family is reused)
- reusable validity helpers exist: `local_first_pair_birth_candidate.
  _is_bounded_public_text(value, maximum)` (str + 1..max + printable-ASCII, no
  rewriting) and `first_pair_cognition_model._check_length`.
- credential/runtime contamination in an inbound answer is handled by
  **rejection** (guard against `.env`/API-key/path markers) rather than
  redaction, because redacting an inbound answer would silently alter operator
  intent. No generic sanitizer framework is introduced.

**Decision — do NOT mechanically call `mark_question_answered`:**

The existing raw writer performs `save_questions` THEN appends the
`answer_question` provenance and has no pending-only/replay boundary. Calling it
from the governed seam would defeat consume-first ordering (provenance would be
wrong-shaped/late) and create duplicate/uncontrolled provenance. Therefore the
governed seam reuses the **lower-level existing primitives** (`load_questions`,
`save_questions`, `store._append_provenance`, `QuestionRecord`) directly and
**leaves `mark_question_answered` untouched** for legacy/demo use.

---

## EXACT_CANONICAL_DELTA

- Answers remain in the existing `questions.json` (within `QuestionRecord.provenance`).
- **No new canonical file for answers.**
- If canonical `questions.json` does not yet exist (it currently does not), it
  is created only when Adam's ask_human question is actually persisted — this is
  the existing question-persistence contract, not a new file.
- **No new `QuestionRecord` type. No new answer ledger.**

---

## PROVENANCE_DELTA

- The existing raw writer appends `answer_question` provenance **after**
  `save_questions`. The governed seam adds:
  - a **consume** provenance event (authorization burned) appended **first**
    (e.g. `answer_authorization_consumed`), and
  - the existing **apply** event (`answer_question`) appended after
    `save_questions`.
- This produces the same failure-window classification used for the goal-status
  writer (below).

---

## REPLAY_RULE

- A consumed authorization is **non-replayable**: any second use of the same
  token is rejected even if a later persistence step failed.
- An already-`answered` question rejects any further answer (first-answer
  immutable), independent of the token check.

---

## PARTIAL_FAILURE_RULE (explicit failure windows)

Given consume-first ordering:

- **A. consume append fails** → nothing durable changed; the authorization is
  reusable; retry succeeds exactly once. (Question unchanged, no provenance.)
- **B. consume succeeds, `save_questions` fails** → question remains `pending`,
  authorization is burned; same-token retry is rejected. (Authorization consumed
  with no applied answer.)
- **C. consume succeeds, `save_questions` succeeds, apply (`answer_question`)
  append fails** → question becomes `answered` but the audit surface is missing.
  Correct classification: **`ANSWER_APPLIED_AUDIT_INCOMPLETE`** (mirrors the
  goal-status writer's Window C). No rollback is invented.
- **D. normal success** → `pending → answered` exactly once; exactly one
  `answer_authorization_consumed` event; exactly one `answer_question` (applied)
  event; replay of the same authorization rejected.

This is the same consume-first reasoning proven for the goal-status writer —
except today the raw answer writer has **no consume-first boundary**, so it
currently exhibits Window C (and re-answer overwrite) unguarded.

---

## REQUIRED STATE MACHINE (pre-consumption, fail-closed)

All of the following reject **before** authorization consumption:

1. question missing → reject (no such `question_id`)
2. `asking_agent_id` mismatch → reject (authorization bound agent ≠ expected)
3. question already `answered` → reject (immutable first-answer)
4. answer invalid (not str / empty / over bound / contamination marker) → reject
5. authorization mismatch (tampered / wrong `question_id` / wrong agent /
   wrong answer material) → reject

Only a valid pending question + a valid, unconsumed authorization proceeds:

```
consume authorization (append answer_authorization_consumed)
→ persist answered QuestionRecord (save_questions)
→ append applied provenance (answer_question)
```

Post-conditions:

- replay of the same authorization → reject
- a fresh authorization attempting to re-answer an already-answered question
  → reject

---

## CANONICAL EXECUTION SEQUENCE — DO NOT COMBINE

The eventual real canonical experiment remains **three separately authorized
boundaries**, never one automatic transaction:

1. **Persist** Adam's already-validated `ask_human` proposal as pending
   `q1-habitat-structure`. → VERIFY (question durable, pending).
2. **Answer** that pending question through the governed operator-answer seam.
   → VERIFY (answered, provenance intact).
3. **Give Adam exactly one new real model cognition** with the answered question
   visible in context. → This third cognition **begins read-only again**.

Do NOT combine into one chain. Each transition gets its own receipt.

---

## AUTHORITY_BOUNDARY

- The operator (Sean) seals the single-use authorization; the seam only
  **validates and consumes** it — it never grants authority to itself or to any
  model output.
- Scope is **exactly one** answer to **exactly one** pending question of an
  expected agent.
- **No** movement, memory persistence, world-state, relationship, gate, or broad
  creation authority.

---

## ANSWER_TO_NEXT_COGNITION_REENTRY (existing, unchanged)

1. `QuestionRecord.status == "answered"`.
2. `_build_context` selects questions where `asking_agent_id == current agent_id`
   and `status == "answered"`.
3. `select_human_context` deterministically bounds selection (≤4, goal/capability
   relevance first).
4. Selected records → `AgentContext.answered_questions` **and**
   `AgentContext.relevant_human_answers`.
5. `build_system_prompt` renders both answer sections.
6. `ModelCognitionBackend`/real inference consumes the context.

So once an answer is durably stored, the **next real cognition** (the exact
path proven in the Ollama milestone) automatically receives it with no new
re-entry code.

---

## NON-GOALS

- No movement.
- No memory persistence merely because an answer exists.
- No world-state mutation.
- No relationship mutation.
- No Gate-7.
- No broad First-Pair creation.
- No automatic second inference (the next cognition is a separate operator-paced step).
- No self-authorization.
- No external provider requirement.
- No new question type, no new answer ledger, no generic authorization
  framework, no new verifier hierarchy.

---

## SUMMARY

**PREEXISTING (wired):** ask_human action, QuestionRecord creation (both routes),
question persistence, raw answer mutation, answered-question owner-filtered
selection, AgentContext re-entry (`answered_questions` +
`relevant_human_answers`), model-prompt exposure.

**MISSING (only this):** the governed single-use operator-answer seam around the
raw answer mutation — pending-only precondition, single-use authorization bound
to `(question_id, asking_agent_id, answer_material)`, consume-first commit
point (reusing lower-level load/save primitives, NOT wrapping the raw writer),
inbound-appropriate answer validation (bounded-text validity; no
`sanitize_public_text`), replay rejection, and the resulting consume-first
state machine / failure-window semantics.