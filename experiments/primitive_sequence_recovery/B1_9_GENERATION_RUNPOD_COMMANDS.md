# B1.9 Generation (corrected control) — Copy-pasteable RunPod command block

**Docs-only.** No generation/judging performed here. Runs on an operator GPU host (RunPod), transformers
backend, sequential single-GPU. Primary contrast **`AUTHENTIC_MAPPING` vs `DISTANT_SOURCE_MAPPING`** (the
corrected distant-source-word control). Expected **144 outputs** (12 items × 6 arms × 2 generators) and **432
ratings** (144 × 3 judges). Every stage is gated/blinded; `run_out/` is gitignored.

**Honest gating caveat (from the prereg §0):** the upstream B1.9 embedding gate returned **null** on the
corrected control. This generation probe is a **confirmatory re-test**, and its interpretation rules are
asymmetric — a null is expected/consistent; a positive is *not credible* until blinding/register/leakage are
re-audited and a powered run confirms it. No terminal `GENUTILITY_*` label may be emitted.

Driver: `run_b1_9_generation.py` (+ `test_run_b1_9_generation.py`, 17 tests) — mock-tested. Judges + aggregation
reuse `run_b1_6_v2_llm_judge_panel.py` and `judge_b1_6_pilot_outputs.aggregate` **unchanged** (arm-agnostic).

---

```bash
# ── 0. Position + preflight ───────────────────────────────────────────────────
cd /workspace/symbolu/experiments/primitive_sequence_recovery
git rev-parse --short HEAD           # expect the commit that added run_b1_9_generation.py or later
ls | grep -iE 'b1[_.]10' && echo "UNEXPECTED B1.10 file" || echo "OK: no B1.10 files"
python3 -c "import torch, transformers; print('torch', torch.__version__, 'transformers', transformers.__version__)"
export HF_HOME=/workspace/.cache/huggingface

# ── 1. Evidence-freeze declaration (built from CURRENT frozen-input hashes) ────
python3 - <<'PY'
import json, datetime, pathlib
import run_b1_9_generation as D
outdir = pathlib.Path("run_out/b1_9_gen"); outdir.mkdir(parents=True, exist_ok=True)
decl = {"artifact": "b1_9_generation_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
        "mode": D.MODE, "representation_version": D.REPRESENTATION,
        "declared_by": "operator",
        "declared_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attestation": D.ATTESTATION,
        **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()}}
p = outdir / "b1_9_gen_EVIDENCE_FREEZE_DECLARED.json"
p.write_text(json.dumps(decl, ensure_ascii=False, indent=2))
print("wrote", p, "| primary contrast:", D.PRIMARY_CONTRAST)
PY

# ── 2. Generation (sequential single-GPU; one model live at a time) ───────────
export DECL=run_out/b1_9_gen/b1_9_gen_EVIDENCE_FREEZE_DECLARED.json
python3 run_b1_9_generation.py part --decl "$DECL" --gen-code M1 \
        --backend transformers --model-id mistralai/Mistral-7B-Instruct-v0.3 --out run_out/b1_9_gen/M1   # 72
python3 run_b1_9_generation.py part --decl "$DECL" --gen-code M2 \
        --backend transformers --model-id Qwen/Qwen2.5-7B-Instruct        --out run_out/b1_9_gen/M2      # 72
python3 run_b1_9_generation.py merge --parts run_out/b1_9_gen/M1 run_out/b1_9_gen/M2 \
        --out run_out/b1_9_gen/generation                                                                # 144

# ── 3. Blind judging (Llama/Gemma judges ≠ Mistral/Qwen generators) ───────────
cat > run_out/b1_9_gen/judge_panel.json <<'JSON'
{"backend":"transformers",
 "judge_models":[{"id":"meta-llama/Llama-3.1-8B-Instruct","family":"Llama"},
                 {"id":"meta-llama/Meta-Llama-3-8B-Instruct","family":"Llama"},
                 {"id":"google/gemma-2-9b-it","family":"Gemma"}],
 "generator_models":[{"id":"mistralai/Mistral-7B-Instruct-v0.3"},{"id":"Qwen/Qwen2.5-7B-Instruct"}]}
JSON
JV=run_out/b1_9_gen/generation/panel_judge_visible_outputs.jsonl
for i in 0 1 2; do
  python3 run_b1_6_v2_llm_judge_panel.py judge --panel run_out/b1_9_gen/judge_panel.json \
          --judge-index $i --judge-visible "$JV" --out run_out/b1_9_gen/J$i          # 144 ratings each
done
python3 run_b1_6_v2_llm_judge_panel.py merge \
        --parts run_out/b1_9_gen/J0 run_out/b1_9_gen/J1 run_out/b1_9_gen/J2 \
        --out run_out/b1_9_gen/judging                                               # llm_judge_ratings_raw.jsonl (432)

# ── 4. Ratings-freeze declaration (reused B1.6 freeze; required before unblinding)
python3 - <<'PY'
import json, datetime, pathlib
import judge_b1_6_pilot_outputs as AGG
jv = pathlib.Path("run_out/b1_9_gen/generation/panel_judge_visible_outputs.jsonl")
rf = pathlib.Path("run_out/b1_9_gen/judging/llm_judge_ratings_raw.jsonl")
decl = {"artifact": "b1_6_pilot_RATINGS_FROZEN", "ratings_frozen": True, "mode": AGG.MODE,
        "judge_visible_outputs_sha256": AGG._sha_file(jv), "ratings_file_sha256": AGG._sha_file(rf),
        "declared_by": "operator",
        "declared_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attestation": AGG.RATINGS_ATTESTATION}
p = pathlib.Path("run_out/b1_9_gen/judging/b1_9_gen_RATINGS_FROZEN.json")
p.write_text(json.dumps(decl, ensure_ascii=False, indent=2)); print("wrote", p)
PY

# ── 5. Aggregate + primary contrast (arm-agnostic reuse; unblind ONLY here) ───
python3 - <<'PY'
import json, pathlib, itertools
import judge_b1_6_pilot_outputs as AGG
J = pathlib.Path("run_out/b1_9_gen")
ratings = [json.loads(l) for l in (J/"judging/llm_judge_ratings_raw.jsonl").read_text().splitlines() if l.strip()]
hidden  = json.loads((J/"generation/panel_hidden_arm_generator_metadata.json").read_text())
agg = AGG.aggregate(
    ratings, hidden,
    freeze_path=J/"judging/b1_9_gen_RATINGS_FROZEN.json",
    judge_visible_file=J/"generation/panel_judge_visible_outputs.jsonl",
    ratings_file=J/"judging/llm_judge_ratings_raw.jsonl",
    require_freeze=True, representation_version="B1.9_generation_corrected_control")
if agg.get("label","").endswith("RATINGS_NOT_FROZEN"):
    raise SystemExit("aggregate refused: " + str(agg.get("reasons")))
print("=== arm-level penalty-adjusted composite (higher = better) ===")
for arm, d in sorted(agg["summary"]["arm_summary"].items(), key=lambda kv:-kv[1]["mean_penalty_adjusted_composite"]):
    print(f"  {arm:34} n={d['n']:3}  adj={d['mean_penalty_adjusted_composite']:.3f}  raw={d['mean_raw_composite']:.3f}")

# primary contrast AUTHENTIC vs DISTANT_SOURCE (paired by item) on adj composite + specificity
arm_of  = {m["blinded_output_id"]: m["true_arm"] for m in hidden}
item_of = {m["blinded_output_id"]: m["item_id"]  for m in hidden}
adj, spec = {}, {}
for r in ratings:
    bid = r["blinded_output_id"]; a = arm_of.get(bid);  it = item_of.get(bid)
    if a is None: continue
    _, ad = AGG.composites(r)
    adj.setdefault((it,a), []).append(ad)
    spec.setdefault((it,a), []).append(float(r["specificity_to_target"]))
def paired(a1, a2, table):
    import statistics as st
    items = sorted({it for (it,a) in table})
    w=l=t=0; diffs=[]
    for it in items:
        if (it,a1) in table and (it,a2) in table:
            m1=st.mean(table[(it,a1)]); m2=st.mean(table[(it,a2)]); diffs.append(m1-m2)
            w+= m1>m2; l+= m1<m2; t+= m1==m2
    md = sum(diffs)/len(diffs) if diffs else float("nan")
    return w,l,t,round(md,3)
for lbl, tab in (("penalty_adjusted_composite", adj), ("specificity_to_target", spec)):
    for ctrl in ("DISTANT_SOURCE_MAPPING","SCRAMBLED_WITHIN_POOL"):
        w,l,t,md = paired("AUTHENTIC_MAPPING", ctrl, tab)
        print(f"[{lbl:28}] AUTHENTIC vs {ctrl:22} win/lose/tie={w}/{l}/{t}  mean_diff={md:+}")
PY

# ── 6. Confirm run_out/ untracked ─────────────────────────────────────────────
git check-ignore run_out && echo "OK: run_out/ git-ignored"; echo "tracked under run_out: $(git ls-files run_out | wc -l)"
```

