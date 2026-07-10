# B1.9 Pole-Logic Sanity — Copy-pasteable RunPod command block

**Docs-only. NO generation** — judges rate the RAW correct/flipped varṇa facet packets directly. Pole-label
coherence sanity check ONLY (not ontology / semantic truth / Sanskrit privilege / generation utility /
word-specific mapping).

Primary statistic **`INT = D_target − D_opposite`** where `D_target = mean(correct fit to W/syn) − mean(flipped fit
to W/syn)` and `D_opposite = mean(correct fit to opp) − mean(flipped fit to opp)`. Coherent ⇒ `D_target>0`,
`D_opposite<0`, `INT>0`. The synonym/opposite table **must be operator-approved before any run** (the judge step
refuses otherwise). Consonant-only packets (inherited limitation).

Driver: `run_b1_9_pole_sanity.py` (+ `test_run_b1_9_pole_sanity.py`, 12 tests) — mock-tested. Three blind judges,
disjoint families. No same-model conflict possible (there are no generators).

---

```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
git pull
export HF_HOME=/workspace/.cache/huggingface

# ── STEP A: CURATE + APPROVE the synonym/opposite table (REQUIRED before any run) ──────
#   The DRAFT was auto-harvested from WordNet and HAS SENSE NOISE (e.g. lock->curl is hair,
#   anchor->mainstay is the metaphor; some antonyms are verbs; 13 words are flagged for fill).
#   1) Review frozen/b1_9_pole_sanity_items.json — check every synonym/opposite SENSE vs the word's context.
#   2) Hand-edit weak entries (fix synonyms/opposites/glosses). Aim for 4 synonyms + 4 opposites/word.
#   3) Set "word_groups_approved": true.  4) Re-run the builder to refresh hashes/scaffold:
python3 build_b1_9_pole_sanity_scaffold.py            # idempotent; preserves your approval flag
python3 -c "import json;d=json.load(open('frozen/b1_9_pole_sanity_items.json'));print('approved:',d['word_groups_approved'],'flags:',len(d['coverage_flags']));assert d['word_groups_approved'] is True,'CURATE + APPROVE first'"

# ── STEP B: prepare the blind rating package (no model; shuffles; strips pole/role/item) ─
python3 run_b1_9_pole_sanity.py prepare --out run_out/b1_9_pole_sanity   # prints n_items / n_rating_tasks / per_role

# ── STEP C: evidence-freeze declaration ───────────────────────────────────────────────
python3 - <<'PY'
import json, datetime, pathlib
import run_b1_9_pole_sanity as D
outdir = pathlib.Path("run_out/b1_9_pole_sanity"); outdir.mkdir(parents=True, exist_ok=True)
decl = {"artifact": "b1_9_pole_sanity_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
        "mode": D.MODE, "representation_version": D.REPRESENTATION, "declared_by": "operator",
        "declared_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attestation": D.ATTESTATION, **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()}}
p = outdir / "b1_9_pole_sanity_EVIDENCE_FREEZE_DECLARED.json"; p.write_text(json.dumps(decl, indent=2))
print("wrote", p, "| approved:", D.word_groups_approved())
PY
export DECL=run_out/b1_9_pole_sanity/b1_9_pole_sanity_EVIDENCE_FREEZE_DECLARED.json
export JV=run_out/b1_9_pole_sanity/panel_judge_visible_ratings.jsonl

# ── STEP D: three blind judges rate DIRECT fit (1-7) + direct/contrastive audit ────────
python3 run_b1_9_pole_sanity.py judge --judge-visible "$JV" --decl "$DECL" \
        --judge-id meta-llama/Llama-3.1-8B-Instruct --backend transformers --out run_out/b1_9_pole_sanity/J0
python3 run_b1_9_pole_sanity.py judge --judge-visible "$JV" --decl "$DECL" \
        --judge-id meta-llama/Meta-Llama-3-8B-Instruct --backend transformers --out run_out/b1_9_pole_sanity/J1
python3 run_b1_9_pole_sanity.py judge --judge-visible "$JV" --decl "$DECL" \
        --judge-id google/gemma-2-9b-it --backend transformers --out run_out/b1_9_pole_sanity/J2

# ── STEP E: aggregate — cells 1-4, D_target, D_opposite, INT (unblind ONLY here) ───────
python3 run_b1_9_pole_sanity.py aggregate \
        --judge-parts run_out/b1_9_pole_sanity/J0 run_out/b1_9_pole_sanity/J1 run_out/b1_9_pole_sanity/J2 \
        --hidden run_out/b1_9_pole_sanity/panel_hidden_metadata.json

# ── STEP F: run_out untracked ─────────────────────────────────────────────────────────
git check-ignore run_out && echo "OK: run_out git-ignored"; echo "tracked under run_out: $(git ls-files run_out | wc -l)"
```

**How to read it.** The four `reported_cells` are your 1–4:
`1_correct_fit_to_target_synonyms` (expect high), `2_flipped_fit_to_target_synonyms` (expect low),
`3_flipped_fit_to_opposites` (expect high), `4_correct_fit_to_opposites` (expect low). The make-or-break line is
**`mean_INT`** with its CI: a CI straddling 0 → pole labels do no directional work (informative negative for
coherence); a robust `INT > 0` → the pole labels ARE coherent, directional descriptors — a **sanity pass only**, no
ontology / semantic truth / Sanskrit privilege / `GENUTILITY_*` / word-specific mapping. Check
`anti_contrastive_audit`: if contrastive rates are high, discount any nonzero `INT`.

B1.9 pole-logic sanity command block documented only. No generation. No readings. No judging performed here. No
B1.10. B1.4b′ remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
