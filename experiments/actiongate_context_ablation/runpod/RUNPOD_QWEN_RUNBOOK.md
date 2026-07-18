# RUNPOD_QWEN_RUNBOOK

End-to-end commands to run the frozen ActionGate Context Minimization benchmark on
RunPod with Qwen2.5-7B. Copy-paste in order. Replace `<POD_IP>`, `<PORT>`,
`<POD_ID>`, and the repo URL with your values.

> The repository remote in this workspace is `rasaha/symbolu` (read via
> `git remote -v`). On RunPod, clone the GitHub HTTPS URL below, or substitute your
> own fork/remote if different. Do not invent a different repo.

Branch: **`claude/token-compression-enterprise-0koy0r`**

---

## 1. Select a RunPod GPU / template
Console → Deploy → pick a **CUDA 12.1** Ubuntu template (e.g. "RunPod PyTorch 2.4")
with **1× NVIDIA GPU, ≥24 GB VRAM** (RTX 4090 24 GB, A5000 24 GB, L4 24 GB, or
A100 40/80 GB) and a **persistent volume ≥ 60 GB mounted at `/workspace`**.
CLI alternative (if `runpodctl` is configured locally):
```bash
runpodctl create pod --name actiongate-qwen --gpuType "NVIDIA GeForce RTX 4090" \
  --gpuCount 1 --volumeSize 60 --volumePath /workspace --imageName runpod/pytorch:2.4.0-py3.11-cuda12.1.1-devel-ubuntu22.04
```

## 2. Connect over SSH
Use the exact SSH command from the pod's Connect panel, e.g.:
```bash
ssh root@<POD_IP> -p <PORT> -i ~/.ssh/id_ed25519
```

## 3. Clone the repository
```bash
git clone https://github.com/rasaha/symbolu.git /workspace/symbolu
```

## 4. Check out the branch
```bash
cd /workspace/symbolu && git checkout claude/token-compression-enterprise-0koy0r && git rev-parse HEAD
```

## 5. (Optional) set the Hugging Face token
Only needed for gated repos or higher rate limits. Never printed or persisted.
```bash
export HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx
```

## 6. Set up the environment
```bash
cd /workspace/symbolu/experiments/actiongate_context_ablation/runpod
bash setup_runpod.sh
```

## 7. Download the smoke model
```bash
MODEL_ID=Qwen/Qwen2.5-0.5B-Instruct python3 download_model.py
```

## 8. Run the smoke test (real 0.5B; fails if mock)
```bash
bash smoke_qwen.sh
```

## 9. Download the 7B primary model
```bash
MODEL_ID=Qwen/Qwen2.5-7B-Instruct python3 download_model.py
```

## 10. Run the primary benchmark
```bash
bash run_qwen_primary.sh
```
Optional stress budgets:
```bash
BUDGETS=0.2,0.3,0.4,0.5,0.6 RUN_ID=primary_qwen7b_stress bash run_qwen_matrix.sh
```

## 11. Resume after interruption
```bash
RUN_ID=primary_qwen7b bash resume_qwen_run.sh
```

## 12. Collect results
```bash
RUN_ID=primary_qwen7b bash collect_results.sh
```

## 13. Verify results
```bash
RUN_ID=primary_qwen7b python3 verify_results.py
```

## 14. Copy the result archive off the pod (run LOCALLY)
```bash
scp -P <PORT> root@<POD_IP>:/workspace/results/actiongate-context-qwen/primary_qwen7b.tar.gz ./
scp -P <PORT> root@<POD_IP>:/workspace/results/actiongate-context-qwen/primary_qwen7b.tar.gz.sha256 ./
shasum -a 256 -c primary_qwen7b.tar.gz.sha256    # confirm integrity BEFORE deleting the pod
```

## 15. Stop / delete the pod (only after the archive is copied + verified)
```bash
runpodctl stop pod <POD_ID>       # stop (keeps volume, billable storage)
runpodctl remove pod <POD_ID>     # delete permanently
```
Or use the console Stop/Terminate buttons. Confirm your `.tar.gz` checksum matches
locally first.

---

## Expected wall-clock (rough, 1× 24 GB GPU)
- 7B load: ~1–2 min. Primary run (77 contexts × 4 methods × ~8 tasks × {20,30,40}%
  ≈ a few thousand short greedy generations at 64 new tokens): roughly **1–3 hours**
  depending on GPU. The run is durable and resumable, so interruptions are safe.

## Expected outputs
`/workspace/results/actiongate-context-qwen/primary_qwen7b/` with
`records.jsonl, run_config.json, environment_probe.json, verify_report.json,
results.json, results.csv, REAL_LLM_RESULTS.md, plots/, run_manifest.json,
SHA256SUMS`, and `../primary_qwen7b.tar.gz (+ .sha256)`.
