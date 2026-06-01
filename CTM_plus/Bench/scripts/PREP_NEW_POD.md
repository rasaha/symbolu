# Prepping a new GPU pod for the int4_protected benchmarks

Two scenarios. **Know which one you're in** — they differ by hours of work.

| Scenario | What survived | Effort |
|---|---|---|
| **A. Volume re-attached / migrated** (`/workspace` is there: venv + `dev/` + repo) | everything | minutes — verify, maybe rebuild kernels |
| **B. Fresh pod, NO volume** (empty `/workspace`) | nothing | ~30–60 min — full venv + kernel build from base |

Confirmed facts (from the repo + Phase 6L/6M findings): **Python 3.12**, venv at
`/workspace/venv-vllm`, **vLLM 0.7.3 (V0)**, model `Qwen/Qwen2.5-7B-Instruct`,
two custom kernels — the vendored `vllm-flash-attn-dev` fork at
`/workspace/dev/vllm-flash-attn-dev` and `int4_protected_C` in
`CTM_plus/CUDA_int4_protected/`. A100 = `sm_80`; H100/H200 = `sm_90`.

---

## Scenario A — volume came along (the common case)

This is you after a migrate/re-attach. The venv (7G) and `dev/` build tree (3.9G)
are on the volume, so you do **not** rebuild from scratch — you verify, and only
rebuild the kernels **if the GPU architecture or driver changed**.

```bash
source /workspace/venv-vllm/bin/activate
bash CTM_plus/Bench/scripts/preflight_gpu_pod.sh
```

The preflight checks every layer (GPU → torch → vLLM → flash-attn → int4 kernel →
model) and prints GREEN / REBUILD per layer. Then:

- **All GREEN** → you're ready. Run the final correctness gate, then benchmark:
  ```bash
  bash CTM_plus/Bench/scripts/verify_phase6e_byte_eq.sh --cuda   # expect PASS
  ```
- **Any REBUILD** (e.g. you moved A100→H100 so the `sm_80` `.so` won't load on
  `sm_90`, or `int4_protected_C` import fails) → rebuild the kernels on THIS pod:
  ```bash
  bash CTM_plus/Bench/scripts/preflight_gpu_pod.sh --rebuild
  # (this calls rebuild_all_kernels.sh --clean --verify-source under the hood)
  ```
- **Model not cached** (you deleted Qwen-7B to slim the migration) → fetch it
  (set your token first; keep it OUT of committed files/logs):
  ```bash
  export HF_TOKEN=hf_xxxx
  bash CTM_plus/Bench/scripts/preflight_gpu_pod.sh --fetch-model
  ```

**Same-arch A100→A100:** the compiled kernels usually load as-is — no rebuild,
just verify. **Cross-arch (A100→H100/H200): a rebuild is mandatory** (cubins are
arch-specific).

---

## Scenario B — fresh pod, no volume (full build from base)

Only if `/workspace` is empty (no venv). Order matters; the gotchas below are the
ones that actually bite.

```bash
# 0. system + repo
apt-get update && apt-get install -y build-essential git python3.12-venv unzip
cd /workspace
git clone https://github.com/rasaha/symbolu.git
cd symbolu
git checkout claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF   # or your working branch

# 1. venv with the pod's Python 3.12
python3.12 -m venv /workspace/venv-vllm
source /workspace/venv-vllm/bin/activate
pip install --upgrade pip

# 2. base runtime — torch matched to the pod's CUDA, then vLLM 0.7.3
#    (cu121 wheels work on CUDA 12.x A100/H100 pods)
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install vllm==0.7.3
pip install transformers accelerate huggingface_hub numpy tqdm

# 3. the CTM+ python packages (editable)
pip install -e CTM_plus/KVPolicy/
#   (DeepSpeed/KVSimulator only if you need them; the int4 bench doesn't)

# 4. get the flash-attn fork source onto the pod.
#    The repo keeps a tarball of it at the volume root on the old pod:
#      /workspace/vllm-flash-attn-dev-src.tar.gz  (122M)
#    On a truly fresh pod you must bring that tarball (scp/HF/git-LFS) to
#    /workspace/, then:
mkdir -p /workspace/dev && cd /workspace/dev
tar xzf /workspace/vllm-flash-attn-dev-src.tar.gz    # -> /workspace/dev/vllm-flash-attn-dev
cd /workspace/symbolu

# 5. build BOTH custom kernels (patch + build + copy-over-vendored + import check)
bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh --clean --verify-source

# 6. model
export HF_HOME=/workspace/.cache/huggingface
export HF_TOKEN=hf_xxxx          # keep out of committed files
huggingface-cli download Qwen/Qwen2.5-7B-Instruct --exclude "*.pth" "original/*"

# 7. verify
bash CTM_plus/Bench/scripts/preflight_gpu_pod.sh
bash CTM_plus/Bench/scripts/verify_phase6e_byte_eq.sh --cuda
```

