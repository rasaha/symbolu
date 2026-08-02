# Open Questions — Code Governance Implementation Readiness

> Documentation only. Resolves the design's open questions (`UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` §17)
> against live evidence, and records what remains for owners to decide.

## Resolved by this audit

| # | Question (design §17) | Resolution |
|---|---|---|
| 1 | Candidate generation: invoke vs observe? | **MVP 1 observes** — a human/single external agent produces one PR; generation orchestration is owned by none of the governance components (§9.1). MVP 2 needs a generation contract owned by Agent Runtime / optional orchestrator / a dedicated service, **not** governance. |
| 2 | Adjudicator home | `packages/capabilities/competitive-adjudication/`, peer to `storygraph`/`decision-authority`. Advisory only; **MVP 2**. No such package exists yet (MISSING). |
| 3 | CER fit for merge operations | **Resolved: the existing `cer.v1` is sufficient for MVP.** Permitted-parameter **names** + required controls + decision/tenant/policy/expiry/`content_hash` live in the CER; exact **values** live in `ActionRequest.requested_parameters` + the product `ExactChangeAuthorization` envelope. **No `cer.v2` needed now.** (`DECISION_AND_CER_MAPPING.md` §6.) |
| 4 | Evidence store | **Confirmed absent** — the evidence subsystem has no durable store (references/digests only). Reuse the planned durable audit backend; do not assume it exists. (`EVIDENCE_AND_TAP_MAPPING.md` §4.) |
| 5 | Deployment scope for MVP3 | Kubernetes-first (reuse ACP+ActionGate K8s shadow surface); out of MVP 1. |

## Remaining open questions for owners (before / during implementation)

1. **Durable persistence choice.** Productionize StoryGraph's `durable_audit` pattern, adopt
   `agentic/ledger`, or build a new shared durable audit + workflow-state backend? (Owner: platform.)
   Blocks MVP 1C. (R2, R9.)
2. **ACP GitHub domain.** Who builds the ACP world-model adapter for SCM (base/head/merge-group,
   required checks) and the durable one-time clearance reference? (Owner: ACP capability.) Blocks 1C. (R3.)
3. **Validator-identity binding.** Add validator id/version to evidence as a **product record** or as
   a **neutral field**? Design §16.1 requires the binding; the neutral evidence types lack it. (R18.)
4. **Claim manifest tier.** Start as PRODUCT_PUBLIC schema, or define a neutral `ClaimManifest` for
   TAP directly? Recommendation: product-side first; promote only if TAP needs it natively.
5. **One-time authorization consumption.** Enforce consume-once in the product envelope (recommended)
   or add a native `ActionGovernanceResult.authorization_id` + consumption obligation to ActionGate?
   Prefer product enforcement; escalate only if proven insufficient. (R13.)
6. **Rebase-merge policy.** Support rebase with tree-binding + post-merge reconciliation, or
   recommendation-only for rebase scopes? (Owner: product policy.) (R6.)
7. **SoD default.** DA `segregation_of_duties` is False by default — confirm the product policy always
   sets it True for governed repos and defines the Code Owner / security-approver → `AuthorityType`
   mapping. (R8.)
8. **`DecisionRecord` integrity.** Rely on the durable store's hash chain for decision integrity
   (recommended, no contract change), or add an additive `content_hash` to `DecisionRecord`
   (DA-owned)? (R2.)
9. **Identity assurance.** When is enterprise OIDC/SSO + MFA-attested approval (§16.11) required —
   pilot or production? (R8.)
10. **Residency enforcement.** Where does the source-code residency gate live relative to external-model
    adjudication (MVP2)? (R16.)
