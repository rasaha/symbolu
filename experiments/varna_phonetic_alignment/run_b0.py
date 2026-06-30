"""Guarded B0 entrypoint (PREREG_VARNA_PHONETIC_ALIGNMENT.md).

Emits NOT_RUN unless a FROZEN, approved artifact config is supplied (the §17
freeze: lexicon hash, frozen IAST→IPA map + PanPhon version, frozen embedding
model id, encodings, C definition, scramble/permutation/bootstrap N, decision
rule). No frozen config exists yet, so this computes NO real T-vs-P alignment and
emits NO B0 verdict. Stage A is untouched.
"""
from __future__ import annotations

REQUIRED_FROZEN_KEYS = (
    "lexicon_sha256",          # frozen lexicon_wordformation.json hash
    "iast_to_ipa_sha256",      # frozen IAST→IPA map (§17)
    "panphon_version",         # pinned feature library
    "embedding_model_id",      # frozen PRIMARY T_embed model
    "categorical_encoding_id", # frozen T_cat sensitivity encoding
    "control_matrix_id",       # frozen C definition
    "scramble_n", "permutation_n", "bootstrap_n",  # frozen Ns
    "decision_rule_sha256",    # frozen §12 decision rule
)


def run(config: dict | None = None) -> dict:
    """Return a status dict. Real alignment runs ONLY with a complete frozen config."""
    if not config:
        return {"status": "NOT_RUN",
                "reason": "no frozen artifact config supplied (PREREG §17 not frozen)",
                "computed_alignment": False, "verdict": None}
    missing = [k for k in REQUIRED_FROZEN_KEYS if k not in config]
    if missing:
        return {"status": "NOT_RUN",
                "reason": f"frozen config incomplete; missing {missing}",
                "computed_alignment": False, "verdict": None}
    # A complete frozen config would gate the real run; the scaffold deliberately
    # does not implement it (no real B0 result is emitted by this scaffold).
    return {"status": "NOT_RUN",
            "reason": "frozen config present but real-run path is gated pending approval",
            "computed_alignment": False, "verdict": None}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
