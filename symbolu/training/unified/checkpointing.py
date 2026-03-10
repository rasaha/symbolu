"""
Checkpoint save/load utilities with split-file format support.

Handles both single-file (legacy) and split-file checkpoint formats
to avoid NFS write limits (~2GB/file).

Extracted from train_unified_llm.py
"""

import os
import pickle
from pathlib import Path
from typing import Optional, Dict, Any

import torch
import torch.nn as nn


def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler._LRScheduler,
    step: int,
    best_val_loss: float,
    path: Path,
    hgs_state: Optional[dict] = None,
    drc_state: Optional[dict] = None,
    sgp_state: Optional[dict] = None,
    sattvic_state: Optional[dict] = None,
    srk_state: Optional[dict] = None,
    scaler_state: Optional[dict] = None,
    # V9.8.6: Three-Phase Curriculum states
    csr_curriculum_state: Optional[dict] = None,
    kosha_curriculum_state: Optional[dict] = None,
    onto_curriculum_state: Optional[dict] = None,
    pidv2_curriculum_state: Optional[dict] = None,
    # V9.8.6: Kosha Gyroscope state (InvertedCurriculumController)
    kosha_gyroscope_state: Optional[dict] = None,
    # V9.8.6: EvoFlow state (EvolutionaryIntelligenceEngine)
    evoflow_state: Optional[dict] = None,
    # Kosha-Vritti Supervision state
    kv_supervisor_state: Optional[dict] = None,
    # Appendix G Phase 4: JEPA injection projector state
    jepa_injection_projector_state: Optional[dict] = None,
    # Dataloader position
    dataloader_position: Optional[dict] = None,
):
    """Save training checkpoint with optional HGS/DRC/SGP/Sattvic/SRK/AMP scaler state.

    Uses split-file format to avoid network filesystem (RunPod MFS/FUSE) write
    limits (~2GB per file). Saves four files:
      {stem}_model.pt  - model state_dict
      {stem}_optim.pt  - optimizer state_dict
      {stem}_meta.pt   - scheduler, step, RNG states, lightweight controller states
      {stem}_aux.pt    - heavy auxiliary module weights (SRK, EvoFlow, KV, JEPA proj)

    V9.9.1: Split heavy nn.Module state_dicts out of meta into aux file.
    Previously meta was ~959MB because SRK (8 modules), EvoFlow (12 gates),
    KV supervisor, and JEPA projector weights were all stuffed into it.
    Now meta is <1MB (scalars, scheduler, RNG) and aux holds the module weights.

    For backwards compatibility, load_checkpoint handles both formats and
    also loads from old meta files that contain the heavy states.
    """
    stem = path.parent / path.stem  # e.g. checkpoints_unified/best

    model_path = Path(f"{stem}_model.pt")
    optim_path = Path(f"{stem}_optim.pt")
    meta_path = Path(f"{stem}_meta.pt")
    aux_path = Path(f"{stem}_aux.pt")

    # Build metadata dict (LIGHTWEIGHT — scalars, scheduler, RNG only)
    meta = {
        "split_format": True,  # Sentinel for load_checkpoint
        "has_aux_file": True,  # V9.9.1: Sentinel for aux file
        "scheduler": scheduler.state_dict(),
        "step": step,
        "best_val_loss": best_val_loss,
        "rng_state": torch.get_rng_state(),
    }

    # Add CUDA RNG state if available
    if torch.cuda.is_available():
        meta["cuda_rng_state"] = torch.cuda.get_rng_state()

    # Add LIGHTWEIGHT auxiliary controller states (scalars, small dicts) to meta
    if hgs_state is not None:
        meta["hgs_state"] = hgs_state
    if drc_state is not None:
        meta["drc_state"] = drc_state
    if sgp_state is not None:
        meta["sgp_state"] = sgp_state
    if sattvic_state is not None:
        meta["sattvic_state"] = sattvic_state
    if scaler_state is not None:
        meta["scaler_state"] = scaler_state
    if csr_curriculum_state is not None:
        meta["csr_curriculum_state"] = csr_curriculum_state
    if kosha_curriculum_state is not None:
        meta["kosha_curriculum_state"] = kosha_curriculum_state
    if onto_curriculum_state is not None:
        meta["onto_curriculum_state"] = onto_curriculum_state
    if pidv2_curriculum_state is not None:
        meta["pidv2_curriculum_state"] = pidv2_curriculum_state
    if kosha_gyroscope_state is not None:
        meta["kosha_gyroscope_state"] = kosha_gyroscope_state
    if dataloader_position is not None:
        meta["dataloader_position"] = dataloader_position

    # V9.9.1: Build HEAVY auxiliary module weights dict (saved separately)
    # These contain nn.Module state_dicts that were bloating meta to ~959MB
    aux = {}
    if srk_state is not None:
        aux["srk_state"] = srk_state
    if evoflow_state is not None:
        aux["evoflow_state"] = evoflow_state
    if kv_supervisor_state is not None:
        aux["kv_supervisor_state"] = kv_supervisor_state
    if jepa_injection_projector_state is not None:
        aux["jepa_injection_projector_state"] = jepa_injection_projector_state

    # Atomic save: write to temp files first, then rename into place.
    # This prevents checkpoint corruption if training crashes mid-save.
    # Previously, files were deleted before writing — any crash between
    # delete and write completion would destroy the best checkpoint.
    tmp_suffix = ".tmp"
    tmp_model = Path(f"{model_path}{tmp_suffix}")
    tmp_optim = Path(f"{optim_path}{tmp_suffix}")
    tmp_meta = Path(f"{meta_path}{tmp_suffix}")
    tmp_aux = Path(f"{aux_path}{tmp_suffix}")

    # Clean up stale temp files from a previously interrupted save
    for tmp in [tmp_model, tmp_optim, tmp_meta, tmp_aux]:
        if tmp.exists():
            tmp.unlink()

    # Write all data to temp files (old checkpoint untouched during this phase)
    torch.save(model.state_dict(), tmp_model)
    torch.save(optimizer.state_dict(), tmp_optim)
    torch.save(meta, tmp_meta)
    if aux:
        torch.save(aux, tmp_aux)

    # Atomically replace old files with new ones (os.replace is atomic on POSIX).
    # Rename meta LAST — it's the file that carries step/best_val_loss, so if we
    # crash mid-rename the worst case is stale metadata with fresh weights, which
    # load_checkpoint can detect and handle.
    os.replace(tmp_model, model_path)
    os.replace(tmp_optim, optim_path)
    if aux:
        os.replace(tmp_aux, aux_path)
    elif aux_path.exists():
        # No aux data this save but old aux file exists — remove it
        aux_path.unlink()
    os.replace(tmp_meta, meta_path)

    # Clean up legacy single-file format if it still exists
    if path.exists() and path != model_path:
        path.unlink()


