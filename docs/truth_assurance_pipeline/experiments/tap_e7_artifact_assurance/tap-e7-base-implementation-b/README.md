# TAP-E7-BASE Independent Implementation B — Clean-Room Conformance Trial

A second, independently authored TAP-E7-BASE verifier — **JavaScript/Node, functional pipeline** —
run blind against the v1.1.1 package to test interoperability with Implementation A (Python).

## Headline
- Fingerprint recomputed independently → **MATCH** (`d01e466e…`); blind boundary enforced (0 expected/derivation reads).
- **Mandatory 86/86 EXACT_PASS**, 0 defects. Informative 4 abstained (non-gate).
- Tests: unit 28/28, metamorphic 11 (+4 N/A), security 8/8, privacy 3/3; anti-cheat 0 fixture-IDs; replay identical; package immutable.
- **A vs B: 86/86 identical, 0 divergences.**
- Verdicts: Impl B **passes** (1); package **independently implementable** (1); interoperability **substantially demonstrated** (2, same-author caveat); Stable **technically supportable after governance** (2).

## Reproduce
```bash
PKG=../tap-e7-base-companion-1.1.1
node tools/recompute_config_fingerprint.js $PKG
node tools/run_blind_conformance.js $PKG
node tools/compare_expected.js $PKG
node tests/run_all_tests.js $PKG
node tools/check_fixture_id_independence.js
```
See CLEAN_ROOM_DECLARATION.md, ARCHITECTURE.md, and reports/final-assessment.md.
