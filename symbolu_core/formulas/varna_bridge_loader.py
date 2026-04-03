"""
Varna Bridge Loader - LEGACY MODULE
====================================

WARNING: EXPERIMENT_ONLY = True

This file MUST NOT be used as ontology source of truth.

DEPRECATION NOTICE:
    This loader is a LEGACY module from before Phase-4A was established.
    For production ontology access, use:
        from agentic.ontology.phase4a import lookup_interaction, get_varna_info

AUTHORITATIVE SOURCE:
    - Ontology executor: symbolu.ontology.phase4a (Phase-4A)
    - Frozen data: docs/data/*.json

This module loads data from:
    /docs/data/varna_bridge_map_v1.json

HARD CONSTRAINTS (NON-NEGOTIABLE):
    - NO heuristics
    - NO inferred mappings
    - NO guessing
    - NO fallback defaults
    - NO re-interpretation of data
    - Use ONLY varna_bridge_map_v1.json
    - Treat it as authoritative
    - Fail closed if any required mapping is missing

ERROR CODES:
    - VARNA_MAPPING_NOT_FOUND: Raised when a requested varna is not in the JSON
    - VARNA_DATA_NOT_LOADED: Raised when JSON file cannot be loaded

Version: 1.0.0 (Legacy - prefer Phase-4A)
Date: 2025-12-17
"""

# EXPERIMENT_ONLY marker — this loader is NOT the authoritative ontology executor
EXPERIMENT_ONLY = True

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, FrozenSet, List


# ============================================================================
# ERROR CLASS - FAIL CLOSED
# ============================================================================

class VarnaMappingNotFoundError(KeyError):
    """
    Raised when a varna mapping is not found in the ground-truth data.

    This is a FAIL-CLOSED error - the system must not proceed with
    missing mappings. No defaults, no guesses, no fallbacks.
    """
    def __init__(self, varna: str):
        self.varna = varna
        super().__init__(f"VARNA_MAPPING_NOT_FOUND: '{varna}' is not in varna_bridge_map_v1.json")


class VarnaDataNotLoadedError(RuntimeError):
    """
    Raised when the ground-truth JSON file cannot be loaded.

    This is a FATAL error - the system cannot operate without
    the authoritative data source.
    """
    def __init__(self, path: Path, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"VARNA_DATA_NOT_LOADED: Cannot load {path}: {reason}")


# ============================================================================
# DATA CLASS - VARNA ENTRY
# ============================================================================

@dataclass(frozen=True)
class VarnaEntry:
    """
    A single varna entry from the ground-truth JSON.

    All fields come DIRECTLY from varna_bridge_map_v1.json.
    No derived or computed fields.

    Attributes:
        symbol: The varna symbol (e.g., "sa", "a", "kha")
        type: "vowel" or "consonant"
        bridge_meaning: The bridge meaning identifier
        aspirated: True if aspirated consonant, False otherwise
        varna_group: Varna group for consonants (e.g., "ka_varga", "sibilant")
    """
    symbol: str
    type: str
    bridge_meaning: str
    aspirated: bool
    varna_group: Optional[str]

    @property
    def is_vowel(self) -> bool:
        """True if this is a vowel."""
        return self.type == "vowel"

    @property
    def is_consonant(self) -> bool:
        """True if this is a consonant."""
        return self.type == "consonant"


# ============================================================================
# VARNA BRIDGE LOADER - SINGLETON
# ============================================================================