> ⚠ If you don't have the `vllm-flash-attn-dev-src.tar.gz` tarball or the `dev/`
> tree, the fork source is not in the GitHub repo — it's a vendored working copy
> on the volume. **Preserve that tarball.** Rebuilding the fork from upstream +
> re-applying the Phase 6K patch is possible but not documented here. This is the
> #1 reason to prefer **re-attaching the volume over a fresh pod.**

---

## The gotchas (true for both scenarios)

1. **`--no-build-isolation` is mandatory — but NOT sufficient.** Without it pip
   downloads the latest torch and the build breaks. **BUT** even with it, the
   kernel `setup.py`/`pyproject` declare a `torch` dependency, so `pip install
   -e .` can still silently **downgrade/swap your torch** (observed live:
   2.5.1 → 2.4.0, which breaks vLLM 0.7.3). The real guard is **also passing
   `--no-deps`**:
   ```bash
   pip install --no-build-isolation --no-deps -e .
   ```
   `rebuild_all_kernels.sh` now does this AND restores torch if a build clobbers
   it. If torch ever ends up wrong, fix with:
   ```bash
   pip install --no-deps --force-reinstall torch==2.5.1 \
       --index-url https://download.pytorch.org/whl/cu121
   python -c "import torch; print(torch.__version__)"   # must read 2.5.1+cu121
   ```
2. **`import torch` BEFORE `import int4_protected_C`** — the `.so` needs
   libc10/libtorch loaded first, else `libc10.so: cannot open shared object file`.
   (The dispatch wrapper handles this in the real code; matters for manual checks.)
3. **vLLM vendors flash-attn.** The fork's built wheel must be copied OVER
   `site-packages/vllm/vllm_flash_attn/` — it is NOT a normal pip package.
   `install_dev_vllm_flash_attn.sh` (called by the rebuild) does this; a backup of
   the original vendored copy lives at
   `/workspace/dev/build-logs/vllm_flash_attn_vendored_backup`.
4. **Kernels are arch-specific.** A100 `sm_80` binaries won't run on H100/H200
   `sm_90`. Cross-arch move ⇒ always `--rebuild`.
5. **`libcuda.so.1: cannot open shared object file` / "UnspecifiedPlatform"** =
   no GPU/driver attached (you'll see this on a CPU pod). Not a build problem —
   the code falls back to Python; no benchmark runs until a GPU is present.
6. **Cache on the volume, not container disk.** Set
   `HF_HOME=/workspace/.cache/huggingface` so a re-download persists across the
   next migration; otherwise it lands on ephemeral disk and vanishes.

## After preflight is GREEN — what to run

- **Test 1 (roofline, the gate):** `bash CTM_plus/Bench/scripts/roofline_ncu_runner.sh`
  on an **ncu-unlocked** pod (runs the §9 unlock probe first).
- **Test 2 (hardware):** `bash CTM_plus/Bench/scripts/hardware_test_runner.sh`.
- **Test 3 prep:** see `PHASE_6F_PREP_RUNBOOK.md` (gated; don't start the kernel
  without Test 1's verdict + go-ahead).
