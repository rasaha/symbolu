# ACP ↔ ActionGate Integration

## How ActionGate produces results

ActionGate is the first real **Action-Governance provider** (`actiongate_provider/`), structured as pure
core + provider adapter:

- `core.py` `ActionGateEngine.evaluate()` — deterministic pure function of request + policy; native
  `ActionGateOutcome` = ALLOW / DENY / ALLOW_WITH_CONSTRAINTS / UNKNOWN; carries `expiry_seconds`,
  constraints, obligations, authority_basis, reason_codes, trace_id.
- `provider.py` `ActionGateProvider.authorize(ActionGovernanceRequest) -> ActionGovernanceResult`
  (`ProviderKind.ACTION_GOVERNANCE`); *"ActionGate governs authorization only — this provider has no
  dispatch/observe surface and never executes"* (`provider.py:5-6`).
- `mapping/result.py` maps ALLOW→AUTHORIZED, ALLOW_WITH_CONSTRAINTS→AUTHORIZED_WITH_CONSTRAINTS,
  DENY→DENIED, UNKNOWN→INDETERMINATE; computes `expiry` from `expiry_seconds`+now and a SHA-256 fingerprint.

**ActionGovernanceResult shape** (the neutral contract): `outcome, constraints, obligations, expiry,
authority_basis, reason_codes, provider_trace_id, fingerprint`.

## Does ActionGate invoke ACP? Does clearance logic live inside ActionGate?

**No, to both.** ActionGate core and provider contain no import of, or reference to, ACP or any "clearance"
type. ActionGate's `evaluate()` performs **no** expiry/freshness computation — it only passes an
`expiry_seconds` through. The `EXPIRED` outcome and the `authorization_expired` freshness check are computed
**outside** ActionGate:

- `packages/governance-provider-framework/.../adapters/action_to_control_plane.py:91` —
  `authorization_expired = cer.expires_at is not None and cer.expires_at < now`.
- `packages/governance-provider-framework/.../reference/action.py:64-65` — returns
  `ActionGovernanceOutcome.EXPIRED` when `request.authorization_expired`.
- `decision_governance/actions/control_plane.py:94-95` — `OfflineDeterministicControlPlane` returns
  `AuthorizationOutcome.EXPIRED` when `cer.expires_at < now`.

So authorization-freshness/expiry — the essence of ACP clearance — is today **distributed across the
provider framework and Decision Authority**, not owned by ActionGate and not owned by a dedicated ACP core.

## Intended ACP↔ActionGate composition (from the specs, realized in the benches)

Per `acp/ACP_ACTIONGATE_BOUNDARY.md` and `acp/ACTIONGATE_ACP_COMPOSITION_SPEC.md`, and realized in
`symbolu_robotics/.../cloud/composition.py` and `robotics_reliability_bench/acp_k8s_integrated/`:

| Question | Point of integration |
|---|---|
| Does ActionGate directly invoke ACP? | **No** — a workflow/composition layer invokes both. |
| Does a workflow service invoke both? | **Yes** — `compose(...)` and the k8s harness. |
| Does ACP consume `ActionGovernanceResult`? | Indirectly — it consumes the *verdict* as an opaque `AuthorizationVerdict` token, not the full result object. |
| Result fingerprint vs full result? | **Opaque token only** — ACP receives the verdict, not the whole result; identity binding is verified separately (`KUBERNETES_OPERATION_IDENTITY_BINDING.md`). |
| How do obligations/constraints propagate? | ActionGate constraints ride on its verdict; ACP adds `permitted_constraints` / `EXECUTE_WITH_CONSTRAINTS`. |
| How is action identity preserved? | manifest digest / `action_identity` / current-state hash bound across both layers. |
| How is expiry calculated? | ActionGate `expiry_seconds`; ACP freshness against live state (`seconds_since_last_action`, `resource_version`). |
| How are stale ActionGate results rejected? | commit-revalidation rejects state/patch/policy drift (`acp_k8s_integrated/harness.py:249-294`, robotics `ReferenceCommitRevalidator`). |
| Can ACP widen permissions? | **No.** |
| Can ACP only narrow or deny? | **Yes** — enforced by the two composition invariants. |

## Security property check

> ACP may preserve, narrow, delay, escalate, or deny an authorization. **ACP may never broaden it.**

The live cloud composition **enforces** this: `DENY ⇒ BLOCKED_BY_AUTHORIZATION` regardless of ACP;
`HELD_BY_ACP` never proceeds; PROCEED requires both layers (`cloud/composition.py:98-120`,
`tests/test_acp_cloud.py`). The property holds for the composition surface. The robotics-V1 grant-minting
step is the one place where the "authorize vs clear" line blurs (see `AUTHORITY_BOUNDARY.md`), but even there
the grant is produced only for already-selected admissible actions and revalidation can only reject.

## Consequence for packaging

Because clearance/freshness already lives partly in Decision Authority and the provider framework, a future
ACP package must be defined as a **consumer of the neutral `ActionGovernance*` seam** that composes with
ActionGate's verdict — **not** an absorber of ActionGate policy, Decision Authority logic, or the
provider-framework adapter. The composition boundary (two orthogonal layers, both must pass) is the correct
model and is already proven in code.
