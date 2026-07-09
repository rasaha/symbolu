# B1.6 — 10-Sample RunPod Generation Commands (Multi-Model Panel)

**Status:** Operator/RunPod command guide (docs only). **This document executes nothing.** Copy-pasteable
commands to run the B1.6 **10-sample exploratory** generation probe with the B1.1-style two-generator panel.
**No generation run. No judging. No evidence freeze. No external API call. No `GENUTILITY_*` label.**
**B1.4b′ remains `NULL_RETURN_BOTTOM`. No ontology, no Sanskrit privilege, no validated meaning. Original B1.4b
remains blocked. Track B remains blocked. Structure, not validated meaning.**

**Readiness label: `B1_6_10_SAMPLE_RUNPOD_GENERATION_COMMANDS_DOCUMENTED`.**
CLI flags, mock-only panel CLI, output filenames, deterministic subset, and the mode-aware attestation were all
**verified against the current code** (`96dd9ab` adapter, `6a09480` panel).

---

## 1. Purpose

Give the exact RunPod/operator command sequence for the 10-sample exploratory multi-model panel. **The assistant
does not run it, does not create the declaration, and does not judge.** Real generation is an operator action on
a model-access host.

## 2. Current status

- Adapter ready (`96dd9ab`); panel orchestration ready (`6a09480`); driver/runbook (`cc56eb1`).
- **No generation. No judging. No evidence freeze. No ratings freeze.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

## 2b. Representation: use B1.6-v2 named-vṛtti (NOT v1)

The active scaffold is **B1.6-v2 named-vṛtti**. The driver/panel now default to
`--representation-version v2_named_vritti`; **do not run v1** (`v1_directional` is superseded/historical,
accessible only if explicitly requested). All hashes below are the **v2** files:

- `frozen/b1_6_pilot_targets_scaffolds_v2_named_vritti.json`
- `frozen/b1_6_pilot_scaffold_manifest_v2_named_vritti.json`
- `frozen/b1_6_pilot_randomized_control_manifest_v2_named_vritti.json`
- table: `track_g_varna_polarity_table_v2_named_vritti.json`

The evidence-freeze declaration must carry `"representation_version": "v2_named_vritti"` and hash the **v2**
files; a v1 declaration (or v1 hashes) is **refused loudly** when a v2 run is requested.

## 3. Model panel (B1.1-style; IDs/revisions operator-frozen at run time)

- **Generators:** `mistralai/Mistral-7B-Instruct-v0.3`, `Qwen/Qwen2.5-7B-Instruct`.
- **Judges (later judging step):** `meta-llama/Llama-3.1-8B-Instruct`, `meta-llama/Meta-Llama-3-8B-Instruct`,
  `google/gemma-2-9b-it`.

Exact model IDs **and revisions must be frozen by the operator** in the panel manifest (§8). Judge families
(Llama/Gemma) differ from generator families (Mistral/Qwen) — conflict-free (no model judges its own output).

## 4. Expected output count

10 targets × 5 arms × 2 generators = **100** generated outputs. **Exploratory only** — cannot emit a
`GENUTILITY_*` terminal label; validates plumbing + whether an effect is even visible before the full pilot
(24 × 5 × 2 = 240).

## 5. RunPod setup

```bash
git clone <repo-url> symbolu && cd symbolu
git fetch origin claude/symbolu-adversarial-eval-zevb4h
git checkout claude/symbolu-adversarial-eval-zevb4h
git merge-base --is-ancestor 6a09480 HEAD && echo "6a09480 present" || echo "6a09480 MISSING"

cd experiments/primitive_sequence_recovery
python3 -m pip install -U pip
python3 -m pip install torch transformers pytest          # transformers backend (option B)
# for the vLLM backend (option A) also:  python3 -m pip install vllm

python3 -m pytest test_b1_6_llm_adapter.py test_b1_6_model_panel.py \
                  test_run_b1_6_pilot_generation.py test_judge_b1_6_pilot_outputs.py -q   # expect 74 passed
```

