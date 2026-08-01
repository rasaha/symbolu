"""Complete evaluation-freeze artifact + final-evaluation guard (§2, H1).

The corpus hash alone is not sufficient. This binds the *entire* evaluation
configuration so an official final run refuses to proceed if any frozen input has
changed, and so default/development thresholds can never produce an official
verdict.
"""

from __future__ import annotations

from composite_threat_detector import ordering, replay
from composite_threat_detector.canonical import digest
from composite_threat_detector.durable_audit import SCHEMA_VERSION as AUDIT_SCHEMA
from composite_threat_detector.ledger import StateLimits, TimescalePolicy
from composite_threat_detector.linkage import (
    BY_ACTOR, BY_CASE, LINKAGE_SCHEMA_VERSION,
)
from composite_threat_detector.recipes import DIGITAL_ONTOLOGY

from . import corpus as C
from . import corpus_gen, review

FREEZE_VERSION = "ctd.freeze/2.0.0"
POLICY_VERSION = "ctd.policy/1.0.0"

# pre-registered acceptance thresholds (frozen before the final run, §14).
# These are experimental development thresholds, NOT universal enterprise
# standards. They gate H7 (operational cost) and H8 (benign review burden).
PREREGISTERED_THRESHOLDS = {
    "preregistered": True,
    "max_p95_runtime_ms_per_event": 5.0,
    "max_false_escalation_rate": 0.02,
    "max_alerts_per_1000_events_enterprise_like": 60.0,
    "min_true_positive_rate_encoded": 0.90,
}


def _split_hashes() -> dict:
    man = C.manifest()
    out = {}
    for sp in ("dev", "calibration", "final"):
        hashes = sorted(e["content_hash"] for e in man["scenarios"]
                        if e["split"] == sp)
        out[sp] = digest(hashes, domain="CTD-SPLIT")
    out["corpus"] = man["corpus_hash"]
    return out


def current_config() -> dict:
    """Snapshot of every frozen input, computed from the live modules."""
    ts, limits = TimescalePolicy(), StateLimits()
    return {
        "freeze_version": FREEZE_VERSION,
        "recipes": sorted(f"{r.recipe_id}@{r.version}" for r in DIGITAL_ONTOLOGY.recipes),
        "recipe_thresholds": {r.ref: [r.observe_threshold, r.escalation_threshold,
                                      r.completion_threshold]
                              for r in DIGITAL_ONTOLOGY.recipes},
        "linkage_schema": LINKAGE_SCHEMA_VERSION,
        "assembly_key_config": [BY_CASE.ref, BY_ACTOR.ref],
        "decay_params": [ts.unit, ts.decay_half_life, ts.decay_floor],
        "retention": [ts.short_window, ts.case_window],
        "benign_rules": sorted(set().union(
            *(r.benign_exclusions for r in DIGITAL_ONTOLOGY.recipes))),
        "provider_fixture_version": "ctd.providers/1.0.0",
        "ordering_rules": [ordering.ORDERED, ordering.PARTIALLY_ORDERED,
                           ordering.AMBIGUOUS_ORDER, ordering.CONFLICTING_ORDER],
        "policy_version": POLICY_VERSION,
        "state_limits": [limits.max_tenants, limits.max_assemblies_per_tenant,
                         limits.max_instances_per_assembly,
                         limits.max_assemblies_per_actor,
                         limits.max_candidate_linkages_per_event],
        "normalization_schema": replay.HISTORICAL_REPLAY_CONTRACT["version"],
        "audit_schema": AUDIT_SCHEMA,
        "review_schema": sorted(review.DISPOSITIONS),
        "corpus_split_hashes": _split_hashes(),
        "generator_profiles": sorted(corpus_gen.PROFILES),
    }


def build_freeze(code_commit: str, *, profile: str = "final", seed: int = 1234) -> dict:
    cfg = current_config()
    body = {**cfg, "code_commit": code_commit, "profile": profile, "seed": seed,
            "acceptance_thresholds": PREREGISTERED_THRESHOLDS}
    body["freeze_digest"] = digest(body, domain="CTD-FREEZE2")
    body["_note"] = ("Frozen before the final evaluation run. The 'final' split "
                     "and pre-registered thresholds must not be tuned after "
                     "freezing (§2, §10, §14).")
    return body


def diff_freeze(frozen: dict) -> list[str]:
    """Return the list of frozen inputs that differ from the current config."""
    cfg = current_config()
    diffs = []
    for k, v in cfg.items():
        if frozen.get(k) != v:
            diffs.append(k)
    return sorted(diffs)


class FreezeViolation(Exception):
    pass


def require_frozen(frozen: dict, *, official: bool = True) -> None:
    """Guard the official final-evaluation run (H1).

    Raises FreezeViolation if any frozen input changed, if the digest is invalid,
    or (for an official run) if the freeze is a dev profile or lacks pre-registered
    thresholds. Development thresholds can never produce an official verdict.
    """
    recomputed = {k: v for k, v in frozen.items()
                  if k not in ("freeze_digest", "_note")}
    if digest(recomputed, domain="CTD-FREEZE2") != frozen.get("freeze_digest"):
        raise FreezeViolation("freeze digest invalid (artifact tampered or malformed)")
    diffs = diff_freeze(frozen)
    if diffs:
        raise FreezeViolation(f"frozen inputs changed since freeze: {diffs}")
    if official:
        if frozen.get("profile") != "final":
            raise FreezeViolation(
                f"official final evaluation requires profile 'final', got "
                f"{frozen.get('profile')!r}")
        thr = frozen.get("acceptance_thresholds", {})
        if not thr.get("preregistered"):
            raise FreezeViolation(
                "official verdict requires pre-registered acceptance thresholds; "
                "default/development thresholds are not permitted")
