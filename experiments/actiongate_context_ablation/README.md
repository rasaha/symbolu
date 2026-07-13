# ActionGate Context Span-Ablation Labeler

A self-contained **feasibility experiment** that measures whether ActionGate-aware
context compression is worth building — *before* any compressor, SCC, USE, or
learned retention model. It ablates context spans and observes, through the **real
deterministic ActionGate gate**, which spans change the canonical action envelope,
the six-outcome decision, or the assurance requirements (evidence / approval /
simulation / constraints / credential scope / freshness).

It does **not** build a compressor. It answers one question:

> Is the genuinely action-relevant fraction of realistic context small enough —
> and detectable reliably enough, net of prompt caching and overhead — that
> protected-context compression could produce useful token savings *without
> changing any ActionGate decision*?

## Scope guarantees

- Reuses the real gate via a thin adapter (`adapter.py`); **does not modify**
  ActionGate decision semantics, KVPro code, behavioral-biometrics code, SCC/USE
  code, or any product/VC claims.
- The shipped corpus is authored-**synthetic**, so an origin lock forces the
  verdict to `SYNTHETIC_NO_SCIENTIFIC_VERDICT`. A product verdict is impossible
  from synthetic data by construction — a positive result cannot be forced.

## Layout

| Path | What |
|---|---|
| `FEASIBILITY_AUDIT.md` | The report: what the run establishes and cannot. |
| `PREREGISTRATION.md` | Frozen thresholds + mechanical-outcome definitions. |
| `ABLATION_DESIGN.md` | Effect taxonomy, ablation modes, frozen interaction method. |
| `EXTRACTOR_SPEC.md` | The real-gate adapter and the two extraction modes + limits. |
| `actiongate_context_ablation/` | Source: adapter, units, extractor, effects, ablation, detector, metrics, economics, verdict, runner, corpus. |
| `tests/` | 19 tests (gate path, effect detection, metrics, origin lock, determinism). |
| `demos/run_demos.py` | The 10 required demonstrations. |
| `results/RESULTS_RECORD.md` | Regenerable results table. |

## Run

```bash
cd experiments/actiongate_context_ablation
python -m pytest tests/ -q
python -m demos.run_demos
python -c "from actiongate_context_ablation import runner; \
           print(runner.render_results_md(runner.run_study()))"
```

## Pipeline

```
context (units) --F--> canonical envelope --D--> decision record Y
      |  ablate span u_i (single/group/redundancy/linked-pair/interaction)
      v
  effect: NO_EFFECT | ENVELOPE | DECISION | ASSURANCE | STRUCTURE | EXTRACTOR_SENSITIVE | REDUNDANT
      |
      v
  metrics: true-critical fraction, detector recall/precision, oracle & deployable
           ceilings, interaction-miss, extractor-instability
      |
      v
  economics (prompt-cache-adjusted)  -->  mechanical verdict (LOCKED on synthetic)
```

## Result on the shipped synthetic corpus

`SYNTHETIC_NO_SCIENTIFIC_VERDICT` (pipeline verified). Indicative-only signal:
`EXTRACTOR_NOT_RELIABLE`, driven by the Tier-3 paraphrase split — a demonstration
that the metrics discriminate, not a finding about real data. See
`FEASIBILITY_AUDIT.md`.
