# Hidden Relationship Corpus (audit-only)

A hidden evaluation corpus for relationship reasoning, separate from the frozen
visible development corpus. Tests generalisation vs cue-memorisation. Resolvers
receive only opaque-id evidence; gold/difficulty/capability live in a separate
annotations module they never import. Not used for tuning; reports no resolver
performance. All data synthetic.

## Audit (no resolver run)
```bash
python -m agentic.hybrid_handover.resolution.hidden_corpus.run_corpus_audit
python -m pytest tests/test_hidden_corpus.py -q
```

## Status
22-case seed: all 24 capabilities covered, difficulty 1-5, 5 negative controls,
leakage-clean, integrity-clean — but shallow (13 single-example capabilities). Not
yet a certification set. Conservative floor for broad generalisation: ~300-600
hidden cases. See GENERALIZATION_PROTOCOL.md (final assessment).

## Docs
`HIDDEN_CORPUS_SPECIFICATION.md` · `CORPUS_DESIGN_RATIONALE.md` ·
`CAPABILITY_COVERAGE_MATRIX.md` · `DIFFICULTY_CALIBRATION.md` ·
`NEGATIVE_CONTROL_ANALYSIS.md` · `LEAKAGE_VERIFICATION.md` ·
`CORPUS_STATISTICS.md` · `GENERALIZATION_PROTOCOL.md`
