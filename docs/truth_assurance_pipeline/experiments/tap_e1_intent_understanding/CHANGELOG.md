# TAP-E1 — Changelog

## v1 (initial research & falsification phase)

**Added** a new, self-contained TAP-E1 Intent Analysis research track under
`truth_assurance_pipeline/tap_e1_intent/`. Nothing outside that directory (and this
docs folder) was modified.

- `schema.py` — versioned, serializable `IntentRecord` (`tap-e1-intent/1.0.0`) with
  typed fields, six-axis confidence vector, provenance kinds, precedence ladder, and
  a schema validator.
- `extraction.py` — deterministic-first extraction with retained source spans
  (quotes, dates, numbers, filenames, identifiers, URLs, imperatives, output formats,
  quantities, prohibitions, requirements).
- `provenance.py` — append-only provenance ledger + deterministic precedence
  resolution; removable default assumptions.
- `ambiguity.py` — materiality-classified ambiguity detection.
- `conflicts.py` — conflict detection with instruction precedence.
- `clarification.py` — proceed / assume / clarify / abstain policy.
- `interpreter.py` — the layer + the V0–V5 ablation ladder.
- `metrics.py` — Section-16 metrics + Section-17 independent critical failures.
- `evaluator.py` — deterministic harness, preregistered gates, verdict, locks.
- `loader.py` — leakage-controlled public loader (hidden gold withheld).
- `corpus/cases.py` — new synthetic 86-case corpus (dev/eval/negative/adversarial),
  content-hash locked hidden split.
- `tests/test_tap_e1.py` — 30 behavioral tests.
- `experiments/` — `run_experiment.py`, `preregistration.json`, `results_v1.json`,
  `experiment_lock.json`.

**Result:** selected config **V4**; all five preregistered gates pass on the hidden
eval split; verdict **`PASS_WITH_LIMITED_CLAIM`**.

**Notable negative results:** structured schema without deterministic extraction/
provenance (V1) is *worse* than raw (V0); the full clarification-asking policy (V5)
reintroduces one adversarial severe failure and over-asks, so the simpler V4 wins.

**Honesty:** corpus is synthetic/human-authored (no prior frozen corpus exists); the
V0/V1 "model" is a deterministic stand-in, not an LLM; results are mechanism
validation only.
