# Combined Gate Evaluation Report

## Environment

| Field | Value |
|-------|-------|
| Date | _YYYY-MM-DD_ |
| Checkpoint | _path/to/checkpoint_ |
| Training step | _step number from checkpoint meta_ |
| Best val loss | _from checkpoint meta_ |
| GPU | _e.g. A100 80GB_ |
| Quantize | _4bit / 8bit / none_ |
| Temperature | _0.7_ |
| Max tokens | _256_ |
| Torch version | _x.y.z_ |
| Branch | `claude/audit-cg-signal-aggregation-HltyO` |

## Executive Summary

_1-3 sentences: Do the gates work? Are they useful? What is the recommendation?_

## Firing Rate Summary

_Paste the table from EVAL_SUMMARY.md, or fill manually:_

| Mode | Vritti Fires | Guna Fires | Vritti Rate | Guna Rate |
|------|-------------|-----------|-------------|-----------|
| A_baseline | 0 | 0 | 0% | 0% |
| B_vritti_only | _?_ | 0 | _?_ | 0% |
| C_guna_only | 0 | _?_ | 0% | _?_ |
| D_both_gates | _?_ | _?_ | _?_ | _?_ |

## Gate Interaction (Mode D)

- Prompts where Vritti fired: _?_ / 15
- Prompts where Guna fired: _?_ / 15
- Prompts where BOTH fired: _?_ / 15
- Overlap rate: _?_%
- Dominant gate: _Vritti / Guna / Neither / Both equally_

## Per-Category Observations

### Factual (fact-01, fact-02, fact-03)
- Gate firing: _none expected_
- Output quality change: _unchanged / improved / degraded_

### Error-prone (err-01, err-02, err-03)
- Gate firing: _expected to fire_
- Output quality change: _did cooling help reduce hallucination?_

### Speculative (spec-01, spec-02)
- Gate firing: _none expected_
- Output quality change: _was creativity preserved?_

### Memory (mem-01, mem-02)
- Gate firing: _none expected_
- Output quality change: _unchanged / improved / degraded_

### Ambiguous (amb-01, amb-02)
- Gate firing: _may or may not fire_
- Output quality change: _?_

### High-agency (agency-01, agency-02)
- Gate firing: _Guna may fire (turbulence from high agency/rajas)_
- Output quality change: _?_

### Long (long-01)
- Gate firing: _may show per-step evolution_
- Output quality change: _any evidence of mid-generation cooling?_

## Over-Cooling Assessment

- [ ] No over-cooling detected
- [ ] Mild over-cooling on _N_ prompts (output shorter but still coherent)
- [ ] Significant over-cooling (output quality degraded on non-error prompts)
- [ ] Double-cooling in mode D (both gates cool same step, excessive suppression)

## 32D State Quality

_Are the Vritti and Guna values from the trained checkpoint meaningful?_

- Vritti distribution: _near-uniform (untrained) / differentiated (trained)_
- Guna distribution: _near-0.5 sigmoid midpoint (untrained) / structured (trained)_
- Bhava distribution: _collapsed to one mode / spread / structured_

_If the state projector is undertrained, the gates cannot be meaningfully
evaluated. Note this explicitly._

## Trace Metadata Assessment

- `vritti_gate_events` fields: _complete / missing fields_
- `guna_gate_events` fields: _complete / missing fields_
- Is the metadata sufficient to debug why cooling occurred? _yes / no_
- Any unexpected values? _describe_

## Safety

- [ ] No generation failures
- [ ] No degenerate outputs (empty, repeated tokens, gibberish)
- [ ] Greedy mode (temperature=0) remains safe
- [ ] No excessive firing rates (> 50% of steps)
- [ ] No evidence of mode collapse from cooling

## Recommendation

Choose one:

- [ ] **Keep both experimental and continue** — gates fire selectively, improve
  error-prone cases, do not harm normal output. Both axes provide distinct signal.
- [ ] **Keep Vritti only** — Vritti gate is useful, Guna adds noise or is redundant.
  Remove Guna gate code.
- [ ] **Keep Guna only** — Guna is more selective than Vritti. Vritti fires too
  broadly or on wrong categories.
- [ ] **Keep both but revise thresholds** — gate logic is sound but thresholds
  need tuning. Proposed changes: _describe_.
- [ ] **Disable one or both** — gates do not provide value at current checkpoint
  quality. Revisit after further training.
- [ ] **Not enough checkpoint quality to judge** — 32D state is near-random,
  gates cannot be meaningfully evaluated. Need more training.

## Rationale

_2-5 sentences explaining the recommendation, referencing specific prompt
results and firing patterns._

## Next Steps

_What should happen after this evaluation?_

1. _..._
2. _..._
3. _..._
