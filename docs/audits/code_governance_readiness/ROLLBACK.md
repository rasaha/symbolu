# Rollback — Code Governance Audit & Implementation

> Documentation only.

## 1. Rolling back THIS audit

This audit adds **only** documentation and machine-readable audit evidence under
`docs/audits/code_governance_readiness/`. It changes **no** runtime code, package, contract, provider,
API snapshot, or frozen artifact.

- **Revert:** delete `docs/audits/code_governance_readiness/` (or `git revert` the docs commits).
- **Impact of revert:** none on any build, test, provider, or frozen artifact. The terminology,
  doc-link, dependency-direction, and freeze validators are unaffected either way (the new docs are
  outside their fixed doc lists and add no import edges).
- **No credentials, tokens, or environment changes** were introduced.

## 2. Rollback posture for future implementation phases

Enforcement is designed to be reversible at each rung (shadow → recommendation → enforced), so a
regression can always drop back a rung without data loss.

| Phase | Rollback action | Returns to |
|---|---|---|
| A (contracts/workflow skeleton) | delete product package | no product |
| B (evidence ingestion, shadow) | disable connector / webhook | no ingestion |
| C (TAP + decision, recommendation) | disable check-run publishing; revert to shadow | shadow record-only |
| D (exact-action mapping) | stop building envelopes | recommendation |
| E (ACP clearance, shadow) | keep clearance shadow-only | recommendation |
| F (execution provider, enforced 1C) | **revoke the merge credential; deregister the provider** | 1B recommendation (humans merge) |
| G (merge queue) | disable queue path | direct-merge only |
| H (competitive adjudication) | disable adjudicator stage | single-candidate standard mode |
| I (deployment governance) | disable deploy connector | merge-only (MERGED terminal) |

## 3. Enforced-mode kill switches (must exist before MVP 1C)

- **Merge-credential revocation** — the execution provider holds the only merge credential; revoking
  it immediately stops all Ugence-driven merges without affecting evidence/decision records.
- **Provider deregistration** — GPF `deregister` / disabling the GitHub `EXTERNAL_EXECUTION` provider
  drops the system to recommendation mode deterministically.
- **Fail-closed default** — any broken governance chain, expired authorization, or ACP hold already
  results in no dispatch (`CHAIN_INCOMPLETE`/`AUTHORIZATION_EXPIRED`/`CLEARANCE_DENIED`), so the safe
  state on any failure is "did not merge."
- **Per-repository enforcement flag** in the policy pack — flip a governed repo back to shadow/
  recommendation without redeploying code.

## 4. Data-safety on rollback

All governance records are immutable and append-only (`frozen=True`; supersession via `supersedes_*`),
so rolling back a phase never rewrites history — it stops producing new enforced actions. The durable
audit trail (once built) is append-only with DB-enforced no-update/no-delete triggers.
