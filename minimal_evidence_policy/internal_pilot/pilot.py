"""Phase 10 - Internal single-tenant natural-artifact utility pilot.

An isolated, non-enforcing, shadow-only pilot on NEW natural artifacts. Compares five policies downstream
through the frozen components, produces audited/replayable minimal-policy decisions, routes ER/escalation
to a review queue, and confirms the native ActionGate vocabulary is preserved. No external actions, no
external customer data, single synthetic internal tenant.

Deterministic, read-only. Writes eval_results/internal_pilot.json.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any, Dict

from minimal_evidence_policy import baselines, classifier, dataset, metrics, schema
from bounded_shadow_pilot import actiongate_contract as ag   # native ActionGate vocabulary (read-only)

_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval_results")
TENANT = "internal-pilot-tenant"

# the five policies the pilot compares
_POLICIES = {
    "frozen_natural_pilot_derivation": baselines.A_prior_uniform,
    "prior_rich_component": baselines.I_rich_component,
    "risk_only": baselines.D_risk_only,
    "minimal_policy": baselines.Full_minimal,
    "oracle": baselines.O_oracle,
}


def run() -> Dict[str, Any]:
    held = dataset.load_partition("HELD_OUT_NATURAL")

    comparison = {name: {"held_out_natural": metrics.score(held, fn)} for name, fn in _POLICIES.items()}

    # minimal-policy audit + replay + review routing (the pilot's operating policy)
    audit_records = []
    review_queue = 0
    enforced_any = False
    replay_a, replay_b = [], []
    for it in held:
        d = classifier.classify(it)
        rec = classifier.audit_record(d)
        rec["tenant"] = TENANT
        rec["enforced"] = False
        audit_records.append(rec)
        replay_a.append(rec["replay_signature"])
        replay_b.append(classifier.replay_signature(classifier.classify(it)))
        # E4 mandates human review; ER routes to review; either enters the queue
        if d.final_obligation in (schema.E4, schema.ER) or d.review_required:
            review_queue += 1

    # native ActionGate vocabulary preserved (6 outcomes, 0 loss)
    ag_conf = ag.conformance()
    ag_loss = ag.semantic_loss_report()

    return {
        "tenant": TENANT,
        "n": len(held),
        "enforced_any": enforced_any,           # False by construction
        "non_enforcing": not enforced_any,
        "policy_comparison": comparison,
        "minimal_policy_review_queue": review_queue,
        "minimal_policy_review_rate": round(review_queue / len(held), 4),
        "audit_completeness": round(sum(1 for r in audit_records if r.get("replay_signature")) / len(held), 4),
        "replay_deterministic": replay_a == replay_b,
        "native_actiongate_outcomes_preserved": ag_conf["all_native_outcomes_preserved"],
        "native_actiongate_semantic_loss_pct": ag_loss["native_semantic_loss_pct"],
        "final_distribution_minimal": dict(Counter(r["final_obligation"][:2] for r in audit_records)),
        "no_external_customer_data": True,
        "no_external_actions": True,
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = run()
    m["internal_pilot_sha256"] = hashlib.sha256(
        json.dumps(m["policy_comparison"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "internal_pilot.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"internal pilot tenant={m['tenant']} n={m['n']} non_enforcing={m['non_enforcing']}")
    print(f"review_rate={m['minimal_policy_review_rate']} audit_completeness={m['audit_completeness']} "
          f"replay_deterministic={m['replay_deterministic']}")
    print(f"native ActionGate preserved={m['native_actiongate_outcomes_preserved']} "
          f"loss={m['native_actiongate_semantic_loss_pct']}%")
    print(f"{'policy':34s} {'clean':>7s} {'unsafe':>7s}")
    for name, r in m["policy_comparison"].items():
        h = r["held_out_natural"]
        print(f"{name:34s} {h['clean_allow_rate']:>7.3f} {h['unsafe_allow']:>7d}")
