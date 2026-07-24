# Dataset Specification (age_corpus_v1)

*Phase 6. Deterministic synthetic corpus. Ground truth is an INDEPENDENT categorical rubric,
authored and frozen before the engine. Source: `assertion_governance/dataset.py`.*

## Composition (343 items)

- **Domains (7):** medical, legal, financial (high/critical risk); scientific, enterprise
  (medium); coding, casual (low).
- **Evidence relations (5):** supports (147), contradicts (49), neutral (49), missing (49),
  conflicting (49).
- **Support × claim-strength buckets (7):** well-supported, small overclaim, large overclaim,
  under-claim, etc.
- **Ground-truth dispositions:** ALLOW 84, QUALIFY 45, ESCALATE 60, REJECT 49, INDETERMINATE 77,
  NOT_SUPPORTED 28.
- **High-risk items:** 147. **Adversarial-to-AGE items:** 18 (well-supported high-risk claims where
  AGE's risk-escalation would be *wrong* — these punish over-escalation).
- **Split:** dev 114 / eval 229 (deterministic by index; baselines tuned on dev only).

## Per-item fields

`domain, risk_class, claim_text, claim_strength∈[0,1], evidence_support∈[0,1],
evidence_relation∈{supports,contradicts,neutral,missing,conflicting}, model_confidence,
authority_governed∈{yes,no,conflict}, gold_disposition, gold_reason, split, adversarial_to_age`.
No credentials/customer data/real content — abstract features + short synthetic claim stubs.

## Ground-truth rubric (independent human-judgment rule, frozen)

```
contradicts                          -> REJECT
missing        & high-risk           -> ESCALATE      (else NOT_SUPPORTED)
conflicting    & high-risk           -> ESCALATE      (else INDETERMINATE)
neutral                              -> INDETERMINATE
supports & gap<=0.10                 -> ALLOW         (gap = claim_strength - evidence_support)
supports & gap>0.10 & high & gap>=0.40 -> ESCALATE
supports & gap>0.10                  -> QUALIFY
```

The rubric expresses a domain-expert standard: contradicted claims are withheld; overclaims are
delivered weaker (QUALIFY); missing/conflicting evidence in high-risk domains goes to a human;
large high-risk overclaims go to a human.

## Anti-circularity design (critical)

- The rubric is **categorical** (relation + gap bucket + risk). It is NOT the AGE engine.
- **A key preliminary finding falls straight out of the baselines:** a trivial composition
  *grounding + entailment + a risk rule* (Baseline **G_risk**) reproduces this rubric **exactly
  (1.0)** on eval, while grounding+entailment alone (Baseline G) reaches 0.83. **This means the
  delivery decision decomposes into existing signals plus a risk overlay** — before AGE is even
  built. The remaining scientific question is therefore sharp: *does a separate AGE engine beat the
  trivial G_risk composition?* If not, AGE is not an independent capability.
- To keep the AGE engine's test non-circular and realistic, AGE (Phase 8) works from **continuous
  scalars** (`evidence_support`, `claim_strength`, `risk`, coarse flags) and must **infer** the
  categorical relation — so it can (and will) make boundary errors the oracle rubric does not. AGE
  is **not** tuned on eval.
- **Adversarial-to-AGE items** (18) specifically punish AGE's risk-escalation heuristic where the
  correct answer is ALLOW.

## Frozen

`age_corpus_v1` and its `corpus_v1.json` are frozen for the evaluation. Any change is a new version.
