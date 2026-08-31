# Repaired Measurement Layer — Relationship Resolution

Makes every resolution metric answer exactly one question with exactly one owner.
Reads only; changes no resolver and nothing frozen. All corpora synthetic.

## Run
```bash
python -m agentic.hybrid_handover.resolution.measurement.run_measurement   # writes MEASUREMENT_RESULTS.json
python -m pytest tests/test_hybrid_handover_resolution_measurement.py -q
```

## Four stages + decision + parser
Discovery · Classification · Governance (Mode G) · Packet (Mode P) · Abstention
decision metrics · Parser-owned metrics. See docs below.

## Freeze verdict: READY TO FREEZE — the measurement framework
Owner-clean, cheat-resistant (no cheat games any capability metric), stage-
isolated, parser-separated, deterministic. This freezes the metric definitions,
NOT the case corpus (still 16 synthetic cases; cue-narrow — expansion is future
work). Full evidence in MEASUREMENT_REPAIR_REPORT.md.

## Docs
`MEASUREMENT_REPAIR_REPORT.md` · `CAPABILITY_DECOMPOSITION.md` ·
`ABSTENTION_METRICS.md` · `GOVERNANCE_EVALUATION.md` ·
`PACKET_REALIZATION_METRICS.md` · `PARSER_ATTRIBUTION.md` ·
`HIDDEN_EVALUATION_PROTOCOL.md`
