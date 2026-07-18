# CER V0.2 Conformance (Deliverable 6)

The multi-runtime, multi-profile conformance machinery. Grounded in `conformance/runner.py`, `conformance/vectors.json`, and the test suites.

Labels: `FACT`.

## Machinery
`FACT`. `python -m cer_v0_2.conformance.runner [--json out]` runs the factorial corpus (`corpus.py`, 20 cases) through all three runtimes × both profiles and the frozen control plane, checks the preregistered identity relationships (equal/different/invalid) and governance equivalence, and reports metrics **by runtime and by profile**. 47 frozen digest vectors in `conformance/vectors.json`. Deterministic (byte-identical reruns).

## Corpus coverage (§8)
`FACT`. Factorial base (3 runtimes × 2 profiles), plus: different provenance / objective (equal); changed target / replicas / image / strategy (different); same-intent-different-surface (different); stale resourceVersion; policy update; missing evidence; unsupported profile; unsupported extension; malformed payload; profile downgrade; direct-tool bypass; auth-deny/ACP-pass; auth-pass/ACP-hold; observation return. Each case is preregistered `equal` / `different` / `invalid`.

## Test suites
`FACT`:
- `tests/test_second_runtime.py` — real OpenAI Agents SDK integration (deliverable 12).
- `tests/test_cross_profile_security.py` — §9 assertions (deliverable 13).
- `tests/test_governance_and_compat.py` — governance equivalence (14) + V0.1 compatibility (15).

## Reused, unchanged
`FACT`. ActionGate v2 identity profile, ACP cloud core, the V0.1 evidence builder and observation loop — all frozen. The control plane receives only the CER; no runtime switch (verified: `ownership_no_runtime_switch = True`).
