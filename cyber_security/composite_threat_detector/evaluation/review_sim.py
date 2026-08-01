"""Expanded operator-review simulation over a generated corpus (§12).

Deterministic reviewer fixtures assign a disposition to each escalation based on
the scenario's ground-truth family/label (NOT on the analyzer's own output beyond
the fact that it escalated). Review feedback is read-only — it never mutates rules
during the run. Operator agreement is a review-quality signal, never proof of
malicious intent.
"""

from __future__ import annotations

from composite_threat_detector import (
    BY_ACTOR, BY_CASE, DIGITAL_ONTOLOGY, FixtureProvider, ProviderRegistry,
    SequenceRiskAnalyzer, signals,
)

from . import corpus_gen, review

# family -> reviewer disposition when the analyzer escalates (deterministic fixture)
_DISPOSITION = {
    "confirmed_harmful": review.AGREE_RISK,
    "cross_session": review.AGREE_RISK,
    "multi_actor": review.AGREE_RISK,
    "long_and_slow": review.AGREE_RISK,
    "reordered": review.AGREE_RISK,
    "renamed_tools": review.AGREE_RISK,
    "noise_inserted": review.AGREE_RISK,
    "duplicate_retried": review.AGREE_RISK,
    "incident_response": review.AGREE_HOLD,        # benign but hold is reasonable
    "expired_approval": review.BENIGN_VERIFIED,    # a false escalation (lapsed auth)
    "scope_mismatched_approval": review.BENIGN_VERIFIED,
    "destination_mismatch": review.BENIGN_VERIFIED,
    "actor_identity_mismatch": review.BENIGN_VERIFIED,
    "legit_backup": review.BENIGN_RECIPE_BROAD,
    "legit_migration": review.BENIGN_RECIPE_BROAD,
    "disaster_recovery": review.BENIGN_RECIPE_BROAD,
    "admin_maintenance": review.BENIGN_RECIPE_BROAD,
    "missing_events": review.BENIGN_RECIPE_BROAD,
    "approved_pentest": review.BENIGN_VERIFIED,
    "competing_explanations": review.BENIGN_VERIFIED,
    "ambiguous_linkage": review.AMBIGUOUS_MORE_EVIDENCE,
    "unknown_threat": review.MISSED_CONTEXT,
    "state_exhaustion": review.UNACTIONABLE,
}


def _providers(sc):
    if sc["providers"]:
        return ProviderRegistry(providers=(FixtureProvider("fx", "1.0.0", sc["providers"]),))
    return None


def simulate(profile: str = "enterprise_like", scale: int = 200, seed: int = 7) -> dict:
    scenarios = corpus_gen.generate(profile, scale, seed)
    led = review.ReviewLedger()
    for sc in scenarios:
        specs = (BY_ACTOR,) if sc["family"] == "cross_session" else (BY_CASE,)
        az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=specs, providers=_providers(sc))
        seen = set()
        for ev in sc["events"]:
            for f in az.observe(ev):
                if f.signal != signals.ESCALATE:
                    continue
                if f.finding_id in seen:
                    disp = review.DUPLICATE_ALERT
                else:
                    seen.add(f.finding_id)
                    disp = _DISPOSITION.get(sc["family"], review.AMBIGUOUS_MORE_EVIDENCE)
                led.record(review.ReviewRecord(
                    finding_id=f.finding_id, recipe_id=f.recipe_id, disposition=disp,
                    reviewer="fixture", evidence_complete=bool(f.explanation)))
    metrics = led.metrics()
    metrics["evidence_label"] = "Measured — synthetic behavioral corpus (fixture reviewers)"
    metrics["caveat"] = ("Fixture reviewers, not human validation. Agreement is a "
                         "review-quality signal, not proof of intent.")
    return metrics
