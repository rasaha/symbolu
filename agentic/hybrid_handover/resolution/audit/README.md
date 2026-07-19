# Relationship Benchmark Audit

Falsification audit of the Relationship Resolution framework — is it trustworthy
before evaluating future resolvers? Audit-only; corrects only objective
measurement flaws in the resolution framework. SEEB and everything else frozen
stay untouched.

## Run
```bash
python -m agentic.hybrid_handover.resolution.audit.run_audit   # writes AUDIT_RESULTS.json
python -m pytest tests/test_hybrid_handover_resolution_audit.py -q
```

## Verdict: **NOT READY TO FREEZE**
Edge-discovery metrics and stage attribution are sound, but several component
metrics are gameable/conflated, resolvers pass by cue-vocabulary matching shared
with the gold (brittle to wording mirrors), and governance is underspecified on
out-of-distribution structures. One objective bug (allows_terminate substring)
was found and fixed. See RELATIONSHIP_BENCHMARK_AUDIT.md for the correction list.

## Docs
`RELATIONSHIP_BENCHMARK_AUDIT.md` · `GROUND_TRUTH_AUDIT.md` · `LEAKAGE_ANALYSIS.md`
· `ADVERSARIAL_RESOLVERS.md` · `MIRROR_CASE_ANALYSIS.md` · `BENCHMARK_ROBUSTNESS.md`
