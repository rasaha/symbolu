"""Two-commit official evidence-chain workflow (§4).

The prior official runtime record was not committed because it carried a placeholder
commit hash. This module implements a stronger, tamper-resistant workflow:

* **Commit A — evaluated implementation.** Code + frozen graph/policy config + corpus
  generator + holdout manifest + seeds + test suite + official runner. The official
  evaluator records Commit A's exact hash.
* **Commit B — evidence-only record.** Only immutable evidence artifacts that
  reference Commit A. No implementation / policy / corpus / threshold change may occur
  between Commit A and the official run, and Commit B may touch only approved evidence
  paths (verified here).

This does NOT rerun the existing holdout — the prior Run-3 result is preserved. The
workflow is for the next official evaluation generation.
"""

from __future__ import annotations

import fnmatch

from ugence_storygraph.canonical import digest

EVIDENCE_CHAIN_VERSION = "ctd.evidence_chain/1.0.0"

# Commit B (evidence-only) may modify ONLY these paths. Anything else means the
# evidence commit smuggled an implementation/config change and must be rejected.
APPROVED_EVIDENCE_PATHS = (
    "packages/capabilities/storygraph/src/ugence_storygraph/evaluation/evidence/*",
    "packages/capabilities/storygraph/src/ugence_storygraph/evaluation/results/*_evidence_record.json",
    "packages/capabilities/storygraph/docs/evaluation/*_EVIDENCE_*.md",
    "packages/capabilities/storygraph/docs/evaluation/STORY_GRAPH_EVIDENCE_LEDGER.md",
)

# Fields an evidence-only record MUST carry (all reference Commit A; no derived
# state that could hide an implementation change).
_REQUIRED_FIELDS = (
    "evidence_chain_version", "evaluated_source_commit", "invoked_at",
    "freeze_digest", "holdout_manifest_hash", "generator_version", "seeds",
    "graph_version", "matcher_version", "policy_version", "witness_tiebreak_version",
    "raw_metric_counts", "derived_metrics", "verdict",
)


class EvidenceChainError(Exception):
    pass


def build_evidence_record(*, evaluated_source_commit: str, invoked_at: str,
                          freeze_digest: str, holdout_manifest_hash: str,
                          generator_version: str, seeds, graph_version: str,
                          matcher_version: str, policy_version: str,
                          witness_tiebreak_version: str, raw_metric_counts: dict,
                          derived_metrics: dict, verdict: str) -> dict:
    """Assemble the immutable Commit-B evidence record and seal it with a digest."""
    record = {
        "evidence_chain_version": EVIDENCE_CHAIN_VERSION,
        "evaluated_source_commit": evaluated_source_commit,
        "invoked_at": invoked_at,
        "freeze_digest": freeze_digest,
        "holdout_manifest_hash": holdout_manifest_hash,
        "generator_version": generator_version,
        "seeds": list(seeds),
        "graph_version": graph_version,
        "matcher_version": matcher_version,
        "policy_version": policy_version,
        "witness_tiebreak_version": witness_tiebreak_version,
        "raw_metric_counts": raw_metric_counts,
        "derived_metrics": derived_metrics,
        "verdict": verdict,
    }
    missing = [f for f in _REQUIRED_FIELDS if f not in record or record[f] in (None, "")]
    if missing:
        raise EvidenceChainError(f"evidence record missing fields: {missing}")
    if evaluated_source_commit.lower() in ("pending", "pending-run3", "placeholder", ""):
        raise EvidenceChainError(
            "evaluated_source_commit must be a real Commit-A hash, not a placeholder")
    record["evaluation_record_digest"] = digest(record, domain="CTD-EVIDENCE-RECORD")
    return record


def verify_evidence_commit_paths(changed_paths) -> dict:
    """Assert a Commit-B diff touches only approved evidence paths (§4)."""
    disallowed = [p for p in changed_paths
                  if not any(fnmatch.fnmatch(p, pat) for pat in APPROVED_EVIDENCE_PATHS)]
    return {"ok": not disallowed, "disallowed_paths": sorted(disallowed),
            "approved_globs": list(APPROVED_EVIDENCE_PATHS)}


def verify_record(record: dict) -> dict:
    """Recompute and check the evidence-record digest (tamper check)."""
    body = {k: v for k, v in record.items() if k != "evaluation_record_digest"}
    recomputed = digest(body, domain="CTD-EVIDENCE-RECORD")
    ok = recomputed == record.get("evaluation_record_digest")
    return {"ok": ok, "recomputed_digest": recomputed}