## 6. Backend option A — local vLLM (OpenAI-compatible) servers

Launch one server per generator on separate ports (placeholders in `<...>`):

```bash
# Mistral on 8001
python3 -m vllm.entrypoints.openai.api_server \
  --model mistralai/Mistral-7B-Instruct-v0.3 \
  --download-dir <MODEL_CACHE_PATH> \
  --tensor-parallel-size <TP_SIZE> \
  --gpu-memory-utilization <GPU_MEM_UTIL> \
  --max-model-len <MAX_MODEL_LEN> \
  --port 8001 &

# Qwen on 8002
python3 -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --download-dir <MODEL_CACHE_PATH> \
  --tensor-parallel-size <TP_SIZE> \
  --gpu-memory-utilization <GPU_MEM_UTIL> \
  --max-model-len <MAX_MODEL_LEN> \
  --port 8002 &

# readiness checks
curl -s http://localhost:8001/v1/models | head -c 400; echo
curl -s http://localhost:8002/v1/models | head -c 400; echo
```

The adapter posts to `<base_url>/v1/chat/completions`, so `base_url` is `http://localhost:8001` /
`http://localhost:8002`.

## 7. Backend option B — transformers local model

Single-process, per-generator (slower than vLLM; needs enough VRAM):

```bash
python3 - <<'PY'
import b1_6_llm_adapter as A
r = A.model_backend_readiness()
assert r["cuda_available"], f"no CUDA backend: {r}"     # transformers path refuses without CUDA
print("CUDA OK; transformers", r["transformers_version"])
PY
```

The transformers adapter loads each generator at its frozen revision (`AutoModelForCausalLM.from_pretrained(id,
revision=...)`).

## 8. Model panel manifest

Write `run_out/b1_6_10_sample_probe/model_panel_manifest.json` (operator-authored; gitignored):

```json
{
  "artifact_type": "b1_6_model_panel_manifest",
  "mode": "exploratory_10_sample_generation_probe",
  "backend": "openai_compat_local",
  "generator_models": [
    {"id": "mistralai/Mistral-7B-Instruct-v0.3", "family": "Mistral", "revision": "<frozen>",
     "endpoint": "http://localhost:8001"},
    {"id": "Qwen/Qwen2.5-7B-Instruct", "family": "Qwen", "revision": "<frozen>",
     "endpoint": "http://localhost:8002"}
  ],
  "judge_models": [
    {"id": "meta-llama/Llama-3.1-8B-Instruct", "family": "Llama", "revision": "<frozen>"},
    {"id": "meta-llama/Meta-Llama-3-8B-Instruct", "family": "Llama", "revision": "<frozen>"},
    {"id": "google/gemma-2-9b-it", "family": "Gemma", "revision": "<frozen>"}
  ],
  "temperature": 0.7,
  "max_tokens": 320,
  "seed": 1101,
  "declared_by": "<operator>",
  "declared_at_utc": "<ISO-8601>"
}
```

## 9. Exploratory evidence-freeze declaration (probe-specific)

> **⚠ OPERATOR ACTION — DO NOT RUN UNLESS AUTHORIZING THE PROBE.** Do **not** use the full-pilot declaration path.

```bash
mkdir -p run_out/b1_6_10_sample_probe
python3 - <<'PY'
import hashlib, json, datetime, pathlib
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
decl = {
  "artifact": "b1_6_pilot_EVIDENCE_FREEZE_DECLARED",
  "evidence_freeze_declared": True,
  "mode": "exploratory_10_sample_generation_probe",
  "representation_version": "v2_named_vritti",
  "scaffold_manifest_sha256": sha("frozen/b1_6_pilot_scaffold_manifest_v2_named_vritti.json"),
  "target_scaffold_sha256": sha("frozen/b1_6_pilot_targets_scaffolds_v2_named_vritti.json"),
  "randomized_control_manifest_sha256": sha("frozen/b1_6_pilot_randomized_control_manifest_v2_named_vritti.json"),
  "prompt_rubric_sha256": sha("B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md"),
  "declared_by": "REPLACE_WITH_OPERATOR_ID",
  "declared_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "attestation": "B1.6 10-sample exploratory generation probe only; no judging; no semantic truth claim; "
                 "no GENUTILITY terminal label; B1.4b′ remains NULL_RETURN_BOTTOM.",
}
pathlib.Path("run_out/b1_6_10_sample_probe/b1_6_10_sample_EVIDENCE_FREEZE_DECLARED.json").write_text(
    json.dumps(decl, indent=2, ensure_ascii=False))
print("exploratory declaration written (gitignored).")
PY
```

