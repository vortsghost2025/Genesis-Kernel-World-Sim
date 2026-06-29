# Kilo Orchestration Templates

This directory contains reusable Kilo orchestration templates for this repository. The templates are safe to commit because they do not contain real provider keys, account identifiers, private routes, or runtime state.

## Layout

- `orchestrator-routing.md` defines the routing policy for the council-style workflow: which subagent should handle audits, local command execution, remote command execution, patching, and proof summarization.
- `command/orchestrate.md` defines the `/orchestrate` command workflow. It tells Kilo how to read the routing policy and ledger, choose the cheapest safe subagent, validate returns, and report results.
- `agent/boring-executor-local.md` is the deterministic local command runner. It should run only exact pre-approved local commands and should not invent scope.
- `agent/boring-executor-remote.md` is the deterministic SSH/remote command runner. It should run only exact pre-approved remote commands and should not invent hosts, credentials, or targets.
- `agent/heavy-hitter-auditor.md` is the read-only policy and code-path auditor for higher-cost analysis.
- `agent/heavy-hitter-patcher.md` is the code patching agent. It should only modify files inside an explicit authority block.
- `agent/proof-summarizer.md` converts logs and evidence into acceptance-ready proof. Its write scope is restricted to `.kilo/state/**`.
- `state/accepted-state-ledger.example.md` is the commit-safe ledger template.

## Local-only files

- `kilo.jsonc` is local-only and gitignored. It can contain private provider topology, local model routing, machine-specific options, and secret environment-variable names.
- `state/accepted-state-ledger.md` is local-only and gitignored. It can contain operational evidence, local hashes, reviewer notes, and phase-specific state.
- `node_modules/`, `package.json`, and `package-lock.json` under `.kilo/` are local dependency artifacts and are gitignored for now.

## Security rules

Never commit real API keys, bearer tokens, provider secrets, private service URLs, local account routing, SSH details, or private operational ledgers. Use `kilo.example.jsonc` as the public starting point and keep the real `kilo.jsonc` local.