## Expected files (all under gitignored `run_out/b1_9_gen/`)
- `b1_9_gen_EVIDENCE_FREEZE_DECLARED.json` — 6 frozen-input hashes + attestation.
- `M1/b1_9_part.json`, `M2/b1_9_part.json` — 72 outputs each (hidden side).
- `generation/panel_judge_visible_outputs.jsonl` (144, blind), `panel_hidden_arm_generator_metadata.json`, `panel_run_manifest.json`.
- `J0|J1|J2/judge_part_*.json`; `judging/llm_judge_ratings_raw.jsonl` (432).
- `judging/b1_9_gen_RATINGS_FROZEN.json`.

## Notes
- The generation `part` **refuses** without a valid B1.9-generation declaration (`mode
  b1_9_generation_corrected_control_probe`, representation `B1.9_generation_corrected_control`, matching hashes,
  exact attestation). A B1.6/B1.8/B1.9-content-distance declaration is rejected loudly.
- Judges never see arm names, generator IDs, planes, varṇa names, or the distant-source id (blind schema =
  `{item_id, target_text, neutral_context, blinded_output_id, generation_text, output_format}`).
- Descriptive `B1_9_GEN_PROBE_*` labels only; **no `GENUTILITY_*`**, no ontology, no Sanskrit privilege. B1.4b′
  remains `NULL_RETURN_BOTTOM`.

B1.9 generation (corrected control) command block documented only. No generation. No judging. No B1.10. Structure,
not validated meaning.
