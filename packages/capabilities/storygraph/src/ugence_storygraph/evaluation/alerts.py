"""Alert-volume + review-burden analysis with repeat-escalation classification
(§11).

Measured counts (synthetic corpus) are kept separate from modeled operational
projections (tenant-day rates, operator workload). Alert deduplication does not
silently hide new evidence: a repeat escalation is classified by *why* it repeated.
"""

from __future__ import annotations

from ugence_storygraph import (
    BY_ACTOR, BY_CASE, DIGITAL_ONTOLOGY, FixtureProvider, ProviderRegistry,
    SequenceRiskAnalyzer, signals,
)

from . import corpus_gen

# repeat-escalation reasons (§11)
SAME_NO_CHANGE = "same_assembly_no_change"
NEW_FRAGMENT = "new_corroborating_fragment"
SEVERITY_INCREASE = "severity_increase"
NEW_ACTOR = "new_actor"
NEW_RESOURCE = "new_resource"
NEW_DESTINATION = "new_destination"
APPROVAL_LAPSE = "approval_expiry_or_revocation"
VERSION_DIVERGENCE = "recipe_version_divergence"


def classify_repeat(prev: dict, new: dict) -> str:
    """Classify why a standing finding for one assembly changed since last seen."""
    if new.get("recipe_version_binding", {}).get("divergent"):
        return VERSION_DIVERGENCE
    prev_frags = {s["fragment_id"] for s in prev.get("present_fragments", [])}
    new_frags = {s["fragment_id"] for s in new.get("present_fragments", [])}
    if new_frags - prev_frags:
        return NEW_FRAGMENT
    if new.get("severity") != prev.get("severity"):
        return SEVERITY_INCREASE
    prev_actors = {s["actor"] for s in prev.get("present_fragments", [])}
    new_actors = {s["actor"] for s in new.get("present_fragments", [])}
    if new_actors - prev_actors:
        return NEW_ACTOR
    if new.get("benign_context_evidence", {}).get("purpose_consistency_status") in (
            "EXPIRED", "REVOKED", "SUPERSEDED") and prev.get(
            "benign_context_evidence", {}).get("purpose_consistency_status") not in (
            "EXPIRED", "REVOKED", "SUPERSEDED"):
        return APPROVAL_LAPSE
    return SAME_NO_CHANGE


def _providers(sc):
    if sc["providers"]:
        return ProviderRegistry(providers=(
            FixtureProvider("fx", "1.0.0", sc["providers"]),))
    return None


def alert_volume(profile: str = "enterprise_like", scale: int = 200, seed: int = 7,
                 modeled_events_per_tenant_day: int = 50_000) -> dict:
    scenarios = corpus_gen.generate(profile, scale, seed)
    total_events = escalations = unavailable = 0
    unique_cases = set()
    neutralized = false_escalations = 0
    for sc in scenarios:
        specs = (BY_ACTOR,) if sc["family"] == "cross_session" else (BY_CASE,)
        az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=specs, providers=_providers(sc))
        esc_here = False
        for ev in sc["events"]:
            total_events += 1
            for f in az.observe(ev):
                if f.signal == signals.ESCALATE:
                    escalations += 1
                    esc_here = True
                    unique_cases.add((f.tenant_id, f.assembly_key, f.recipe_id))
                    if sc["label"] == "benign" and sc["expected_escalation"] is False:
                        false_escalations += 1
                elif f.signal == signals.UNAVAILABLE:
                    unavailable += 1
        # count neutralizations (benign that correctly did not escalate under valid auth)
        if sc["label"] == "benign" and not esc_here and sc["providers"]:
            neutralized += 1
    per_1000 = round(escalations * 1000 / total_events, 2) if total_events else 0
    return {
        "profile": profile, "scale": scale, "seed": seed,
        "measured": {
            "evidence_label": "Measured — synthetic behavioral corpus",
            "total_events": total_events, "escalations": escalations,
            "unavailable": unavailable, "unique_cases": len(unique_cases),
            "false_escalations": false_escalations,
            "benign_neutralized": neutralized,
            "alerts_per_1000_events": per_1000,
            "alerts_per_10000_events": round(per_1000 * 10, 2),
        },
        "modeled": {
            "evidence_label": "Modeled — operator workload",
            "assumption": f"{modeled_events_per_tenant_day} events/tenant-day (modeled)",
            "alerts_per_tenant_day": round(
                per_1000 * modeled_events_per_tenant_day / 1000, 1),
            "note": "modeled projection, NOT a measured deployment rate",
        },
    }
