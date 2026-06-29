---
description: Bootstrap the orchestrator - read routing policy and state ledger, preserve ledger integrity, route work to the cheapest safe subagent, reserve heavy-hitters, enforce return format.
---

# Orchestrate Command

## Purpose
Dispatch work to subagents under the relay contract: read routing policy and ledger, select cheapest safe subagent, delegate, validate return, update ledger.

## Invocation
`/orchestrate <task-description>` or `/orchestrate` (reads task from current conversation context).

## Step-by-Step Procedure

### Phase 0: Pre-Flight
1. Read `.kilo/orchestrator-routing.md` (routing policy).
2. Read `.kilo/state/accepted-state-ledger.md` (current state).
3. If ledger status is `locked`, output `VERDICT: BLOCKED — ledger locked` and halt.
4. If any hash in the ledger mismatches the actual file on disk (run `Get-FileHash -Algorithm SHA256`), output `VERDICT: BLOCKED — ledger hash mismatch` and halt.
5. Record the pre-flight checkpoint timestamp.

### Phase 1: Task Analysis
1. Parse the task description into: **intent** (what to do), **scope** (which files/paths affected), **permissions-required** (read-only, edit, bash).
2. Classify the task type:
   - `audit` — read-only inspection of code/policy (routes to auditor)
   - `patch` — code modification required (routes to patcher)
   - `exec-local` — run a local command deterministically (routes to local executor)
   - `exec-remote` — run a remote/SSH command deterministically (routes to remote executor)
   - `summarize` — convert evidence/logs into acceptance proof (routes to proof-summarizer)
3. If the task type is ambiguous, default to the **cheapest** agent that can read and report, then escalate if needed.

### Phase 2: Agent Selection (Cost-Ascending Order)
Priority order from cheapest to most expensive:
1. `proof-summarizer` (nvidia-k7/gpt-oss-20b) — cheapest, read+restricted-write only
2. `boring-executor-local` (nvidia-k4/openai/gpt-oss-20b) — cheap, bash(read-only)+read
3. `boring-executor-remote` (nvidia-k7/openai/gpt-oss-20b) — cheap, bash(read-only)+read
4. `heavy-hitter-auditor` (nvidia-k5/openai/gpt-oss-120b) — expensive, read/search only
5. `heavy-hitter-patcher` (nvidia-k3/openai/gpt-oss-120b) — most expensive, edit+bash(ask)

Selection rules:
- If the task requires **only** reading/searching: select `proof-summarizer` or `boring-executor-local` (whichever key has more capacity remaining).
- If the task requires **bash execution**: select `boring-executor-local` (or `boring-executor-remote` if SSH/remote is needed).
- If the task requires **code editing**: only `heavy-hitter-patcher` may be used — but **reserve** it unless the orchestrator explicitly authorises in the ledger.
- If the task requires **policy audit**: select `heavy-hitter-auditor` — also reserved, require explicit ledger entry.
- Never dispatch a heavy-hitter for a task a cheaper agent can handle.

### Phase 3: Delegation
1. Construct the subagent prompt with:
   - The parsed **intent** and **scope** from Phase 1.
   - The **authority block**: which paths the agent may touch (from routing policy `Allowed Mutations`).
   - The **mandatory return format** (AGENT label + 6 sections: SUMMARY, FILES_CHANGED, COMMANDS_RUN, EVIDENCE, RISKS, VERDICT).
   - The **ledger reference**: instruct the subagent to read `.kilo/state/accepted-state-ledger.md` if it needs filesystem context.
2. Launch the subagent via the Kilo Task tool using the `subagent_type` matching the selected agent.
3. Wait for return. If timeout or error, set `VERDICT: BLOCKED — subagent failure`.

### Phase 4: Return Validation
1. Verify the subagent return contains all 6 required sections.
2. Cross-check `FILES_CHANGED` against the **allowed mutations** in the routing policy.
   - If any file was changed outside the authority block: reject, set `VERDICT: BLOCKED — authority violation`.
3. Cross-check `COMMANDS_RUN` against the **forbidden actions** list.
   - If any forbidden command was run: reject, set `VERDICT: BLOCKED — forbidden action`.
4. Verify `EVIDENCE` is verifiable (file paths exist, command output is quoted, hashes match where claimed).
5. If `VERDICT: BLOCKED` in the subagent return:
   - Log the blocker in the ledger under `Open Blockers`.
   - Attempt re-routing to the next cheapest safe subagent (Phase 2, skip the failed agent).
   - If no remaining agents can satisfy the task: report `VERDICT: BLOCKED — no remaining subagent`, halt.
6. If all checks pass: proceed to Phase 5.

### Phase 5: Ledger Update
1. Append a new entry to `.kilo/state/accepted-state-ledger.md`:
   ```markdown
   ### Phase Entry: <phase-name> — <timestamp>
   - **Subagent:** <agent-name>
   - **Task:** <brief description>
   - **Verdict:** <PASSED / BLOCKED>
   - **Files Changed:** <list or `none`>
   - **Hashes After:** <SHA-256 of each changed file>
   - **Evidence Summary:** <1–2 sentence summary>
   ```
2. Recompute the `Current Hashes` table for any file that was changed.
3. Update the `Latest Evidence` section.
4. If the phase is now complete, set status to `complete` and unlock.

### Phase 6: Report
Output to the user:
```
ORCHESTRATION RESULT
  Phase: <phase-name>
  Subagent: <agent-name>
  Verdict: <PASSED / BLOCKED>
  Summary: <1–2 sentence summary>
  Files Changed: <list or `none`>
  Ledger Updated: <yes/no>
```

## Emergency Procedures
- **Hash mismatch at pre-flight**: Do not proceed. Report the mismatched files. The user must manually verify and either restore from checkpoint or update hashes.
- **Subagent authority violation**: Immediately lock the ledger. Report the violation. The user must manually review and unlock.
- **All subagents exhausted**: Report `BLOCKED` with the sequence of failed agents and reasons.
- **Key exhaustion (429)**: If a subagent returns a rate-limit error, wait 60s and retry once. If still 429, mark that provider key as `depleted` in the ledger and re-route to the next agent on a different key.

## Constraints
- The orchestrator itself runs under the Kilo session's primary model (nvidia/glm-5.1).
- The orchestrator does **not** edit files directly — it only delegates to subagents and updates the ledger.
- The only file the orchestrator mutates is `.kilo/state/accepted-state-ledger.md`.
- All other mutations are performed by subagents within their authority blocks.
- No subagent may touch `kilo.jsonc` or provider/runtime configuration.