def load_checkpoint(
    path: Path,
    model: nn.Module,
    optimizer: Optional[torch.optim.Optimizer] = None,
    scheduler: Optional[torch.optim.lr_scheduler._LRScheduler] = None,
    weights_only: bool = False,
    device: torch.device = None,
) -> Dict[str, Any]:
    """Load training checkpoint.

    Handles both single-file format (legacy) and split-file format:
      {stem}_model.pt + {stem}_optim.pt + {stem}_meta.pt

    Args:
        path: Path to checkpoint file (e.g. checkpoints_unified/best.pt)
        model: Model to load weights into
        optimizer: Optimizer to restore state (None if weights_only)
        scheduler: Scheduler to restore state (None if weights_only)
        weights_only: If True, only load model weights (fresh optimizer/scheduler)
        device: Device to map tensors to

    Returns:
        Dict with checkpoint info (step, best_val_loss, etc.)
    """
    # Detect split-file format: check for {stem}_model.pt
    stem = path.parent / path.stem
    model_path = Path(f"{stem}_model.pt")
    optim_path = Path(f"{stem}_optim.pt")
    meta_path = Path(f"{stem}_meta.pt")
    aux_path = Path(f"{stem}_aux.pt")
    use_split = model_path.exists()

    if not use_split and not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path} (also checked split format at {model_path})")

    # Validate split checkpoint completeness — catch partially-written saves
    if use_split and not meta_path.exists():
        # model_path exists but meta_path doesn't: save was interrupted mid-rename.
        # Stale temp files may be present; refuse to load an incomplete checkpoint.
        raise RuntimeError(
            f"Incomplete split checkpoint: {model_path} exists but {meta_path} is missing. "
            f"This typically means a save was interrupted. "
            f"Delete the partial files and resume from last.pt or an earlier checkpoint."
        )

    if use_split:
        print(f"\n  \U0001f4c2 Loading split checkpoint from: {stem}_*.pt")
    else:
        print(f"\n  \U0001f4c2 Loading checkpoint from: {path}")

    # Load checkpoint with error handling for corrupted files
    try:
        if use_split:
            # Split format: load model state separately
            model_state_raw = torch.load(model_path, map_location=device, weights_only=False)
            checkpoint = torch.load(meta_path, map_location=device, weights_only=False)
            checkpoint["model"] = model_state_raw
            # V9.9.1: Load aux file (heavy module weights) if present
            if aux_path.exists():
                aux_data = torch.load(aux_path, map_location=device, weights_only=False)
                checkpoint.update(aux_data)
                del aux_data
                print(f"    \u2713 Auxiliary module weights loaded (from {aux_path.name})")
            # Optimizer loaded on-demand below (only if needed)
        else:
            checkpoint = torch.load(path, map_location=device, weights_only=False)
    except (EOFError, pickle.UnpicklingError, RuntimeError, FileNotFoundError) as e:
        # Checkpoint file is corrupted, incomplete, or partially missing
        ckpt_loc = f"{stem}_*.pt" if use_split else str(path)
        print(f"\n  \u26a0\ufe0f  ERROR: Checkpoint file is corrupted or incomplete: {ckpt_loc}")
        print(f"      Error: {type(e).__name__}: {e}")
        print(f"      This typically happens if training was interrupted during checkpoint save.")
        print(f"\n  Solutions:")
        print(f"      1. Delete the corrupted checkpoint: rm {ckpt_loc}")
        print(f"      2. Use a different checkpoint: --resume <path_to_valid_checkpoint>")
        print(f"      3. Start from scratch: remove --resume flag")
        raise RuntimeError(f"Cannot load corrupted checkpoint: {ckpt_loc}") from e

    # Load model weights
    # Filter out runtime buffers that may have been saved with tensor values
    # but are initialized as None in fresh models (e.g., prev_state in OntologicalHybridTransformer)
    model_state = checkpoint["model"]
    runtime_buffers = ["prev_state"]  # Buffers that are runtime state, not trained weights
    filtered_state = {k: v for k, v in model_state.items() if k not in runtime_buffers}
    if len(filtered_state) < len(model_state):
        removed = [k for k in model_state if k in runtime_buffers]
        print(f"    \u2192 Filtered runtime buffers: {removed}")

    # V9.6.8: Handle old state_projector (nn.Sequential) -> new SovereignStateProjector
    # Old unconstrained weights produce extreme values that saturate softmax.
    # Drop them entirely so SovereignStateProjector initializes with small weights.
    migrated = False
    old_projector_keys = [k for k in filtered_state if k.startswith("state_projector.") and ".projector." not in k and "layer_norm" not in k]
    if old_projector_keys:
        migrated = True
        print(f"    \u2192 Detected old state_projector format (unconstrained nn.Sequential)")
        print(f"    \u2192 Dropping old weights to allow fresh SovereignStateProjector init")
        for old_key in old_projector_keys:
            del filtered_state[old_key]
            print(f"      Dropped: {old_key}")
        print(f"    \u2713 state_projector will initialize fresh with proper normalization")

    # V12.7: Extract slot_memory._adaptive.* keys before load_state_dict.
    # PyTorch's model.load_state_dict() uses _load_from_state_dict() internally
    # and does NOT call child module load_state_dict() overrides. So the
    # SlotMemoryGCT.load_state_dict() pre-processing (adaptive key extraction)
    # and post-processing (scale overrides) never run. Handle them here.
    _slot_adaptive_vals = {}
    _slot_adaptive_keys = [k for k in filtered_state if '._adaptive.' in k]
    for k in _slot_adaptive_keys:
        # e.g. "slot_memory._adaptive._gate_ceiling" → "_gate_ceiling"
        attr_name = k.split('._adaptive.', 1)[1]
        _slot_adaptive_vals[attr_name] = filtered_state.pop(k)

    model.load_state_dict(filtered_state, strict=False)
    print(f"    \u2713 Model weights loaded")

    # V12.7: Restore slot memory adaptive values and apply post-load overrides
    if hasattr(model, 'slot_memory') and model.slot_memory is not None:
        model.slot_memory._restore_adaptive_values(_slot_adaptive_vals)
        model.slot_memory.apply_checkpoint_overrides()

    result = {
        "step": checkpoint.get("step", 0),
        "best_val_loss": checkpoint.get("best_val_loss", float('inf')),
    }

    if weights_only:
        print(f"    \u2192 Weights-only mode: Optimizer/Scheduler will start fresh")
        result["step"] = 0  # Start from step 0 with fresh optimizer
        return result

    # Skip optimizer/scheduler restore if architecture was migrated (param groups don't match)
    if migrated:
        print(f"    \u2192 Architecture migrated: Optimizer/Scheduler will start fresh")
        return result

    # Restore optimizer state
    if optimizer is not None:
        try:
            if use_split and optim_path.exists():
                optim_state = torch.load(optim_path, map_location=device, weights_only=False)
                optimizer.load_state_dict(optim_state)
                del optim_state  # Free memory immediately
                print(f"    \u2713 Optimizer state restored (from split file)")
            elif "optimizer" in checkpoint:
                optimizer.load_state_dict(checkpoint["optimizer"])
                print(f"    \u2713 Optimizer state restored")
        except ValueError as e:
            if "parameter group" in str(e):
                print(f"    \u26a0 Optimizer param groups changed (e.g. new slot params): starting optimizer fresh")
            else:
                raise

    # Restore scheduler state
    if scheduler is not None and "scheduler" in checkpoint:
        scheduler.load_state_dict(checkpoint["scheduler"])
        print(f"    \u2713 Scheduler state restored")

    # Restore RNG states for reproducibility
    if "rng_state" in checkpoint:
        try:
            rng_state = checkpoint["rng_state"]
            # Ensure RNG state is ByteTensor on CPU
            if not isinstance(rng_state, torch.ByteTensor):
                rng_state = rng_state.to(dtype=torch.uint8, device='cpu')
            torch.set_rng_state(rng_state)
            print(f"    \u2713 RNG state restored")
        except Exception as e:
            print(f"    \u26a0 RNG state restoration failed: {e} (continuing without)")

    if "cuda_rng_state" in checkpoint and torch.cuda.is_available():
        try:
            cuda_rng_state = checkpoint["cuda_rng_state"]
            # Ensure CUDA RNG state is ByteTensor
            if not isinstance(cuda_rng_state, torch.ByteTensor):
                cuda_rng_state = cuda_rng_state.to(dtype=torch.uint8)
            torch.cuda.set_rng_state(cuda_rng_state)
            print(f"    \u2713 CUDA RNG state restored")
        except Exception as e:
            print(f"    \u26a0 CUDA RNG state restoration failed: {e} (continuing without)")

    # Return additional state for HGS/DRC restoration
    if "hgs_state" in checkpoint:
        result["hgs_state"] = checkpoint["hgs_state"]
        print(f"    \u2713 HGS state available for restoration")

    if "drc_state" in checkpoint:
        result["drc_state"] = checkpoint["drc_state"]
        print(f"    \u2713 DRC state available for restoration")

    # Return SGP state for restoration
    if "sgp_state" in checkpoint:
        result["sgp_state"] = checkpoint["sgp_state"]
        print(f"    \u2713 SGP state available for restoration")

    # Return Sattvic Controller state for restoration
    if "sattvic_state" in checkpoint:
        result["sattvic_state"] = checkpoint["sattvic_state"]
        print(f"    \u2713 Sattvic Controller state available for restoration")

    # V9.8.0: Return SRK state for restoration
    if "srk_state" in checkpoint:
        result["srk_state"] = checkpoint["srk_state"]
        print(f"    \u2713 SRK state available for restoration")

    # V9.8.1: Return AMP GradScaler state for restoration
    if "scaler_state" in checkpoint:
        result["scaler_state"] = checkpoint["scaler_state"]
        print(f"    \u2713 AMP GradScaler state available for restoration")

    # V9.8.6: Return Three-Phase Curriculum states for restoration
    if "csr_curriculum_state" in checkpoint:
        result["csr_curriculum_state"] = checkpoint["csr_curriculum_state"]
        print(f"    \u2713 CSR Curriculum state available for restoration")
    if "kosha_curriculum_state" in checkpoint:
        result["kosha_curriculum_state"] = checkpoint["kosha_curriculum_state"]
        print(f"    \u2713 Kosha Curriculum state available for restoration")
    if "onto_curriculum_state" in checkpoint:
        result["onto_curriculum_state"] = checkpoint["onto_curriculum_state"]
        print(f"    \u2713 Onto Curriculum state available for restoration")
    if "pidv2_curriculum_state" in checkpoint:
        result["pidv2_curriculum_state"] = checkpoint["pidv2_curriculum_state"]
        print(f"    \u2713 PIDv2 Curriculum state available for restoration")
    # V9.8.6: Return Kosha Gyroscope state (InvertedCurriculumController)
    if "kosha_gyroscope_state" in checkpoint:
        result["kosha_gyroscope_state"] = checkpoint["kosha_gyroscope_state"]
        print(f"    \u2713 Kosha Gyroscope state available for restoration")
    # V9.8.6: Return EvoFlow state (EvolutionaryIntelligenceEngine)
    if "evoflow_state" in checkpoint:
        result["evoflow_state"] = checkpoint["evoflow_state"]
        print(f"    \u2713 EvoFlow state available for restoration")

    # KV Supervision state
    if "kv_supervisor_state" in checkpoint:
        result["kv_supervisor_state"] = checkpoint["kv_supervisor_state"]
        print(f"    \u2713 KV Supervision state available for restoration")

    # Appendix G Phase 4: JEPA injection projector state
    if "jepa_injection_projector_state" in checkpoint:
        result["jepa_injection_projector_state"] = checkpoint["jepa_injection_projector_state"]
        print(f"    \u2713 JEPA injection projector state available for restoration")

    # V9.8.6: Return dataloader position for restoration
    if "dataloader_position" in checkpoint:
        result["dataloader_position"] = checkpoint["dataloader_position"]
        print(f"    \u2713 Dataloader position available for restoration")

    print(f"    \u2192 Resuming from step {result['step']}, best_val_loss={result['best_val_loss']:.4f}")

    return result
