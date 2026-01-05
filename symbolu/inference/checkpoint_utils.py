"""
Checkpoint Utilities for Sovereign Inference
=============================================

Utilities for saving and loading model checkpoints with inference metadata.
Ensures the inference engine "remembers" the training context and can
auto-configure resonance, layer splits, and other parameters.

The checkpoint metadata includes:
- Authority/Sensory split configuration (9:3 or 6:6)
- Dynamic Relaxation Controller (DRC) state
- Recommended resonance alpha based on training phase
- sGP (Stochastic Gradient Projection) rate used during training

Training Reference:
    DynamicRelaxationController (train_unified_llm.py) manages state transitions:
    STATE_AUTHORITY (9:3) → STATE_BALANCED (6:6) → Evolution stages

Usage:
------
    from symbolu.inference import (
        save_sovereign_checkpoint,
        load_sovereign_config,
        InferenceConfig,
    )

    # Save with inference hints
    save_sovereign_checkpoint(
        model=model,
        drc_state="authority",
        evolution_stage=2,
        path="checkpoint.pt",
    )

    # Load and auto-configure
    config = load_sovereign_config("checkpoint.pt")
    print(f"Recommended alpha: {config.recommended_alpha}")
    print(f"Split: {config.authority_sensory_split}")
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import torch
import torch.nn as nn


@dataclass
class InferenceConfig:
    """
    Inference configuration extracted from checkpoint metadata.

    Contains all hints needed to auto-configure the InferenceManager
    based on the model's training state.

    Attributes:
        authority_sensory_split: Tuple of (authority_layers, sensory_layers)
        evolution_stage: Current evolution stage index from DRC
        recommended_alpha: Recommended resonance alpha for karma injection
        sgp_rate: Stochastic Gradient Projection rate used in training
        training_state: DRC state name ("authority", "balanced", etc.)
        checkpoint_version: Version of checkpoint format
    """
    authority_sensory_split: Tuple[int, int] = (9, 3)
    evolution_stage: int = 0
    recommended_alpha: float = 0.1
    sgp_rate: int = 25
    training_state: str = "authority"
    checkpoint_version: str = "2.0"

    # Optional extended metadata
    total_steps: int = 0
    final_loss: float = 0.0
    guna_balance: Tuple[float, float, float] = (0.33, 0.33, 0.34)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for checkpoint storage."""
        return {
            "authority_sensory_split": self.authority_sensory_split,
            "evolution_stage": self.evolution_stage,
            "recommended_alpha": self.recommended_alpha,
            "sgp_rate": self.sgp_rate,
            "training_state": self.training_state,
            "checkpoint_version": self.checkpoint_version,
            "total_steps": self.total_steps,
            "final_loss": self.final_loss,
            "guna_balance": self.guna_balance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InferenceConfig":
        """Create from dictionary (loaded from checkpoint)."""
        return cls(
            authority_sensory_split=tuple(data.get("authority_sensory_split", (9, 3))),
            evolution_stage=data.get("evolution_stage", 0),
            recommended_alpha=data.get("recommended_alpha", 0.1),
            sgp_rate=data.get("sgp_rate", 25),
            training_state=data.get("training_state", "authority"),
            checkpoint_version=data.get("checkpoint_version", "1.0"),
            total_steps=data.get("total_steps", 0),
            final_loss=data.get("final_loss", 0.0),
            guna_balance=tuple(data.get("guna_balance", (0.33, 0.33, 0.34))),
        )

    def get_layer_config_mode(self) -> str:
        """
        Determine layer configuration mode based on training state.

        Returns:
            "authority" for 9:3 split, "balanced" for 6:6 split
        """
        auth, sens = self.authority_sensory_split
        if auth == 9 and sens == 3:
            return "authority"
        elif auth == 6 and sens == 6:
            return "balanced"
        else:
            return "custom"


def save_sovereign_checkpoint(
    model: nn.Module,
    path: str,
    drc_state: str = "authority",
    evolution_stage: int = 0,
    recommended_alpha: Optional[float] = None,
    sgp_rate: int = 25,
    optimizer: Optional[Any] = None,
    scheduler: Optional[Any] = None,
    evolutionary_bridge: Optional[nn.Module] = None,
    csr_components: Optional[Dict[str, nn.Module]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Save model checkpoint with comprehensive inference metadata.

    This enhanced checkpoint format ensures the InferenceManager can
    auto-configure based on the model's specific training state.

    Args:
        model: The transformer model
        path: Path to save checkpoint
        drc_state: DRC state name ("authority", "balanced", "probe")
        evolution_stage: Current evolution stage index
        recommended_alpha: Resonance alpha (auto-computed if None)
        sgp_rate: sGP rate used during training
        optimizer: Optional optimizer state
        scheduler: Optional scheduler state
        evolutionary_bridge: Optional EvolutionaryBridge module
        csr_components: Optional dict of CSR components (entropy_sink, synthesis_gate)
        extra_metadata: Additional metadata to include

    Returns:
        Path where checkpoint was saved
    """
    # Determine split configuration based on DRC state
    if drc_state in ("authority", "locked"):
        authority_sensory_split = (9, 3)
    elif drc_state in ("balanced", "relaxed"):
        authority_sensory_split = (6, 6)
    elif drc_state == "probe":
        authority_sensory_split = (3, 9)  # Stress-probe inverted
    else:
        authority_sensory_split = (9, 3)  # Default

    # Auto-compute recommended alpha if not provided
    if recommended_alpha is None:
        if drc_state in ("authority", "locked"):
            recommended_alpha = 0.1
        elif drc_state in ("balanced", "relaxed"):
            recommended_alpha = 0.15
        else:
            recommended_alpha = 0.12

    # Build inference config
    inference_config = InferenceConfig(
        authority_sensory_split=authority_sensory_split,
        evolution_stage=evolution_stage,
        recommended_alpha=recommended_alpha,
        sgp_rate=sgp_rate,
        training_state=drc_state,
        checkpoint_version="2.0",
    )

    # Build checkpoint
    checkpoint = {
        "model": model.state_dict(),
        "inference_config": inference_config.to_dict(),
    }

    # Add optional components
    if optimizer is not None:
        checkpoint["optimizer"] = optimizer.state_dict()

    if scheduler is not None:
        checkpoint["scheduler"] = scheduler.state_dict()

    if evolutionary_bridge is not None:
        checkpoint["evolutionary_bridge"] = evolutionary_bridge.state_dict()

    if csr_components is not None:
        checkpoint["csr_components"] = {
            name: comp.state_dict()
            for name, comp in csr_components.items()
        }

    if extra_metadata is not None:
        checkpoint["metadata"] = extra_metadata

    # Save
    torch.save(checkpoint, path)
    return path


def load_sovereign_config(
    checkpoint_path: str,
    device: str = "cpu",
) -> InferenceConfig:
    """
    Load inference configuration from a checkpoint.

    Extracts the inference_config metadata to auto-configure
    the InferenceManager with correct parameters.

    Args:
        checkpoint_path: Path to checkpoint file
        device: Device for loading (default "cpu" for metadata only)

    Returns:
        InferenceConfig with training state hints
    """
    checkpoint = torch.load(checkpoint_path, map_location=device)

    if "inference_config" in checkpoint:
        return InferenceConfig.from_dict(checkpoint["inference_config"])

    # Fallback: try to infer from checkpoint structure
    return _infer_config_from_checkpoint(checkpoint)


def _infer_config_from_checkpoint(checkpoint: Dict[str, Any]) -> InferenceConfig:
    """
    Infer inference configuration from legacy checkpoint format.

    Attempts to detect training state from available checkpoint keys.

    Args:
        checkpoint: Loaded checkpoint dictionary

    Returns:
        Best-effort InferenceConfig
    """
    config = InferenceConfig()

    # Check for DRC state
    if "drc_state" in checkpoint:
        drc = checkpoint["drc_state"]
        config.training_state = drc.get("state", "authority")
        config.evolution_stage = drc.get("current_stage_idx", 0)

    # Check for evolutionary bridge (indicates karma training)
    if "evolutionary_bridge" in checkpoint:
        # Presence of bridge suggests full training
        config.recommended_alpha = 0.12

    # Check for metadata
    if "metadata" in checkpoint:
        meta = checkpoint["metadata"]
        if "total_steps" in meta:
            config.total_steps = meta["total_steps"]
        if "final_loss" in meta:
            config.final_loss = meta["final_loss"]

    return config


def load_model_with_config(
    checkpoint_path: str,
    model: nn.Module,
    device: str = "cuda",
    strict: bool = True,
) -> Tuple[nn.Module, InferenceConfig]:
    """
    Load model weights and extract inference configuration.

    Convenience function that loads model state and returns
    the inference config for InferenceManager setup.

    Args:
        checkpoint_path: Path to checkpoint file
        model: Model instance to load weights into
        device: Device to load model onto
        strict: Whether to require exact key matching

    Returns:
        (model, InferenceConfig) tuple
    """
    checkpoint = torch.load(checkpoint_path, map_location=device)

    # Load model weights
    if "model" in checkpoint:
        model.load_state_dict(checkpoint["model"], strict=strict)
    else:
        # Try loading directly (old format)
        model.load_state_dict(checkpoint, strict=strict)

    model = model.to(device)

    # Extract config
    if "inference_config" in checkpoint:
        config = InferenceConfig.from_dict(checkpoint["inference_config"])
    else:
        config = _infer_config_from_checkpoint(checkpoint)

    return model, config


def get_checkpoint_info(checkpoint_path: str) -> Dict[str, Any]:
    """
    Get summary information about a checkpoint without fully loading it.

    Useful for checkpoint inspection and selection.

    Args:
        checkpoint_path: Path to checkpoint file

    Returns:
        Dict with checkpoint information
    """
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    info = {
        "path": str(checkpoint_path),
        "keys": list(checkpoint.keys()),
        "has_model": "model" in checkpoint,
        "has_optimizer": "optimizer" in checkpoint,
        "has_evolutionary_bridge": "evolutionary_bridge" in checkpoint,
        "has_csr_components": "csr_components" in checkpoint,
        "has_inference_config": "inference_config" in checkpoint,
    }

    if "inference_config" in checkpoint:
        config = InferenceConfig.from_dict(checkpoint["inference_config"])
        info["inference_config"] = {
            "split": config.authority_sensory_split,
            "state": config.training_state,
            "stage": config.evolution_stage,
            "alpha": config.recommended_alpha,
        }

    if "metadata" in checkpoint:
        info["metadata"] = checkpoint["metadata"]

    return info
