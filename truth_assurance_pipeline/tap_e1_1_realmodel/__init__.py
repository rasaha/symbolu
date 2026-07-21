"""
TAP-E1.1 — Real Model Validation.

A validation track (NOT a new TAP layer) for the frozen TAP-E1 Intent Analysis
Layer. It imports TAP-E1 UNCHANGED and replaces only the interpretation engine with a
real LLM, then measures — under preregistered gates, leakage controls, and a metric
audit — whether real-model reasoning improves intent understanding without increasing
unsupported assumptions or reducing constraint preservation.

HONESTY: no Anthropic API key is available here, so the real-model outputs were produced
by the in-session agent model (claude-opus-4-8) and cached. The same model authored and
interpreted the corpus (author==interpreter confound). Results are mechanism validation
on a small synthetic corpus only — not production evidence. See the experiment report.
"""

__version__ = "1.1.0"
