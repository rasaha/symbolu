# TAP-E7-BASE Independent Implementation A — Conformance Trial

A clean-room TAP-E7-BASE verifier and a blind conformance trial against the corrected v1.1.0
companion package. Goal: **falsify, not prove-by-construction** — determine whether an
independently authored verifier can reproduce the mandatory conformance results from the actual
`(ValidationRecord, CandidateArtifact)` bytes.

## Result (headline)
- Config fingerprint recomputed independently → **MATCH** (`d01e466e…`).
- Blind run of all 90 fixtures; **blind boundary enforced** (0 reads of `expected/`/`derivations/`).
- Mandatory 86: **81 exact + 2 projection-equal = 83 semantic pass**, **0 implementation defects**,
  **3 package defects** surfaced (DT03, UC08, UC09).
- Tests: unit 32/32, metamorphic 8 (+4 engine-level N/A), security 8/8, privacy 3/3.
- Deterministic replay identical; package left byte-immutable (`006ab443…`).
- **Implementation A verdict: 2** (substantially conforms). **Package verdict: 2** (needs listed
  fixture corrections). **Maturity: not ready for Implementation B until blockers resolved.**

## Layout
```
src/verifier.py            clean-room verifier (stdlib only)
tools/recompute_config_fingerprint.py
tools/run_blind_conformance.py   phase 1 (blind)
tools/compare_expected.py        phase 2 (reveal + triage)
tests/run_all_tests.py           unit + metamorphic + security + privacy
results/                   produced records, mandatory/informative/metamorphic/performance JSON, defects/
reports/                   conformance, independence, spec-ambiguities, interoperability, final-assessment, impl-B handoff
```

## Reproduce
```bash
PKG=../tap-e7-base-companion-1.1.0
python3 tools/recompute_config_fingerprint.py $PKG
python3 tools/run_blind_conformance.py $PKG
python3 tools/compare_expected.py $PKG
python3 tests/run_all_tests.py $PKG
```

See `IMPLEMENTATION_SCOPE.md`, `INDEPENDENCE_DECLARATION.md`, `DEPENDENCY_BOUNDARY.md`, and
`reports/final-assessment.md`.