The attestation string above is **exactly** what the gate requires for `exploratory_10_sample_generation_probe`
(verified: `run_b1_6_pilot_generation.ATTESTATIONS[EXPLORATORY_MODE]`); the pilot attestation would be refused
in this mode.

## 10. 10-sample deterministic subset

`--limit-items 10` selects (deterministic balanced round-robin over the six strata — **verified**):

`river, balance, Maya, lotus, Lumen, grief, bridge, freedom, Rowan, dawn`.

## 11. Generation command (multi-model panel)

**The panel CLI (`b1_6_model_panel.py`) supports only `--mock` for non-real plumbing** — a **real** multi-model
run is driven by a tiny operator harness that builds one adapter per generator and calls `run_panel(...)` with
the probe declaration. Verified against the code (real panel CLI intentionally refuses).

```bash
python3 - <<'PY'
import json, pathlib
import b1_6_model_panel as P
import b1_6_llm_adapter as A

PROBE = pathlib.Path("run_out/b1_6_10_sample_probe")
panel = json.loads((PROBE / "model_panel_manifest.json").read_text())

def adapter_factory(gen):
    # OPTION A (vLLM / OpenAI-compatible local server):
    return A.build_adapter(A.GenerationSettings(
        model_id=gen["id"], backend="openai_compat_local", base_url=gen["endpoint"],
        temperature=panel["temperature"], max_tokens=panel["max_tokens"], seed=panel["seed"]))
    # OPTION B (transformers): return A.build_adapter(A.GenerationSettings(
    #     model_id=gen["id"], backend="transformers", revision=gen.get("revision"),
    #     temperature=panel["temperature"], max_tokens=panel["max_tokens"], seed=panel["seed"]))

res = P.run_panel(
    panel,
    adapter_factory=adapter_factory,
    mock=False,
    mode="exploratory_10_sample_generation_probe",   # matches the declaration mode
    limit_items=10,
    decl_path=PROBE / "b1_6_10_sample_EVIDENCE_FREEZE_DECLARED.json",
    out_dir=PROBE / "generation",
    write=True,
)
print(json.dumps(res["panel_manifest"], indent=2))   # expect n_outputs == 100, run_label exploratory
PY
```

