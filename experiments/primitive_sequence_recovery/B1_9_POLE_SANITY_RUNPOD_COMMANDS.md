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

# ── STEP A: CURATE (curated-contrast mode) + APPROVE the table (REQUIRED before any run) ─
#   CURATED-CONTRAST: synonyms = PRIMARY WordNet synset only (tight sense, no lock->curl/terror->brat);
#   opposites = TRUE antonyms ONLY (the opposite-pole item-word pool is NOT used). WordNet coverage is
#   sparse, so most of the 24 words are flagged NEEDS_MANUAL_REPLACEMENT — you curate them by hand:
#   1) Edit frozen/b1_9_pole_sanity_overrides.json — for each word set
#        "synonyms":  4 same-SENSE synonyms (as in the item context)
#        "opposites": 4 TRUE antonyms / direct contrast words (NOT generic opposite-pole words)
#      (the overrides file is merged, TAKES PRECEDENCE, and survives rebuilds; verb 'antonyms' are flagged).
#   2) Rebuild and check nothing is still flagged:
python3 build_b1_9_pole_sanity_scaffold.py            # idempotent; merges overrides; preserves approval flag
python3 -c "import json;d=json.load(open('frozen/b1_9_pole_sanity_items.json'));print('fully_curated:',d['n_fully_curated'],'/',d['n_items'],'| need_manual:',d['n_need_manual']);assert d['n_need_manual']==0,'CURATE the NEEDS_MANUAL words in the overrides file first'"
#   3) Set "word_groups_approved": true in b1_9_pole_sanity_items.json, then rebuild once more and verify:
python3 build_b1_9_pole_sanity_scaffold.py
python3 -c "import json;d=json.load(open('frozen/b1_9_pole_sanity_items.json'));assert d['word_groups_approved'] is True,'APPROVE after curation'"

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

**How to read it.** Read the **two `primary_diagnostics`** together, not INT alone:
1. **`1_INT`** — coherence crossover. A CI straddling 0 → pole labels do no directional work (informative
   negative); a robust `INT > 0` → pole-label / **valence** coherence — *necessary, not sufficient*.
2. **`2_cell_1_correct_fit_to_target_synonyms`** — the word-level number. Word-level packet coherence needs this
   **high** (well above `vs_neutral_midpoint_4 ≈ 0` and with a positive `minus_cell_2_flipped_to_target`).

`verdict_logic`: **`INT>0` but `Cell① ` low ⇒ the test does NOT support word-level packet coherence** (the crossover
is generic valence). Even `INT>0` **and** `Cell①` high is a **sanity pass only** — no ontology / semantic truth /
Sanskrit privilege / `GENUTILITY_*` / word-specific mapping. Check `anti_contrastive_audit`; high contrastive rates
discount any nonzero `INT`. The four `reported_cells` (① ② ③ ④) back these up.

B1.9 pole-logic sanity command block documented only. No generation. No readings. No judging performed here. No
B1.10. B1.4b′ remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
