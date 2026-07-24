# Architectural Decision (Phase 23)

*`minimal_evidence_policy/architectural_decision.py` → `eval_results/decision.json`. One architectural
decision (of 9) and one pilot decision (A–I), evidence-gated from the frozen results.*

## Dimension findings

| Dimension | Finding |
|---|---|
| **Architectural need** | a small distinct obligation stage is justified — uniform (0% clean), global-threshold (unsafe), and the rich component (85 unsafe) all fail |
| **Safety** | 0 unsafe high-risk, 0 unsafe action, 0 self-verification escapes, monotonic (0/528) |
| **Utility** | clean allow 0% → 50%, over-qualification 85.5% → 0% |
| **Reviewer evidence** | **NOT EVALUATED** (no real reviewers; proxy only) |
| **Complexity** | 12 policy-logic rules (≤20); minimum viable safe = risk+claim+temporal+action |
| **Latency** | sub-ms, stdlib-only, deterministic |
| **Metadata burden** | risk + claim-type are load-bearing |
| **Internal-pilot readiness** | READY (bounded, non-enforcing, audited) |
| **External-pilot readiness** | **BLOCKED** (human validation missing) |
| **Production readiness** | NOT established |

## Architectural decision: **Option 1 — KEEP MINIMAL EVIDENCE POLICY AS A DISTINCT STAGE**

The obligation concept is needed and the minimal policy is safe, useful, monotonic, explainable, and
within budget — so Options 3 (risk-floor only, unsafe), 7 (retain rich, unsafe), 8 (not enough
evidence), and 9 (reject) are excluded. **Option 2 (risk floor + anti-self-verification only) is
insufficient** because the ablation shows **claim-type is safety-critical** (removing it adds 43 unsafe
allows) — the safe policy needs the risk floor **and** the claim-type/temporal/actionability modifiers,
which is exactly the distinct minimal stage. So the minimal policy is kept **as a distinct stage** at
~12 policy-logic rules, with the anti-self-verification invariants retained as cheap
classification-independent insurance.

*Documented reduction:* within the stage, the **minimum viable safe policy is risk + claim-type +
temporal + actionability** (12 rules); the 12 invariants may be trimmed to the ~5 anti-self-verification
ones (`INV-1/2/5/6/12`) once a cleaner adversarial isolation confirms their marginal value.

## Pilot decision: **B — PROCEED TO INTERNAL SINGLE-TENANT PILOT**

The policy passes all 10 frozen technical criteria and is safe, but **human validation is NOT
EVALUATED**, so an external customer pilot (A) is blocked by the frozen protocol. The constructive next
step is an **internal single-tenant pilot** — bounded, non-enforcing, audited — whose primary purpose is
to run the **real human-review study** (Phase 12 protocol) that closes the outstanding gate. Options E/F/G
(fix reviewer-agreement / utility / safety-invariants first) are unnecessary — utility and safety already
pass; the gap is real human validation, which the internal pilot provides. H/I are too strong given
10/10 technical criteria.

## One-line statement

> A minimal, monotonic, 12-rule evidence-obligation policy restores natural-artifact utility (clean allow
> 0% → 50%, over-qualification 85.5% → 0%) with **0 unsafe high-risk/action allows and 0 self-verification
> escapes** — safer than both risk-only and the rich component — and is ready for an **internal**
> single-tenant pilot; an external pilot stays blocked until real human validation is done.
