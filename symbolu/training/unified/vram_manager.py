"""
VRAM management utilities for unified training.

Provides VRAMGovernor for dynamic batch resizing during training and
AutoBatchSizer for automatic batch size detection at startup.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any


class VRAMGovernor:
    """
    VRAM-Aware Dynamic Batch Governor.

    Monitors GPU memory usage and dynamically scales batch size to prevent
    OOM crashes. When batch size is reduced, increases λ_B1 (Consistency
    Lagrangian) to compensate for noisier gradients.

    Patent Integration:
    - [B1] ConsistencyLagrangian: Scaled up when batch reduces (noisy batches
      need stronger consistency enforcement)
    - [S8] StabilityHook: Notified of batch changes to adjust entropy thresholds

    Usage:
        governor = VRAMGovernor(initial_batch_size=32)

        # In training loop:
        new_batch, actions = governor.check_and_resize(current_step)
        if new_batch != current_batch:
            train_loader = reinit_dataloader(new_batch)
    """

    def __init__(
        self,
        initial_batch_size: int = 32,
        min_batch_size: int = 4,
        vram_threshold: float = 0.95,  # Trigger at 95% usage
        vram_critical: float = 0.98,   # Emergency at 98%
        vram_recovery_buffer: float = 0.12,  # Recovery when < (threshold - buffer)
        check_interval: int = 10,      # Check every N steps
        b1_compensation_rate: float = 0.20,  # 20% λ_B1 increase per reduction
        enable_accumulation_scaling: bool = True,
        target_effective_batch: int = 32,  # Target effective batch via accumulation
    ):
        self.initial_batch_size = initial_batch_size
        self.current_batch_size = initial_batch_size
        self.min_batch_size = min_batch_size
        self.vram_threshold = vram_threshold
        self.vram_critical = vram_critical
        self.vram_recovery_buffer = vram_recovery_buffer
        self.check_interval = check_interval
        self.b1_compensation_rate = b1_compensation_rate
        self.enable_accumulation_scaling = enable_accumulation_scaling
        self.target_effective_batch = target_effective_batch

        # Tracking
        self.b1_scale_factor = 1.0
        self.accumulation_steps = 1
        self.resize_count = 0
        self.last_check_step = 0
        self.vram_history = []

        # State
        self.in_recovery_mode = False
        self.recovery_start_step = None

    def get_vram_usage(self) -> Tuple[float, float, float]:
        """
        Get current VRAM usage statistics.

        Returns:
            (usage_fraction, used_gb, total_gb)

        Note: Uses memory_allocated() (actual tensor memory) not memory_reserved()
        (which includes PyTorch's caching allocator overhead). This prevents
        false VRAM pressure signals from cached but unused memory.
        """
        if not torch.cuda.is_available():
            return 0.0, 0.0, 0.0

        # Use memory_allocated() - actual tensor memory
        # NOT memory_reserved() which includes caching allocator overhead
        allocated = torch.cuda.memory_allocated()
        reserved = torch.cuda.memory_reserved()
        total = torch.cuda.get_device_properties(0).total_memory

        # Primary metric: allocated memory (actual usage)
        # But also consider if reserved is very high (fragmentation risk)
        # Use max of allocated and 70% of reserved as a balanced metric
        used = max(allocated, reserved * 0.7)

        usage = used / total
        used_gb = used / (1024 ** 3)
        total_gb = total / (1024 ** 3)

        return usage, used_gb, total_gb

    def check_and_resize(
        self,
        current_step: int,
        sovereign_engine: Optional[object] = None,
        force_check: bool = False,
    ) -> Tuple[int, List[str]]:
        """
        Check VRAM usage and resize batch if needed.

        Args:
            current_step: Current training step
            sovereign_engine: Optional SovereignEngine for λ_B1 adjustment
            force_check: Force check regardless of interval

        Returns:
            (new_batch_size, list of action strings)
        """
        actions = []

        # Only check at intervals (or if forced)
        if not force_check and (current_step - self.last_check_step) < self.check_interval:
            return self.current_batch_size, actions

        self.last_check_step = current_step

        # Get VRAM usage
        usage, used_gb, total_gb = self.get_vram_usage()
        self.vram_history.append({"step": current_step, "usage": usage, "used_gb": used_gb})

        # Keep history bounded
        if len(self.vram_history) > 100:
            self.vram_history = self.vram_history[-100:]

        # Check for critical VRAM (emergency)
        if usage > self.vram_critical:
            actions.append(f"🚨 [VRAM CRITICAL] Usage at {usage:.1%} ({used_gb:.1f}GB/{total_gb:.1f}GB)")
            actions.append("   Emergency cache purge initiated!")

            # Emergency cleanup
            import gc
            gc.collect()
            torch.cuda.empty_cache()

            # Force batch reduction by 8 (two steps)
            new_batch = max(self.min_batch_size, ((self.current_batch_size // 4) - 2) * 4)
            if new_batch < self.current_batch_size:
                self._apply_batch_reduction(new_batch, sovereign_engine, actions, emergency=True)

        # Check for high VRAM (warning threshold)
        elif usage > self.vram_threshold:
            actions.append(f"📊 [VRAM Governor] Adaptive resize: {usage:.1%} ({used_gb:.1f}GB/{total_gb:.1f}GB)")

            # Clear cache first
            torch.cuda.empty_cache()

            # Reduce batch by 4
            new_batch = max(self.min_batch_size, ((self.current_batch_size // 4) - 1) * 4)
            if new_batch < self.current_batch_size:
                self._apply_batch_reduction(new_batch, sovereign_engine, actions, emergency=False)

        # Check if we can recover (increase batch) after being in recovery mode
        elif self.in_recovery_mode and usage < (self.vram_threshold - self.vram_recovery_buffer):
            # VRAM is below recovery threshold - safe to try increasing
            steps_in_recovery = current_step - self.recovery_start_step
            if steps_in_recovery > 200:  # Wait at least 200 steps
                # Try increasing batch by 4
                new_batch = min(self.initial_batch_size, self.current_batch_size + 4)
                if new_batch > self.current_batch_size:
                    self._apply_batch_increase(new_batch, sovereign_engine, actions)

        return self.current_batch_size, actions

    def _apply_batch_reduction(
        self,
        new_batch: int,
        sovereign_engine: Optional[object],
        actions: List[str],
        emergency: bool = False,
    ):
        """Apply batch size reduction with patent compensation."""
        old_batch = self.current_batch_size
        self.current_batch_size = new_batch
        self.resize_count += 1

        # Enter recovery mode
        self.in_recovery_mode = True
        self.recovery_start_step = self.last_check_step

        # [B1] Increase λ_B1 to compensate for noisier gradients
        compensation = self.b1_compensation_rate * (1.5 if emergency else 1.0)
        self.b1_scale_factor = min(2.0, self.b1_scale_factor * (1.0 + compensation))

        if sovereign_engine is not None and hasattr(sovereign_engine, 'config'):
            # Apply the compensation to the engine
            sovereign_engine.config.lambda_b1 *= (1.0 + compensation)
            actions.append(f"   λ_B1 scaled: {sovereign_engine.config.lambda_b1 / (1 + compensation):.2f} → {sovereign_engine.config.lambda_b1:.2f} (noise compensation)")

        # Auto-scale gradient accumulation if batch gets too small
        # V9.8.1: Use ceiling division to maintain effective batch size
        if self.enable_accumulation_scaling and new_batch < self.target_effective_batch:
            # Ceiling division: ensures effective batch >= target
            new_accum = max(1, (self.target_effective_batch + new_batch - 1) // new_batch)
            if new_accum != self.accumulation_steps:
                old_accum = self.accumulation_steps
                self.accumulation_steps = new_accum
                effective = new_batch * new_accum
                actions.append(f"   📊 Gradient accumulation: {old_accum} → {new_accum} (effective batch: {effective})")

        if emergency:
            actions.append(f"   🚨 Emergency: Batch {old_batch} → {new_batch} | Resizes: {self.resize_count}")
        else:
            actions.append(f"   ✓ Adjusted: Batch {old_batch} → {new_batch} | Resizes: {self.resize_count}")

    def _apply_batch_increase(
        self,
        new_batch: int,
        sovereign_engine: Optional[object],
        actions: List[str],
    ):
        """Apply batch size increase (recovery)."""
        old_batch = self.current_batch_size
        self.current_batch_size = new_batch

        # Reduce λ_B1 compensation (partial - keep some stability)
        reduction = self.b1_compensation_rate * 0.5  # Only reduce by half
        self.b1_scale_factor = max(1.0, self.b1_scale_factor / (1.0 + reduction))

        if sovereign_engine is not None and hasattr(sovereign_engine, 'config'):
            old_b1 = sovereign_engine.config.lambda_b1
            sovereign_engine.config.lambda_b1 /= (1.0 + reduction)
            actions.append(f"   λ_B1 relaxed: {old_b1:.2f} → {sovereign_engine.config.lambda_b1:.2f}")

        # Adjust accumulation steps (V9.8.1: ceiling division)
        if self.enable_accumulation_scaling:
            new_accum = max(1, (self.target_effective_batch + new_batch - 1) // new_batch)
            if new_accum != self.accumulation_steps:
                old_accum = self.accumulation_steps
                self.accumulation_steps = new_accum
                effective = new_batch * new_accum
                actions.append(f"   📊 Gradient accumulation: {old_accum} → {new_accum} (effective batch: {effective})")

        # Check if fully recovered
        if new_batch >= self.initial_batch_size:
            self.in_recovery_mode = False
            actions.append(f"   ✅ [RECOVERED] Batch restored to {new_batch}")
        else:
            actions.append(f"   📈 [RECOVERING] Batch: {old_batch} → {new_batch}")

    def get_status_string(self) -> str:
        """Get formatted status string."""
        usage, used_gb, total_gb = self.get_vram_usage()
        mode = "RECOVERY" if self.in_recovery_mode else "NORMAL"
        return (
            f"VRAM:{usage:.0%}({used_gb:.1f}GB) | "
            f"Batch:{self.current_batch_size} | "
            f"λ_B1×{self.b1_scale_factor:.2f} | "
            f"[{mode}]"
        )

    def get_dataloader_config(self) -> Dict[str, int]:
        """Get current DataLoader configuration."""
        return {
            "batch_size": self.current_batch_size,
            "accumulation_steps": self.accumulation_steps,
            "effective_batch": self.current_batch_size * self.accumulation_steps,
        }


class AutoBatchSizer:
    """
    VRAM-Aware Automatic Batch Size Detector.

    At training startup, probes GPU memory to find the optimal batch size
    that utilizes a target percentage of VRAM (default 80%). Uses binary
    search for efficiency.

    This runs ONCE at startup, before training begins. The determined
    batch size remains fixed throughout training (VRAMGovernor handles
    dynamic adjustments during training if needed).

    Usage:
        sizer = AutoBatchSizer(model, seq_len=2048, target_utilization=0.80)
        batch_size, grad_accum = sizer.find_optimal_batch(target_effective=32)

        # Use these to configure your dataloader
        config.batch_size = batch_size
        config.gradient_accumulation = grad_accum
    """

    def __init__(
        self,
        model: nn.Module,
        seq_len: int = 2048,
        vocab_size: int = 50257,
        target_utilization: float = 0.80,
        min_batch_size: int = 1,
        max_batch_size: int = 128,
        safety_margin: float = 0.05,  # Extra headroom below target
        device: Optional[torch.device] = None,
    ):
        """
        Args:
            model: The model to probe (should be on GPU)
            seq_len: Maximum sequence length for probing
            vocab_size: Vocabulary size for dummy inputs
            target_utilization: Target VRAM utilization (0.80 = 80%)
            min_batch_size: Minimum batch size to try
            max_batch_size: Maximum batch size to try
            safety_margin: Extra margin below target (0.05 = 5% headroom)
            device: Device to probe (defaults to cuda:0)
        """
        self.model = model
        self.seq_len = seq_len
        self.vocab_size = vocab_size
        self.target_utilization = target_utilization
        self.effective_target = target_utilization - safety_margin
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size
        self.device = device or torch.device("cuda:0")

        # Results
        self.probed_batch_size: Optional[int] = None
        self.peak_memory_gb: float = 0.0
        self.total_memory_gb: float = 0.0

    def _get_memory_info(self) -> Tuple[float, float, float]:
        """Get current VRAM usage."""
        if not torch.cuda.is_available():
            return 0.0, 0.0, 0.0

        torch.cuda.synchronize()
        allocated = torch.cuda.memory_allocated(self.device)
        reserved = torch.cuda.memory_reserved(self.device)
        total = torch.cuda.get_device_properties(self.device).total_memory

        return allocated / total, reserved / (1024**3), total / (1024**3)

    def _clear_memory(self):
        """Aggressively clear GPU memory."""
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

    def _probe_batch_size(self, batch_size: int) -> Tuple[bool, float]:
        """
        Probe if a given batch size fits in memory.

        Returns:
            (success, peak_utilization)
        """
        self._clear_memory()

        try:
            # Create dummy batch
            dummy_input = torch.randint(
                0, self.vocab_size,
                (batch_size, self.seq_len),
                device=self.device,
                dtype=torch.long
            )
            dummy_target = torch.randint(
                0, self.vocab_size,
                (batch_size, self.seq_len),
                device=self.device,
                dtype=torch.long
            )

            # Forward pass
            self.model.train()
            with torch.amp.autocast('cuda', dtype=torch.bfloat16):
                outputs = self.model(dummy_input)

                # Handle different output formats
                if isinstance(outputs, dict):
                    # Ontological models return dict with 'logits' key
                    logits = outputs.get('logits', outputs.get('output', list(outputs.values())[0]))
                elif isinstance(outputs, tuple):
                    logits = outputs[0]
                elif hasattr(outputs, 'logits'):
                    logits = outputs.logits
                else:
                    logits = outputs

                # Compute loss (simulates full training step memory)
                loss = F.cross_entropy(
                    logits.view(-1, logits.size(-1)),
                    dummy_target.view(-1),
                    ignore_index=-100
                )

            # Backward pass (this is where most memory is used)
            loss.backward()

            # Check peak memory
            torch.cuda.synchronize()
            peak_allocated = torch.cuda.max_memory_allocated(self.device)
            total = torch.cuda.get_device_properties(self.device).total_memory
            peak_utilization = peak_allocated / total

            # Cleanup
            del dummy_input, dummy_target, outputs, logits, loss
            self.model.zero_grad(set_to_none=True)
            self._clear_memory()
            torch.cuda.reset_peak_memory_stats()

            return True, peak_utilization

        except RuntimeError as e:
            if "out of memory" in str(e).lower() or "CUDA" in str(e):
                # OOM - this batch size is too large
                self.model.zero_grad(set_to_none=True)
                self._clear_memory()
                torch.cuda.reset_peak_memory_stats()
                return False, 1.0
            else:
                raise

    def find_optimal_batch(
        self,
        target_effective_batch: int = 32,
        verbose: bool = True
    ) -> Tuple[int, int]:
        """
        Find optimal batch size using binary search.

        Args:
            target_effective_batch: Desired effective batch size (for grad accum calculation).
                                   If 0, just finds max batch that fits and sets accum=1.
            verbose: Print progress

        Returns:
            (batch_size, gradient_accumulation_steps)
        """
        if not torch.cuda.is_available():
            if verbose:
                print("  ⚠️  No CUDA available, using default batch size")
            if target_effective_batch > 0:
                return self.min_batch_size, target_effective_batch // self.min_batch_size
            return self.min_batch_size, 1

        # Get total memory
        total_mem = torch.cuda.get_device_properties(self.device).total_memory
        self.total_memory_gb = total_mem / (1024**3)

        if verbose:
            print(f"\n  {'='*60}")
            print(f"  AUTO BATCH SIZER: Probing optimal batch size")
            print(f"  {'='*60}")
            print(f"  GPU: {torch.cuda.get_device_name(self.device)}")
            print(f"  Total VRAM: {self.total_memory_gb:.1f} GB")
            print(f"  Target Utilization: {self.target_utilization:.0%} (effective: {self.effective_target:.0%})")
            print(f"  Sequence Length: {self.seq_len:,}")
            if target_effective_batch > 0:
                print(f"  Target Effective Batch: {target_effective_batch}")
            else:
                print(f"  Mode: Find maximum batch (no accumulation target)")
            print(f"  {'─'*60}")

        # Build list of candidate batch sizes (multiples of 8 for Tensor Core efficiency)
        # V9.5.2 Metabolic Tuning: Also include intermediate batch sizes (48, 40) for better
        # gradient accumulation granularity (e.g., 48/6=288 effective, 40/8=320 effective)
        alignment = 8
        if target_effective_batch > 0:
            max_candidate = min(self.max_batch_size, target_effective_batch)
        else:
            max_candidate = self.max_batch_size
        candidates = [b for b in range(alignment, max_candidate + 1, alignment)]
        # Add intermediate values for fine-grained accumulation tuning
        for intermediate in [40, 48, 56, 72]:
            if intermediate not in candidates and intermediate <= max_candidate:
                candidates.append(intermediate)
        candidates = sorted(set(candidates))
        if not candidates:
            candidates = [alignment]  # Minimum fallback

        if verbose:
            print(f"  Candidates (multiples of {alignment}): {candidates}")

        # Binary search for optimal batch size
        low_idx = 0
        high_idx = len(candidates) - 1
        optimal_batch = candidates[0]
        optimal_utilization = 0.0

        # First, find the maximum that fits
        if verbose:
            print(f"  Phase 1: Finding maximum batch size that fits...")

        while low_idx <= high_idx:
            mid_idx = (low_idx + high_idx) // 2
            mid = candidates[mid_idx]
            if verbose:
                print(f"    Probing batch_size={mid}...", end=" ", flush=True)

            success, utilization = self._probe_batch_size(mid)

            if success:
                if verbose:
                    print(f"✓ ({utilization:.1%} VRAM)")

                if utilization <= self.effective_target:
                    # Fits within target, try larger
                    optimal_batch = mid
                    optimal_utilization = utilization
                    low_idx = mid_idx + 1
                else:
                    # Exceeds target but doesn't OOM, this is close
                    optimal_batch = mid
                    optimal_utilization = utilization
                    high_idx = mid_idx - 1
            else:
                if verbose:
                    print(f"✗ OOM")
                high_idx = mid_idx - 1

        # Verify final choice fits within target
        if optimal_utilization > self.effective_target:
            # Step down to previous candidate
            current_idx = candidates.index(optimal_batch)
            while current_idx > 0:
                current_idx -= 1
                optimal_batch = candidates[current_idx]
                success, utilization = self._probe_batch_size(optimal_batch)
                if success and utilization <= self.effective_target:
                    optimal_utilization = utilization
                    if verbose:
                        print(f"    Stepping down to batch_size={optimal_batch}... ✓ ({utilization:.1%} VRAM)")
                    break

        # Calculate gradient accumulation
        if target_effective_batch <= 0 or optimal_batch >= target_effective_batch:
            grad_accum = 1
        else:
            grad_accum = max(1, target_effective_batch // optimal_batch)

        effective_batch = optimal_batch * grad_accum

        # Store results
        self.probed_batch_size = optimal_batch
        self.peak_memory_gb = optimal_utilization * self.total_memory_gb

        if verbose:
            print(f"  {'─'*60}")
            print(f"  ✓ OPTIMAL CONFIGURATION FOUND:")
            print(f"    Batch Size: {optimal_batch}")
            print(f"    Gradient Accumulation: {grad_accum}")
            print(f"    Effective Batch: {effective_batch}")
            print(f"    Peak VRAM: {self.peak_memory_gb:.1f} GB ({optimal_utilization:.1%})")
            print(f"  {'='*60}\n")

        return optimal_batch, grad_accum

    def get_summary(self) -> Dict[str, any]:
        """Get summary of probing results."""
        return {
            "batch_size": self.probed_batch_size,
            "total_vram_gb": self.total_memory_gb,
            "peak_vram_gb": self.peak_memory_gb,
            "target_utilization": self.target_utilization,
            "seq_len": self.seq_len,
        }
