"""
Volume Profile Analysis

Tick-based volume profile for identifying key price levels:
- POC (Point of Control): Price with highest volume - strongest S/R
- Value Area: 70% of volume - fair value range
- VAH/VAL: Value Area High/Low - boundaries
- HVN (High Volume Nodes): Support/Resistance levels
- LVN (Low Volume Nodes): Price moves quickly through these

Tick data is superior to time bars because:
- Exact volume at each price level (not aggregated)
- True market activity (not sampled)
- Sub-cent precision for profiles
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from enum import Enum
import math


class PriceLocation(Enum):
    """Price location relative to volume profile."""
    ABOVE_VA = "above_value_area"      # Price above VAH - extended
    AT_VAH = "at_vah"                   # At resistance
    INSIDE_VA = "inside_value_area"    # Fair value zone
    AT_VAL = "at_val"                   # At support
    BELOW_VA = "below_value_area"      # Price below VAL - extended
    AT_POC = "at_poc"                   # At highest volume


@dataclass
class VolumeNode:
    """A volume node at a specific price level."""
    price: float
    volume: float
    trade_count: int = 0
    buy_volume: float = 0.0  # Volume on upticks
    sell_volume: float = 0.0  # Volume on downticks

    @property
    def delta(self) -> float:
        """Buy-sell volume imbalance."""
        return self.buy_volume - self.sell_volume

    @property
    def delta_percent(self) -> float:
        """Delta as percentage of total volume."""
        if self.volume == 0:
            return 0.0
        return self.delta / self.volume


@dataclass
class ValueArea:
    """Value area containing 70% of volume."""
    high: float  # VAH
    low: float   # VAL
    poc: float   # Point of Control
    volume: float  # Total volume in VA
    volume_percent: float  # Percentage of total (usually ~70%)


@dataclass
class VolumeProfileResult:
    """Complete volume profile analysis result."""
    poc: float  # Point of Control
    poc_volume: float
    vah: float  # Value Area High
    val: float  # Value Area Low
    value_area: ValueArea
    high_volume_nodes: List[VolumeNode]  # HVN - S/R levels
    low_volume_nodes: List[VolumeNode]   # LVN - fast move zones
    total_volume: float
    price_range_high: float
    price_range_low: float
    current_location: PriceLocation
    distance_to_poc: float  # As percentage
    distance_to_vah: float
    distance_to_val: float
    nearest_hvn_above: Optional[float]
    nearest_hvn_below: Optional[float]
    nearest_lvn: Optional[float]


class VolumeProfile:
    """
    Tick-based volume profile calculator.

    Accumulates volume at each price level from tick data
    and calculates key levels for trading decisions.
    """

    def __init__(
        self,
        tick_size: float = 0.01,
        value_area_percent: float = 0.70,
        hvn_threshold: float = 1.5,  # Multiplier of average volume
        lvn_threshold: float = 0.3,  # Multiplier of average volume
        rolling_window: Optional[int] = None,  # None = session, int = rolling ticks
    ):
        """
        Initialize volume profile calculator.

        Args:
            tick_size: Price granularity for bucketing (default $0.01)
            value_area_percent: Percentage for value area (default 70%)
            hvn_threshold: Volume multiplier to identify HVN
            lvn_threshold: Volume multiplier to identify LVN
            rolling_window: If set, use rolling window of N ticks
        """
        self.tick_size = tick_size
        self.value_area_percent = value_area_percent
        self.hvn_threshold = hvn_threshold
        self.lvn_threshold = lvn_threshold
        self.rolling_window = rolling_window

        # Volume accumulation by price level
        self._volume_map: Dict[float, VolumeNode] = defaultdict(
            lambda: VolumeNode(price=0.0, volume=0.0)
        )

        # Tick history for rolling window
        self._tick_history: List[Tuple[float, float, bool]] = []  # (price, volume, is_uptick)

        # Cached calculations
        self._poc: float = 0.0
        self._vah: float = 0.0
        self._val: float = 0.0
        self._last_price: Optional[float] = None
        self._total_volume: float = 0.0
        self._recalc_needed: bool = True
        self._recalc_interval: int = 10
        self._tick_count: int = 0

    def update(
        self,
        price: float,
        volume: float = 1.0,
        is_buy: Optional[bool] = None,
    ) -> VolumeProfileResult:
        """
        Update profile with new tick.

        Args:
            price: Trade price
            volume: Trade volume (default 1 for tick counting)
            is_buy: True if uptick, False if downtick, None to auto-detect

        Returns:
            Current VolumeProfileResult
        """
        self._tick_count += 1

        # Determine tick direction
        if is_buy is None and self._last_price is not None:
            is_buy = price >= self._last_price
        elif is_buy is None:
            is_buy = True  # Default for first tick

        # Round price to tick size
        bucket_price = self._round_to_tick(price)

        # Update volume map
        node = self._volume_map[bucket_price]
        node.price = bucket_price
        node.volume += volume
        node.trade_count += 1
        if is_buy:
            node.buy_volume += volume
        else:
            node.sell_volume += volume

        self._total_volume += volume
        self._last_price = price

        # Handle rolling window
        if self.rolling_window:
            self._tick_history.append((bucket_price, volume, is_buy))
            if len(self._tick_history) > self.rolling_window:
                self._remove_oldest_tick()

        # Recalculate periodically
        self._recalc_needed = True
        if self._tick_count % self._recalc_interval == 0:
            self._calculate_levels()

        return self.get_profile(price)

    def _round_to_tick(self, price: float) -> float:
        """Round price to nearest tick size."""
        return round(price / self.tick_size) * self.tick_size

    def _remove_oldest_tick(self) -> None:
        """Remove oldest tick from rolling window."""
        if self._tick_history:
            old_price, old_volume, old_is_buy = self._tick_history.pop(0)
            node = self._volume_map.get(old_price)
            if node:
                node.volume -= old_volume
                node.trade_count -= 1
                if old_is_buy:
                    node.buy_volume -= old_volume
                else:
                    node.sell_volume -= old_volume
                self._total_volume -= old_volume

                # Remove empty nodes
                if node.volume <= 0:
                    del self._volume_map[old_price]

    def _calculate_levels(self) -> None:
        """Calculate POC, VAH, VAL, and nodes."""
        if not self._volume_map or self._total_volume == 0:
            return

        # Sort price levels by volume (descending)
        sorted_nodes = sorted(
            self._volume_map.values(),
            key=lambda n: n.volume,
            reverse=True
        )

        # POC is highest volume price
        self._poc = sorted_nodes[0].price if sorted_nodes else 0.0

        # Calculate Value Area (70% of volume)
        self._calculate_value_area(sorted_nodes)

        self._recalc_needed = False

    def _calculate_value_area(self, sorted_nodes: List[VolumeNode]) -> None:
        """
        Calculate Value Area using TPO-style algorithm.

        Start from POC and expand up/down adding highest adjacent volume
        until 70% of total volume is included.
        """
        if not sorted_nodes:
            return

        target_volume = self._total_volume * self.value_area_percent
        accumulated_volume = 0.0

        # Get all prices sorted
        all_prices = sorted(self._volume_map.keys())
        if not all_prices:
            return

        poc_idx = all_prices.index(self._poc) if self._poc in all_prices else 0

        # Start with POC
        included_indices = {poc_idx}
        accumulated_volume = self._volume_map[self._poc].volume

        low_idx = poc_idx
        high_idx = poc_idx

        while accumulated_volume < target_volume:
            # Look at volume one step above and below
            vol_above = 0.0
            vol_below = 0.0

            if high_idx + 1 < len(all_prices):
                vol_above = self._volume_map[all_prices[high_idx + 1]].volume

            if low_idx - 1 >= 0:
                vol_below = self._volume_map[all_prices[low_idx - 1]].volume

            if vol_above == 0 and vol_below == 0:
                break

            # Add the side with more volume
            if vol_above >= vol_below and high_idx + 1 < len(all_prices):
                high_idx += 1
                accumulated_volume += vol_above
                included_indices.add(high_idx)
            elif low_idx - 1 >= 0:
                low_idx -= 1
                accumulated_volume += vol_below
                included_indices.add(low_idx)
            else:
                break

        self._vah = all_prices[high_idx]
        self._val = all_prices[low_idx]

    def get_profile(self, current_price: float) -> VolumeProfileResult:
        """
        Get complete volume profile analysis.

        Args:
            current_price: Current market price

        Returns:
            VolumeProfileResult with all levels and analysis
        """
        if self._recalc_needed:
            self._calculate_levels()

        # Identify HVN and LVN
        hvn, lvn = self._identify_nodes()

        # Determine price location
        location = self._get_price_location(current_price)

        # Calculate distances
        poc = self._poc if self._poc else current_price
        vah = self._vah if self._vah else current_price
        val = self._val if self._val else current_price

        dist_poc = (current_price - poc) / poc * 100 if poc else 0.0
        dist_vah = (current_price - vah) / vah * 100 if vah else 0.0
        dist_val = (current_price - val) / val * 100 if val else 0.0

        # Find nearest HVN above/below
        hvn_above = None
        hvn_below = None
        for node in hvn:
            if node.price > current_price:
                if hvn_above is None or node.price < hvn_above:
                    hvn_above = node.price
            elif node.price < current_price:
                if hvn_below is None or node.price > hvn_below:
                    hvn_below = node.price

        # Find nearest LVN
        nearest_lvn = None
        min_lvn_dist = float('inf')
        for node in lvn:
            dist = abs(node.price - current_price)
            if dist < min_lvn_dist:
                min_lvn_dist = dist
                nearest_lvn = node.price

        # Price range
        all_prices = list(self._volume_map.keys())
        price_high = max(all_prices) if all_prices else current_price
        price_low = min(all_prices) if all_prices else current_price

        # Value area details
        va_volume = sum(
            n.volume for p, n in self._volume_map.items()
            if val <= p <= vah
        )
        va_percent = va_volume / self._total_volume if self._total_volume else 0.0

        value_area = ValueArea(
            high=vah,
            low=val,
            poc=poc,
            volume=va_volume,
            volume_percent=va_percent,
        )

        return VolumeProfileResult(
            poc=poc,
            poc_volume=self._volume_map.get(self._round_to_tick(poc), VolumeNode(0, 0)).volume,
            vah=vah,
            val=val,
            value_area=value_area,
            high_volume_nodes=hvn,
            low_volume_nodes=lvn,
            total_volume=self._total_volume,
            price_range_high=price_high,
            price_range_low=price_low,
            current_location=location,
            distance_to_poc=dist_poc,
            distance_to_vah=dist_vah,
            distance_to_val=dist_val,
            nearest_hvn_above=hvn_above,
            nearest_hvn_below=hvn_below,
            nearest_lvn=nearest_lvn,
        )

    def _identify_nodes(self) -> Tuple[List[VolumeNode], List[VolumeNode]]:
        """Identify High Volume Nodes and Low Volume Nodes."""
        if not self._volume_map or self._total_volume == 0:
            return [], []

        # Calculate average volume per level
        avg_volume = self._total_volume / len(self._volume_map)

        hvn_threshold = avg_volume * self.hvn_threshold
        lvn_threshold = avg_volume * self.lvn_threshold

        hvn = []
        lvn = []

        for price, node in self._volume_map.items():
            if node.volume >= hvn_threshold:
                hvn.append(node)
            elif node.volume <= lvn_threshold and node.volume > 0:
                lvn.append(node)

        # Sort HVN by volume (highest first)
        hvn.sort(key=lambda n: n.volume, reverse=True)

        # Sort LVN by price
        lvn.sort(key=lambda n: n.price)

        return hvn, lvn

    def _get_price_location(self, price: float) -> PriceLocation:
        """Determine price location relative to value area."""
        if not self._poc:
            return PriceLocation.INSIDE_VA

        poc_tolerance = self.tick_size * 2
        vah_tolerance = self.tick_size * 2
        val_tolerance = self.tick_size * 2

        if abs(price - self._poc) <= poc_tolerance:
            return PriceLocation.AT_POC
        elif abs(price - self._vah) <= vah_tolerance:
            return PriceLocation.AT_VAH
        elif abs(price - self._val) <= val_tolerance:
            return PriceLocation.AT_VAL
        elif price > self._vah:
            return PriceLocation.ABOVE_VA
        elif price < self._val:
            return PriceLocation.BELOW_VA
        else:
            return PriceLocation.INSIDE_VA

    def get_trading_signal(self, current_price: float) -> Dict[str, any]:
        """
        Get trading signal based on volume profile.

        Returns signal with:
        - direction: 'long', 'short', or 'neutral'
        - strength: 0-1
        - reason: explanation
        - key_levels: nearby S/R levels
        """
        profile = self.get_profile(current_price)
        location = profile.current_location

        signal = 0.0
        strength = 0.0
        reason = ""
        bias = "neutral"

        if location == PriceLocation.BELOW_VA:
            # Below value - looking for long entries back to VA
            signal = 0.5
            strength = min(1.0, abs(profile.distance_to_val) / 2)
            reason = "Price below value area - potential long to VAL"
            bias = "long"

        elif location == PriceLocation.AT_VAL:
            # At value area low - support test
            signal = 0.3
            strength = 0.6
            reason = "Testing VAL support"
            bias = "long"

        elif location == PriceLocation.ABOVE_VA:
            # Above value - looking for short entries back to VA
            signal = -0.5
            strength = min(1.0, abs(profile.distance_to_vah) / 2)
            reason = "Price above value area - potential short to VAH"
            bias = "short"

        elif location == PriceLocation.AT_VAH:
            # At value area high - resistance test
            signal = -0.3
            strength = 0.6
            reason = "Testing VAH resistance"
            bias = "short"

        elif location == PriceLocation.AT_POC:
            # At POC - fair value, neutral
            signal = 0.0
            strength = 0.3
            reason = "At POC - fair value"
            bias = "neutral"

        elif location == PriceLocation.INSIDE_VA:
            # Inside value area - trade with trend
            if profile.distance_to_poc > 0:
                signal = 0.1  # Slightly bullish above POC
                reason = "Inside VA, above POC"
            else:
                signal = -0.1  # Slightly bearish below POC
                reason = "Inside VA, below POC"
            strength = 0.4
            bias = "neutral"

        # Adjust for nearby HVN (support/resistance)
        if profile.nearest_hvn_above and abs(current_price - profile.nearest_hvn_above) / current_price < 0.005:
            signal -= 0.2
            reason += f" | HVN resistance at {profile.nearest_hvn_above:.2f}"

        if profile.nearest_hvn_below and abs(current_price - profile.nearest_hvn_below) / current_price < 0.005:
            signal += 0.2
            reason += f" | HVN support at {profile.nearest_hvn_below:.2f}"

        # LVN nearby suggests fast move potential
        if profile.nearest_lvn and abs(current_price - profile.nearest_lvn) / current_price < 0.003:
            strength *= 1.3  # Increase strength for LVN breakout
            reason += " | LVN nearby (fast move zone)"

        return {
            "signal": max(-1.0, min(1.0, signal)),
            "strength": min(1.0, strength),
            "bias": bias,
            "reason": reason,
            "location": location.value,
            "poc": profile.poc,
            "vah": profile.vah,
            "val": profile.val,
            "distance_to_poc_pct": profile.distance_to_poc,
            "hvn_above": profile.nearest_hvn_above,
            "hvn_below": profile.nearest_hvn_below,
            "lvn_nearby": profile.nearest_lvn,
        }

    def reset(self) -> None:
        """Reset profile (for new session)."""
        self._volume_map.clear()
        self._tick_history.clear()
        self._poc = 0.0
        self._vah = 0.0
        self._val = 0.0
        self._last_price = None
        self._total_volume = 0.0
        self._recalc_needed = True
        self._tick_count = 0

    def get_volume_at_price(self, price: float) -> float:
        """Get volume at specific price level."""
        bucket = self._round_to_tick(price)
        node = self._volume_map.get(bucket)
        return node.volume if node else 0.0

    def get_delta_at_price(self, price: float) -> float:
        """Get buy-sell delta at specific price level."""
        bucket = self._round_to_tick(price)
        node = self._volume_map.get(bucket)
        return node.delta if node else 0.0


class SessionVolumeProfile(VolumeProfile):
    """
    Session-based volume profile that resets daily.

    Extends VolumeProfile with:
    - Session boundaries
    - Developing POC tracking
    - Initial Balance (first hour) tracking
    """

    def __init__(
        self,
        tick_size: float = 0.01,
        value_area_percent: float = 0.70,
        initial_balance_ticks: int = 3600,  # First hour in ticks (approx)
    ):
        super().__init__(tick_size=tick_size, value_area_percent=value_area_percent)
        self.initial_balance_ticks = initial_balance_ticks
        self._ib_high: float = 0.0
        self._ib_low: float = float('inf')
        self._ib_complete: bool = False
        self._developing_poc_history: List[float] = []

    def update(
        self,
        price: float,
        volume: float = 1.0,
        is_buy: Optional[bool] = None,
    ) -> VolumeProfileResult:
        """Update with tick and track Initial Balance."""
        result = super().update(price, volume, is_buy)

        # Track Initial Balance
        if not self._ib_complete:
            self._ib_high = max(self._ib_high, price)
            self._ib_low = min(self._ib_low, price)

            if self._tick_count >= self.initial_balance_ticks:
                self._ib_complete = True

        # Track developing POC
        if self._tick_count % 100 == 0:
            self._developing_poc_history.append(self._poc)

        return result

    @property
    def initial_balance_high(self) -> float:
        """Get Initial Balance high."""
        return self._ib_high

    @property
    def initial_balance_low(self) -> float:
        """Get Initial Balance low."""
        return self._ib_low if self._ib_low != float('inf') else 0.0

    @property
    def is_initial_balance_complete(self) -> bool:
        """Check if Initial Balance period is complete."""
        return self._ib_complete

    def new_session(self) -> None:
        """Start new trading session."""
        self.reset()
        self._ib_high = 0.0
        self._ib_low = float('inf')
        self._ib_complete = False
        self._developing_poc_history.clear()
