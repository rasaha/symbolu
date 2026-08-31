# ACP Open Questions

Decisions the project must make before an ACP canonical package can be justified. Each blocks or shapes the
migration; none is answered by this audit.

1. **Authority: does ACP authorize or only clear?** The robotics V1 core mints a `ControlAuthorization`
   grant; the cloud/console framing never authorizes. Which is the product? (Blocks naming and boundary — R1.)

2. **Which world does the package serve?** The robotics Autonomous Control Plane, the console digital
   clearance, or the governance-chain freshness seam (Decision Authority)? They share no code today. Is the
   goal one package spanning all three via a neutral kernel, or a governance-only clearance that composes
   with ActionGate? (Blocks source selection — R3.)

3. **Contract family:** define a new `Clearance*` family, or extend/reuse the neutral `ActionGovernance*`
   (`EXPIRED`, `authorization_expired`, `expiry`) already frozen in `ugence_governance_contracts`? (R2, R11.)

4. **Package dependency floor:** stdlib-only leaf (like `ugence_model_selection`) or single downward
   dependency on `ugence-governance-contracts>=0.1.0` (like the provider-framework core)? Tied to Q3.

5. **One-time-use / replay:** where does consumption state live? Confirmed recommendation: an execution/
   idempotency ledger downstream, with ACP evaluating prior-consumption as a **received** signal. Is that
   acceptable, and which component owns the ledger? (R8, R9.)

6. **Missing controls:** are actor identity, credential validity, incidents, and duplicate-dispatch in scope
   for the first ACP product, and if so which are ACP-received vs ActionGate/incident-system-owned? (R17.)

7. **Freeze amendment:** is the ACP V1 digest freeze retired, superseded by a package-level freeze, or
   re-based on the neutral kernel? Who updates the `acp_k8s_integrated` frozen-core pin in lockstep? (R5.)

8. **Console vs robotics reconciliation:** should the console `ClearanceVerdict` (CLEAR/HOLD) and the
   robotics `ActionDecision`/`CloudRecommendation` be unified, or remain separate domain expressions behind
   one kernel? (R6, R18.)

9. **Naming:** `ugence_action_clearance` / `ugence-action-clearance` are candidates. Given the acronym
   collision (`ACP/` vs `acp/`, robotics vs console "Autonomous Control Plane"), is "Action Clearance" the
   product name, or does the platform keep "Autonomous Control Plane"? (R18.)

10. **Consumer migration appetite:** `cer_v0_1/2/3` deep-import `.cloud.*`. Is the team ready to migrate them
    onto a curated API behind an identity-preserving shim, and to keep the shadow benches on the legacy
    surface? (R7.)
