# Semantic Evidence Normalization + TAP Assertion Governance

**Decisive question:** can models interpret uncertain language without being allowed to silently
invent enterprise facts, authority, approval, policy status, or execution rights?

This phase begins from realistic **unstructured** procurement documents and tests the boundary
between information that can be normalized/computed exactly, information that genuinely needs model
interpretation, and assertions that must be governed after interpretation. Everything downstream of
the authoritative ledger is the **frozen deterministic pipeline** (ledger → joins → P5 slots → exact
typed fields → deterministic mapper), imported unchanged.

```
raw documents → evidence normalization → authoritative ledger → deterministic reasoning
             → Hybrid-LLM explanation → TAP assertion validation → (Decision Governance → ActionGate)
```

## Simulation note (honest scope)

The environment has no guaranteed live frontier-LLM loop, so the **interpreter is a controllable
simulator** with a quality knob `q` (correct-reading probability) and a hallucination rate `h`.
This is the *rigorous* way to test governance: we inject exactly the §12 failure modes and the §14
corruptions and measure whether the **governance layers** (normalization validation + TAP) catch
them, as a function of interpreter quality — more informative than one model's point accuracy. The
governance layers themselves are deterministic and fully tested.

## Normalization arms (N0–N5)

`N0` end-to-end LLM (not allowed as authority) · `N1` unconstrained LLM extraction (no validation) ·
`N2` schema-constrained · `N3` hybrid (deterministic exact + LLM interpretation) + validation ·
`N4` N3 + consistency/authority validation · `N5` oracle normalization (ceiling). N3/N4 are the
production candidates.

## TAP arms (T0–T5)

`T0` draft without TAP · `T1` prompt-only grounding · `T2` TAP decomposition + evidence matching ·
`T3` TAP + deterministic authority/certainty ceilings · `T4` T3 + forced revision loop · `T5` oracle
labels. T3/T4 are the production candidates.

## Governance guarantees (enforced, not learned)

- The **normalization validator** admits only records with a verifiable source span, sufficient
  confidence, and EXACT/high-confidence-INFERRED status; hallucinations (missing span), corrupted
  provenance, and unauthorized records are blocked; uncertain interpretations route to provisional /
  human-review / conflict-set — never into the exact ledger as fact.
- **TAP** decomposes the generated explanation into typed atomic claims and blocks/escalates
  unsupported, contradicted, and authority-exceeding claims; the interpretation layer may propose
  evidence but may never declare the outcome, compliance, authority, or execution rights.

## Files

`corpus_generator.py` · `document_schema.py` · `evidence_schema.py` · `deterministic_extractors.py`
· `semantic_interpreter.py` · `normalization_validator.py` · `provisional_evidence.py` ·
`hybrid_handoff.py` · `claim_decomposer.py` · `tap_validator.py` · `revision_loop.py` ·
`causal_controls.py` · `evaluate_normalization.py` · `evaluate_tap.py` · `run_semantic_tap.py` ·
`tests/` · `results/` · `SEMANTIC_EVIDENCE_TAP_REPORT.md` · `SEMANTIC_EVIDENCE_TAP_RESULTS.json`.
