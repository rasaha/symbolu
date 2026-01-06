#!/usr/bin/env python3
"""
Checkpoint Utilities for Inference
===================================

Utilities for loading checkpoints with inference-ready components.

Handles:
- Model loading with proper device placement
- Evolutionary bridge weight extraction
- CSR component loading
- Inference configuration from checkpoint metadata

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

import torch
import torch.nn as nn
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
import warnings


class InferenceCheckpointLoader:
    """
    Load checkpoints for inference with all components.

    Handles graceful degradation when components are missing and
    provides warnings about disabled features.

    Example:
        loader = InferenceCheckpointLoader(checkpoint_path)

        model = loader.load_model(model_class)
        engine = loader.load_evolutionary_engine(model)
        guard = loader.load_csr_guard(model.lm_head)

        # Check what was loaded
        print(loader.get_loading_summary())
    """

    def __init__(
        self,
        checkpoint_path: Union[str, Path],
        device: Union[str, torch.device] = 'cpu',
    ):
        """
        Initialize checkpoint loader.

        Args:
            checkpoint_path: Path to checkpoint file
            device: Target device for loading
        """
        self.checkpoint_path = Path(checkpoint_path)
        self.device = torch.device(device) if isinstance(device, str) else device

        # Loading state
        self._checkpoint: Optional[Dict] = None
        self._loaded_components: Dict[str, bool] = {}
        self._warnings: List[str] = []

    def _ensure_loaded(self) -> Dict:
        """Ensure checkpoint is loaded."""
        if self._checkpoint is None:
            self._checkpoint = torch.load(
                self.checkpoint_path,
                map_location=self.device,
            )
        return self._checkpoint

    def get_model_state_dict(self) -> Dict[str, torch.Tensor]:
        """
        Get model state dict from checkpoint.

        Returns:
            state_dict: Model weights
        """
        checkpoint = self._ensure_loaded()

        # Try different key patterns
        if 'model' in checkpoint:
            return checkpoint['model']
        elif 'model_state_dict' in checkpoint:
            return checkpoint['model_state_dict']
        elif 'state_dict' in checkpoint:
            return checkpoint['state_dict']
        else:
            # Assume checkpoint IS the state dict
            return checkpoint

    def load_model(
        self,
        model_class: type,
        model_kwargs: Optional[Dict] = None,
        strict: bool = False,
    ) -> nn.Module:
        """
        Load model from checkpoint.

        Args:
            model_class: Model class to instantiate
            model_kwargs: Arguments for model constructor
            strict: Whether to enforce strict state dict loading

        Returns:
            model: Loaded model on target device
        """
        checkpoint = self._ensure_loaded()
        model_kwargs = model_kwargs or {}

        # Try to get config from checkpoint
        if 'config' in checkpoint:
            saved_config = checkpoint['config']
            # Merge with provided kwargs (provided take precedence)
            if hasattr(saved_config, '__dict__'):
                for k, v in saved_config.__dict__.items():
                    if k not in model_kwargs:
                        model_kwargs[k] = v

        # Instantiate model
        model = model_class(**model_kwargs)

        # Load state dict
        state_dict = self.get_model_state_dict()

        try:
            missing, unexpected = model.load_state_dict(state_dict, strict=strict)

            if missing:
                self._warnings.append(f"Missing keys in model: {len(missing)} keys")
            if unexpected:
                self._warnings.append(f"Unexpected keys in model: {len(unexpected)} keys")

            self._loaded_components['model'] = True

        except Exception as e:
            self._warnings.append(f"Model loading error: {e}")
            self._loaded_components['model'] = False

        return model.to(self.device)

    def load_evolutionary_engine(
        self,
        model: nn.Module,
    ) -> 'EvolutionaryInferenceEngine':
        """
        Load evolutionary inference engine.

        Args:
            model: Loaded model

        Returns:
            engine: Evolutionary inference engine
        """
        from .evolutionary_inference import EvolutionaryInferenceEngine, EvolutionaryConfig

        checkpoint = self._ensure_loaded()

        # Get config from checkpoint
        inference_config = checkpoint.get('inference_config', {})
        resonance_alpha = inference_config.get('recommended_resonance_alpha', 0.1)

        config = EvolutionaryConfig(
            resonance_alpha=resonance_alpha,
        )

        engine = EvolutionaryInferenceEngine(model, config)

        # Try to load bridge weights
        if 'evolutionary_bridge' in checkpoint:
            success = engine.bridge.load_from_checkpoint(checkpoint['evolutionary_bridge'])
            engine.bridge_enabled = success
            self._loaded_components['evolutionary_bridge'] = success

            if not success:
                self._warnings.append("Failed to load evolutionary bridge weights")
        else:
            # Try loading from flat checkpoint
            success = engine.bridge.load_from_checkpoint(checkpoint)
            engine.bridge_enabled = success
            self._loaded_components['evolutionary_bridge'] = success

            if not success:
                self._warnings.append(
                    "Checkpoint does not contain evolutionary bridge - karma disabled"
                )

        engine.to(self.device)
        return engine

    def load_csr_guard(
        self,
        lm_head: Optional[nn.Module] = None,
        embed_dim: int = 768,
    ) -> 'CSRInferenceGuard':
        """
        Load CSR inference guard.

        Args:
            lm_head: Language model head (may be None)
            embed_dim: Embedding dimension

        Returns:
            guard: CSR inference guard
        """
        from .csr_inference import CSRInferenceGuard, CSRGuardConfig

        checkpoint = self._ensure_loaded()

        config = CSRGuardConfig()
        guard = CSRInferenceGuard(
            config=config,
            embed_dim=embed_dim,
            lm_head=lm_head,
        )

        # Try to load CSR components
        if guard.load_from_checkpoint(checkpoint):
            self._loaded_components['csr_guard'] = True
        else:
            self._loaded_components['csr_guard'] = False
            self._warnings.append(
                "Checkpoint does not contain CSR components - using default initialization"
            )

        if lm_head is None:
            self._warnings.append(
                "lm_head is None - CSR re-projection will be disabled"
            )

        guard.to(self.device)
        return guard

    def load_layer_config(self) -> 'LayerInferenceConfig':
        """
        Load layer configuration from checkpoint.

        Returns:
            config: Layer inference configuration
        """
        from .layer_config import LayerInferenceConfig

        checkpoint = self._ensure_loaded()
        config = LayerInferenceConfig.from_checkpoint(checkpoint)

        self._loaded_components['layer_config'] = True
        return config

    def get_training_step(self) -> int:
        """Get training step from checkpoint."""
        checkpoint = self._ensure_loaded()
        return checkpoint.get('global_step', checkpoint.get('step', 0))

    def get_training_config(self) -> Dict[str, Any]:
        """Get training configuration from checkpoint."""
        checkpoint = self._ensure_loaded()
        return checkpoint.get('config', {})

    def get_inference_config(self) -> Dict[str, Any]:
        """Get inference-specific configuration."""
        checkpoint = self._ensure_loaded()
        return checkpoint.get('inference_config', {})

    def get_loading_summary(self) -> str:
        """
        Get summary of what was loaded.

        Returns:
            summary: Human-readable loading summary
        """
        lines = [
            f"Checkpoint: {self.checkpoint_path}",
            f"Device: {self.device}",
            "",
            "Components loaded:",
        ]

        for component, loaded in self._loaded_components.items():
            status = "OK" if loaded else "FAILED"
            lines.append(f"  {component}: {status}")

        if self._warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in self._warnings:
                lines.append(f"  - {warning}")

        return "\n".join(lines)

    def get_warnings(self) -> List[str]:
        """Get all warnings from loading."""
        return self._warnings.copy()


def load_inference_engine(
    checkpoint_path: Union[str, Path],
    model_class: type,
    model_kwargs: Optional[Dict] = None,
    device: Union[str, torch.device] = 'cuda' if torch.cuda.is_available() else 'cpu',
) -> Tuple['EvolutionaryInferenceEngine', 'CSRInferenceGuard', Dict[str, Any]]:
    """
    Convenience function to load all inference components.

    Args:
        checkpoint_path: Path to checkpoint
        model_class: Model class to instantiate
        model_kwargs: Model constructor arguments
        device: Target device

    Returns:
        engine: Evolutionary inference engine
        guard: CSR inference guard
        info: Dict with loading info and warnings
    """
    loader = InferenceCheckpointLoader(checkpoint_path, device)

    # Load model
    model = loader.load_model(model_class, model_kwargs)

    # Get lm_head if available
    lm_head = getattr(model, 'lm_head', None)
    embed_dim = getattr(model, 'embed_dim', 768)

    # Load components
    engine = loader.load_evolutionary_engine(model)
    guard = loader.load_csr_guard(lm_head, embed_dim)

    info = {
        'loaded_components': loader._loaded_components,
        'warnings': loader.get_warnings(),
        'training_step': loader.get_training_step(),
        'summary': loader.get_loading_summary(),
    }

    return engine, guard, info


def save_inference_checkpoint(
    checkpoint_path: Union[str, Path],
    model: nn.Module,
    evolutionary_bridge: Optional[nn.Module] = None,
    csr_entropy_sink: Optional[nn.Module] = None,
    csr_synthesis_gate: Optional[nn.Module] = None,
    training_step: int = 0,
    config: Optional[Any] = None,
    inference_config: Optional[Dict] = None,
) -> None:
    """
    Save checkpoint with inference components.

    Args:
        checkpoint_path: Save path
        model: Model to save
        evolutionary_bridge: Optional bridge module
        csr_entropy_sink: Optional entropy sink
        csr_synthesis_gate: Optional synthesis gate
        training_step: Current training step
        config: Training configuration
        inference_config: Inference-specific configuration
    """
    checkpoint = {
        'model': model.state_dict(),
        'global_step': training_step,
    }

    if config is not None:
        checkpoint['config'] = config

    if inference_config is not None:
        checkpoint['inference_config'] = inference_config

    if evolutionary_bridge is not None:
        checkpoint['evolutionary_bridge'] = evolutionary_bridge.state_dict()

    if csr_entropy_sink is not None:
        checkpoint['csr_entropy_sink'] = csr_entropy_sink.state_dict()

    if csr_synthesis_gate is not None:
        checkpoint['csr_synthesis_gate'] = csr_synthesis_gate.state_dict()

    torch.save(checkpoint, checkpoint_path)
