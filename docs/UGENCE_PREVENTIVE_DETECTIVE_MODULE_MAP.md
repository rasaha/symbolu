# Ugence — preventive / detective module map

**Status:** scoping map, 2026-09-06. Documentation only; no code changed. Labels:
`[V]` verified, `[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

For a client running ServiceNow, Snowflake and Microsoft, which Ugence units may be sold
as **preventive controls** (Ugence enforces) and which as **detective controls** (Ugence
observes), without crossing the §11.2 non-goals — no live execution, no credentials `[V]`
(`Project_documentation/repository/ugence_platform/UGENCE_PRODUCTIZATION_ROADMAP.md:353-359`)?

**Answer: one unit is preventive, and only at a boundary Ugence hosts. Everything else is
detective today.** Nothing in the portfolio is pilot-validated or production-certified
`[V]` (Appendix B.5: zero capabilities carry either tag,
`docs/UGENCE_ENTERPRISE_AI_GOVERNANCE_CAPABILITY_PIPELINE.md:1502`).

## 2 — Classification rule

A unit is **preventive** only if all three hold:

1. it fills a gap the vendors structurally will not close — cross-vendor clearance, an
   independently verifiable receipt, or re-clearance on retry;
2. enforcement occurs at a boundary Ugence hosts (a provider or tool the client's agent
   calls), so Ugence holds no client credential;
3. the unit's own README does not declare itself shadow-only.

Otherwise it is **detective**: it evaluates, records and reports, and emits the same
receipt with a would-have-decided field (§4).

## 3 — The map

The 66 packages under `packages/` group into nine units. Stage tags are Appendix B.2
vocabulary `[V]` (`...CAPABILITY_PIPELINE.md:1380-1395`).

| # | Unit | Packages | Class | Why | Stage / evidence |
|---|---|---|---|---|---|
| 1 | **Action clearance and reservation** | `action-clearance`, `execution-reservation`, `providers/actiongate`, `risk_authority`, `risk-authority-runtime`, `agent-runtime-governance`, `runtime/agent-runtime`, `durable-execution`, `decision-authority` | **Preventive at a hosted boundary; detective otherwise** | The hook fires before any provider invocation and re-clears on retry `[V]` (`packages/runtime/agent-runtime/src/ugence_agent_runtime/governance/interfaces.py:118`; `packages/integration/agent-runtime-governance/src/ugence_agent_runtime_governance/hook.py:129,174`); reservation is one-time per execution key `[V]` (`.../ugence_execution_reservation/reservation.py:345`). Structural gap 3. Enforcing on a system Ugence does not host needs client credentials — §11.2. | ActionGate, Action Clearance: Core implemented (B.4 rows 36-37). Agent Runtime: CI-verified, pilot pending, "not enforcement-ready" (row 38). Execution Reservation README: "Reference-grade, shadow-only, not enforcement-ready" `[V]`. |
| 2 | **Evidence and receipt** | `trusted-evidence-authority`, `jcs`, `control-plane-root`, `risk-authority-evidence-runtime` (RA-5), `-effect-attestation`, `-execution-assurance` (RA-8), `-runtime-assurance` (RA-7), `-status-runtime` (RA-6), `agent-assurance-evidence` | **Detective** | Structural gap 2. RA-8 observes and assesses post-effect and emits no authority `[V]`. Effect attestation types `EXECUTING_PROVIDER` against `INDEPENDENT_OBSERVER` and states provider self-attestation is not independent `[V]` (README, SE-2) — the independence thesis is already a typed role. | TEA: Core implemented (row 26). RA-5 to RA-8: Reference-grade (rows 28, 40-42). Effect attestation "NOT PRODUCTION-READY. Not wired into RA-8" `[V]`. |
| 3 | **Human authority and approval** | `approval-workflow`, `governed-review`, `governed-review-service`, `approver-identity-jwt`, `authority-directory` | **Detective**; preventive only inside unit 1's hosted boundary | ServiceNow and Entra own approvals. Ugence binds the client's approval into the receipt and consumes it once `[V]` (`governed-review` README: "binds and consumes; never approves"). | "Reference-grade, shadow-only, not enforcement-ready" `[V]` (READMEs). |
| 4 | **Policy authority and constitution** | `policy-authority`, `uvi-policy-contracts`, `agent-constitution-policy`, `-activation`, `-conformance`, `agentic-proposer-strategy-permission-policy`, `-runtime`, `tooling/policy-workflow-compiler`, `cloud-scaling-capacity-bounds-policy` | **Detective**; input to unit 1 | Supplies the digest-bound, signed policy version in the receipt; not a competing policy engine. | Policy Authority: Core implemented, persistence deferred (row 6). Constitution: Phase in progress (rows 8, 12). No signing key or trust root in the repository (row 9) `[G]`. |
| 5 | **Registry and declarations** | `ai-system-registry`, `data-use-admission`, `vendor-dependency`, `incident-response`, `benchmark-registry`, `-authority` | **Detective**, not sellable alone | READMEs: "Contracts only" or "Records only. Not enforcement-ready" `[V]`. AICT and Agent 365 are richer registries; these feed receipt provenance. | Contract-only (rows 4, 27) `[V]`. |
| 6 | **Cloud-scaling execution ladder** | `cloud-scaling-operations`, `-authorization-contracts`, `-action-admission`, `-bounded-execution`, `-envelope-issuance`, `-policy-authenticity`, `-producer-attestation`, `-credential-broker`, `-risk-integration`, `cloud-scaling-controller` | **Detective in `SHADOW`; preventive only after §11.2 is reopened** | The one unit with a real executor: Kubernetes and ArgoCD actuation, `LIVE` off by default, `SHADOW` = "authorized read-only observation only; never mutates" `[V]` (`.../ugence_cloud_scaling_operations/contracts.py:20-26`). `LIVE` and credential brokering are what §11.2 forbids. | Operations: Core implemented, not live-cluster validated (row 39). 5X "holds no provider secret", 5D "holds no credential" `[V]`. |
| 7 | **Advisory capabilities** | `agentic-proposer`, `agent-workforce-composer`, `model-selection`, `llm-steering-controller`, `context-minimization` (+ token accounting), `storygraph`, `agent-value-readiness`, `governed-value`, `providers/tap`, `reasoning-method-governance`, `reasoning-method-advisor`; research-only and excluded: `readiness-comparison`, `workflow-fit-pilot` | **Not a control** | Advisory inputs. TAP is the one detective-shaped member (feeds "evidence accepted or rejected"). The two reasoning-method packages enter under `ADR_UGENCE_REASONING_METHOD_PRODUCT_ENTRY.md` (RM-1..3): an advisory is product input only through a `ReasoningMethodAdvisoryAdmission` backed by comparison evidence, of which none real exists yet `[G]`. Two remain Research-only under §11.2 (rows 18-19). | Core implemented, Frozen, Experimental, Research-only (B.5). |
| 8 | **Domain products** | `products/ai-hiring`, `products/procurement` | **Out of this map** | Vertical systems of record `[V]`. For a ServiceNow client they are replacements, not insertions. | Not assessed. |
| 9 | **Substrate** | `governance-contracts`, `governance-provider-framework` | **Not sellable** | Contract layer every unit depends on. | Core implemented (rows 1-2). |

**Hosted-boundary reading of unit 1 `[I]`.** If Ugence hosts the provider — an MCP server
or tool the client's ServiceNow, Copilot or Cortex agent calls — the hook clears before
invocation using Ugence's own tool-scoped credential, and no client credential is held. If
Ugence must instead call the client's system with the client's credential, that is §11.2.
No hosted-boundary provider exists today `[G]`; the studio's fixture providers are the
nearest thing (`ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md` §3 row 7).

## 4 — The single receipt

Both classes emit one artifact, extending the existing `ClearanceReceipt` `[V]`
(`packages/integration/execution-reservation/src/ugence_execution_reservation/receipts.py:160`),
which already carries `target_ref`, `operation`, `profile_id`,
`action_governance_result_fingerprint`, `decision_record_ref`, `context_envelope_ref`
and `context_envelope_hash`. Fields, in the order an auditor reads them:

| Field | Source | Platform read API needed |
|---|---|---|
| `proposal` — the exact action digest | unit 1 (`ActionGate` result fingerprint) | no |
| `policy_version` — digest-bound, signed | unit 4 (Policy Authority resolution) | no |
| `evidence` — accepted and rejected, with trust level | unit 2 (RA-5) and TAP | partly: evidence originating in Snowflake or Purview `[G]` |
| `identity_and_authority` — who, which role grant, until when | unit 3 (`authority-directory`, `approver-identity-jwt`) | yes, for Entra Agent ID or ServiceNow identity `[G]` |
| `approval` — required, obtained, consumed once | unit 3 | yes, where the approval lives in ServiceNow `[G]` |
| `decision` — `CLEAR`, `HOLD`, `ESCALATE`, `BLOCK`, with reason codes | unit 1 (`action-clearance` statuses `[V]`) | no |
| `control_class` — `PREVENTIVE` or `DETECTIVE` | deployment configuration | no |
| `would_have_decided` — for `DETECTIVE`, the decision Ugence would have enforced; for `PREVENTIVE`, equal to `decision` | unit 1 in shadow | no |
| `observed_effect` — `MATCHED`, `MISMATCH`, `PARTIAL`, and the attester role | unit 2 (RA-8 assessment; effect attestation role) | **yes** — the effect record is the executing platform's `[G]` |
| `audit_ref` — ledger position | unit 2 (`control-plane-root`) | no |

`control_class` and `would_have_decided` exist nowhere today `[G]`. `observed_effect` is
what makes the receipt independent, and it depends entirely on platform records Ugence does
not own. Without it the receipt proves clearance, not outcome.

## 5 — First-cycle findings, per detective unit

A detective unit that produces no finding in its first cycle is shelfware and is withdrawn
from the deployment. The finding each must emit:

| Unit | First-cycle finding | Exists |
|---|---|---|
| 1 (shadow) | Count of actions Ugence would have refused, and the **adjudicated wrongful-refusal rate**: refusals a named human later judged wrong, over all attempted actions in the window | The scoring shape exists — predictions joined to independently captured outcomes, false-eligible and false-ineligible rates `[V]` (`execution_gate_shadow/metrics.py:57-61`, `outcomes.py:65-73`, `dry_run.py:106-108`). It scores **provider eligibility**, not action clearance; retargeting to `CLEAR`/`BLOCK` decisions is unbuilt `[G]`. |
| 2 | Consequential actions in the window with **no resolvable authorization** — the "fourteen actions nobody can prove" report | Requires the platform read API `[G]`; RA-8 correlation exists for actions Agent Runtime itself attempted `[V]`. |
| 3 | Actions executed with an approval that was absent, expired, or granted by a role outside the directory's window | `approval-workflow` derived expiry and `authority-directory` time-bounded grants exist `[V]`; reading the client's approval system `[G]`. |
| 4 | Actions executed under a policy version that was superseded or revoked at execution time | Policy Authority revocation exists `[V]` (row 6); binding to external actions `[G]`. |
| 5 | Agents acting that are unregistered, or acting on data or vendors never declared | Contracts exist; no connector to AICT or Agent 365 `[G]`. |
| 6 (`SHADOW`) | Divergence between the recommended and the actual scaling change | Shadow mode exists `[V]` (`contracts.py:25`); not live-cluster validated (row 39). |

## 6 — Where §11.2 is triggered

- Unit 1 enforcing on a system Ugence does not host: credentials — **triggered**.
- Unit 6 in `LIVE`: live execution and credentials — **triggered**.
- Unit 3 as preventive: only through unit 1, so inherits unit 1's condition.
- Units 2, 4, 5: never; detective by construction.

**Documentation drift `[V]`.** The roadmap says the Credential Broker "remains unbuilt"
(`UGENCE_PRODUCTIZATION_ROADMAP.md:356`) and Appendix B row 34 lists 5C, 5X and 5D as not
implemented, yet `cloud-scaling-credential-broker` (5X), `-action-admission` (5C) and
`-bounded-execution` (5D) exist at 0.1.0. Neither holds a credential, so §11.2's intent
holds; its wording does not. Correct the roadmap before a buyer reads it.

## 7 — Rulings for ratification `[R]`

1. **Preventive units are drawn only from structural gaps** — cross-vendor clearance, the
   independently verifiable receipt, re-clearance on retry. Unit 1 qualifies; no other
   unit does today.
2. **Ugence enforces only at a boundary it hosts** until §11.2 is reopened by its own ADR.
   A hosted-boundary provider is the first build, because none exists.
3. **The control vocabulary is preventive and detective.** "Risk mitigation" and "risk
   control" are retired; every unit, screen and receipt carries `control_class`.

## 8 — Next step

The map turns on one missing thing: a boundary Ugence hosts. Specify it before any
enforcement claim is made:

> Write `docs/ADR_UGENCE_HOSTED_BOUNDARY_PROVIDER_SCOPING.md`: scope the first provider
> Ugence hosts — an MCP server or tool that a ServiceNow, Copilot or Cortex agent calls —
> through which unit 1 enforces without holding any client credential. State the exact
> Agent Runtime provider contract it satisfies with `file:line`, the clearance and
> reservation path it exercises (`hook.py`, `reservation.py`), the receipt it emits per §4
> of the module map, how a retry is forced and re-cleared under GAS-R6, and the refusal
> case. State which §11.2 non-goals it preserves and which it does not. Close with one
> owner ruling on the first tool to host. Max 1200 words. Commit to
> `claude/agentic-studios-comparison-n8jlbv`.
