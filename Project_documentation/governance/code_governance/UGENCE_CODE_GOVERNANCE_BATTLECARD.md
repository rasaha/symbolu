# Ugence Code Governance — Competitive Battlecard

*One-page sales/website reference. Full analysis:
[`UGENCE_CODE_GOVERNANCE_COMPETITIVE_POSITIONING.md`](UGENCE_CODE_GOVERNANCE_COMPETITIVE_POSITIONING.md).
Competitor facts from vendor docs reviewed 2026-08-02 — re-verify before publishing.*

---

## The one-liner
**Copilot and CodeRabbit tell you what's wrong with the code. Ugence decides whether
that exact change is allowed to merge and deploy — and proves why.**

## The wedge (lead with this)
**Ugence prevents the same AI or developer from writing, validating, approving, and
executing its own change.**

## Category
Enterprise **software-change authorization & governance** — *not* AI code review, SAST,
or merge automation.

---

## Review vs. Governance
| Code review (Copilot, CodeRabbit) | Code governance (Ugence) |
|---|---|
| "What looks wrong, and how to fix it?" | "Is this **exact** change authorized to merge/deploy — given evidence, policy, identity, approvals, live state?" |
| Comments, suggestions, pass/fail checks | Binding decision + exact-artifact authorization + live clearance + reconstructable chain |
| Advisory or configurable gate | **Independent** decision authority, separate from author & reviewer |

---

## Six differentiators
1. **Independent evidence validation** — findings & CI are *evidence, not authority*; provenance/admissibility checked.
2. **Binding decision authority** — a recommendation ships only via an authorized decision.
3. **Exact-change authorization** — bound to base SHA, head SHA, merge method, merge-tree/merge-group, artifact digest.
4. **Live pre-execution clearance** — rechecks SHA/CI/incident/freeze/expiry right before merge or deploy.
5. **Cross-event governance** — detects control-erosion sequences (weaken tests → alter policy → change sensitive code).
6. **End-to-end reconstruction** — who decided, on what evidence, under which policy, what exact artifact, what executed.

---

## Complement, not replace (they're inputs)
```
Copilot / CodeRabbit / Qodo · Snyk / Semgrep / SonarQube · GitHub / GitLab · CI · humans
                    ↓ evidence & findings
              Ugence Code Governance
                    ↓
   binding decision → exact authorization → live clearance → governed execution
```

## Quick objection handling
| They say… | You say… |
|---|---|
| "We already use CodeRabbit." | "Great — it becomes an evidence source. Ugence decides whether its findings + your approvals authorize this exact merge." |
| "GitHub Rulesets enforce our merges." | "Repo rules count approvals and require green checks. Ugence validates *who produced the check, with which policy/tool version, supporting which claim*, and binds the exact merge artifact — plus separate deploy authority." |
| "Isn't this Copilot?" | "Copilot always submits a *Comment* review — advisory, can't approve or block. Ugence is the authority layer above it." |
| "Isn't this just CodeRabbit + Snyk + GitHub rules + Mergify + Harness?" | "That stack approximates parts as five loosely-connected tools. Ugence is one reconstructable chain from evidence → decision → exact authorization → live clearance → execution, and treats those tools as inputs." |
| "Harness/OPA already does policy." | "Inside its own pipeline. Ugence is vendor-neutral across AI decisions, repos, and execution systems — Harness can be an execution target or evidence source." |

---

## Closest competitor
**CodeRabbit** — AI review + configurable pre-merge gate; real overlap on policy checks,
PR blocking, approval workflows, override auditability. **Center of gravity differs:**
CodeRabbit = AI review + pre-merge validation; Ugence = decision authority + exact-action
authorization + execution governance. Best treated as an **integration partner &
evidence source**, not a replacement target.

## Claims to avoid
- Don't say "proves code correct" → say evidence-supported, policy-compliant,
  bound-to-exact-artifact, reconstructable, operationally cleared.
- Don't say "better AI reviewer" (wrong category) or "no one can do this" (say: no
  single product presents the *complete* chain per documented boundaries).
- Don't overstate maturity (TAP = prototype; ACP/ActionGate = shadow; durable audit
  store = planned).

## Proof to show
Reconstruct a merge on demand: **DecisionRecord → evidence refs → policy → exact-artifact
authorization → ACP clearance → executed merge.**
