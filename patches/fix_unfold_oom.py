#!/usr/bin/env python3
"""
Patch: Fix LocalAttention unfold OOM for large batches
=======================================================

Adds chunked processing to _forward_unfold when B * N > 32K
to prevent OOM errors with large batch sizes and long sequences.

Usage:
    python patches/fix_unfold_oom.py
"""

import re
from pathlib import Path

PATCH_FILE = Path(__file__).parent.parent / "symbolu" / "phase_transformer.py"

OLD_CODE = '''    def _forward_unfold(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                        B: int, N: int, causal: bool) -> torch.Tensor:
        """Unfold-based sliding window - TRUE O(n×w), no N×N tensors."""
        w = self.window_size

        # Pad K and V on the left so each position can look back w-1 positions
        K_padded = F.pad(K, (0, 0, w - 1, 0), value=0)  # (B, H, N+w-1, head_dim)
        V_padded = F.pad(V, (0, 0, w - 1, 0), value=0)

        # Use unfold to create sliding windows of size w
        K_windows = K_padded.unfold(2, w, 1)  # (B, H, N, head_dim, w)
        V_windows = V_padded.unfold(2, w, 1)

        # Rearrange for attention computation
        K_windows = K_windows.permute(0, 1, 2, 4, 3)  # (B, H, N, w, head_dim)
        V_windows = V_windows.permute(0, 1, 2, 4, 3)

        # Compute attention scores: Q @ K^T for each window
        Q_expanded = Q.unsqueeze(3)  # (B, H, N, 1, head_dim)
        attn = torch.matmul(Q_expanded, K_windows.transpose(-2, -1)) * self.scale
        attn = attn.squeeze(3)  # (B, H, N, w)

        if causal:
            # Mask out padding positions
            positions = torch.arange(N, device=Q.device)
            valid_counts = torch.clamp(positions + 1, max=w)
            window_indices = torch.arange(w, device=Q.device)
            mask = window_indices.unsqueeze(0) < (w - valid_counts.unsqueeze(1))
            attn = attn.masked_fill(mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)

        # Apply attention to values
        attn_expanded = attn.unsqueeze(3)  # (B, H, N, 1, w)
        output = torch.matmul(attn_expanded, V_windows)
        output = output.squeeze(3)  # (B, H, N, head_dim)

        return output'''

