"""
TAP-E1 research corpus (NEW and explicitly labeled for this study).

HONESTY (Section 21): this corpus is SYNTHETIC and human-authored for the TAP-E1
Intent Understanding study. There is no pre-existing "frozen intent corpus" in this
repository; none is claimed as a prerequisite. Gold annotations are author-assigned.
Because both the corpus and the deterministic interpreter are authored here, a
positive result is *mechanism / construction* validation on synthetic inputs — it is
NOT evidence of real-world intent-understanding accuracy or production readiness.

Splits (Section 13):
  dev         — development set (visible gold, used for tuning)
  eval        — hidden evaluation set (content-hash locked; gold withheld by loader)
  negative    — negative controls (well-specified; must NOT be over-flagged)
  adversarial — prompts designed to induce unsupported assumptions
"""

from truth_assurance_pipeline.tap_e1_intent.corpus.cases import (
    Case, Gold, ALL_CASES, cases_for_split, all_case_ids, eval_lock,
    corpus_manifest, SPLITS,
)

__all__ = [
    "Case", "Gold", "ALL_CASES", "cases_for_split", "all_case_ids",
    "eval_lock", "corpus_manifest", "SPLITS",
]
