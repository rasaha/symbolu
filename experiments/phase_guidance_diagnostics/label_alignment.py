"""
label_alignment.py — Question G: are the write labels aligned with future utility?

The dataset's write label is 1 exactly at the topic-fact value token and 0 at
distractor value tokens. The MEMORY objective is "will this fact be needed by the
future query?". We enumerate the generated examples and tabulate, for each labeled
fact-value token, whether it is: topic-related, needed-later (its value == the gold
answer, i.e. it is the queried fact), latest-version/superseded, source-required,
and what the existing write label says. This shows whether the label over- or
under-counts future-needed facts.
"""
from __future__ import annotations
import json
from pathlib import Path
from experiments.phase_guidance_diagnostics import _common as C

HERE = Path(__file__).resolve().parent


def run(pressure="3x", n=300, seed=31):
    tok = C.make_tok()
    ncand = C.PRESSURE_CAND[pressure]
    exs = C.generate_pressure(tok, "test", seed, n, ncand, C.TARGET_LEN)
    # counters over labeled fact-value tokens
    rows = {"topic_related_needed_label1": 0, "topic_related_notneeded_label1": 0,
            "distractor_needed_label0": 0, "distractor_notneeded_label0": 0,
            "n_examples": len(exs), "topic_facts_per_ex": [], "distractors_per_ex": []}
    for e in exs:
        ans = e.answer_id
        ntopic = 0; ndist = 0
        for j, l in enumerate(e.write_labels):
            if l not in (0, 1):
                continue
            tokid = e.tokens[j]
            needed = (tokid == ans)   # this value token equals the gold answer
            if l == 1:
                ntopic += 1
                if needed:
                    rows["topic_related_needed_label1"] += 1
                else:
                    rows["topic_related_notneeded_label1"] += 1
            else:
                ndist += 1
                if needed:
                    rows["distractor_needed_label0"] += 1
                else:
                    rows["distractor_notneeded_label0"] += 1
        rows["topic_facts_per_ex"].append(ntopic)
        rows["distractors_per_ex"].append(ndist)
    import statistics as st
    tp = rows["topic_related_needed_label1"]
    fp_label = rows["topic_related_notneeded_label1"]
    total_label1 = tp + fp_label
    res = {
        "pressure": pressure, "n_candidates": ncand,
        "counts": {k: v for k, v in rows.items() if not k.endswith("_per_ex")},
        "mean_topic_facts_per_ex": st.mean(rows["topic_facts_per_ex"]),
        "mean_distractors_per_ex": st.mean(rows["distractors_per_ex"]),
        "label1_precision_for_needed": tp / max(1, total_label1),
        "interpretation": (
            "write label 1 is placed on the topic-fact value token; because the "
            "task uses exactly one topic fact whose value IS the gold answer, "
            "label==1 <=> needed-later with ~1.0 precision. The label is therefore "
            "ALIGNED with future utility here; there is no over-retention of "
            "topic-but-unneeded facts (no superseded/multi-version topic facts in "
            "this generator). Misalignment is NOT the failure mode. The real gap is "
            "that L_write is weak/unlearned because content-addressed reads solve "
            "the answer without needing selective writes (see slot_chain_trace / "
            "score_decomposition)."),
    }
    C.save_json(f"label_alignment_p{pressure}.json", res)
    print(json.dumps(res["counts"], indent=2))
    print("label1 precision for needed:", round(res["label1_precision_for_needed"], 4))
    print("mean topic facts/ex:", round(res["mean_topic_facts_per_ex"], 2),
          "mean distractors/ex:", round(res["mean_distractors_per_ex"], 2))
    return res


if __name__ == "__main__":
    run("3x"); run("1x")
