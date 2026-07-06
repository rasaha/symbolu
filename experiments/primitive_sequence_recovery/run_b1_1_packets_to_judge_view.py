#!/usr/bin/env python3
"""B1.1 packet -> judge_view converter (pure stdlib reshaping; NO models, NO judging, NO scoring).

Maps the blinded pairwise packets to the schema the committed B1 judge (`run_b1_llm_judge.py`) consumes:
`display_id / key_word / task_text / outputs[{id,text}]`. Strips everything else — NO arm/control/truth/
bridge/conditioning/prompt in the output. A judge result maps back to private truth via
display_id (== packet_id) -> blinded_pairwise_packet_manifest.json truth_map[packet_id].

Does not modify frozen artifacts or the freeze manifest, change the B1 verdict, or unblock Track B.

    python3 experiments/primitive_sequence_recovery/run_b1_1_packets_to_judge_view.py
"""
from __future__ import annotations
import hashlib, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_1_generation as R                          # leak_scan + frozen-config loading (no model)

PKTDIR = HERE / "b1_1_judge_packets"
BLINDED = PKTDIR / "blinded_pairwise_packets.jsonl"
PKT_MANIFEST = PKTDIR / "blinded_pairwise_packet_manifest.json"
VIEW = PKTDIR / "b1_1_judge_view.jsonl"
VIEW_MANIFEST = PKTDIR / "b1_1_judge_view_manifest.json"

JUDGE_VIEW_FIELDS = ("display_id", "key_word", "task_text", "outputs")
# private/truth fields that must NEVER appear in a judge-facing view record
FORBIDDEN_KEYS = ("arm", "control_type", "comparison", "a_output_position", "output_1_arm", "output_2_arm",
                  "raw_key_A", "raw_key_control", "model_id", "seed", "conditioning_text", "prompt_text",
                  "truth_map", "packet_id", "target_word", "task_instruction")
FORBIDDEN_SUBSTR = ("A_vs_", "R_deranged", "R_domain", "R_same", "control_arm")


def main():
    if not BLINDED.exists():
        raise SystemExit(f"ABORT: {BLINDED} not found (run run_b1_1_packet_build.py first).")
    lex = R.load_frozen_configs(R.verify_frozen_or_abort(require_frozen=True))["lexicon"]
    blinded = [json.loads(l) for l in BLINDED.read_text(encoding="utf-8").splitlines() if l.strip()]

    views, leak_total, bad_struct, bad_substr = [], 0, [], []
    for p in blinded:
        v = {"display_id": p["packet_id"], "key_word": p["target_word"],
             "task_text": p["task_instruction"],
             "outputs": [{"id": p["output_1"]["id"], "text": p["output_1"]["text"]},
                         {"id": p["output_2"]["id"], "text": p["output_2"]["text"]}]}
        for k in FORBIDDEN_KEYS:                          # no private key present
            if k in v or any(k in o for o in v["outputs"]):
                bad_struct.append((v["display_id"], k))
        blob = json.dumps(v, ensure_ascii=False)
        for s in FORBIDDEN_SUBSTR:                        # no arm/control token anywhere in the record
            if s in blob:
                bad_substr.append((v["display_id"], s))
        leak_total += R.leak_scan(" \n ".join([v["task_text"], v["outputs"][0]["text"],
                                               v["outputs"][1]["text"]]), lex)[0]
        views.append(v)

    view_text = "".join(json.dumps(v, ensure_ascii=False) + "\n" for v in views)
    VIEW.write_text(view_text, encoding="utf-8")
    view_sha = hashlib.sha256(view_text.encode()).hexdigest()
    src_sha = hashlib.sha256(BLINDED.read_bytes()).hexdigest()
    n_unique = len({v["display_id"] for v in views})

    manifest = {"B1_1_JUDGE_VIEW_MANIFEST": {
        "n_views": len(views), "expected": 4200, "judge_view_file": VIEW.name, "judge_view_sha256": view_sha,
        "source_blinded_packets": BLINDED.name, "source_blinded_sha256": src_sha,
        "source_packet_manifest": PKT_MANIFEST.name,
        "fields": list(JUDGE_VIEW_FIELDS), "outputs_fields": ["id", "text"],
        "mapping_back_to_truth": "display_id == packet_id -> blinded_pairwise_packet_manifest.json "
                                 "truth_map[packet_id] (a_output_position, per-output arm, control_type, "
                                 "raw keys, model, seed).",
        "unique_display_ids": n_unique, "leak_total": leak_total,
        "structural_forbidden_key_hits": bad_struct[:5], "forbidden_substr_hits": bad_substr[:5],
        "no_truth_in_view": (not bad_struct and not bad_substr),
        "b1_verdict_anchor": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_anchor": "BLOCKED",
        "non_claims": ["no judging", "no scoring", "no model calls", "structure not validated meaning"],
    }}
    VIEW_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"views {len(views)} | unique_display {n_unique} | leak {leak_total} | "
          f"struct_bad {len(bad_struct)} | substr_bad {len(bad_substr)}")
    print(f"judge_view_sha256 {view_sha[:16]} | wrote {VIEW.name}, {VIEW_MANIFEST.name}")
    if bad_struct or bad_substr or leak_total:
        print("  WARNING: view is NOT clean — do not judge until resolved.")


if __name__ == "__main__":
    main()
