# R2 — Remediation Corpus & Retry-Governance Study (evidence for planner automation)

Purpose: **not** to build an LLM planner, but to determine, using measured evidence, whether
planner automation is justified. Deterministic (no LLM), grounded in the REAL reference gate;
ActionGate semantics are unchanged.

## Deliverables
| file | role |
|---|---|
| `corpus.py` | 153 grounded scenarios across all 10 operations; 5-class ground truth (EVIDENCE / SIMULATION / ACTION_MODIFICATION / HUMAN_ONLY / TERMINAL); adversarial / repeated-retry / oscillation / conflicting / policy-opt-in cases |
| `simulator.py` | deterministic retry-governance simulator: evaluate → project remediation → apply a deterministic transform → re-evaluate, until ALLOW\*/terminal/human/oscillation/stall/budget |
| `metrics.py` | all required metrics + the evidence-based verdict |
| `run_r2.py` | runs the study, writes `r2_metrics.json` + `R2_REMEDIATION_STUDY.md` |
| `r2_metrics.json` | measured metrics (generated) |
| `R2_REMEDIATION_STUDY.md` | the report (generated) |
| `../../tests/test_r2_study.py` | corpus/simulator/security/verdict tests (17) |

Regenerate: `python3 run_r2.py` (from this dir).

## Headline (measured)
- **LLM planner automation: `STOP`.** Deterministic remediation: `LIMITED_GO`.
- Action-modification is ~15% of scenarios; **61%** of those are resolved by a *deterministic*
  numeric transform (no planning). Every action-modification failure is a **safety stop**
  (modification unbinds a hard precondition/approval → DENY) or a capability/human limit, so the
  **measured planning gap an LLM could close is 0%**.
- Security invariants all hold: no execution token minted, a fresh `action_hash` on every
  modification, no retry bypasses DENY, no success reached through a DENY. Policy leakage 0;
  decision stability 100%.

## The question this answers
> "Should ActionGate ever be allowed to drive an automatic planner loop, and under exactly what
> measured conditions?"

**No, not on this evidence.** An automatic loop would only be justified if a future (production)
corpus showed action-modification is a large share (≥30%) AND a substantial fraction fail for
reasons genuine *search* could fix (planning-gap ≥10%) rather than safety/capability/human
limits, AND every security invariant is preserved. Until then, the safe path is a *deterministic*
remediation loop confined to policy-opted-in mechanical classes, with any LLM planner kept
outside the trust boundary. See `R2_REMEDIATION_STUDY.md`.
