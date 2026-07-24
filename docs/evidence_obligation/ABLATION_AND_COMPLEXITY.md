# Ablation Study & Complexity Challenge (Phases 18–19)

*`evidence_obligation/ablation.py` → `eval_results/ablation.json`. Which features are load-bearing, and
does the full component earn its complexity?*

## Ablation (remove one feature from the full component)

Full component: clean allow 0.584, high-risk unsafe 0, adversarial unsafe 10.

| Ablated feature | clean allow | Δ clean | adversarial unsafe | load-bearing for safety |
|---|---|---|---|---|
| authority_guard | 0.584 | 0.000 | 10 | **No** |
| risk_escalation | 0.584 | 0.000 | 10 | **No** |
| structural_floors | 0.584 | 0.000 | 10 | **No** |
| source_role | 0.316 | −0.268 | 10 | No (utility only) |
| **risk** | 0.624 | +0.040 | **20** | **Yes** |

**Only `risk` is load-bearing for safety** — removing it doubles adversarial unsafe (10→20). The
authority guard, risk escalation, and structural floors are **inert on this dataset**: removing them
changes nothing, because the natural artifacts rarely trigger them and the one adversarial leak (model
self-verification → `CONTEXTUAL`) is caught by none of them. `source_role` is load-bearing for **utility
only** (it enables implementation-evidence allows; clean allow drops 27pp without it) but not for safety.

**Minimum viable safe policy ≈ risk-tier**, with claim-type + source-role added only to recover utility.
Most of the component's machinery is defensive-but-untriggered here — reported honestly.

## Complexity challenge

| Comparator | clean allow | adversarial unsafe | approx rules |
|---|---|---|---|
| **Simple1 risk_only** | **0.668** | **0** | **3** |
| Simple2 claim+risk | 0.264 | 0 | 31 |
| Simple3 source+authority | 0.000 | 0 | 15 |
| Simple4 claim+source+risk | 0.264 | 0 | 46 |
| Learned S | 0.332 | 0 | ~0 |
| **Full Q** | 0.584 | **10** | **90** |

**Simple1 (risk-only) dominates the full component on every axis: higher clean allow (0.668 vs 0.584),
zero adversarial unsafe (vs 10), and 3 rules vs 90.** The full component's 90 rules do not earn their
complexity — they add adversarial unsafe allows *without* adding utility. (Risk-only's residual is 16
low/medium-risk unsafe allows, off the safety-critical surface; the learned comparator trades clean-allow
for ~1 total unsafe.)

## Falsification impact

- **H0-2 (risk tier alone performs as well)** — **RETAINED**: risk-only exceeds the full component on
  clean allow and adversarial safety.
- **H0-13 (simple comparator matches the component)** — **RETAINED**: Simple1 and S both match-or-beat Q
  at far lower complexity and better safety.
- **H0-4 (source role adds no value)** — **REJECTED for utility** (27pp clean-allow drop when ablated),
  but source role is **not** load-bearing for safety.
- **H0-17 (a distinct EvidenceObligation stage is unnecessary)** — **leaning RETAINED**: the distinct
  90-rule stage is not justified over a 3-rule risk policy on this evidence; the value is in the
  *obligation concept + contract*, deliverable by a much simpler policy.

## Bottom line

The rich `EvidenceObligation` component is **not** justified by the ablation/complexity evidence. Its
safety-relevant content reduces to risk assessment; its utility content reduces to claim-type +
source-role. A small, safety-calibrated policy (risk-tier, optionally + claim-type + source-role)
captures the benefit without the 90-rule surface — and, critically, without Q's adversarial unsafe
allows. This directs the architectural decision toward **reduce/simplify**.
