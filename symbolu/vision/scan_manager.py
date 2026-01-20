"""
ScanManager2D: Manages 2D grid to 1D scan order mappings.

For 2D images, the Phase Integrator needs consistent scan orders to
perform 1D cumsum operations. This module handles the mapping between
2D grid coordinates and 1D scan sequences.

Supports:
- row_order: Row-major (raster) scan
- col_order: Column-major scan
- hilbert_order: (optional) Hilbert curve for better locality
"""

from typing import Optional, Tuple
from functools import lru_cache

import torch
from torch import Tensor, LongTensor


class ScanManager2D:
    """
    Manages 2D grid ↔ 1D scan order mappings.

    The Phase Integrator operates on 1D sequences, but images are 2D.
    This class handles the reordering needed for bi-axial phase scans.

    Attributes:
        H_p: Number of patch rows.
        W_p: Number of patch columns.
        N: Total number of patches (H_p * W_p).
        row_order: Indices for row-major (raster) scan.
        col_order: Indices for column-major scan.
    """

    def __init__(
        self,
        H_p: int,
        W_p: int,
        device: Optional[torch.device] = None,
    ):
        """
        Initialize scan orders for grid of size H_p × W_p.

        Args:
            H_p: Number of patch rows.
            W_p: Number of patch columns.
            device: Device for index tensors.
        """
        self.H_p = H_p
        self.W_p = W_p
        self.N = H_p * W_p
        self._device = device or torch.device("cpu")

        # Precompute scan orders
        self._row_order: Optional[LongTensor] = None
        self._col_order: Optional[LongTensor] = None
        self._row_inverse: Optional[LongTensor] = None
        self._col_inverse: Optional[LongTensor] = None
        self._hilbert_order: Optional[LongTensor] = None

    @property
    def row_order(self) -> LongTensor:
        """
        Row-major (raster) scan order.

        Returns:
            [N] indices where row_order[i] gives the canonical index
            for position i in the row-major scan.
        """
        if self._row_order is None:
            # Row-major is the canonical order, so it's identity
            self._row_order = torch.arange(self.N, device=self._device)
        return self._row_order

    @property
    def col_order(self) -> LongTensor:
        """
        Column-major scan order.

        Returns:
            [N] indices where col_order[i] gives the canonical index
            for position i in the column-major scan.
        """
        if self._col_order is None:
            # Create column-major ordering
            # If canonical is row-major [(0,0), (0,1), ..., (H-1, W-1)]
            # Column-major is [(0,0), (1,0), ..., (H-1, W-1)]
            indices = []
            for c in range(self.W_p):
                for r in range(self.H_p):
                    # Canonical index for (r, c) in row-major
                    canonical_idx = r * self.W_p + c
                    indices.append(canonical_idx)
            self._col_order = torch.tensor(indices, device=self._device, dtype=torch.long)
        return self._col_order

    @property
    def row_inverse(self) -> LongTensor:
        """Inverse permutation for row order (to restore canonical)."""
        if self._row_inverse is None:
            # Row order is identity, so inverse is also identity
            self._row_inverse = torch.arange(self.N, device=self._device)
        return self._row_inverse

    @property
    def col_inverse(self) -> LongTensor:
        """Inverse permutation for column order (to restore canonical)."""
        if self._col_inverse is None:
            self._col_inverse = torch.argsort(self.col_order)
        return self._col_inverse

    @property
    def hilbert_order(self) -> LongTensor:
        """
        Hilbert curve scan order (optional, for better locality).

        Lazily computed. Only available for power-of-2 dimensions.

        Returns:
            [N] indices for Hilbert curve traversal.

        Raises:
            ValueError: If dimensions are not equal powers of 2.
        """
        if self._hilbert_order is None:
            if self.H_p != self.W_p:
                raise ValueError(
                    f"Hilbert curve requires square grid, got {self.H_p}x{self.W_p}"
                )
            if not (self.H_p & (self.H_p - 1) == 0):
                raise ValueError(
                    f"Hilbert curve requires power-of-2 size, got {self.H_p}"
                )
            self._hilbert_order = self._compute_hilbert_order(self.H_p)
        return self._hilbert_order

    def _compute_hilbert_order(self, size: int) -> LongTensor:
        """Compute Hilbert curve indices for size x size grid."""
        indices = []
        for i in range(size * size):
            x, y = self._d2xy(size, i)
            # Convert to canonical row-major index
            canonical_idx = y * size + x
            indices.append(canonical_idx)
        return torch.tensor(indices, device=self._device, dtype=torch.long)

    def _d2xy(self, n: int, d: int) -> Tuple[int, int]:
        """Convert Hilbert curve index to (x, y) coordinates."""
        x = y = 0
        s = 1
        while s < n:
            rx = 1 & (d // 2)
            ry = 1 & (d ^ rx)
            x, y = self._rot(s, x, y, rx, ry)
            x += s * rx
            y += s * ry
            d //= 4
            s *= 2
        return x, y

    def _rot(self, n: int, x: int, y: int, rx: int, ry: int) -> Tuple[int, int]:
        """Rotate quadrant for Hilbert curve."""
        if ry == 0:
            if rx == 1:
                x = n - 1 - x
                y = n - 1 - y
            x, y = y, x
        return x, y

    def gather(self, x: Tensor, order: LongTensor) -> Tensor:
        """
        Reorder tensor according to scan order.

        Args:
            x: [B, N, ...] tensor in canonical (row-major) order.
            order: [N] index permutation.

        Returns:
            x_reordered: [B, N, ...] tensor in scan order.
        """
        B = x.shape[0]
        N = x.shape[1]

        # Expand order for batch dimension
        # order: [N] -> [1, N] -> [B, N]
        order_exp = order.unsqueeze(0).expand(B, -1)

        # Handle arbitrary trailing dimensions
        trailing_dims = x.shape[2:]
        if trailing_dims:
            # Expand order for trailing dims
            for _ in trailing_dims:
                order_exp = order_exp.unsqueeze(-1)
            order_exp = order_exp.expand(-1, -1, *trailing_dims)

        return torch.gather(x, 1, order_exp)

    def scatter(self, x: Tensor, order: LongTensor) -> Tensor:
        """
        Inverse of gather - restore canonical order.

        Args:
            x: [B, N, ...] tensor in scan order.
            order: [N] index permutation used in gather.

        Returns:
            x_canonical: [B, N, ...] tensor in canonical (row-major) order.
        """
        B = x.shape[0]

        # Get inverse permutation
        inverse_order = torch.argsort(order)

        # Use gather with inverse order
        return self.gather(x, inverse_order)

    def to(self, device: torch.device) -> "ScanManager2D":
        """
        Move scan manager to specified device.

        Args:
            device: Target device.

        Returns:
            New ScanManager2D with tensors on specified device.
        """
        new_manager = ScanManager2D(self.H_p, self.W_p, device)

        # Move cached orders if they exist
        if self._row_order is not None:
            new_manager._row_order = self._row_order.to(device)
        if self._col_order is not None:
            new_manager._col_order = self._col_order.to(device)
        if self._row_inverse is not None:
            new_manager._row_inverse = self._row_inverse.to(device)
        if self._col_inverse is not None:
            new_manager._col_inverse = self._col_inverse.to(device)
        if self._hilbert_order is not None:
            new_manager._hilbert_order = self._hilbert_order.to(device)

        return new_manager


@lru_cache(maxsize=32)
def get_scan_manager(H_p: int, W_p: int, device: str = "cpu") -> ScanManager2D:
    """
    Get or create a cached ScanManager2D.

    Args:
        H_p: Number of patch rows.
        W_p: Number of patch columns.
        device: Device string (for caching).

    Returns:
        Cached ScanManager2D instance.
    """
    return ScanManager2D(H_p, W_p, torch.device(device))
