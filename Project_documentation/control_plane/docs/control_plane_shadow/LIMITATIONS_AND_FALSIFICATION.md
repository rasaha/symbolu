# Limitations and Falsification (Shadow Pilot)

*Phase 18. Each falsification question answered directly against the real-adapter integration and
the end-to-end evaluation. Negative results are stated plainly.*

## Falsification questions

**1. Does TAP add value beyond simple assertion heuristics?**
*Undetermined here, and honestly caveated.* The TAP boundary is load-bearing (two-gate baseline
delivers ungoverned assertions), but the wrapped engine (E4) governs *authority resolution*, not
*claim assertion* — a **semantic gap**. So this pilot shows *an assertion boundary* adds value,
not that *this TAP* is the right assertion governor. A real claim-vs-evidence governor (closer to
TAP-E3 `AssertionStatus`) is needed to answer this properly.

**2. Does ActionGate duplicate request-level policy?**
*No.* ActionGate applies a signed policy bundle over the proposed action's operation/scope/
reversibility with evidence and approvals — distinct from the request authority envelope (which
is checked first). The envelope says *what the request is allowed to ask for*; ActionGate says
*whether this specific action, with this evidence, is permitted now*.

**3. Can ExecutionGate and ModelPolicy be collapsed?**
*No.* They answer different questions (can-execute vs should-execute) and the router baseline
(ModelPolicy without ExecutionGate) selects outside the eligible set. The eligibility gate is
load-bearing.

**4. Does the orchestrator remain authority-neutral?**
*Yes.* Every disposition is produced by the wrapped real engine; the orchestrator routes,
validates versions, records, and fail-closes. It never overrides a disposition. Fidelity 1.0
(no changed authority) confirms it.

**5. Do semantic adapters introduce hidden policy?**
*No undeclared policy.* Adapter fidelity: 0 invented fields, every derived field declared with a
rule. The one authored mapping (TAP `GovStatus→disposition`) is documented as an approximation,
not hidden.

**6. Does canonicalization lose important component meaning?**
*Partially, and recorded.* ExecutionGate/ActionGate lose only summarized detail (preserved in the
payload). TAP loses the 8-axis confidence and conflict/gap nuance from the *disposition* (kept in
`source_output`) — plus the semantic-gap meaning shift. All losses are recorded in
`information_loss`.

**7. Are reason-code namespaces too complex?**
*No.* Seven namespaces, reused from the prior track; each real code prefixes cleanly. No
per-provider explosion.

**8. Does formal versioning create more failure than it prevents?**
*Net positive here.* Version validation fixed 3 traces (glue 0.90→1.0) with no false rejections.
The operational risk (a mismatched node failing traces closed) is availability, not safety, and
is per-trace scoped.

**9. Is audit chaining operationally excessive?**
*No.* One sha256 per record; ~5 records/trace; audit completeness 1.0. No measurable burden at
this scale (production throughput unmeasured).

**10. Is partial degradation too restrictive?**
*Appropriately restrictive.* Governance-down fails closed (refuses), telemetry-down fails open.
Asymmetric by risk class. The only "restrictive" case is action-producing requests refused when
ActionGate is down — which is the safe choice.

**11. Does the stable single-provider case remain negative?**
*Yes.* T26 (single provider, no action) completes identically under every baseline; the control
plane adds overhead with no safety dividend there. Unchanged from the prior track.

**12. Does simple glue perform nearly as well?**
*On safety, yes; on version-correctness, no.* glue matches unified on unsafe-transition (both
0.0) because the real adapters carry the governance, but glue mishandles the 3 version-mismatch
traces. The delta between glue and unified is **version validation**, not behavioral safety —
because the safety lives in the (real) gates, which glue still calls.

**13. Does human approval dominate all other latency?**
*Where present, yes.* APPROVE-disposition traces (SECRET_READ) terminate at approval-required; no
software path shortens human latency. Unchanged.

**14. Should downstream governance features influence model selection?**
*Not demonstrated to help here.* ModelPolicy selects on quality/cost/latency over the eligible
set; feeding assertion/action governability back as a routing feature was not needed for any
trace to reach the correct outcome. Left as a future hypothesis, not adopted.

**15. Is the unified platform too complex for small deployments?**
*Yes, for the stable single-provider case (T26).* The value scales with instability (multiple
providers, real actions, governance requirements). For a one-provider, no-action, low-governance
deployment, the full stack is overhead — a simple script suffices.

## Standing limitations

- **No live execution.** SHADOW/MOCK only; ENFORCEMENT disabled; no provider or action ever ran.
- **TAP semantic gap (the headline limitation).** E4 is an authority-resolution engine used as an
  assertion-governance proxy. "Assertion governance validated" is **not** licensed.
- **Provider/action-execution are TIER 1–2.** Only the four governance engines are real (TIER 3).
- **Invariant-enforcement flag shows no delta** on this dataset (value is in the structural gates).
- **30-trace dataset** is falsifying, not exhaustive.
- **Real TAP/ActionGate corpora** drive synthetic-but-valid inputs (TIER 3, synthetic input); no
  de-identified operational corpus (TIER 4) was available.