class VarnaBridgeLoader:
    """
    Ground-truth data loader for varna bridge mappings.

    This class provides the SOLE authoritative access to varna data.
    All lookups are from the JSON file - no heuristics, no defaults.

    Usage:
        loader = VarnaBridgeLoader()
        entry = loader.lookup("sa")  # Returns VarnaEntry or raises error

        # Or use the singleton
        entry = get_varna_entry("sa")
    """

    _instance: Optional["VarnaBridgeLoader"] = None

    def __new__(cls, json_path: Optional[Path] = None) -> "VarnaBridgeLoader":
        """Singleton pattern - only one loader instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, json_path: Optional[Path] = None):
        """
        Initialize the loader with the ground-truth JSON.

        Args:
            json_path: Optional path to JSON file. Defaults to canonical location.
        """
        if self._initialized:
            return

        # Resolve path to ground-truth JSON
        if json_path is None:
            # Canonical location: /docs/data/varna_bridge_map_v1.json
            # Relative to this file's location
            module_dir = Path(__file__).parent
            repo_root = module_dir.parent.parent
            json_path = repo_root / "docs" / "data" / "varna_bridge_map_v1.json"

        self._json_path = json_path
        self._data: Dict[str, Any] = {}
        self._entries: Dict[str, VarnaEntry] = {}
        self._vowel_symbols: FrozenSet[str] = frozenset()
        self._consonant_symbols: FrozenSet[str] = frozenset()
        self._all_symbols: FrozenSet[str] = frozenset()
        self._meta: Dict[str, Any] = {}

        self._load()
        self._initialized = True

    def _load(self) -> None:
        """Load and parse the ground-truth JSON file."""
        if not self._json_path.exists():
            raise VarnaDataNotLoadedError(
                self._json_path,
                "File does not exist"
            )

        try:
            with open(self._json_path, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        except json.JSONDecodeError as e:
            raise VarnaDataNotLoadedError(
                self._json_path,
                f"Invalid JSON: {e}"
            )
        except IOError as e:
            raise VarnaDataNotLoadedError(
                self._json_path,
                f"IO error: {e}"
            )

        # Store metadata
        self._meta = self._data.get("meta", {})

        # Build entries from vowels
        vowels = self._data.get("vowels", {})
        vowel_symbols = set()
        for symbol, info in vowels.items():
            entry = VarnaEntry(
                symbol=symbol,
                type=info.get("type", "vowel"),
                bridge_meaning=info.get("bridge_meaning", ""),
                aspirated=False,  # Vowels are never aspirated
                varna_group=None,
            )
            self._entries[symbol] = entry
            vowel_symbols.add(symbol)
        self._vowel_symbols = frozenset(vowel_symbols)

        # Build entries from consonants
        consonants = self._data.get("consonants", {})
        consonant_symbols = set()
        for symbol, info in consonants.items():
            entry = VarnaEntry(
                symbol=symbol,
                type=info.get("type", "consonant"),
                bridge_meaning=info.get("bridge_meaning", ""),
                aspirated=info.get("aspirated", False),
                varna_group=info.get("varna_group"),
            )
            self._entries[symbol] = entry
            consonant_symbols.add(symbol)
        self._consonant_symbols = frozenset(consonant_symbols)

        # Build all symbols
        self._all_symbols = self._vowel_symbols | self._consonant_symbols

    def lookup(self, varna: str, *, strict: bool = True) -> Optional[VarnaEntry]:
        """
        Look up a varna by symbol.

        Args:
            varna: The varna symbol to look up
            strict: If True (default), raises VarnaMappingNotFoundError if not found.
                    If False, returns None if not found.

        Returns:
            VarnaEntry if found

        Raises:
            VarnaMappingNotFoundError: If strict=True and varna not in data
        """
        entry = self._entries.get(varna)
        if entry is None and strict:
            raise VarnaMappingNotFoundError(varna)
        return entry

    def get_bridge_meaning(self, varna: str) -> str:
        """
        Get the bridge meaning for a varna.

        FAIL-CLOSED: Raises error if varna not found.

        Args:
            varna: The varna symbol

        Returns:
            Bridge meaning string

        Raises:
            VarnaMappingNotFoundError: If varna not in data
        """
        entry = self.lookup(varna, strict=True)
        return entry.bridge_meaning

    def is_vowel(self, varna: str) -> bool:
        """
        Check if varna is a vowel.

        Returns False for unknown varnas (does not raise error).
        """
        return varna in self._vowel_symbols

    def is_consonant(self, varna: str) -> bool:
        """
        Check if varna is a consonant.

        Returns False for unknown varnas (does not raise error).
        """
        return varna in self._consonant_symbols

    def is_aspirated(self, varna: str) -> bool:
        """
        Check if consonant is aspirated.

        Returns False for unknown varnas (does not raise error).
        """
        entry = self._entries.get(varna)
        return entry.aspirated if entry else False

    def is_known(self, varna: str) -> bool:
        """Check if varna is in the ground-truth data."""
        return varna in self._all_symbols

    @property
    def vowel_symbols(self) -> FrozenSet[str]:
        """Get all vowel symbols from ground-truth."""
        return self._vowel_symbols

    @property
    def consonant_symbols(self) -> FrozenSet[str]:
        """Get all consonant symbols from ground-truth."""
        return self._consonant_symbols

    @property
    def all_symbols(self) -> FrozenSet[str]:
        """Get all varna symbols from ground-truth."""
        return self._all_symbols

    @property
    def meta(self) -> Dict[str, Any]:
        """Get metadata from ground-truth JSON."""
        return self._meta

    def get_symbols_sorted_by_length(self) -> List[str]:
        """
        Get all symbols sorted by length (longest first).

        Useful for greedy matching algorithms.
        """
        return sorted(self._all_symbols, key=len, reverse=True)


# ============================================================================
# MODULE-LEVEL SINGLETON ACCESS
# ============================================================================

_loader: Optional[VarnaBridgeLoader] = None


def _get_loader() -> VarnaBridgeLoader:
    """Get or create the singleton loader instance."""
    global _loader
    if _loader is None:
        _loader = VarnaBridgeLoader()
    return _loader


def get_varna_entry(varna: str, *, strict: bool = True) -> Optional[VarnaEntry]:
    """
    Look up a varna entry from ground-truth data.

    Args:
        varna: The varna symbol to look up
        strict: If True (default), raises error if not found

    Returns:
        VarnaEntry if found

    Raises:
        VarnaMappingNotFoundError: If strict=True and varna not found
    """
    return _get_loader().lookup(varna, strict=strict)


def get_bridge_meaning(varna: str) -> str:
    """
    Get bridge meaning for a varna from ground-truth data.

    FAIL-CLOSED: Raises error if varna not found.

    Args:
        varna: The varna symbol

    Returns:
        Bridge meaning string

    Raises:
        VarnaMappingNotFoundError: If varna not in ground-truth
    """
    return _get_loader().get_bridge_meaning(varna)


def is_known_varna(varna: str) -> bool:
    """Check if varna is in ground-truth data."""
    return _get_loader().is_known(varna)


def is_vowel(varna: str) -> bool:
    """Check if varna is a vowel (from ground-truth)."""
    return _get_loader().is_vowel(varna)


def is_consonant(varna: str) -> bool:
    """Check if varna is a consonant (from ground-truth)."""
    return _get_loader().is_consonant(varna)


def is_aspirated(varna: str) -> bool:
    """Check if consonant is aspirated (from ground-truth)."""
    return _get_loader().is_aspirated(varna)


def get_all_symbols() -> FrozenSet[str]:
    """Get all varna symbols from ground-truth."""
    return _get_loader().all_symbols


def get_vowel_symbols() -> FrozenSet[str]:
    """Get all vowel symbols from ground-truth."""
    return _get_loader().vowel_symbols


def get_consonant_symbols() -> FrozenSet[str]:
    """Get all consonant symbols from ground-truth."""
    return _get_loader().consonant_symbols


def get_symbols_sorted_by_length() -> List[str]:
    """Get all symbols sorted by length (longest first)."""
    return _get_loader().get_symbols_sorted_by_length()


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_ground_truth_loaded() -> bool:
    """
    Validate that ground-truth data is loaded correctly.

    Raises:
        VarnaDataNotLoadedError: If data cannot be loaded
    """
    loader = _get_loader()

    # Check required structure
    if not loader.vowel_symbols:
        raise VarnaDataNotLoadedError(
            loader._json_path,
            "No vowels found in ground-truth data"
        )
    if not loader.consonant_symbols:
        raise VarnaDataNotLoadedError(
            loader._json_path,
            "No consonants found in ground-truth data"
        )

    # Check required vowels
    required_vowels = {"a", "e", "i", "o", "u"}
    missing_vowels = required_vowels - loader.vowel_symbols
    if missing_vowels:
        raise VarnaDataNotLoadedError(
            loader._json_path,
            f"Missing required vowels: {missing_vowels}"
        )

    return True


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Error classes
    "VarnaMappingNotFoundError",
    "VarnaDataNotLoadedError",
    # Data class
    "VarnaEntry",
    # Loader class
    "VarnaBridgeLoader",
    # Module-level functions
    "get_varna_entry",
    "get_bridge_meaning",
    "is_known_varna",
    "is_vowel",
    "is_consonant",
    "is_aspirated",
    "get_all_symbols",
    "get_vowel_symbols",
    "get_consonant_symbols",
    "get_symbols_sorted_by_length",
    # Validation
    "validate_ground_truth_loaded",
]