*(Mock plumbing only, no model needed:
`python3 b1_6_model_panel.py --model-panel-manifest run_out/b1_6_10_sample_probe/model_panel_manifest.json
--mock --mode exploratory_10_sample_generation_probe --limit-items 10` — still requires a matching declaration
at the driver's default path; the harness above is the real path.)*

## 12. Expected output files

`run_panel(write=True)` writes to `run_out/b1_6_10_sample_probe/generation/` (**verified filenames**; the
multi-model panel uses `panel_*` names, distinct from the single-model driver's `judge_visible_outputs.jsonl`):

- `panel_judge_visible_outputs.jsonl` — **blinded**, re-blinded ids `F0001…F0100`.
- `panel_hidden_arm_generator_metadata.json` — `Fid → true_arm + generator_code + generator_id + item_id`.
- `panel_run_manifest.json` — counts, `generator_codes`, conflicts, `panel_sha256`, `judging_performed: false`.

*(A single-model run via `run_b1_6_pilot_generation.py` instead writes `judge_visible_outputs.jsonl`,
`hidden_arm_metadata.json`, `generation_run_manifest.json`, `rendered_prompts_hidden.jsonl`.)*

## 13. Blinding verification

```bash
cd run_out/b1_6_10_sample_probe/generation
wc -l panel_judge_visible_outputs.jsonl                         # expect 100
# no arm names / generator ids / opaque codes / system labels in judge-visible:
grep -Ec "SYMBOLU|PLAIN_PROMPT|GENERIC_STRUCTURED|RANDOMIZED|SEMANTIC_LLM|Mistral|Qwen|generator_code|generator_id|true_arm|KCPR|varna|scaffold|polarity" \
  panel_judge_visible_outputs.jsonl                             # expect 0
test -f panel_hidden_arm_generator_metadata.json && echo "hidden metadata present (separate)"
# hidden metadata is NOT part of the judge package; keep it withheld until ratings freeze.
```

*(There is no `rendered_prompts_hidden.jsonl` in the panel path — prompts are not written by `run_panel`. If you
also need them, run the single-model driver per generator; they remain hidden, never judge-visible.)*

## 14. Git safety

```bash
cd /path/to/symbolu
git status --short
git check-ignore experiments/primitive_sequence_recovery/run_out/x && echo "run_out ignored"
```

- **Do NOT commit** `run_out/` (gitignored), the evidence-freeze declaration, generated outputs, hidden
  metadata, or the panel manifest with real endpoints. Confirm `git status --short` shows none before any commit.

## 15. After generation

Next step is **blind judging** with the 3-judge panel (`B1_6_PILOT_BLIND_JUDGING_RUNBOOK.md`) — **not**
interpretation of the outputs by the runner. **Judge models must differ from the generator models** (Llama/Gemma
judges vs Mistral/Qwen generators; no model judges its own output). **No unblinding before a ratings-freeze
declaration.** A pilot/probe emits only `B1_6_PILOT_JUDGING_*` plumbing labels — never a `GENUTILITY_*` verdict.

## 16. Guardrails

This guide executes nothing. The 10-sample probe is **exploratory only**. No `GENUTILITY_*`; no ontology; no
semantic-truth claim; KCPR caveat `THEORY_NONCANONICAL_INPUT_POLARITY` remains active. **B1.4b′ remains
`NULL_RETURN_BOTTOM`**; original B1.4b remains blocked; Track B remains blocked. **Structure, not validated
meaning.**

## 17. Readiness label

**`B1_6_10_SAMPLE_RUNPOD_GENERATION_COMMANDS_DOCUMENTED`.**

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_6_10_SAMPLE_RUNPOD_GENERATION_COMMANDS.md`.
  (Also, a small verified correctness fix: the freeze gate is now mode-aware for the exploratory attestation —
  `run_b1_6_pilot_generation.py` + tests; so §9's attestation is actually accepted.)
- **Commit hash:** (recorded on commit below).
- **Readiness label:** `B1_6_10_SAMPLE_RUNPOD_GENERATION_COMMANDS_DOCUMENTED`.
- **Exact CLI flags verified from current code?** **Yes** — `--mode`, `--limit-items`, `--local-model`,
  `--base-url`, `--adapter-config`, `--item-ids` (driver) and `--model-panel-manifest`, `--mock` (panel);
  panel real-run refuses from CLI → documented the `run_panel(adapter_factory=...)` harness; output filenames
  (`panel_*`) and the deterministic 10-word subset confirmed by running the selector.
- **Model panel command summary:** two vLLM servers (8001/8002) or transformers; a probe-specific exploratory
  declaration; a `run_panel` harness building one `openai_compat_local`/`transformers` adapter per generator →
  100 blinded, re-blinded outputs under `run_out/b1_6_10_sample_probe/generation/`.
- **Commands were documented only.**
- **No generation was run.**
- **No evidence freeze was declared.**
- **No judging occurred.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

> B1.6 10-sample RunPod generation commands documented only. No generation run. No judging. No evidence freeze.
> No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B
> remains blocked. Structure, not validated meaning.
