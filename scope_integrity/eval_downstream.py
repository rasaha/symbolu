"""Downstream evaluation (M4). Runs every variant through the FROZEN ClaimIntegrity downstream adapter
(primary endpoint: unsafe delivery) and computes scope-graph secondary endpoints. Reports overall and
HELD-OUT separately (a win must survive held-out). Deterministic. Writes eval_results/downstream.json.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

from claim_integrity import downstream, metrics
from . import dataset, variants

_SUBJECTLESS_START = ("not ", "does not ", "logs ", "improves ", "cures ", "requires ", "is ", "was ")


def _scope_secondary(exs, fn):
    """subject-carry accuracy, exception faithfulness (present where governed, absent where not),
    spurious attachment, omission/invention against the gold alignment."""
    subj_ok = subj_tot = 0
    exc_ok = exc_tot = 0
    spurious = 0
    indeterminate = 0
    for e in exs:
        produced = fn(e)
        if len(produced) == 1 and produced[0] == e["original_text"] and e["expected_claim_count"] > 1:
            indeterminate += 1
        pairs, omitted, invented = metrics._align(e["gold_claims"], produced)
        for g, p in pairs:
            if p is None:
                continue
            # subject carry: produced claim should begin with a capitalized/`the` subject, not a verb
            subj_tot += 1
            low = p.lower().lstrip()
            has_subj = not low.startswith(("not ", "does not ", "logs ", "improves ", "cures ",
                                           "requires ", "is ", "was ", "and ", "but "))
            subj_ok += int(has_subj)
            # exception faithfulness
            gold_exc = [x.lower() for x in (g.get("exceptions") or [])]
            if gold_exc:
                exc_tot += 1
                exc_ok += int(all(x in p.lower() for x in gold_exc))
            else:
                # spurious: an exception marker present where gold has none
                if (" unless " in p.lower() or " except " in p.lower()):
                    spurious += 1
    n = len(exs)
    return {
        "subject_carry_accuracy": round(subj_ok / subj_tot, 4) if subj_tot else 0.0,
        "exception_attachment_accuracy": round(exc_ok / exc_tot, 4) if exc_tot else 0.0,
        "spurious_attachment": spurious,
        "spurious_attachment_rate": round(spurious / n, 4),
        "indeterminate_rate": round(indeterminate / n, 4),
    }


def _row(exs, name, fn):
    d = downstream.score_method(exs, fn)
    s = _scope_secondary(exs, fn)
    return {"variant": name,
            "unsafe_delivery_rate": d["unsafe_delivery_rate"],
            "false_rejection_rate": d["false_rejection_rate"],
            "evidence_query_altered_rate": d["evidence_query_altered_rate"],
            **s}


def _general_crosscheck() -> dict:
    """DECISIVE un-rigged test: run the gated extension on the FROZEN general ClaimIntegrity corpus
    (not constructed for this mechanism) and confirm it reduces the 0.068 residual without new harm."""
    from claim_integrity import dataset as cdata, baselines as cbaselines
    gen = [asdict(e) for e in cdata.all_examples()]
    res = {}
    for name, fn in [("P_current_frozen", cbaselines.BASELINES["P_claim_integrity"]),
                     ("H_integrated_gated", variants.variant_h_integrated)]:
        d = downstream.score_method(gen, fn)
        res[name] = {"unsafe_delivery_rate": d["unsafe_delivery_rate"],
                     "false_rejection_rate": d["false_rejection_rate"],
                     "evidence_query_altered_rate": d["evidence_query_altered_rate"]}
    return res


def run() -> dict:
    exs = [asdict(e) for e in dataset.all_examples()]
    held = [e for e in exs if e["heldout"]]
    prov = [e for e in exs if e["provable"]]
    out = {"corpus": dataset.DATASET_VERSION, "n": len(exs), "n_heldout": len(held),
           "baseline_residual": 0.068, "overall": {}, "heldout": {}, "provable_only": {},
           "general_corpus_crosscheck": _general_crosscheck()}
    for name, fn in variants.VARIANTS.items():
        out["overall"][name] = _row(exs, name, fn)
        out["heldout"][name] = _row(held, name, fn)
        out["provable_only"][name] = _row(prov, name, fn)
    return out


def main() -> None:
    r = run()
    out = os.path.join(os.path.dirname(__file__), "eval_results", "downstream.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)
    print(f"corpus={r['corpus']} n={r['n']} heldout={r['n_heldout']} baseline_residual=0.068\n")
    print("=== DECISIVE general-corpus cross-check (frozen ClaimIntegrity corpus, not built for this) ===")
    for name, s in r["general_corpus_crosscheck"].items():
        print(f"  {name:22} unsafe={s['unsafe_delivery_rate']:.4f} "
              f"false_rej={s['false_rejection_rate']:.4f} evq={s['evidence_query_altered_rate']:.4f}")
    print()
    for scope in ("overall", "heldout"):
        print(f"=== {scope} (primary = unsafe delivery, lower better) ===")
        print(f"  {'variant':22} {'unsafe':>7} {'false_rej':>9} {'evq':>6} {'subj_acc':>8} "
              f"{'exc_acc':>7} {'spurious':>8} {'indet':>6}")
        for name, s in sorted(r[scope].items(), key=lambda x: x[1]["unsafe_delivery_rate"]):
            print(f"  {name:22} {s['unsafe_delivery_rate']:>7.3f} {s['false_rejection_rate']:>9.3f} "
                  f"{s['evidence_query_altered_rate']:>6.3f} {s['subject_carry_accuracy']:>8.3f} "
                  f"{s['exception_attachment_accuracy']:>7.3f} {s['spurious_attachment_rate']:>8.3f} "
                  f"{s['indeterminate_rate']:>6.3f}")
        print()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
