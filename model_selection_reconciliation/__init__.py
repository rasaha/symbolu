"""model_selection_reconciliation package.

RESEARCH IMPLEMENTATION — intentionally SEPARATE from the canonical Model Selection
product core (``ugence_model_selection`` / distribution ``ugence-model-selection``).

This is an objective-reconciliation study (Policy A soft-utility vs B hard-quality-floor
vs C lexicographic) layered read-only on ``model_selection_experiment``. It exists to
compare selection *objectives* on the synthetic corpus; the variants B/C are research
policies, not production defaults, and the audited soft-by-default quality floor is left
unchanged by this migration. It is not folded into, nor exported from, the canonical
package. See ``Project_documentation/repository/docs/migrations/model_selection/RESEARCH_SEPARATION.md``.
"""
