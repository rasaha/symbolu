"""Append-only preservation of prior frozen StoryGraph evaluation runs (§1).

Historical evidence is never overwritten. Run 1's frozen hashes, metrics, commit,
and corrected verdict are recorded here as immutable constants so a superseding run
cannot silently erase them. See ``STORY_GRAPH_EVIDENCE_LEDGER.md`` for prose.
"""

from __future__ import annotations

# Run 1 — captured from commit 78911a9f BEFORE any Run-2 code change, via
# evaluation.freeze.build_freeze('78911a9f','final') and story_corpus.evaluate_corpus().
RUN_1 = {
    "run_id": "run-1-ato-partial-match-defect",
    "status": "SUPERSEDED",
    "commit": "78911a9f",
    "freeze_version": "ctd.freeze/2.0.0",
    "storygraph_schema": "ctd.storygraph/1.0.0",
    "freeze_digest":
        "sha-256:318e321bc825c8ed954c29a78787a9875f381a978c5b6ddb18ee3879f2dcfaf0",
    "story_graphs": {
        "ACCOUNT_TAKEOVER_TRANSFER@1.0.0":
            "sha-256:4b716710ed71b77ba67aefe9f5a8927348b92a41de8f18cd15481020937b852d",
        "DIGITAL_EXFILTRATION_STORY@1.0.0":
            "sha-256:b4fe287d88fa28b81cd625641b35dd83f9f6a29051d7ab43c4b7319051185a46",
    },
    "corpus_split_hashes": {
        "dev": "sha-256:78adbccc7edde449df5dd9579babaaf3aa97c68b81aab4bc898702c2edaeb95e",
        "calibration":
            "sha-256:ef5bfa4e3c3439c5b537808c59a1411b64be8e6c81fbbba405fabdc6246e66f8",
        "final":
            "sha-256:c37482f3e4a6106e1bc10fd3ca2d2d290df2ab80bd121b25b18ac6c08c4ee436",
        "corpus":
            "sha-256:94ffbfdfe798fcd21c325e232c604ada450df9eb902e467bb7cd30630c24c727",
    },
    "metrics": {
        "n_cases": 9, "n_harmful": 5, "n_benign": 4,
        "true_completion_detection_rate": 1.0,
        "benign_false_completion_rate": 0.0,
        "evasion_false_completion_rate": 0.0,
        "benign_escalate_advisory_rate": 0.75,
    },
    "original_verdict": "CONTINUE — StoryGraph adversarial validation passed",
    "corrected_verdict": "CONTINUE — StoryGraph adversarial validation incomplete",
    "defect": (
        "storygraph._build_match consistency fraction defaulted to 1.0 when zero "
        "edges of a kind were evaluable; absent completion node => discriminating "
        "edges non-evaluable => dimensions defaulted to 1.0 => incomplete benign "
        "workflows escalated on untested relationships."),
}

PRIOR_RUNS = (RUN_1,)
