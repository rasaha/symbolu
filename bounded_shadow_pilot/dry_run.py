"""Phase 10 - Dry run.

Exercises the full pilot path on a small deterministic slice before the frozen evaluation: build cases,
run the read-only wrapper, route review-triggering dispositions to the tenant-scoped review queue
(reused read-only from customer_shadow_readiness), and evaluate all six stop conditions. Proves the
machinery works end-to-end and that a clean slice does not trip a stop condition.

Non-enforcing, read-only, deterministic.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from bounded_shadow_pilot import orchestrator_wrapper as ow
from bounded_shadow_pilot import stop_conditions as sc
from customer_shadow_readiness import human_review, security, killswitch

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "natural_pilot_v1")
DRY_RUN_N = 25


def _load():
    corpus = json.load(open(os.path.join(_DATA, "corpus.json")))
    gt = json.load(open(os.path.join(_DATA, "ground_truth.json")))
    gts = {g["artifact_id"]: g for g in gt["labels"]}
    return corpus["artifacts"], gts


def run(n: int = DRY_RUN_N) -> Dict[str, Any]:
    artifacts, gts = _load()
    slice_ = sorted(artifacts, key=lambda a: a["artifact_id"])[:n]
    text_by_id = {a["artifact_id"]: a["text"] for a in slice_}

    records = ow.run_batch(slice_, gts)

    # route review-triggering dispositions to the tenant-scoped queue
    killswitch.restore_pilot()
    q = human_review.ReviewQueue()
    enqueued = 0
    for r in records:
        if q.maybe_enqueue("pilot-internal", r):
            enqueued += 1
    # a pilot reviewer (own tenant, review scope) can see the queue; cross-tenant cannot
    reviewer = security.issue_token("tok-acme-reviewer")   # acme != pilot-internal -> cross-tenant
    cross_tenant_blocked = False
    try:
        q.queue_for(reviewer, "pilot-internal")
    except PermissionError:
        cross_tenant_blocked = True

    stops = sc.evaluate_stops(records, text_by_id, ow.replay_signature)

    from collections import Counter
    return {
        "n": len(records),
        "final_distribution": dict(Counter(r.final_shadow_disposition for r in records)),
        "enqueued_for_review": enqueued,
        "review_cross_tenant_blocked": cross_tenant_blocked,
        "actions_derived": sum(r.action_derived for r in records),
        "all_non_enforcing": all(r.enforced is False for r in records),
        "stop_conditions": stops,
        "clean_slice_no_stop": not stops["should_stop"],
    }


if __name__ == "__main__":
    res = run()
    print(f"dry run: n={res['n']} finals={res['final_distribution']}")
    print(f"enqueued_for_review={res['enqueued_for_review']} "
          f"cross_tenant_blocked={res['review_cross_tenant_blocked']} "
          f"actions_derived={res['actions_derived']}")
    print(f"non_enforcing={res['all_non_enforcing']}")
    for c in res["stop_conditions"]["conditions"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['name']}: {c['detail']}")
    print(f"should_stop={res['stop_conditions']['should_stop']}  "
          f"clean_slice_no_stop={res['clean_slice_no_stop']}")
