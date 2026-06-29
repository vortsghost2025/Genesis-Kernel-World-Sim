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
