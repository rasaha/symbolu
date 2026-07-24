# Architectural Decision (Phase 25)

*`evidence_obligation/architectural_decision.py` → `eval_results/decision.json`. One architectural
decision (of 10) and one pilot decision (A–H), evidence-gated from the frozen results.*

## Dimension findings (each judged on its own evidence)

| Dimension | Finding |
|---|---|
| **Architectural need** | the obligation **concept** is needed — uniform and global-threshold approaches fail (0% clean or 100 unsafe) |
| **Algorithmic complexity** | the 90-rule component is **not** justified over a 3-rule risk / claim+source policy |
| **Natural-artifact utility** | large gain: 0% → 29.6% (safe oracle) / 58.4% (reference); over-qual 85.5% → 2% |
| **High-risk safety** | held-out high-risk unsafe **0**; adversarial disguise leaks **10** (reference), **0** (oracle) |
| **Reviewer burden** | simulated agreement 0.316; overrides skew stricter; **real study required** |
| **Latency** | sub-ms, stdlib-only, deterministic |
| **Metadata** | load-bearing features = claim-type + source-role + risk |
| **Operational maturity** | shadow-only, read-only; no real reviewers/evidence/traffic |
| **Customer-pilot readiness** | **blocked** |
| **Production readiness** | **not established** |

## Architectural decision: **Option 3 — REDUCE TO CLAIM-TYPE + SOURCE-ROLE POLICY**

The obligation **concept** is validated (utility rises with zero safety cost under the oracle; uniform
and global calibration fail), so Options 8 (global sufficient), 9 (not enough evidence), and 10 (reject)
are excluded. But the **distinct 90-rule stage is not justified**: risk-only (3 rules) reaches higher
safe clean-allow, and the ablation shows the authority-guard / risk-escalation / structural-floor
machinery is inert on this data while `source_role` (utility) and `risk` (safety) are the load-bearing
features. So Option 1 (keep distinct stage) is not supported.

**Reduce to a claim-type + source-role policy** (Option 3): keep the two features that carry the
signal — claim-type for the hard-floor safety (medical/financial/legal never shortcut) and source-role
for the utility gain (implementation/authoritative allows) — plus risk as the safety knob, and drop the
inert rule surface. This preserves the validated benefit at a fraction of the complexity.

*Documented simpler alternative:* **Option 4 (risk-tier policy)** reaches the highest safe clean-allow
(0.668) and is the minimal viable safe policy; it is the fallback if claim-type/source-role
classification proves unreliable on real traffic. *Documented narrower alternative:* **Option 2
(high-risk domains only)** if the general utility gain does not justify the machinery outside
medical/financial/legal.

## Pilot decision: **D — FIX EVIDENCE OBLIGATION FIRST**

The reference classifier leaks 10 adversarial disguise cases (model self-verification) and the simulated
review study shows unstable fine labels with stricter-skewed overrides. No external or internal pilot
should run on a classifier that clean-allows disguised high-burden claims. **Fix the obligation
classifier's adversarial safety and simplify it to the claim-type + source-role policy first**; then an
**internal single-tenant pilot (B)** with a **real review study** is the constructive next step. Options
A (external) and C (low-risk-only) are premature; G/H are too strong given the validated concept.

## One-line statement

> Contextual evidence obligation **works as a concept** — it converts the natural-artifact over-
> qualification failure (0% clean allow) into 29.6% safe clean-allow with over-qualification down from
> 85.5% to 2% — but the **rich 90-rule component is neither the safest nor the simplest way to get
> there**: reduce it to a claim-type + source-role (+ risk) policy, fix its adversarial self-verification
> blind spot, and re-gate on an internal pilot with real reviewers before any external exposure.
