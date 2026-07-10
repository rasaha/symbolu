# B1.9 Pole Diff-in-Diff — Copy-pasteable RunPod command block

**Docs-only.** 4 arms — `OWN_CORRECT_POLE`, `OWN_FLIPPED_POLE`, `CONTROL_CORRECT_POLE`, `CONTROL_FLIPPED_POLE`.
Primary statistic **`DiD = (OWN_CORRECT − OWN_FLIPPED) − (CONTROL_CORRECT − CONTROL_FLIPPED)`**. The correct pole
is fixed by the frozen referent classification, which **must be operator-approved before any generation** (the
runner refuses otherwise). Expected **192 outputs** (24 × 4 × 2) and **576 ratings**. Consonant-only canonical
varṇas (Stage A′ + bridge; vowels dropped — prereg §5b).

Driver: `run_b1_9_pole_did.py` (+ `test_run_b1_9_pole_did.py`, 13 tests) — mock-tested. Judges + aggregation reuse
`run_b1_6_v2_llm_judge_panel.py` and `judge_b1_6_pilot_outputs.aggregate` unchanged.

**Interpretation (fixed):** `DiD ≈ 0` → correct-vs-flipped is just generic pole-valence congruence, not
varṇa-specific (informative null). `DiD > 0` robust → low-level pole-specific signal only (no ontology/truth/
privilege/GENUTILITY). `DiD < 0` → anti-supports.

---

