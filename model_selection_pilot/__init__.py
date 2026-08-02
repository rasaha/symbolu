"""model_selection_pilot package.

RESEARCH / PILOT IMPLEMENTATION — intentionally SEPARATE from the canonical Model
Selection product core (``ugence_model_selection`` / distribution ``ugence-model-selection``).

This is a self-contained real-provider *shadow pilot* for the Model Selection policy.
It carries its OWN dict-based selection engine (``policy.route`` with F1/F2/G modes and a
reliability gate), its own registry/corpus/telemetry, and — outside any canonical
concern — provider EXECUTION code (``provider.py``, ``execute.py``, credential-blocked,
runs a deterministic stub). Provider invocation, retries, cost accounting, and the
counterfactual runner are deliberately NOT part of the canonical package (Model Selection
chooses within policy; routing dispatches; provider execution invokes — three separate
concerns). Its selection modes and I/O differ from the canonical dataclass core, so it is
classified as a genuinely different *research algorithm*, not a copy, and is not folded
into or exported from the canonical package. See
``docs/migrations/model_selection/RESEARCH_SEPARATION.md``.
"""
