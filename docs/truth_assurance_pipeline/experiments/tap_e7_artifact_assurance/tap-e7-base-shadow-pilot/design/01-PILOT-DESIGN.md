# 1. Pilot Design Document — TAP-E7-BASE Read-Only Shadow Pilot

## Purpose
Measure whether TAP-E7-BASE (frozen at Companion Package **v1.2.0**) provides **useful assurance**
on realistic production artifacts. This is **not** an attempt to improve TAP-E7. Every result is
**observational**; **no production decision may depend on TAP-E7 during the pilot**.

## Non-negotiable constraints
- TAP-E7 stays **verification-only**: it never repairs, regenerates, rewrites, recommends wording,
  or changes outcomes. Its sole output is an `AssuranceRecord`.
- The protocol, package, and both reference implementations are **frozen and unmodified**. The pilot
  consumes Implementation B **read-only** as the reference engine and **verifies the config
  fingerprint** before every run.
- TAP-E7 output **must never influence artifact generation** (shadow mode).

## Read-only pipeline
```
Validation Source ──► Artifact Generator ──► CandidateArtifact ──► TAP-E7 (frozen, read-only)
                                                                        │
                                                                        ▼
                                                                  AssuranceRecord
                                                                        │
                          Human Review ◄──────────────────────────────┘   (TAP output shown AFTER human forms independent view where blinding applies)
                                │
                                ▼
                          Pilot Analysis (observational only)
```
TAP-E7 sits *beside* the real workflow: the generator and any downstream decision run exactly as
they would without TAP-E7; the AssuranceRecord is logged and analyzed, never acted upon.

## Target domains (9)
AI-generated compliance reports, financial summaries, insurance claim summaries, healthcare
documentation, legal summaries, governance reports, enterprise audit evidence, policy explanations,
AI-agent execution summaries. **Public or synthetic data only; no confidential data.** The bundled
demonstration uses a synthetic, author-labeled corpus so precision/recall are measurable; a live
pilot substitutes real artifacts + independent human ground truth.

## What the pilot can and cannot conclude
It can conclude whether TAP-E7-BASE's **structural** assurance (correspondence, status, citation,
provenance, integrity) is precise and where its **bounded recall** leaves gaps (engine-level
semantic categories). It cannot conclude anything outside TAP-E7's verify-only scope, and it cannot
change the protocol.

## Bundled demonstration result (162 synthetic artifacts, see reports/overall-pilot-report.md)
Precision **1.00**, recall **1.00** on BASE-detectable classes / **0.75** overall, indeterminate
rate **0.22**, **0** false positives, **36** engine-gap misses (scope-expansion / omitted-qualifier).
Interpretation: a high-precision structural triage layer, complementary to human semantic review.
