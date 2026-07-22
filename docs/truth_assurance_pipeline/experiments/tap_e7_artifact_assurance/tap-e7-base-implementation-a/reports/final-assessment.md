# TAP-E7-BASE Implementation A — Final Assessment

## Exact values
- Package commit: `57c7106`
- Implementation path: `docs/…/tap-e7-base-implementation-a/`
- Runtime config fingerprint (recomputed, MATCH): `sha-256:d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734`
- Package root: `sha-256:bff7685055fb99e9bec1ebfe3cec150f56540cd16421d36f40962ade9975f5ff`
- Package composite hash before == after: `006ab443…` (immutable)
- Mandatory fixtures: **86** — EXACT_PASS **81**, SEMANTIC_PASS(Π-equal) **2**, PACKAGE_DEFECT **3**, IMPLEMENTATION_DEFECT **0**
- Informative fixtures: **4** — all abstained (engine-required, non-gate)
- Unit tests: **32/32**; Metamorphic: **8 pass + 4 N/A_ENGINE / 12**; Security: **8/8**; Privacy: **3/3**
- Deterministic replay: **identical** (produced bundle sha-256 stable across runs)
- Performance: 90 fixtures in 0.54s; median 0.067 ms; p95 0.5 ms; max 236 ms (JS17, 100k-field JSON); peak 15.2 MB

## Deviations from the expected corpus (every one listed)
- DT03 → produced NOT_ASSURED(FABRICATION) vs expected ASSURED — **package defect**.
- UC08, UC09 → produced INDETERMINATE(CORRESPONDENCE_UNRESOLVED) vs expected ASSURED — **package defect**.
- SEC05, UC07 → outcome/findings/Π identical; only `x-tap` method sub-count differs (exact vs structured) — **spec ambiguity**, not outcome-affecting.
- INF01–INF04 → abstained vs engine-level expected — **non-mandatory informative**.

## Independent scores
| Dimension | /10 |
| --- | --- |
| Specification implementability | 8 |
| Resource sufficiency | 8 |
| Parser determinism | 10 |
| Correspondence determinism | 10 |
| Fidelity-rule determinism | 8 |
| Security behavior | 9 |
| Privacy behavior | 9 |
| Corpus oracle quality | 7 (3 mandatory fixtures defective) |
| Implementation independence | 9 |
| Mandatory conformance | 8 (83/86 semantic; 3 blocked by package defects) |
| Informative-category readiness | 4 (engine-level, underspecified for resource-only) |
| Interoperability enablement | 7 |
| Normative precision | 8 |

## Verdicts

**Implementation A verdict — 2: substantially conforms, with explicitly listed bounded issues.**
83/86 mandatory fixtures are semantically reproduced from the actual inputs; the 3 that are not
are package defects (Impl A's byte-faithful result is the correct one), and there are 0
implementation defects. Because it does not reach 86/86 exact, it does not claim complete
mandatory conformance under §29.

**Package verdict — 2: the v1.1.0 package requires explicitly listed corrections/clarifications.**
Three mandatory fixtures (DT03, UC08, UC09) encode expected outcomes unreachable from their bytes,
and the exact/structured method labeling is inconsistent (SEC05, UC07). None require altering a
frozen TAP-E7-BASE semantic; all are fixture corrections or documentation clarifications.

**Maturity — Not ready to commission clean-room Implementation B until the listed blockers are
resolved.** Handing B a corpus with 3 known-wrong mandatory expected results would generate
spurious B failures. Fix DT03/UC08/UC09 (and clarify the exact/structured boundary + publish the
fingerprint and Π recipes) in a corpus point-release, then commission B via the handoff spec.

Stable promotion is **not** claimed: it requires two independently developed TAP-E7 implementations
to pass the same corrected mandatory corpus. Implementation A is only the first.
