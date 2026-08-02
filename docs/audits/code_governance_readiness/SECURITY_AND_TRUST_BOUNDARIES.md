# Security & Trust-Boundary Audit — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§16.1, §16.2).
> Verified against live code at commit `3ec11e4e`.

Owner legend: **P** = Code Governance product; **DA** = Decision Authority; **AG** = ActionGate;
**ACP** = ACP; **GPF** = provider framework; **conn** = GitHub connector; **exec** = GitHub execution
provider. Priority: P0 (mandatory before enforcement/pilot), P1 (before broad pilot), P2 (production hardening).

| Control | Owner | Existing implementation | Adapter required | Product work | Missing dependency | Priority |
|---|---|---|---|---|---|---|
| GitHub webhook-signature validation | conn | none | — | **yes** | — | **P0** |
| GitHub App installation-token scoping (least privilege, per-op) | conn/exec | none | — | **yes** | — | **P0** |
| repository / organization allowlists | P | none | — | **yes** | — | **P0** |
| least-privilege permissions | exec | none | — | **yes** | — | **P0** |
| no merge credentials in coding-agent environments | P | none (design constraint) | — | **yes** (env isolation) | — | **P0** |
| no production credentials in candidate worktrees | P | none | — | **yes** | — | **P0** |
| trusted policy from approved base/control repo | P/DA | policy loaded from base (design); `policy_refs` versioned | — | **yes** (loader) | — | **P0** |
| signed / digest-bound claim manifests | P/TAP | content-hashing pervasive; no signature/manifest | — | **yes** (manifest schema + signing) | signing infra | **P0** |
| validator identity binding | P/TAP | provenance present; **no validator_id/version field** | — | **yes** | evidence-record binding | **P0** |
| validator version binding | P/TAP | `policy_version`/profile only | — | **yes** | as above | **P0** |
| evidence digest | conn/TAP | **REUSE** `content_hash`/`with_fingerprint` | — | wire-up | — | P0 |
| toolchain provenance | P | `PatchCandidate.tooling_environment` (design) | — | **yes** | — | P1 |
| tenant isolation | DA/P | `tenant_id` on all DA records; StoryGraph registry isolates | — | wire-up (GPF resolution has none) | — | **P0** |
| source-code residency | P | none | — | **yes** (pre-external-model gate) | — | **P0** |
| secret redaction | P/conn | CER rejects credential-like keys (`cer_binding_service.py:80`); DA credential markers | — | extend to connector | — | P1 |
| external-model data policy | P/ModelSel | Model Selection routing | — | **yes** (policy) | — | P1 |
| replay protection | AG/DA | `idempotency_key`; DA execution idempotency; ACP nonce (design) | — | wire-up | durable dedup store | **P0** |
| idempotency | DA | **REUSE** two-key model | — | wire-up | — | P0 |
| authorization expiry | AG/DA | **REUSE** CER `expires_at`, `ActionGovernanceResult.expiry` | — | wire-up | — | P0 |
| one-time dispatch | P/exec | not native | — | **yes** (consume-once envelope) | durable consumption store | **P0** |
| audit-log access controls | P | StoryGraph durable_audit (append-only DB triggers); DA audit in-memory | — | **yes** (unify + ACL) | durable backend | **P0** |

## Trust boundaries

1. **Untrusted content boundary.** PR prose, comments, commit messages, and source text are
   **data, never instructions**. TAP and the adjudicator consume *structured evidence records* with
   explicit provenance. (design §16.1; enforced by keeping evidence as `evidence_refs`, not prose.)
2. **Credential boundary.** No merge/production credentials in coding-agent or candidate-worktree
   environments. The execution provider holds the only merge credential, scoped per operation.
3. **Policy boundary.** Effective policy is resolved from the **approved base branch**, never from
   files the candidate introduces or edits (no self-governing candidates).
4. **Provider boundary.** Vendor errors normalize to fail-safe `INDETERMINATE`/`UNKNOWN` at the GPF
   adapter boundary — a GitHub outage never yields a spurious "authorized" (framework invariant).
5. **Authority boundary.** The execution provider cannot interpret policy; ACP cannot mint
   authorization; the adjudicator cannot produce a `DecisionRecord`.

## P0 summary (must exist before any credential can merge — MVP 1C)

webhook-signature validation · least-privilege scoped installation tokens · repo/org allowlists ·
no merge/prod credentials in agent/candidate environments · trusted base-branch policy · signed/
digest-bound claim manifests + validator identity/version binding · tenant isolation wired through ·
replay protection + one-time dispatch (needs durable dedup/consumption store) · authorization expiry ·
append-only audit with access controls (needs durable backend). Several P0 controls **depend on a
durable store that does not yet exist for the decision kernel** — see `DURABLE_AUDIT_AND_RECONSTRUCTION.md`.
