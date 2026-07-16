# K0 — reproducible build of the production INT4 decode kernel (fresh A100 pod)

> **Goal (milestone K0):** stand up the exact toolchain, build the INT4-patched `vllm_flash_attn`
> wheel + `int4_protected_C`, install, and pass the import + hash + A100 smoke gates — so we have the
> *recovered production kernel* running before any optimization. **This is a build, not a kernel change.**
> Orchestrates the repo's proven scripts (`rebuild_all_kernels.sh`, `install_dev_vllm_flash_attn.sh`,
> `smoke_test_fa_install.sh`) — do not hand-roll the kernel build.

**Provenance (frozen):** base = `github.com/vllm-project/flash-attention` @ `720c94869cf2e0ff5a706e9c7f1dce0939686ade`
(`720c948`); INT4 = additive in-repo patches; stack = **vLLM 0.7.3 · torch 2.5.1 · Python 3.12 · sm_80**.
Full detail in `kernel_provenance.json`. Time ~30–60 min; disk ~40–60 GB.

---

## Step 0 — confirm the fresh-pod state

```bash
cd /workspace/symbolu && git pull origin claude/kvpro-v2-tier1-d8b4ae
nvidia-smi -L                       # must be A100 (sm_80). H100/H200 => rebuild is mandatory anyway.
ls /workspace                       # fresh pod: only `symbolu` (no venv-vllm, no dev/)
python3.12 --version || echo "need python3.12"
df -h /workspace                    # need ~40-60 GB free
```

## Step 1 — system + venv + pinned stack

```bash
apt-get update && apt-get install -y build-essential git python3.12-venv unzip ninja-build
python3.12 -m venv /workspace/venv-vllm
source /workspace/venv-vllm/bin/activate
pip install --upgrade pip wheel setuptools packaging
# base runtime — the pins that MUST hold (a wrong stack builds but imports garbage):
pip install --no-deps --force-reinstall torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121
pip install vllm==0.7.3
pip install transformers accelerate huggingface_hub numpy tqdm ninja cmake pybind11
pip install -e CTM_plus/KVPolicy/          # the CTM+ python packages (backend install lives here)
```
> The measured GREEN build used torch **2.5.1+cu124** + CUDA toolkit **12.8**; `rebuild_all_kernels.sh`
> defaults to the **cu121** torch wheel. Both load on a CUDA-12.x A100. If you hit an ABI/symbol error at
> import, re-pin torch to `+cu124` (`--index-url .../whl/cu124`) to match the recorded build exactly.

## Step 2 — get the INT4-patched fork source onto the pod

**Path A — you have the tarball (preferred; exact byte-for-byte source).**
```bash
# bring vllm-flash-attn-dev-src.tar.gz (~122 MB) to /workspace/ (scp / HF / git-LFS from your archive)
mkdir -p /workspace/dev && cd /workspace/dev
tar xzf /workspace/vllm-flash-attn-dev-src.tar.gz     # -> /workspace/dev/vllm-flash-attn-dev (already patched)
```

**Path B — reconstruct from base (no tarball): clone @ 720c948 + apply the in-repo patches IN ORDER.**
```bash
mkdir -p /workspace/dev && cd /workspace/dev
git clone https://github.com/vllm-project/flash-attention vllm-flash-attn-dev
git -C vllm-flash-attn-dev checkout 720c94869cf2e0ff5a706e9c7f1dce0939686ade
git -C vllm-flash-attn-dev log -1 --oneline          # must show 720c948
# back up vLLM's vendored copy FIRST (install/restore depend on it):
mkdir -p /workspace/dev/build-logs
cp -r "$(python -c 'import os,vllm.vllm_flash_attn as m;print(os.path.dirname(m.__file__))')" \
      /workspace/dev/build-logs/vllm_flash_attn_vendored_backup
cd /workspace/symbolu
for p in apply_phase1 apply_phase2_1 apply_phase2_2 apply_phase2_3 apply_phase2_5 \
         apply_phase3 apply_phase4 apply_phase2_4_1a; do          # canonical order (idempotent)
    bash CTM_plus/Bench/scripts/$p.sh || { echo "FAILED at $p"; break; }
done
```

## Step 3 — build + install both kernels (the canonical builder)

```bash
cd /workspace/symbolu
# builds vllm-flash-attn-dev (the decode kernel) + int4_protected_C (the writer), installs, and
# --verify-source asserts the patched source matches the installed .so. MAX_JOBS auto-sizes from RAM;
# pin it (e.g. MAX_JOBS=8) on a RAM-tight pod.
TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16 NVCC_THREADS=2 \
    bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh --clean --verify-source
# (rebuild logs land in /workspace/dev/build-logs/ — read THOSE on failure; console shows only the tail.)
```

## Step 4 — K0 gates (all must pass before K1)

```bash
export PYBIN=/workspace/venv-vllm/bin/python3
# (a) import gate — the op must exist:
$PYBIN -c "import torch, vllm.vllm_flash_attn as m; \
  print('wrapper', hasattr(m,'flash_attn_with_int4_kvcache')); \
  print('op', hasattr(torch.ops._vllm_fa2_C,'fwd_kvcache_int4'))"     # both True
# (b) hash manifest — pin the exact installed binary:
$PYBIN scripts/kvpro_kernel_recovery/02_hash_installed_kernel.py
# (c) A100 smoke — vs the RUNBOOK baselines (FA p50@16k +/-10%, Cell A@32k +/-5%):
bash CTM_plus/Bench/scripts/smoke_test_fa_install.sh
# (d) contract validator (CPU, any env):
$PYBIN scripts/kvpro_kernel_recovery/test_contract_cpu.py            # 16/16
# (e) record the recovery verdict (now SOURCE_RECOVERED_EXACT once the op imports):
bash scripts/kvpro_kernel_recovery/run_recovery_audit.sh
git add -f scripts/kvpro_kernel_recovery/runs/*.json
```

**K0 GREEN =** import True/True · hash recorded · smoke within ±10%/±5% · contract 16/16 · verdict
`SOURCE_RECOVERED_EXACT`. Only then proceed to K1 (numerical contract). If smoke crashes, run
`restore_vendored_vllm_flash_attn.sh` and inspect the build log before retrying.

## Convenience orchestrator

`k0_build.sh` chains Steps 1→4 for a fresh pod (idempotent checks; delegates the kernel build to
`rebuild_all_kernels.sh`; runs the gates; writes `runs/k0_build_status.json`). Use it, or run the steps
by hand if you want to watch each phase:
```bash
FA_TARBALL=/workspace/vllm-flash-attn-dev-src.tar.gz \
    bash scripts/kvpro_kernel_recovery/k0_build.sh            # Path A (tarball) if present, else prints Path B
```

## Reminder (why we're doing this)

K0 only *recovers* the kernel. The optimization it unlocks (`OPTIMIZE_RECOVERED_PRODUCTION_KERNEL` — fuse
the ~15% gather + ~6% copy into the kernel's existing paged path) has an **honest ceiling ~16–19% aggregate;
a net loss vs bf16 remains** (GEMMs ~66% + inherent INT4 reconstruction untouched). If the ~hour build +
bounded upside isn't worth it, the strategic forks (`PIVOT_TO_INT8_KV`, `POSITION_INT4_AS_CAPACITY_ONLY`)
stay open. No modeled number is a measured TPS.
