# B1.10 — Stage-4 Real Judge Run Runbook (RunPod)

**This runbook does NOT run judges here.** It is the exact procedure for the operator to execute the gated
real Llama/Gemma run on a GPU host, once approved. The runner is fail-closed: `verify_real_run_preconditions`
aborts before the first rating on any mismatch (see `run_b1_10_control_ext.py`). No result/verdict label is
emitted by the runner. Interpretation ceiling: a positive later result shows **source-condition legibility to
judges only** — no ontology / semantic-truth / Sanskrit-privilege / generation-utility / individual-varṇa
claim. B1.4b′ remains `NULL_RETURN_BOTTOM`. Structure, not validated meaning.

---

## The authorized declaration (hardened)

Use **only** the hardened re-issued declaration, which pins the hardened runner:

- **`frozen/b1_10_control_ext_v3_HARDENED_EVIDENCE_FREEZE_DECLARED.json`**
- expected SHA256: **`e71889d44e90a86e11fb5fbe3a1db3d49b03db630aaba35d8a00233f596e0181`**

The Step-2 declaration (`b1_10_control_ext_v3_EVIDENCE_FREEZE_DECLARED.json`, sha `9b1d4d63…`) is the
historical record and is **stale on its `runner` pin** after hardening — the gate fail-closes on it. Do **not**
use it, and do **not** edit it.

## Step 0 — check out the pinned commit and verify the runner matches

```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
git fetch origin claude/symbolu-adversarial-eval-zevb4h && git checkout claude/symbolu-adversarial-eval-zevb4h && git pull
# the hardened declaration pins this exact runner; if you later change the runner, re-issue the declaration.
```

## Step 1 — preflight (no judges, no model): inputs consistent with the hardened declaration

```bash
python3 run_b1_10_control_ext.py preflight \
    --decl frozen/b1_10_control_ext_v3_HARDENED_EVIDENCE_FREEZE_DECLARED.json \
    --items frozen/b1_10_control_ext_items_v3_qwen.json \
    --seed 20260712 \
    --expect-decl-sha e71889d44e90a86e11fb5fbe3a1db3d49b03db630aaba35d8a00233f596e0181
# expect: {"preflight":"PASS", ..., "n_cells":72, "expected_total_ratings":216}
```

Preflight aborts fail-closed on: hash mismatch, wrong/altered items file, wrong seed, or declaration mismatch.

## Step 2 — the gated judge run (J0 → J1 → J2, one model at a time)

The panel is enforced as EXACTLY `{Llama-3.1-8B-Instruct, Meta-Llama-3-8B-Instruct, gemma-2-9b-it}` (greedy,
temp 0, 0–6 rubric; no Claude/Mistral/Qwen). All three judge objects are constructed up front (so the gate
sees the full panel), but each **lazy-loads its model on first rating and frees it before the next** — so only
one model is resident at a time. `run_real_gated` rates J0's 72 cells, frees, then J1, then J2. Save this
driver on the pod as `run_b1_10_v3_judges.py`:

```python
# run_b1_10_v3_judges.py  — pod driver (constructs REAL judges; one model resident at a time)
import argparse, torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import run_b1_10_control_ext as R

class RealJudge:
    is_real = True; temperature = 0; scale = (0, 6); rubric = "b1_10_0_6"
    def __init__(self, model_id): self.model_id = model_id; self._tok=None; self._m=None; self.revision_resolved=None
    def _load(self):
        self._tok = AutoTokenizer.from_pretrained(self.model_id)
        self._m = AutoModelForCausalLM.from_pretrained(self.model_id, torch_dtype=torch.float16, device_map="auto")
        self.revision_resolved = getattr(self._m.config, "_commit_hash", None)   # MUST resolve (gate aborts if not)
        if self.revision_resolved in R.UNRESOLVED_REVS:
            raise SystemExit(f"could not resolve HF revision for {self.model_id}; aborting (do not use bare 'main')")
    def rate(self, prompt):
        if self._m is None: self._load()
        msgs=[{"role":"user","content":prompt}]
        enc=self._tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True).to(self._m.device)
        out=self._m.generate(**enc, max_new_tokens=24, do_sample=False, temperature=None, top_p=None,
                             pad_token_id=self._tok.eos_token_id)       # greedy (temp 0)
        return self._tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
    def close(self):
        del self._m; self._m=None
        import gc; gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()

ap=argparse.ArgumentParser()
ap.add_argument("--decl", required=True); ap.add_argument("--seed", type=int, default=20260712)
ap.add_argument("--run-id", required=True); ap.add_argument("--expect-decl-sha", required=True)
a=ap.parse_args()
panel=[RealJudge(m) for m in R.ALLOWED_JUDGE_IDS]      # J0, J1, J2 in the frozen order
man=R.run_real_gated(a.decl, panel, seed=a.seed, run_id=a.run_id, expected_decl_sha=a.expect_decl_sha)
print("RUN_OK", man["run_id"], "ratings", man["n_ratings_collected"], "revs", man["judge_revisions"])
```

