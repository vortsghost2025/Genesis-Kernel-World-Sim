# Security Policy

## Reporting a Vulnerability

If you discover a security issue in this project, please open a GitHub issue with the label `security`. Do not disclose sensitive runtime or deployment details in the issue body.

For issues involving credentials, provider keys, or private infrastructure, contact the repository owner directly through GitHub rather than posting details publicly.

## What Is In Scope

- The pure modules in `world-sim/backend/` (ledger, mapper, validator)
- The Genesis canon specification in `world-sim/docs/genesis_canon_boundaries.md`
- Public documentation files

## What Is Out of Scope

- Runtime or deployment infrastructure
- VPS, container, or Docker configurations
- Provider API keys, tokens, or billing details
- Machine identifiers, remote access labels, or network connection targets
- Private runtime notes (git-ignored files such as `AGENT_RUNTIME_PRIVATE.md` or `PRIVATE_RUNTIME.md`)

These are intentionally excluded from public CI, public documentation, and agent-visible simulation scope. Do not submit them in issues, pull requests, or commits.

## Public CI and Testing

The project's CI workflow runs only pure-module tests from phases 10K and 10L. It does not:

- Connect to any provider, model, or network service
- Require secrets, credentials, or API keys
- Run daemon, tick, scheduler, or provider processes
- Access `world-sim/data`
- Use Docker or a VPS

Runtime phases require explicit operator verification on the canonical runtime host and are not part of automated CI.