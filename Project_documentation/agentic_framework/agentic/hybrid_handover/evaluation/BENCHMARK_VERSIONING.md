# BENCHMARK_VERSIONING — SEEB

Versioning policy, case lifecycle rules, compatibility guarantees, and
overfitting protection (Phases B + G). The benchmark is a stable research
artifact; its stability is the product.

## Current version
**SEEB v1.0.0 — FROZEN.** 16 cases, 13 injectors, 4 validators, 10 metrics.
Identifiers live in `version.py`.

## Semantic versioning
`MAJOR.MINOR.PATCH`:

| Bump | When | Effect on comparability |
|---|---|---|
| **MAJOR** | Change to case semantics, metric definitions, the routing/decision protocol, the packet contract, or the frozen `agentic/hybrid_handover/` package it couples to (see LIMITATIONS A9) | **Breaks** comparability; prior baselines are not comparable and must be re-run |
| **MINOR** | Additive, backward-compatible: new cases, new capability categories, new *reported* metrics that do not alter existing ones | Existing case scores unchanged; new dimensions added |
| **PATCH** | Documentation, or an objective ground-truth correction that changes **no** passing/failing outcome | Fully comparable |

A baseline number is only comparable to another under the **same MAJOR.MINOR**.
Reports are stamped with `benchmark_version`; always cite it.

## Rules for adding future evaluation cases
1. New cases are **additive** and get **new** `case_id`s — never renumber or
   repurpose an existing id (baselines reference ids).
2. Every new case MUST pass `integrity.check_case` with zero ERRORs before merge.
3. Every new case MUST declare full ground truth: decisive spans, any defeaters,
   any definitions, any precedence, coverage manifest, expected routing, and
   `expected_abstention` consistent with routing.
4. A new case MUST map to a capability in BENCHMARK_COVERAGE and state its
   difficulty and whether it is keyword-trivial.
5. Adding cases is a **MINOR** bump; it never changes existing case scores.

## Rules for deprecating cases
1. Cases are **never silently removed**. Deprecation marks a case `deprecated`
   with a reason (e.g. "keyword-trivial, superseded by case X") and a version.
2. A deprecated case is still runnable and still reported for one MAJOR cycle
   (for back-comparison), then may be dropped at the next MAJOR bump.
3. Removing or re-semanticising a case is a **MAJOR** bump.

## Compatibility guarantees
- The `ExtractorProtocol`, `EvidencePacket` contract, and `ValidatorProtocol` are
  stable within a MAJOR version. Any extractor built to v1 runs on all v1.x.
- Metric definitions in BENCHMARK_SPEC §8 are stable within a MAJOR version.
- The report JSON schema is stable within a MAJOR version (additive keys only in MINOR).
- Determinism is guaranteed within a version: identical inputs → byte-identical report (minus absolute paths).

## Overfitting protection (Phase G)
The benchmark is public/synthetic and therefore memorisable. To keep it
meaningful as extractors improve:

1. **Hidden/held-out set.** Maintain a private SEEB-Hidden mirror (same
   capabilities, different corpora) that is never committed. Headline claims
   must report both public and hidden scores; a large public-minus-hidden gap
   indicates overfitting.
2. **Rotating adversarial cases.** Each MINOR release retires keyword-trivial
   cases into a "solved" archive and introduces harder replacements for the same
   capability, so leaderboards cannot stagnate on memorised items.
3. **Cross-domain evaluation.** Before claiming generalisation, run the extractor
   on a domain the benchmark's lexicons were NOT tuned for (see LIMITATIONS A1);
   report the drop.
4. **Real-corpus gate.** No "enterprise-ready" claim is permitted from synthetic
   scores alone; a real (non-synthetic) corpus run is required (ROADMAP).
5. **Span-precision auditing.** Because retrieval matching is substring-based
   (A7), periodically audit that high-recall extractors are not returning
   over-broad spans; add span-length penalties in v2 if gaming is observed.
6. **No training on the benchmark.** Extractors MUST NOT be trained or tuned on
   SEEB corpora or ground truth. SEEB is an evaluation set, not a training set.

## Change-control checklist (any proposed benchmark edit)
- [ ] Is this an extractor improvement disguised as a benchmark change? → reject.
- [ ] Does it change any existing case's pass/fail? → MAJOR, and justify.
- [ ] Integrity check still clean? Determinism test still passes?
- [ ] `version.py` bumped; reports re-stamped; baseline re-run and re-recorded.