```bash
export HF_HOME=/workspace/hf_cache HF_HUB_DISABLE_XET=1
python3 run_b1_10_v3_judges.py \
    --decl frozen/b1_10_control_ext_v3_HARDENED_EVIDENCE_FREEZE_DECLARED.json \
    --seed 20260712 --run-id run01 \
    --expect-decl-sha e71889d44e90a86e11fb5fbe3a1db3d49b03db630aaba35d8a00233f596e0181
# writes runs/b1_10_control_ext_v3_run_run01/{<judge>/{E01.raw.txt..,parsed_ratings.json,per_judge_manifest.json},
#         run_manifest.json, aggregation_inputs.json}
```

The gate resolves and records each judge's HF revision in the per-judge manifest and `run_manifest.json`
(execution provenance for the final evidence package). If any revision fails to resolve, the run aborts.

Replicate seed (optional, recommended): repeat with `--seed 20260713 --run-id run02` (both are declared seeds).

## Step 3 — merge / coverage verification (216 ratings, 72/judge, none missing)

```bash
python3 - <<'PY'
import json, pathlib
run=pathlib.Path("runs/b1_10_control_ext_v3_run_run01")
man=json.loads((run/"run_manifest.json").read_text())
agg_in=json.loads((run/"aggregation_inputs.json").read_text())
assert man["n_judges"]==3 and man["n_cells"]==72 and man["expected_total_ratings"]==216
assert len(agg_in)==216, f"expected 216 ratings, got {len(agg_in)}"
by_judge={}
for r in agg_in: by_judge.setdefault(r["judge"],set()).add((r["word"],r["context_pole"],r["tier"],r["packet_pole"]))
for j,cells in by_judge.items():
    assert len(cells)==72, f"{j}: {len(cells)} unique cells (expected 72)"
missing=[r for r in agg_in if r["score"] is None]
print("COVERAGE_OK judges", list(by_judge), "missing", len(missing))
PY
```

## Step 4 — aggregation (run ONLY after ratings exist; NOT part of this prep step)

```bash
python3 - <<'PY'
import json, pathlib
import run_b1_10_control_ext as R
agg_in=json.loads(pathlib.Path("runs/b1_10_control_ext_v3_run_run01/aggregation_inputs.json").read_text())
rows=[{"word":r["word"],"context_pole":r["context_pole"],"tier":r["tier"],
       "packet_pole":r["packet_pole"],"score":r["score"]} for r in agg_in if r["score"] is not None]
agg=R.aggregate(rows, n_total_cells=72)   # per-word + aggregate margins + both increments; NO verdict label
print(json.dumps(agg["aggregate"], indent=2))
PY
```

Aggregation emits **descriptive statistics only** (specific / valence / generic-source-condition margins +
`increment_over_valence` + `increment_over_source_condition`); no accept/reject or positive/null verdict.

## Step 5 — run-directory git-ignore verification

```bash
git check-ignore -v runs/b1_10_control_ext_v3_run_run01 && echo "RUN DIR IS GIT-IGNORED (ok)" \
    || echo "ERROR: run dir NOT ignored — do not commit run outputs"
```

## Fail-closed summary (any one aborts BEFORE the first rating)

declaration missing / wrong SHA / wrong mode-version / `evidence_freeze_declared`≠true · any pinned input hash
mismatch (incl. runner/builder) · wrong or altered items file (only `b1_10_control_ext_items_v3_qwen.json`
accepted; the excluded-context file is rejected) · not 72 unique cells / duplicate or missing combination ·
wrong/forbidden/duplicate judge id · non-greedy or wrong scale/rubric · unresolved judge revision ·
non-real backend · undeclared seed · non-git-ignored or non-empty run directory · missing `run_id`.

## Guardrails
No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; B1.4b′ `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B
blocked; structure, not validated meaning. Under B1.10; no new experiment number.
