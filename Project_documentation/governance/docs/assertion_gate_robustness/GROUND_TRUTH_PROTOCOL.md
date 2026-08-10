# Ground-Truth Protocol

*Phase 6. Ground truth is generated **independently of any gate's logic** and independently of the
**observed (noisy) signals**. It is adjudicated from two independent annotator rule formulations on
the TRUE latent facts. Source: `assertion_gate_robustness/dataset.py`.*

## Separation of concerns

| Layer | What it sees | Role |
|---|---|---|
| **TRUE latent facts** | true_support, true_relation, true_adequacy, claim_strength, true_stale, risk | reality |
| **Ground truth** | the TRUE facts (via annotators A + B) | what SHOULD be delivered |
| **Observed signals** | possibly-perturbed `SignalBundle` | what a method actually sees |
| **Method under test** | observed signals only | its decision |

Ground truth is a function of **reality**, not of the corrupted observations. Robustness is then
precisely "how well does a method recover the reality-based ground truth as its observations are
corrupted?" — the exact question this track exists to answer.

## Two independent annotators

- **Annotator A** (relation-and-gap first, adequacy as modifier): checks the evidence relation and
  the claim-vs-support gap, then applies adequacy/staleness/risk adjustments.
- **Annotator B** (adequacy-and-risk first, then relation): checks evidence adequacy and risk before
  the relation — a genuinely different decomposition order.

They are **not** the same rule renamed: because B checks adequacy first, A and B diverge on items
that are *supported but inadequate* (A → QUALIFY, B → ESCALATE/INDETERMINATE) and on some
stale/high-risk items.

## Adjudication (disagreement is recorded, not hidden)

- If A == B → that is the gold label.
- If A ≠ B → gold = the **more conservative** (safer withholding) of the two, and
  `annotator_disagreement = True` is recorded on the item.
- **Disagreement rate: 8.4%** (33 / 392 items). These items are flagged and reported separately;
  disagreement is never silently converted to consensus.

## Why adjudicate toward conservatism

For a *safety* layer, the cost of under-governance (delivering an unsupported claim) exceeds the
cost of over-governance (an unnecessary qualification/escalation). The adjudication rule encodes
that asymmetry explicitly, and the false-blocking metric tracks its cost.

## Corpus (agr_corpus_v1)

- **392 base items** across 8 domains (medical, legal, financial, cybersecurity [high-risk];
  scientific, enterprise [medium]; software, casual [low]) × 5 evidence relations × 7 support/claim
  buckets.
- **Gold distribution:** ALLOW 88, QUALIFY 52, ESCALATE 84, REJECT 56, INDETERMINATE 84,
  NOT_SUPPORTED 28. High-risk: 196. dev/eval = 98/294.
- **Partitions (1176 stored cases):** CLEAN (392, signals=truth), CONTROLLED_NOISE (392, one
  perturbation @0.3 cycling all types), COMPOUND_FAILURE (392, 2–3 interacting perturbations).
- **NOT the frozen 343-item AGE dataset** — independent construction; AGE data is calibration-only.

## Independence from the gate

The gate (Phase 8) computes dispositions from *observed signals* using *its own* thresholds. The
gold uses *true facts* via *A/B annotators*. No gate rule is reused to define gold, so a gate that
matches gold under noise is genuinely recovering reality, not re-deriving its own inputs.
