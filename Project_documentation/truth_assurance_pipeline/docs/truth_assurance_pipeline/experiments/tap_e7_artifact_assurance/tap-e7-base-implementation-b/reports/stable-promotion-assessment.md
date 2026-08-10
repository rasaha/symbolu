# Stable-Promotion Assessment

## Technical criteria (all satisfied)
- Two independently authored implementations (A: Python; B: JavaScript) each pass 86/86 mandatory fixtures.
- Both recompute the published runtime config fingerprint and gate on it.
- The v1.1.1 package is publication-complete; no mandatory specification ambiguity remains.
- Frozen semantics (thresholds, precedence, taxonomy, polarity, band order, scope, verify-only) were not changed during any trial.
- Runtime resources are sufficient to reach every mandatory result from bytes.
- Expected results are reproducible; deterministic replay holds for both implementations.
- Security and privacy behaviors are implemented and tested in both.
- External outputs are interoperable (byte-identical mandatory projections).

## Verdict: **2 — Stable promotion is technically supportable, subject to governance/publication steps**
The technical gate is met. The remaining items are governance, not implementation defects:
1. **Organizational independence** — commission a genuinely third-party implementation (different
   author/team). A and B currently share one author; this is the single substantive gap to a full
   independence claim.
2. **Normative documentation** — publish the config-fingerprint serialization recipe and the
   projection-Π field-set schema (both currently recomputable but under-documented).
3. **Release governance** — independent reviewer sign-off; release tagging; immutable artifact and
   public hash publication; a specification-errata process; conformance-report publication.

Stable promotion is **not** claimed. Two same-author implementations are not a substitute for the
organizational independence the Stable criterion intends.