```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
git pull
export HF_HOME=/workspace/.cache/huggingface

# ── STEP A: classification ALREADY APPROVED and committed — verify only ────────
#   (The 24-item table was reviewed and approved as-is; classification_approved=true is in the repo.
#    `git pull` above brings the approved frozen files. Just confirm; do NOT re-edit poles.)
python3 -c "import json;d=json.load(open('frozen/b1_9_pole_did_items.json'));print('classification_approved:',d['classification_approved']);assert d['classification_approved'] is True,'NOT approved — git pull the approved commit'"
python3 build_b1_9_pole_did_scaffold.py   # idempotent: preserves approval, reproduces the same scaffold (hashes unchanged)

# ── 1. Evidence-freeze declaration ────────────────────────────────────────────
python3 - <<'PY'
import json, datetime, pathlib
import run_b1_9_pole_did as D
outdir = pathlib.Path("run_out/b1_9_pole_did"); outdir.mkdir(parents=True, exist_ok=True)
decl = {"artifact": "b1_9_pole_did_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
        "mode": D.MODE, "representation_version": D.REPRESENTATION, "declared_by": "operator",
        "declared_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attestation": D.ATTESTATION, **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()}}
p = outdir / "b1_9_pole_did_EVIDENCE_FREEZE_DECLARED.json"; p.write_text(json.dumps(decl, indent=2))
print("wrote", p, "| approved:", D.classification_approved())
PY

# ── 2. Generation ─────────────────────────────────────────────────────────────
export DECL=run_out/b1_9_pole_did/b1_9_pole_did_EVIDENCE_FREEZE_DECLARED.json
python3 run_b1_9_pole_did.py part --decl "$DECL" --gen-code M1 \
        --backend transformers --model-id mistralai/Mistral-7B-Instruct-v0.3 --out run_out/b1_9_pole_did/M1   # 96
python3 run_b1_9_pole_did.py part --decl "$DECL" --gen-code M2 \
        --backend transformers --model-id Qwen/Qwen2.5-7B-Instruct        --out run_out/b1_9_pole_did/M2      # 96
python3 run_b1_9_pole_did.py merge --parts run_out/b1_9_pole_did/M1 run_out/b1_9_pole_did/M2 \
        --out run_out/b1_9_pole_did/generation                                                                # 192

# ── 3. Blind judging ──────────────────────────────────────────────────────────
cat > run_out/b1_9_pole_did/judge_panel.json <<'JSON'
{"backend":"transformers",
 "judge_models":[{"id":"meta-llama/Llama-3.1-8B-Instruct","family":"Llama"},
                 {"id":"meta-llama/Meta-Llama-3-8B-Instruct","family":"Llama"},
                 {"id":"google/gemma-2-9b-it","family":"Gemma"}],
 "generator_models":[{"id":"mistralai/Mistral-7B-Instruct-v0.3"},{"id":"Qwen/Qwen2.5-7B-Instruct"}]}
JSON
JV=run_out/b1_9_pole_did/generation/panel_judge_visible_outputs.jsonl
for i in 0 1 2; do
  python3 run_b1_6_v2_llm_judge_panel.py judge --panel run_out/b1_9_pole_did/judge_panel.json \
          --judge-index $i --judge-visible "$JV" --out run_out/b1_9_pole_did/J$i
done
python3 run_b1_6_v2_llm_judge_panel.py merge \
        --parts run_out/b1_9_pole_did/J0 run_out/b1_9_pole_did/J1 run_out/b1_9_pole_did/J2 \
        --out run_out/b1_9_pole_did/judging

# ── 4. Ratings-freeze declaration ─────────────────────────────────────────────
python3 - <<'PY'
import json, datetime, pathlib
import judge_b1_6_pilot_outputs as AGG
jv = pathlib.Path("run_out/b1_9_pole_did/generation/panel_judge_visible_outputs.jsonl")
rf = pathlib.Path("run_out/b1_9_pole_did/judging/llm_judge_ratings_raw.jsonl")
decl = {"artifact": "b1_6_pilot_RATINGS_FROZEN", "ratings_frozen": True, "mode": AGG.MODE,
        "judge_visible_outputs_sha256": AGG._sha_file(jv), "ratings_file_sha256": AGG._sha_file(rf),
        "declared_by": "operator",
        "declared_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attestation": AGG.RATINGS_ATTESTATION}
pathlib.Path("run_out/b1_9_pole_did/judging/b1_9_pole_did_RATINGS_FROZEN.json").write_text(json.dumps(decl, indent=2))
print("wrote ratings-freeze")
PY

# ── 5. Aggregate + DIFF-IN-DIFF (unblind ONLY here) ───────────────────────────
python3 - <<'PY'
import json, pathlib, statistics as st, random
import judge_b1_6_pilot_outputs as AGG
J = pathlib.Path("run_out/b1_9_pole_did")
ratings=[json.loads(l) for l in (J/"judging/llm_judge_ratings_raw.jsonl").read_text().splitlines() if l.strip()]
hidden =json.loads((J/"generation/panel_hidden_arm_generator_metadata.json").read_text())
agg=AGG.aggregate(ratings, hidden,
    freeze_path=J/"judging/b1_9_pole_did_RATINGS_FROZEN.json",
    judge_visible_file=J/"generation/panel_judge_visible_outputs.jsonl",
    ratings_file=J/"judging/llm_judge_ratings_raw.jsonl",
    require_freeze=True, representation_version="B1.9_pole_did")
if str(agg.get("label","")).endswith("RATINGS_NOT_FROZEN"): raise SystemExit("refused: "+str(agg.get("reasons")))
print("=== arm-level penalty-adjusted composite ===")
for arm,d in sorted(agg["summary"]["arm_summary"].items(), key=lambda kv:-kv[1]["mean_penalty_adjusted_composite"]):
    print(f"  {arm:22} n={d['n']:3}  adj={d['mean_penalty_adjusted_composite']:.3f}")
arm_of={m["blinded_output_id"]:m["true_arm"] for m in hidden}; item_of={m["blinded_output_id"]:m["item_id"] for m in hidden}
cell={}
for r in ratings:
    bid=r["blinded_output_id"]; a=arm_of.get(bid); it=item_of.get(bid)
    if a is None: continue
    _,ad=AGG.composites(r); cell.setdefault((it,a),[]).append(ad)
def m(it,a): 
    v=cell.get((it,a)); return st.mean(v) if v else None
items=sorted({i for (i,a) in cell})
dids=[]
for it in items:
    o1,o0,c1,c0=m(it,"OWN_CORRECT_POLE"),m(it,"OWN_FLIPPED_POLE"),m(it,"CONTROL_CORRECT_POLE"),m(it,"CONTROL_FLIPPED_POLE")
    if None in (o1,o0,c1,c0): continue
    dids.append(((o1-o0)-(c1-c0), o1-o0, c1-c0, it))
own=[d[1] for d in dids]; ctrl=[d[2] for d in dids]; did=[d[0] for d in dids]
def boot(x,n=2000,seed=7):
    r=random.Random(seed); ms=sorted(sum(r.choice(x) for _ in range(len(x)))/len(x) for _ in range(n))
    return round(ms[int(.025*n)],3), round(ms[int(.975*n)],3)
print(f"\nn_items paired: {len(did)}")
print(f"mean OWN diff  (OWN_CORRECT-OWN_FLIPPED)     = {st.mean(own):+.3f}")
print(f"mean CTRL diff (CONTROL_CORRECT-CONTROL_FLIP)= {st.mean(ctrl):+.3f}")
print(f"mean DiD                                      = {st.mean(did):+.3f}  CI95 {boot(did)}  "
      f"(pos {sum(1 for d in did if d>0)}/neg {sum(1 for d in did if d<0)})")
PY

# ── 6. run_out untracked ──────────────────────────────────────────────────────
git check-ignore run_out && echo "OK: run_out git-ignored"; echo "tracked under run_out: $(git ls-files run_out | wc -l)"
```

**The make-or-break line is `mean DiD`.** A CI straddling 0 → informative null (correct-vs-flipped is generic
valence, not varṇa-specific). A robust `DiD > 0` → low-level pole-specific varṇa signal only — no ontology, no
semantic truth, no Sanskrit privilege, no `GENUTILITY_*`. Consonant-only; vowel omission is a stated limitation
(prereg §5b).

B1.9 pole diff-in-diff command block documented only. No generation. No judging. No B1.10. Structure, not
validated meaning.
