# B1.9 Pole-Sensitivity (Q2) — Copy-pasteable RunPod command block

**Docs-only.** Tests **`POLE_CORRECT` vs `POLE_FLIPPED`** — same word, same varṇas, only the pole differs. The
correct pole comes from the frozen referent-ontology classification, which **must be operator-approved before any
generation** (the runner refuses otherwise). Expected **96 outputs** (12 × 4 arms × 2 gens) and **288 ratings**.

Driver: `run_b1_9_pole_sensitivity.py` (+ `test_run_b1_9_pole_sensitivity.py`, 12 tests) — mock-tested. Judges +
aggregation reuse `run_b1_6_v2_llm_judge_panel.py` and `judge_b1_6_pilot_outputs.aggregate` unchanged.

**Prior/scope:** low prior (B1.4b′ + content nulls), but this is the FIRST probe that tests pole resolution.
Interpretation is fixed in the prereg §4: a positive needs a coherence-confound recheck + independent
re-classification before it means anything; no `GENUTILITY_*` under any outcome.

---

```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
git pull
export HF_HOME=/workspace/.cache/huggingface

# ── STEP A (MANDATORY, do FIRST): review + APPROVE the referent classification ─
#   Open frozen/b1_9_pole_referent_classification.json, check EVERY row's correct_pole
#   against your rule (physical/objectified -> binding; subjective-mental -> liberating).
#   Pay attention to rows with "debatable": true. Edit any correct_pole you disagree with.
#   Then set the top-level flag to true — this is the pre-commitment; do NOT touch it again after generating.
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("frozen/b1_9_pole_referent_classification.json")
c = json.loads(p.read_text())
# >>> EDIT correct_pole rows ABOVE this line as needed, THEN approve: <<<
c["classification_approved"] = True
c["status"] = "APPROVED"
p.write_text(json.dumps(c, ensure_ascii=False, indent=2))
print("approved:", c["classification_approved"])
PY
# rebuild the scaffold from the approved classification (hashes will update)
python3 build_b1_9_pole_scaffold.py

# ── 1. Evidence-freeze declaration (built from CURRENT frozen-input hashes) ────
python3 - <<'PY'
import json, datetime, pathlib
import run_b1_9_pole_sensitivity as D
outdir = pathlib.Path("run_out/b1_9_pole"); outdir.mkdir(parents=True, exist_ok=True)
decl = {"artifact": "b1_9_pole_sensitivity_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
        "mode": D.MODE, "representation_version": D.REPRESENTATION, "declared_by": "operator",
        "declared_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attestation": D.ATTESTATION,
        **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()}}
p = outdir / "b1_9_pole_EVIDENCE_FREEZE_DECLARED.json"; p.write_text(json.dumps(decl, indent=2))
print("wrote", p, "| approved:", D.classification_approved())
PY

# ── 2. Generation (sequential single-GPU) ─────────────────────────────────────
export DECL=run_out/b1_9_pole/b1_9_pole_EVIDENCE_FREEZE_DECLARED.json
python3 run_b1_9_pole_sensitivity.py part --decl "$DECL" --gen-code M1 \
        --backend transformers --model-id mistralai/Mistral-7B-Instruct-v0.3 --out run_out/b1_9_pole/M1   # 48
python3 run_b1_9_pole_sensitivity.py part --decl "$DECL" --gen-code M2 \
        --backend transformers --model-id Qwen/Qwen2.5-7B-Instruct        --out run_out/b1_9_pole/M2      # 48
python3 run_b1_9_pole_sensitivity.py merge --parts run_out/b1_9_pole/M1 run_out/b1_9_pole/M2 \
        --out run_out/b1_9_pole/generation                                                                # 96

# ── 3. Blind judging (Llama/Gemma ≠ Mistral/Qwen) ─────────────────────────────
cat > run_out/b1_9_pole/judge_panel.json <<'JSON'
{"backend":"transformers",
 "judge_models":[{"id":"meta-llama/Llama-3.1-8B-Instruct","family":"Llama"},
                 {"id":"meta-llama/Meta-Llama-3-8B-Instruct","family":"Llama"},
                 {"id":"google/gemma-2-9b-it","family":"Gemma"}],
 "generator_models":[{"id":"mistralai/Mistral-7B-Instruct-v0.3"},{"id":"Qwen/Qwen2.5-7B-Instruct"}]}
JSON
JV=run_out/b1_9_pole/generation/panel_judge_visible_outputs.jsonl
for i in 0 1 2; do
  python3 run_b1_6_v2_llm_judge_panel.py judge --panel run_out/b1_9_pole/judge_panel.json \
          --judge-index $i --judge-visible "$JV" --out run_out/b1_9_pole/J$i
done
python3 run_b1_6_v2_llm_judge_panel.py merge \
        --parts run_out/b1_9_pole/J0 run_out/b1_9_pole/J1 run_out/b1_9_pole/J2 \
        --out run_out/b1_9_pole/judging                                             # llm_judge_ratings_raw.jsonl

# ── 4. Ratings-freeze declaration ─────────────────────────────────────────────
python3 - <<'PY'
import json, datetime, pathlib
import judge_b1_6_pilot_outputs as AGG
jv = pathlib.Path("run_out/b1_9_pole/generation/panel_judge_visible_outputs.jsonl")
rf = pathlib.Path("run_out/b1_9_pole/judging/llm_judge_ratings_raw.jsonl")
decl = {"artifact": "b1_6_pilot_RATINGS_FROZEN", "ratings_frozen": True, "mode": AGG.MODE,
        "judge_visible_outputs_sha256": AGG._sha_file(jv), "ratings_file_sha256": AGG._sha_file(rf),
        "declared_by": "operator",
        "declared_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attestation": AGG.RATINGS_ATTESTATION}
pathlib.Path("run_out/b1_9_pole/judging/b1_9_pole_RATINGS_FROZEN.json").write_text(json.dumps(decl, indent=2))
print("wrote ratings-freeze")
PY

# ── 5. Aggregate + POLE_CORRECT vs POLE_FLIPPED (unblind ONLY here) ────────────
python3 - <<'PY'
import json, pathlib, statistics as st
import judge_b1_6_pilot_outputs as AGG
J = pathlib.Path("run_out/b1_9_pole")
ratings=[json.loads(l) for l in (J/"judging/llm_judge_ratings_raw.jsonl").read_text().splitlines() if l.strip()]
hidden =json.loads((J/"generation/panel_hidden_arm_generator_metadata.json").read_text())
agg=AGG.aggregate(ratings, hidden,
    freeze_path=J/"judging/b1_9_pole_RATINGS_FROZEN.json",
    judge_visible_file=J/"generation/panel_judge_visible_outputs.jsonl",
    ratings_file=J/"judging/llm_judge_ratings_raw.jsonl",
    require_freeze=True, representation_version="B1.9_pole_sensitivity")
if str(agg.get("label","")).endswith("RATINGS_NOT_FROZEN"): raise SystemExit("refused: "+str(agg.get("reasons")))
print("=== arm-level penalty-adjusted composite ===")
for arm,d in sorted(agg["summary"]["arm_summary"].items(), key=lambda kv:-kv[1]["mean_penalty_adjusted_composite"]):
    print(f"  {arm:28} n={d['n']:3}  adj={d['mean_penalty_adjusted_composite']:.3f}  raw={d['mean_raw_composite']:.3f}")
arm_of={m["blinded_output_id"]:m["true_arm"] for m in hidden}; item_of={m["blinded_output_id"]:m["item_id"] for m in hidden}
adj,spec={}, {}
for r in ratings:
    bid=r["blinded_output_id"]; a=arm_of.get(bid); it=item_of.get(bid)
    if a is None: continue
    _,ad=AGG.composites(r); adj.setdefault((it,a),[]).append(ad); spec.setdefault((it,a),[]).append(float(r["specificity_to_target"]))
def paired(a1,a2,tab):
    w=l=t=0; diffs=[]
    for it in sorted({i for (i,a) in tab}):
        if (it,a1) in tab and (it,a2) in tab:
            m1=st.mean(tab[(it,a1)]); m2=st.mean(tab[(it,a2)]); diffs.append(m1-m2); w+=m1>m2; l+=m1<m2; t+=m1==m2
    return w,l,t,(round(sum(diffs)/len(diffs),3) if diffs else float("nan")),len(diffs)
for lbl,tab in (("penalty_adjusted_composite",adj),("specificity_to_target",spec)):
    w,l,t,md,n=paired("POLE_CORRECT","POLE_FLIPPED",tab)
    print(f"[{lbl:26}] POLE_CORRECT vs POLE_FLIPPED  win/lose/tie={w}/{l}/{t}  n_pairs={n}  mean_diff={md:+}")
PY

# ── 6. run_out untracked ──────────────────────────────────────────────────────
git check-ignore run_out && echo "OK: run_out git-ignored"; echo "tracked under run_out: $(git ls-files run_out | wc -l)"
```

**The one make-or-break line** is `POLE_CORRECT vs POLE_FLIPPED`. If correct ≈ flipped (win-rate ≈ 0.5) → the
binding/liberating resolution carries no recoverable meaning (clean negative for the hypothesis). If correct
reliably wins → candidate signal, then the prereg §4 coherence-confound recheck is required before any claim.

B1.9 pole-sensitivity command block documented only. No generation. No judging. No B1.10. Structure, not
validated meaning.
