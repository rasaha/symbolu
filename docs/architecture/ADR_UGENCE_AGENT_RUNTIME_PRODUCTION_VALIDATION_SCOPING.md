# ADR — Agent Runtime production validation scoping (RT-ROW, RT-SINK, RT-PHASE5, RT-PILOT)

**Status:** rulings ratified by the owner, 2026-09-06. This record **builds no
capability**: it corrects two stale statements, restates one wave-5 row against
its real blockers, and fixes the evidence bar for a claim nobody may yet make.
**Maturity:** `agent-runtime` 0.7.0 remains `IMPLEMENTED_AND_CI_VERIFIED` and is
**not** live-verified, pilot-validated, distributed-safe, cluster-safe,
exactly-once, enforcement-ready or production-ready.
`ugence-agent-runtime-governance` 0.1.0 remains core-implemented, **not**
pilot-validated and **not** production-certified. Nothing here lifts
`ProductionContainmentError`, adds a credential broker, or wires a deployment.
**Predecessors:** `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 5,
row 5), `ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md` (GAS-2, GAS-3, OD-1–OD-3, §10).

## 1 — The question

Wave 5 row 5 says the runtime's README names pilot and production validation as
the next step. Is that still the position? No: the next rung shipped, and what
now blocks pilot lies entirely outside the runtime.

## 2 — Audit findings

| Finding | Evidence |
| --- | --- |
| `agent-runtime` 0.7.0 completes the H22 ladder through **H22-D** (0.6.0) and adds CM-TA1 provider-attempt telemetry, additive and opt-in `[V]` | `CHANGELOG.md` 0.7.0; `docs/AGENT_RUNTIME_H22_READINESS.md` ordering |
| Every release states `IMPLEMENTED_AND_CI_VERIFIED` and disclaims pilot and production in the same breath `[V]` | `README.md` maturity blocks |
| With no adapter, `UnconfiguredGovernanceHook` BLOCKs every consequential transition; the runtime mints no governance reference `[V]` | `docs/AGENT_RUNTIME_GOVERNANCE_INTEGRATION.md` |
| **The row's evidence is stale.** The ladder's next rung — runtime-to-governance integration — shipped as `ugence-agent-runtime-governance` 0.1.0 (`GovernedExecutionHook`, projecting a `GovernedExecutionDecision` from the ratified `RiskAuthorityCompositionEngine`, bound to the exact proposal), scoped GAS-3, with DBOS ratified as the engine under OD-3 `[V]` | that package's `__init__`; `ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md` §8B, §9 |
| The runtime's own integration doc still called that package "a future" one `[G]` | before this change: `AGENT_RUNTIME_GOVERNANCE_INTEGRATION.md` |
| Risk Authority `issue_envelope` fails closed in `production_mode`: signed envelope issuance is Phase 5, and "Production Risk Authority integration stops at a non-executable RiskDecision" `[V]` | `packages/risk_authority/src/risk_authority/api/dependencies.py:771-777` |
| No Credential Broker (cloud-scaling 5X) exists, so **no live execution is reachable regardless of engine** `[V]` | `ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md` §10 |
| ESCALATE has a sink (GAS-7 HR-A: `packages/integration/governed-review` binds an approval and consumes it before the engine advances); **HOLD, DEFER and MANUAL_REVIEW do not**, and HR-C/HR-D are unbuilt `[G]` | same §10 |
| Row 5's dependency is **execution authority**, not the evidence-attesting authority wave 5 rows 2–4 wait on; custody converges only at HSM/KMS, untouched in both `[I]` | this audit |

## 3 — Rulings

| Ruling | Consequence |
| --- | --- |
| **RT-ROW = RESTATE_AGAINST_REAL_BLOCKERS** | Wave 5 row 5 is amended in place, not closed. Closing it would drop three live gaps from the wave-5 ledger on the strength of a rung having shipped. The row now names Phase 5 envelope issuance, the absent Credential Broker, and the three unsunk dispositions, and cites this record. The runtime's integration doc is corrected in the same pass: the adapter is built, and a document calling it future reads as an open item that is not open. |
| **RT-SINK = HOLD_UNTIL_A_PILOT_NEEDS_THEM** | HR-C and HR-D are **not** built here. Nothing can park in production today — containment stands and no credential broker exists — so a human surface for a flow that cannot run would be built against imagined requirements, and HR-A already fixes the pattern to copy when one is real. The gap stays recorded, ranked behind RT-PHASE5, and is not closed by this ruling: the hook still emits HOLD, DEFER and MANUAL_REVIEW faithfully, the runtime still parks correctly, and a human still cannot see the parked instance. **Amended 2026-09-06 (RT-SINK-RESTATE) — the ruling stands; two of the facts it rested on did not.** ***What was wrong*** [G]. This row cited `ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md` §10, "the queue and decision surfaces (HR-C, HR-D) are not built", and reasoned from it that a human surface would be built against imagined requirements. **Both are built.** HR-C ships as `ugence-governed-review-service` 0.6.0 — `list_queue`, run rendering, decision recording and re-arm of the bound instance — and HR-D is recorded implemented on 2026-09-05 in `apps/ugence-governance-studio/docs/HUMAN_REVIEW_SCREEN_API_AUDIT.md`, two screens and five v2 relay routes, with `human_review_implemented = True` [V]. So "do not build HR-C/HR-D" was never a deferral: it was an instruction not to build what already existed. That §10 line is stale and is corrected in the same pass. ***What the gap actually is*** [V]. Not three dispositions — **one**. The hook emits exactly `CLEAR`, `BLOCK`, `HOLD` and `ESCALATE` (`agent-runtime-governance/dispositions.py`): `HOLD_NON_EXECUTABLE` becomes `ESCALATE` when `required_approvals` is present and `HOLD` otherwise, and **`DEFER` and `MANUAL_REVIEW` are never emitted at all** — they fall to `anything else -> BLOCK`, so no instance parks on them. `ESCALATE` is sunk by HR-A, and narrowly: `ApprovalBoundInputSource` acts on "one thing: whether the Decision Authority result is a HOLD carrying `required_approvals`". What remains unsunk is a `HOLD_NON_EXECUTABLE` **without** `required_approvals`. ***Why the deferral nonetheless stands, on the replaced ground*** [R]. Closing that residual case is not a surface build — the surfaces exist — but a change to what `ApprovalBoundInputSource` treats as reviewable, which HR-5 fixed. It is a ruling about what an unapproved hold *means*, and it is ruled below rather than left as a build item. |
| **RT-PHASE5 = CONTAINMENT_STANDS** | `ProductionContainmentError` is not lifted, and no schedule is set here. Lifting it means minting signed execution-authority artifacts through a production ActionGate — a capability with its own audit, custody and approval questions, none of which a scoping round may settle. Any future lift is its own ratification. |
| **RT-PILOT = DEFINE_PILOT_EVIDENCE_NOW** | The bar is fixed here so the word cannot drift into use. **"Pilot-validated" requires all of:** (1) a real `GovernanceHook` — never `AllowAllGovernanceHook` — deciding every consequential transition, with the deciding authority named; (2) a live environment with a real provider, real persistence and a real clock, not a simulation seam; (3) every disposition the hook can emit having somewhere to land, a human included; (4) execution actually reachable, which today needs both Phase 5 and 5X; and (5) recorded evidence — the runs, their dispositions, and what a human did with the parked ones. Until every one holds, no artifact of either package may say pilot-validated, production-certified, live-verified or enforcement-ready. |
| **HR-5-SCOPE = DELIBERATELY_NOT_REVIEWABLE** (ruled 2026-09-06 with the amendment above) | A `HOLD_NON_EXECUTABLE` carrying no `required_approvals` is **not** a human-review case, and HR-5's reviewable set is not widened. Such a hold names no approver and states no obligation, so the review queue would show an item with nothing decidable in it — an entry a human can look at and not act on, which is worse than no entry because it reads as pending approval. The instance still parks and still requires an explicit `resume_workflow`: that is an **operator** act, not a review, and this row rules it as such rather than leaving the case unclassified. **Stated so it is not read as closed** [G]: the operability question survives the ruling — an operator must still learn that an instance parked, and no surface in this repository tells them. That is a monitoring gap, recorded here, and it is not the human-review gap RT-SINK described. |

## 4 — What this record does not do

It builds nothing. It lifts no containment, adds no credential broker, no sink,
no queue, no decision surface, no adapter and no deployment. It changes no
package version, public surface, test or capability, and it does not claim any
gap is closed — RT-SINK defers one and says so.

## 5 — Next step

Row 5 moves when Phase 5 envelope issuance and the Credential Broker are
scheduled, and neither is scheduled by this record.