NEW_CODE = '''    def _forward_unfold(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                        B: int, N: int, causal: bool) -> torch.Tensor:
        """Unfold-based sliding window - TRUE O(n×w), no N×N tensors.

        Uses chunked processing to reduce peak memory usage for long sequences.
        """
        w = self.window_size

        # For large batch × sequence, process in chunks to avoid OOM
        # Threshold: B * N > 32K suggests chunking needed
        chunk_size = max(1024, min(N, 65536 // max(B, 1)))

        if B * N > 32768 and N > chunk_size:
            # Process in chunks along sequence dimension
            return self._forward_unfold_chunked(Q, K, V, B, N, causal, chunk_size)

        # Pad K and V on the left so each position can look back w-1 positions
        K_padded = F.pad(K, (0, 0, w - 1, 0), value=0)  # (B, H, N+w-1, head_dim)
        V_padded = F.pad(V, (0, 0, w - 1, 0), value=0)

        # Use unfold to create sliding windows of size w
        K_windows = K_padded.unfold(2, w, 1)  # (B, H, N, head_dim, w)
        V_windows = V_padded.unfold(2, w, 1)

        # Rearrange for attention computation
        K_windows = K_windows.permute(0, 1, 2, 4, 3)  # (B, H, N, w, head_dim)
        V_windows = V_windows.permute(0, 1, 2, 4, 3)

        # Compute attention scores: Q @ K^T for each window
        Q_expanded = Q.unsqueeze(3)  # (B, H, N, 1, head_dim)
        attn = torch.matmul(Q_expanded, K_windows.transpose(-2, -1)) * self.scale
        attn = attn.squeeze(3)  # (B, H, N, w)

        if causal:
            # Mask out padding positions
            positions = torch.arange(N, device=Q.device)
            valid_counts = torch.clamp(positions + 1, max=w)
            window_indices = torch.arange(w, device=Q.device)
            mask = window_indices.unsqueeze(0) < (w - valid_counts.unsqueeze(1))
            attn = attn.masked_fill(mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)

        # Apply attention to values
        attn_expanded = attn.unsqueeze(3)  # (B, H, N, 1, w)
        output = torch.matmul(attn_expanded, V_windows)
        output = output.squeeze(3)  # (B, H, N, head_dim)

        return output

    def _forward_unfold_chunked(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                                 B: int, N: int, causal: bool, chunk_size: int) -> torch.Tensor:
        """Chunked unfold processing for memory efficiency with large batches."""
        w = self.window_size
        H = Q.shape[1]
        head_dim = Q.shape[-1]

        # Pad K and V once
        K_padded = F.pad(K, (0, 0, w - 1, 0), value=0)  # (B, H, N+w-1, head_dim)
        V_padded = F.pad(V, (0, 0, w - 1, 0), value=0)

        # Pre-compute causal mask info
        if causal:
            positions = torch.arange(N, device=Q.device)
            valid_counts = torch.clamp(positions + 1, max=w)
            window_indices = torch.arange(w, device=Q.device)
            causal_mask = window_indices.unsqueeze(0) < (w - valid_counts.unsqueeze(1))

        # Process in chunks
        outputs = []
        for start in range(0, N, chunk_size):
            end = min(start + chunk_size, N)
            chunk_len = end - start

            # Extract Q chunk
            Q_chunk = Q[:, :, start:end, :]  # (B, H, chunk_len, head_dim)

            # Extract corresponding K, V windows
            # K_padded indices [start:end] correspond to original [start-w+1:end]
            K_chunk_padded = K_padded[:, :, start:end + w - 1, :]
            V_chunk_padded = V_padded[:, :, start:end + w - 1, :]

            # Unfold this chunk
            K_windows = K_chunk_padded.unfold(2, w, 1)  # (B, H, chunk_len, head_dim, w)
            V_windows = V_chunk_padded.unfold(2, w, 1)
            K_windows = K_windows.permute(0, 1, 2, 4, 3)  # (B, H, chunk_len, w, head_dim)
            V_windows = V_windows.permute(0, 1, 2, 4, 3)

            # Attention for this chunk
            Q_expanded = Q_chunk.unsqueeze(3)  # (B, H, chunk_len, 1, head_dim)
            attn = torch.matmul(Q_expanded, K_windows.transpose(-2, -1)) * self.scale
            attn = attn.squeeze(3)  # (B, H, chunk_len, w)

            if causal:
                chunk_mask = causal_mask[start:end, :]  # (chunk_len, w)
                attn = attn.masked_fill(chunk_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

            attn = F.softmax(attn, dim=-1)
            attn = self.dropout(attn)

            # Apply to values
            attn_expanded = attn.unsqueeze(3)  # (B, H, chunk_len, 1, w)
            out_chunk = torch.matmul(attn_expanded, V_windows)
            out_chunk = out_chunk.squeeze(3)  # (B, H, chunk_len, head_dim)
            outputs.append(out_chunk)

        return torch.cat(outputs, dim=2)'''


def apply_patch():
    print("=" * 60)
    print("  PATCH: Fix LocalAttention unfold OOM")
    print("=" * 60)
    print()

    if not PATCH_FILE.exists():
        print(f"ERROR: File not found: {PATCH_FILE}")
        return False

    content = PATCH_FILE.read_text()

    # Check if already patched
    if "_forward_unfold_chunked" in content:
        print("SKIP: Patch already applied (chunked method exists)")
        return True

    # Check if old code exists
    if OLD_CODE not in content:
        print("ERROR: Could not find target code to patch")
        print("       The file may have been modified")
        return False

    # Apply patch
    new_content = content.replace(OLD_CODE, NEW_CODE)

    PATCH_FILE.write_text(new_content)

    print(f"SUCCESS: Patched {PATCH_FILE}")
    print()
    print("Changes:")
    print("  - Added chunked processing when B * N > 32K")
    print("  - Added _forward_unfold_chunked method")
    print("  - Prevents OOM with batch_size 32 @ 8K sequences")

    return True


if __name__ == "__main__":
    import sys
    success = apply_patch()
    sys.exit(0 if success else 1)
