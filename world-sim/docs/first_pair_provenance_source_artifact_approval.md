# First-Pair Provenance Source-Artifact Approval

Repo-local operator-proof approval record for the First-Pair provenance
commitment operation.

- **operator**: Sean
- **claim_scope**: operator_proof
- **authorization timestamp (UTC)**: `2026-08-24T03:50:14Z`
- **approved source artifact**: `world-sim/docs/first_pair_identity_spec.md`
- **approved exact SHA-256**:
  `360e1c916afa9bc1e1d792e90ebb0b46afe7bec07f7a7db8e80d85aa2fceaac4`
- **scope**: this shared repository artifact is designated as the provenance
  source artifact for BOTH Adam and Eve.
- **identity distinction**: Adam and Eve remain distinct through separate
  provenance envelopes and `canonical_name = "Adam"` / `canonical_name = "Eve"`.
- **commit evidence**: committed with documentation commit `docs: record
  first-pair provenance approval` (see git history for the commit SHA).

## What this approval establishes

- Repository/operator designation only: "Sean explicitly designated the
  approved source artifact as the provenance source for the First-Pair
  provenance commitment operation, at the authorization timestamp above."

## What this approval does NOT establish

- External truth, authentication, or authority outside the repository.
- Freshness, uniqueness, or non-replay guarantees.
- Resistance to a malicious caller fabricating a self-consistent envelope.
- Any authorization to create, write, or execute Adam or Eve.
- Any change to `FIRST_PAIR_CREATION_AUTHORIZED`, Gate-7, or heartbeat status.

`FIRST_PAIR_CREATION_AUTHORIZED` remains False. Gate-7 remains closed. No
heartbeat was executed by this record.