"""High-volume deterministic corpus generator with configurable prevalence
(§3, §4).

Deterministic given ``(profile, scale, seed)`` — it uses a *seeded* PRNG
(``random.Random(seed)``), which is reproducible and replay-stable. It reuses the
25-family building blocks in ``corpus.py`` but perturbs entity identifiers across
pools to create realistic cardinality (many actors/resources/workflows), and
mixes families according to a profile's prevalence.

Prevalence is a **modeled evaluation assumption** — NOT a claim about any specific
industry. Profiles:

* ``balanced``            — all families roughly equally (debugging)
* ``enterprise_like``     — predominantly benign, rare risky (base-rate realism)
* ``stress``              — high volume, ambiguity, duplicates, provider failure
* ``adversarial_evasion`` — long-and-slow, cross-session, renamed tools, noise
"""

from __future__ import annotations

import random

from composite_threat_detector.canonical import digest

from . import corpus as C

# family categories used to compose profiles
HARMFUL = ["confirmed_harmful", "cross_session", "multi_actor", "long_and_slow",
           "reordered", "renamed_tools", "noise_inserted", "duplicate_retried"]
BENIGN_CLEAN = ["legit_backup", "legit_migration", "disaster_recovery",
                "admin_maintenance", "missing_events"]
BENIGN_LOOKALIKE = ["expired_approval", "scope_mismatched_approval",
                    "destination_mismatch", "actor_identity_mismatch",
                    "incident_response"]
APPROVED = ["approved_pentest", "competing_explanations"]
AMBIGUOUS = ["ambiguous_linkage"]
UNKNOWN = ["unknown_threat"]
INFRA = ["state_exhaustion"]

# profile -> {category: weight}. Weights are modeled prevalence assumptions.
PROFILES = {
    "balanced": {"HARMFUL": 8, "BENIGN_CLEAN": 5, "BENIGN_LOOKALIKE": 5,
                 "APPROVED": 2, "AMBIGUOUS": 1, "UNKNOWN": 1, "INFRA": 1},
    "enterprise_like": {"HARMFUL": 1, "BENIGN_CLEAN": 80, "BENIGN_LOOKALIKE": 8,
                        "APPROVED": 8, "AMBIGUOUS": 2, "UNKNOWN": 1, "INFRA": 0},
    "stress": {"HARMFUL": 10, "BENIGN_CLEAN": 30, "BENIGN_LOOKALIKE": 20,
               "APPROVED": 10, "AMBIGUOUS": 10, "UNKNOWN": 5, "INFRA": 15},
    "adversarial_evasion": {"HARMFUL": 60, "BENIGN_CLEAN": 10, "BENIGN_LOOKALIKE": 20,
                            "APPROVED": 5, "AMBIGUOUS": 3, "UNKNOWN": 2, "INFRA": 0},
}
_CATEGORY = {"HARMFUL": HARMFUL, "BENIGN_CLEAN": BENIGN_CLEAN,
             "BENIGN_LOOKALIKE": BENIGN_LOOKALIKE, "APPROVED": APPROVED,
             "AMBIGUOUS": AMBIGUOUS, "UNKNOWN": UNKNOWN, "INFRA": INFRA}


def _pick(rng: random.Random, weights: dict) -> str:
    cats, w = zip(*weights.items())
    return rng.choices(cats, weights=w, k=1)[0]


def _perturb(events, providers, rng: random.Random, idx: int):
    """Assign identity from pools to spread cardinality; keep linkage consistent."""
    tenant = f"tenant-{rng.randrange(8)}"
    actor = f"agent://svc-{rng.randrange(50)}"
    workflow = f"wf-{rng.randrange(200)}-{idx}"
    new_events = []
    for e in events:
        e = dict(e)
        if e.get("tenant_id"):
            e["tenant_id"] = tenant
        # keep multi-actor / mixed families' distinct actors, else unify
        if e.get("actor") and e["actor"].startswith("agent://a"):
            e["actor"] = actor
            e["credential_scope"] = {"principal": actor}
        if e.get("workflow_id"):
            e["workflow_id"] = workflow
        new_events.append(e)
    new_providers = []
    for r in providers:
        r = dict(r)
        if r.get("tenant") and r["tenant"] != "*":
            r["tenant"] = tenant
        if r.get("workflow") and r["workflow"] != "*":
            r["workflow"] = workflow
        new_providers.append(r)
    return new_events, new_providers


def generate(profile: str = "enterprise_like", scale: int = 100, seed: int = 1234):
    """Return a deterministic list of generated scenario dicts."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; choose {sorted(PROFILES)}")
    rng = random.Random(seed)
    weights = PROFILES[profile]
    out = []
    for i in range(scale):
        cat = _pick(rng, weights)
        fam = rng.choice(_CATEGORY[cat])
        events, providers, label, expected, difficulty = C._family(fam)
        events, providers = _perturb(events, providers, rng, i)
        body = {"events": events, "providers": providers}
        out.append({
            "scenario_id": f"{profile}-{i:05d}-{fam}",
            "family": fam, "category": cat, "label": label,
            "expected_escalation": expected, "difficulty": difficulty,
            "profile": profile, "seed": seed,
            "events": events, "providers": providers,
            "content_hash": digest(body, domain="CTD-CORPUS-GEN"),
        })
    return out


def profile_summary(profile: str, scale: int, seed: int) -> dict:
    scen = generate(profile, scale, seed)
    by_label: dict = {}
    by_cat: dict = {}
    for s in scen:
        by_label[s["label"]] = by_label.get(s["label"], 0) + 1
        by_cat[s["category"]] = by_cat.get(s["category"], 0) + 1
    return {
        "profile": profile, "scale": scale, "seed": seed,
        "prevalence_label": "Modeled — prevalence assumption",
        "by_label": dict(sorted(by_label.items())),
        "by_category": dict(sorted(by_cat.items())),
        "corpus_hash": digest([s["content_hash"] for s in scen], domain="CTD-GEN-SET"),
    }
