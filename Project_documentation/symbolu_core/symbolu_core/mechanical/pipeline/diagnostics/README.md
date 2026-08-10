# Symbol-U Pipeline Diagnostics

Diagnostic and evaluation tools for analyzing Symbol-U pipeline outputs.

## Modules

### `phonetic_stutter_eval.py`

Empirical testing framework for the "phonetic stuttering" hypothesis.

**Purpose**: Test whether phonetic features (stop consonants, sibilants, etc.) correlate with output brokenness (repetition, fragments, awkward phrasing).

**Components**:
- `PhonemeExtractor`: Extract phoneme-proxy features from text
- `BrokennessCalculator`: Calculate 3 brokenness metrics
- `PhoneticReranker`: Reduce phonetic conflicts via synonym substitution
- `CorpusGenerator`: Generate deterministic test prompts
- `PhoneticStutterEvaluator`: Main evaluation orchestrator

**Quick Start**:
```python
from symbolu.mechanical.pipeline.diagnostics import PhoneticStutterEvaluator

evaluator = PhoneticStutterEvaluator(seed=42)

# Evaluate single output
record = evaluator.evaluate_output(
    prompt="What is AI?",
    output_text="AI is artificial intelligence...",
)

print(f"Brokenness score: {record.brokenness_metrics.brokenness_score:.3f}")
print(f"Phoneme features: {record.phoneme_features.to_dict()}")
```

**Run Full Evaluation**:
```bash
# Standalone
python symbolu/mechanical/pipeline/diagnostics/test_phonetic_stutter.py

# With pytest (if available)
pytest symbolu/mechanical/pipeline/diagnostics/test_phonetic_stutter.py -v -s
```

**Results**: Generated in `phonetic_stutter_results.json`

**Report**: See `docs/phonetic_stutter_evaluation_report.md`

## Usage

```python
from symbolu.mechanical.pipeline.diagnostics import (
    PhoneticStutterEvaluator,
    PhonemeExtractor,
    BrokennessCalculator,
    PhoneticReranker,
    CorpusGenerator,
    run_hypothesis_test,
)

# Generate test prompts
generator = CorpusGenerator(seed=42)
prompts = generator.generate_prompts(count=200)

# Extract phoneme features
extractor = PhonemeExtractor()
features = extractor.extract("The cat sat on the mat.")
print(features.to_dict())

# Calculate brokenness
calculator = BrokennessCalculator()
metrics = calculator.calculate("Consider this. Consider that. Consider everything.")
print(f"Brokenness: {metrics.brokenness_score:.3f}")

# Apply reranking
reranker = PhoneticReranker()
improved = reranker.post_process("Consider this. Consider that.")
print(f"Improved: {improved}")

# Run full corpus evaluation
outputs = [
    ("What is AI?", "AI is artificial intelligence..."),
    ("How does ML work?", "Machine learning works by..."),
    # ... 200+ pairs
]

evaluation = evaluator.run_corpus_evaluation(outputs)
evaluator.print_report(evaluation)
```

## Testing

```bash
# Run hypothesis test with mock data
python test_phonetic_stutter.py

# Expected output:
# - Baseline evaluation report
# - Reranked evaluation report
# - Before/after comparison
# - Hypothesis verdict
# - Results JSON file
```

## Documentation

- Full report: `docs/phonetic_stutter_evaluation_report.md`
- Module docs: `phonetic_stutter_eval.py` (inline docstrings)
- Test docs: `test_phonetic_stutter.py` (inline comments)

## Status

✅ Framework complete and validated
⚠️ Requires real Symbol-U outputs for valid conclusions
📊 Current results based on mock data (for testing only)

## Next Steps

1. Run evaluation on real Symbol-U corpus (200+ outputs)
2. Analyze correlations and effect sizes
3. Determine if hypothesis is supported
4. Deploy reranker if effective (>5% improvement)

## License

Part of Symbol-U AGI - Patent Protected
