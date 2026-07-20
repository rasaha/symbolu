# Agreement Report (v0.1)

Judge A / Judge B agreement and Judge C adjudication, from the deterministic run.

> **Not inter-human reliability.** The judges are deterministic rule engines, not
> independent human annotators or LLMs. This report is **process-level**: it
> describes where the advocate and challenger disagreed and what the adjudicator
> did. It does **not** establish inter-annotator or inter-human reliability, and no
> such claim is made.

---

## 1. A/B disagreement and adjudication

| Quantity | Value |
|---|---|
| Claims reaching the judges (not deterministically resolved) | 42 of 48 |
| Claims where A (support) and B (contradiction) disagreed on a predicate | 4 |
| Claims sent to Judge C | 4 |
| Judge C → UNKNOWN (equally explicit) | 4 |

The 4 adjudicated claims are exactly the equally-explicit **direction-conflict**
cases (`K0`–`K3`): Judge A found an explicit forward assertion in the cited span,
Judge B found an explicit exclusive-reverse assertion elsewhere. Judge C, seeing
both sides explicit, routed them to UNKNOWN / manual review rather than guessing.

## 2. Did Judge C improve over two judges alone?

Yes, measurably, on those 4 claims:

| Case set | V3 (A+B, no C) | V4 (A+B+C) |
|---|---|---|
| Equally-explicit direction conflicts (K0–K3) | resolved in advocate's favor → **SUPPORTED / retained** (4 false acceptances) | **UNKNOWN / manual review** (0 false acceptances) |

Effect: V3 precision 0.8333 → V4 precision **1.0000**; V3 status accuracy 0.9167 →
V4 **1.0000**. The improvement is entirely attributable to the adjudicator handling
the equally-explicit conflicts.

## 3. Where the other components disagreed with the baseline

- Judge A vs V0 (identity): A abstains/removes claims with no cited relation
  support (the 8 unsupported + 8 insufficient), 0 breaks.
- Judge B vs A: B adds detection of the 8 contradictions that A alone accepts.

## 4. Agreement caveat

Because the judges are deterministic and the corpus is self-authored, "agreement"
here is a property of the rule design, not of independent observers. A genuine
inter-annotator or inter-LLM study is future work and is **not** claimed here.
