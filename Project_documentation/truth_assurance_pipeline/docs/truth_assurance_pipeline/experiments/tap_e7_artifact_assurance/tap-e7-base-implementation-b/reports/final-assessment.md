# Implementation B — Final Assessment

## Exact values
- Package commit: `a876ce4`; package path `…/tap-e7-base-companion-1.1.1/`.
- Implementation B commit: (this commit); language **JavaScript / Node.js v22**, **zero external dependencies**.
- Runtime config fingerprint (recomputed independently, gated): `sha-256:d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734` — **MATCH** (39 runtime resources; corpus excluded).
- resource_root `a6ab8788…`, schema_root `d1f1a95c…`, corpus_root `f8c83c91…`, package_root `fa22021a…`.
- Package composite hash before == after execution: `39672e11…` (immutable).
- **Mandatory 86/86 EXACT_PASS** — 0 Implementation-B defects, 0 package defects, 0 mandatory ambiguities.
- Informative INF01–04: abstained (engine-level), non-gate, unaltered.
- Tests: unit **28/28**; metamorphic **11 pass + 4 N/A_ENGINE / 15**; security **8/8**; privacy **3/3**.
- Anti-cheating: **0** fixture-ID strings in runtime source; blind boundary intact (0 expected/derivation reads); result independent of fixture identity.
- Deterministic replay: identical blind bundle across runs.
- Performance: 90 fixtures in 441 ms; median 0.095 ms; p95 7.7 ms; max 242 ms (JS17, 100k-field JSON).

## Iteration history (§44)
- **B0** = the verifier's first evaluation. `src/verifier.js` was **never changed** after authoring — 0 verifier corrections. One fix was applied to the *harness* tool (`run_blind_conformance.js` misused `JSON.stringify`'s replacer argument), which is tooling, not the verifier, and changed no result and no expected value. No initial failure was erased.

## Deviations from the expected corpus
None on the mandatory gate (86/86 exact). Informative INF01–04 abstained by design (engine-level categories).

## Independent scores
| Dimension | /10 |
| --- | --- |
| Clean-room independence (code/language/architecture) | 9 |
| Clean-room independence (organizational) | 4 — same author as A (governance caveat) |
| Specification implementability | 9 |
| Resource sufficiency | 9 |
| Strict-JSON determinism | 10 |
| Markdown determinism (bounded subset) | 8 |
| Language/segmentation determinism | 8 |
| Correspondence determinism | 10 |
| Fidelity determinism | 8 |
| Unicode-security behavior | 10 |
| Citation behavior | 9 |
| Privacy behavior | 9 |
| Corpus oracle quality | 10 |
| Mandatory conformance | 10 |
| Cross-implementation agreement | 10 (86/86 identical to A) |
| Interoperability | 8 (technical yes; organizational caveat) |
| Normative precision | 9 |
| Stable-readiness | 7 |

## Verdicts
- **Implementation B — Verdict 1: passes the complete mandatory TAP-E7-BASE v1.1.1 corpus.**
- **Package — Verdict 1: TAP-E7-BASE v1.1.1 is independently implementable as published** (a second, different-language implementation reproduced all mandatory results from the bytes).
- **Interoperability — Verdict 2: substantially demonstrated with one explicitly listed bounded limitation** — two genuinely different codebases (Python/class-based and JavaScript/functional) recompute the same fingerprint and produce byte-identical mandatory outputs (86/86, 0 divergences); the only residual is that both share a single author, so *organizational* independence is not yet established.
- **Stable-readiness — Verdict 2: technically supportable subject to governance/publication steps.** All technical criteria hold (both implementations pass, no ambiguity, frozen semantics intact, replay deterministic, security/privacy implemented, outputs interoperable). The outstanding steps are governance, not technical: (a) a genuinely third-party (different author/team) implementation to establish organizational independence; (b) publish the config-fingerprint and projection-Π recipes normatively; (c) reviewer sign-off, release tagging, and public hash publication.

Stable promotion is **not** claimed.
