# Signal Model

*Phase 2. Each input signal defined independently. No signal is assumed correct by construction;
every one carries a value, a confidence, provenance, a timestamp, and explicit missing/conflict
behavior. Implemented in `assertion_gate_robustness/signals.py`.*

## Signals

### Grounding
- **Question:** does supplied evidence *contain support relevant* to the assertion?
- **Value:** `support ∈ [0,1]`. **Categorical:** none / weak / partial / strong.
- **May independently REJECT?** No (absence of grounding ≠ contradiction). **May independently
  ALLOW?** No (relevance ≠ logical support). **Missing:** treated as no-support, not contradiction.

### Entailment
- **Question:** does the evidence *logically support* the assertion (not merely mention it)?
- **Value:** label ∈ {supports, contradicts, neutral}. **Confidence** ∈ [0,1].
- **May independently REJECT?** Yes, `contradicts` at high confidence. **May independently ALLOW?**
  No (needs adequacy + risk). **Missing:** neutral/indeterminate.

### Evidence adequacy
- **Question:** is the evidence *sufficient* in quantity, quality, relevance, scope?
- **Value:** `adequacy ∈ [0,1]`. **Categorical:** insufficient / marginal / adequate.
- **Role:** a gate on ALLOW — high support+entailment with low adequacy ⇒ not ALLOW.

### Risk
- **Question:** consequence of delivering the assertion wrong / unqualified?
- **Value:** low / medium / high / critical. **Effect:** raises the bar; unknown ⇒ treat as high.

### Freshness
- **Question:** is the evidence current enough for the claim?
- **Value:** `age_days`, `required_recency_days`. **Stale ⇒** down-weight support; may force QUALIFY/
  ESCALATE for time-sensitive claims.

### Conflict (disagreement)
- **Question:** do credible sources disagree?
- **Value:** `conflict ∈ {none, minor, major}`. **Effect:** major conflict ⇒ ESCALATE (high-risk) or
  INDETERMINATE.

### Authority
- **Question:** is the evidence/policy source authorized for the domain?
- **Value:** authorized / unauthorized / unknown. **Effect:** unauthorized source down-weights
  support; does not by itself ALLOW.

### Calibration (signal trust)
- **Question:** how trustworthy is the signal-producing component?
- **Value:** per-signal reliability ∈ [0,1]. **Effect:** low calibration ⇒ the signal's confidence
  is discounted (uncertainty propagation).

## Per-signal contract

| Property | Rule |
|---|---|
| value range | as above; normalized |
| categorical interpretation | documented buckets |
| confidence | every signal carries `[0,1]` confidence; missing ⇒ 0 |
| provenance | source id; unknown provenance down-weights |
| timestamp | for freshness; missing ⇒ treat as stale |
| failure modes | false-positive / false-negative / missing / stale (see NOISE_TAXONOMY) |
| missing-state | fail toward uncertainty, never toward ALLOW |
| conflict-state | surface, never average away |
| may independently REJECT | only entailment=contradicts (high conf) |
| may independently ALLOW | **none** — ALLOW requires support ∧ entailment ∧ adequacy ∧ risk-ok |

## Load-bearing principle (tested in ablation)

The central design claim: **no single noisy signal is authoritative for ALLOW**, and **signal
confidence/freshness/conflict are propagated** so the gate can distinguish *uncertainty* (→
INDETERMINATE/ESCALATE) from *contradiction* (→ REJECT). Whether these propagated meta-signals are
actually load-bearing under noise is exactly what Phases 12–14 test — they are not assumed to help.
