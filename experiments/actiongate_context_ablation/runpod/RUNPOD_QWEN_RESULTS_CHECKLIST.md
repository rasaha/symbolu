# RUNPOD_QWEN_RESULTS_CHECKLIST

A primary Qwen result set is valid and citable only if ALL of the following hold.

## Provenance
- [ ] `run_manifest.json` present; `is_real: true`; `run_kind: "PRIMARY"`.
- [ ] `model_id: "Qwen/Qwen2.5-7B-Instruct"` and a concrete `model_revision`
      (a real HF commit sha, not `local-unpinned`).
- [ ] `git.branch == claude/token-compression-enterprise-0koy0r`; `git.dirty: false`.
- [ ] `frozen_fingerprint` matches the committed frozen surface (unchanged benchmark).
- [ ] `environment_probe.json` shows CUDA available, VRAM ≥ 24 GB, BF16 or FP16.

## Completeness (from `verify_report.json`)
- [ ] `ok: true`, `n_missing: 0`, `n_extra: 0`.
- [ ] methods = `original, structural_only, protected, protection_unaware`.
- [ ] budgets = `0.2, 0.3, 0.4` (plus 0.5/0.6 only if the stress run was requested).
- [ ] every context × task family present for each method/budget.
- [ ] no duplicate keys; single model revision; single run kind.

## Records (`records.jsonl`)
- [ ] every record has nonzero `prompt_tokens`; generated records have real `output`.
- [ ] `peak_mem_mb` and `throughput_tps` populated (real GPU run).
- [ ] `status: "OK"` for the vast majority; any `ERROR:*` (e.g. OOM) understood.

## Reports
- [ ] `results.json`, `results.csv`, `REAL_LLM_RESULTS.md`, `plots/*.png` present.
- [ ] `recommendation` ∈ {`GO`, `LIMITED_GO`, `STOP`} — NOT `BLOCKED_NO_MODEL`.

## Frozen success criteria (emitted automatically; do not re-judge by hand)
- [ ] ActionGate decision flips (protected): **0** (`zero_decision_flips: true`).
- [ ] Envelope preservation (protected): **100%** (`envelope_preservation_100: true`).
- [ ] Task-accuracy degradation (protected vs original): **< 2%**.
- [ ] Tool-argument correctness (protected): **≥ 98%**.

## Integrity / handoff
- [ ] `SHA256SUMS` present and matches files.
- [ ] `<RUN_ID>.tar.gz` excludes `*.safetensors`/`*.bin` weights and any secret.
- [ ] `<RUN_ID>.tar.gz.sha256` verified locally after `scp`.
- [ ] Pod stopped/terminated only after the archive checksum verified locally.
