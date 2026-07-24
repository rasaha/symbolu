# Test Suite (Phase 20)

*EvidenceAssurance tests: `evidence_assurance/tests/`. This phase also **re-runs the prior AGE and
AssertionGate-robustness suites unchanged** and reports their status honestly — no test was modified,
skipped, or masked to accommodate this track.*

## Combined result

```
evidence_assurance/tests/                 25 passed
assertion_governance/tests/               (AGE)   ─┐
assertion_gate_robustness/tests/          (AGR)   ─┼ 32 passed, unchanged
model_selection_reconciliation/tests/      9 passed
────────────────────────────────────────────────────
total                                     66 passed
```

The prior AGE + AGR suites (32 tests) pass **as-is** against their frozen datasets and results;
`verify_prior_artifacts.py` confirms the four guarded artifacts are byte-identical. This track added no
change that touches them.

## What the EvidenceAssurance suite locks down

The 25 tests are written so that a regression which quietly breaks a *result* fails a *test* — the
headline claims are assertions, not just prose.

**Corpus invariants**
- version `ea_corpus_v1_1`, 624 cases, all four partitions present;
- `AUTHORITY_MISMATCH` is reachable and has exactly 24 cases (guards the v1_1 gate fix from
  regressing back to the always-false comparison);
- gold is reproducible from TRUE latent fields via the two annotators + conservative adjudication
  (anti-circularity — gold does not depend on observed metadata);
- annotator disagreement never lands on a safety-critical (hard-precedence) state.

**Layer behavior**
- adversarial provenance is never certified independent;
- clean-dependent → DUPLICATE; all MISALIGNED-gold flagged by alignment;
- counterevidence recall is imperfect (0.85–0.95, not oracle) and false-conflict noise exists.

**Component — the load-bearing claims**
- correlated-failure escape = 0 and overall escape = 0;
- false-block equals the injected NLI-noise floor (15/132) exactly — proving it is noise, not a
  structural refusal;
- gold-REJECT cases are never delivered as supported;
- emptied provenance → abstain, never VERIFIED;
- **the no-tell correlated failure escapes** (the honest ceiling is asserted, not hidden);
- **independence alone leaks ≥0.4 under fabricated provenance while the full stack holds at 0**
  (defense-in-depth), using the same fabrication routine as the ablation report so test and report
  cannot drift.

**Adapter / taxonomy**
- delivery-level escape = 0 end-to-end;
- only VERIFIED / VERIFIED_WITH_LIMITATIONS are "supported"; conservatism order and delivery-effect
  map cover all eleven states.

## One test failure found and fixed during authoring

The defense-in-depth test initially used a hand-written fabrication that omitted
`observed_distinct_retrieval_paths`; provenance then caught the trap via retrieval-path collapse and
independence-alone escaped 0.0 instead of the reported 0.5. Rather than weaken the assertion, the test
was pointed at the ablation study's canonical `_fully_fabricate`, so the test measures the *same*
attack the report documents. Recorded here because "the test disagreed with the report" is exactly the
kind of discrepancy this study surfaces rather than silently reconciles — here the report was right and
the test's attack was incomplete.
