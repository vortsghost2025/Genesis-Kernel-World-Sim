# Accepted State Ledger Example

This is a sanitized template. Copy this file to `accepted-state-ledger.md` for local operational use. The real ledger is gitignored because it may contain private hashes, phase notes, local evidence, and reviewer state.

## Accepted State

- accepted_state_id: example-accepted-state-001
- date: YYYY-MM-DD
- verdict: accepted | blocked | needs-review
- reviewer: reviewer-name-or-role

## Files

| file | sha256 | verdict | reviewer |
| --- | --- | --- | --- |
| path/to/file.ext | `<sha256-placeholder>` | accepted | reviewer-name-or-role |

## Evidence Summary

- Describe the verification evidence without including private tokens, account details, provider capacity notes, or secret values.

## Notes

- Keep real local hashes in `accepted-state-ledger.md` only.
- Do not commit private operational evidence.
- Do not store API keys, bearer tokens, passwords, SSH keys, or provider secrets in any ledger.
