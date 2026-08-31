# TAP-E7-BASE — Read-Only Shadow Pilot

A read-only, observational pilot that measures whether **frozen** TAP-E7-BASE (Companion Package
v1.2.0) provides useful assurance on realistic artifacts. It never modifies the protocol, package,
or either implementation; it consumes Implementation B **read-only** as the reference engine and
verifies the config fingerprint before evaluating. **No production decision depends on TAP-E7.**

## Layout
```
design/   10 deliverables (design, methodology, metrics, taxonomy, governance,
          report templates, dashboard spec, checklist, risk register, readiness)
pilot/    run_pilot.js — generates synthetic multi-domain cases, runs the frozen
          engine read-only, computes in-scope metrics
data/     generated dataset (cases + ground-truth labels)
results/  assurance-records.json, metrics.json, domain-summary.json
reports/  overall-pilot-report.md, domain-summary.md, executive-dashboard.html
```

## Run
```bash
node pilot/run_pilot.js   # reads ../tap-e7-base-companion-1.2.0 + ../tap-e7-base-implementation-b (read-only)
```

## Bundled demonstration (162 synthetic cases)
Precision **1.00**, recall **1.00** on BASE-detectable classes (**0.75** overall), indeterminate
**0.22**, **0** false positives, **36** engine-gap misses (scope-expansion / omitted-qualifier).
TAP-E7-BASE is a high-precision **structural** assurance layer with bounded recall — a complement to,
not a replacement for, human semantic review. See `design/10-FINAL-READINESS-ASSESSMENT.md`.

The synthetic corpus lets precision/recall be measured; a live pilot substitutes real artifacts and
independent human ground truth. reviewer-agreement and review-time are human-pilot metrics (N/A here).
