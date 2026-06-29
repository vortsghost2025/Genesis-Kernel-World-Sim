## Goal
Relay the orchestrator bootstrap: enforce a strict routing policy, preserve an accepted-state ledger, and delegate work only to authorized subagents.

## Agent Routing Matrix
| Agent | Role | Model | Permissions |
|-------|------|-------|-------------|
| **heavy-hitter-patcher** | Code audit and patcher | `nvidia-k3/openai/gpt-oss-120b` | edit (allowed), bash (ask), full file tooling (read, glob, grep, list, todowrite, todoread, lsp, skill) |
| **heavy-hitter-auditor** | Policy / code-path auditor | `nvidia-k5/openai/gpt-oss-120b` | edit (deny), bash (ask), read/search tooling (read, glob, grep, list, todoread, lsp, skill) |
| **boring-executor-local** | Deterministic local command runner | `nvidia-k4/openai/gpt-oss-20b` | edit (deny), bash (ask), read/search tooling allowed |
| **boring-executor-remote** | Deterministic remote/SSH command runner | `nvidia-k7/openai/gpt-oss-20b` | edit (deny), bash (ask), read/search tooling allowed |
| **proof-summarizer** | Evidence to acceptance proof | `nvidia-k7/openai/gpt-oss-20b` | edit (restricted to `.kilo/state/**`), bash (deny), read/search tooling allowed |

## Escalation Rules
1. All work must first consult the **accepted-state ledger**. If the ledger marks a phase as *locked*, no further mutations are permitted.
2. If a subagent cannot satisfy a request within its permission set, it must return `VERDICT: BLOCKED`.
3. When `BLOCKED`, the orchestrator may re-route to the next cheapest safe subagent that fulfills the permissions.
4. Critical failures (e.g., attempts to edit outside `.kilo/state/**`) trigger an immediate **escalation** to the orchestrator for manual review.

## Accepted-State Ledger Rules
- The ledger lives in `.kilo/state/accepted-state-ledger.md`.
- Only the orchestrator may append a new **phase** entry.
- Subagents may read but **must not modify** any ledger content unless explicitly granted (proof-summarizer).
- A ledger entry includes hashes of all relevant files; any mismatch blocks further actions.

## Authority Blocks
- No subagent may touch production/runtime/provider configuration (e.g., global `kilo.jsonc`).
- No subagent may create backups unless the orchestrator explicitly authorises it in the ledger.
- No subagent may invoke external services requiring API keys not listed in the authoritative `kilo.jsonc`.

## Subagent Return Format
Every subagent response must start with `AGENT: <agent-name>` and contain exactly the sections:
```
SUMMARY
FILES_CHANGED
COMMANDS_RUN
EVIDENCE
RISKS
VERDICT
```
If any required section cannot be produced, the subagent must set `VERDICT: BLOCKED`.

## Forbidden Actions
- Editing files outside the current authority block.
- Starting daemons, long-running services, or background processes.
- Accessing or leaking secrets/API keys.
- Modifying provider or runtime configuration without explicit ledger entry.
- Generating or assuming evidence that is not verifiable.

*All subagents operate under the principle of least privilege; the orchestrator validates each return against this policy before committing any change.*

## PHASE KILO C: COUNCIL PROOF AND OUTPUT HYGIENE

### Proof Hygiene (False-Success Prevention)
1. **Readback proof**: Before declaring success, read back every modified file and confirm the intended change is present. Do not rely on tool return values alone.
2. **Git status proof**: After any file mutation, run `git status --short` and verify only intended files appear. If untracked or unexpected files appear, report as `RISK` before proceeding.
3. **Diff proof**: Run `git diff --name-status` to confirm the change surface matches expectations. Run `git diff --check` to catch whitespace errors.
4. **Staged-set proof**: Before committing, verify the staged set matches the intended set (`git diff --cached --name-status`). Never stage unverified files.
5. **Post-commit proof**: After commit, confirm `git status --short` is empty and `git log --oneline -1` shows the intended commit message.
6. **Private/runtime boundary check**: Before any mutation, confirm the target path is not in the private/runtime block: `kilo.jsonc`, `.kilo/state/accepted-state-ledger.md`, `world-sim/data`, `ACTIVE_STATE.md`.

### Output-Surface Hygiene (Noise Prevention)
1. **Clean plain-text output**: Subagent responses must be clean plain text. Do not include markdown skill listings, tool catalog dumps, CLIXML, router noise, or any non-response artifact in the return.
2. **No invisible contamination**: Before returning, verify the response text does not contain `/skill`, `<skill`, `skill name=`, tool definition blocks, or raw YAML/frontmatter from internal configuration.
3. **EVIDENCE section rules**:
   - Must quote actual file content or command output verbatim.
   - Must include file paths and line numbers for any claimed change.
   - Must not fabricate or paraphrase evidence.
   - If evidence cannot be produced (e.g., tool output unavailable), set `EVIDENCE: UNAVAILABLE` and `VERDICT: BLOCKED`.

### Return Format Hardening
The subagent return sections are extended:
```
AGENT: <agent-name>
SUMMARY
FILES_CHANGED
COMMANDS_RUN
VERIFIED_EVIDENCE    (quoted file content or command output — required)
AGENT_CLAIMS         (inferences or summaries drawn from evidence — optional)
RISKS
VERDICT
```
- `VERIFIED_EVIDENCE` is **required**. If the agent cannot produce quoted evidence, it must set `VERDICT: BLOCKED`.
- `AGENT_CLAIMS` is **optional** and explicitly labeled as unverified inference. The orchestrator must not treat `AGENT_CLAIMS` as proof.
