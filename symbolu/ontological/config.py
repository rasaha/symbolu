#!/usr/bin/env python3
"""
Ontological Engine Configuration
================================

Central configuration for switching between ontological engines.
Only ONE engine can be active at a time.

Usage:
------
    # Option 1: Environment variable
    export SYMBOLU_ENGINE=symbolu12_llm_bhava

    # Option 2: Python configuration
    from symbolu.ontological.config import config, EngineSwitch

    config.set_engine(EngineSwitch.SYMBOLU12_LLM_BHAVA)

    # Option 3: Context manager (temporary switch)
    with config.use_engine(EngineSwitch.MINILM_V2):
        engine = config.get_engine()
        result = engine.analyze("text")

    # Get the currently active engine
    engine = config.get_engine()
    result = engine.analyze("What is consciousness?")
"""

import os
from enum import Enum
from typing import Optional, Any
from contextlib import contextmanager


class EngineSwitch(Enum):
    """Available engine configurations."""

    # Enterprise (Classification + RAG)
    MINILM_V2 = "minilm_v2"
    """MiniLM-based, 156D output, best for RAG"""

    SYMBOLU12_HYBRID = "symbolu12_hybrid"
    """MiniLM encoder + SymbolU12 layers"""

    # Generative (LLM)
    SYMBOLU12_LLM = "symbolu12_llm"
    """Full 12-layer transformer, token generation"""

    SYMBOLU12_LLM_BHAVA = "symbolu12_llm_bhava"
    """Full LLM with Vedic Bhava relationships"""

    # CPU-Friendly
    SYMBOLU12_OPTIMIZED_BHAVA = "symbolu12_optimized_bhava"
    """CPU-friendly 256D with Bhava"""

    SYMBOLU12_TINY_BHAVA = "symbolu12_tiny_bhava"
    """Smallest model for edge devices"""


# Default engine profiles
ENGINE_PROFILES = {
    "enterprise": EngineSwitch.MINILM_V2,
    "hybrid": EngineSwitch.SYMBOLU12_HYBRID,
    "generative": EngineSwitch.SYMBOLU12_LLM_BHAVA,
    "cpu": EngineSwitch.SYMBOLU12_OPTIMIZED_BHAVA,
    "edge": EngineSwitch.SYMBOLU12_TINY_BHAVA,
}


class OntologicalConfig:
    """
    Singleton configuration manager for ontological engines.

    Ensures only ONE engine is active at a time.
    """

    _instance = None
    _engine_cache = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize configuration from environment or defaults."""
        self._active_engine: EngineSwitch = EngineSwitch.MINILM_V2
        self._engine_instance = None
        self._load_from_env()

    def _load_from_env(self):
        """Load configuration from environment variables."""
        env_engine = os.environ.get("SYMBOLU_ENGINE")
        if env_engine:
            try:
                self._active_engine = EngineSwitch(env_engine.lower())
            except ValueError:
                # Try profile name
                if env_engine.lower() in ENGINE_PROFILES:
                    self._active_engine = ENGINE_PROFILES[env_engine.lower()]
                else:
                    print(f"Warning: Unknown engine '{env_engine}', using default")

    @property
    def active_engine(self) -> EngineSwitch:
        """Get the currently active engine type."""
        return self._active_engine

    @property
    def active_engine_name(self) -> str:
        """Get the name of the currently active engine."""
        return self._active_engine.value

    def set_engine(self, engine: EngineSwitch) -> None:
        """
        Switch to a different engine.

        Args:
            engine: The engine to activate

        Note:
            This invalidates any cached engine instance.
        """
        if engine != self._active_engine:
            self._active_engine = engine
            self._engine_instance = None  # Clear cache
            print(f"Switched to engine: {engine.value}")

    def set_profile(self, profile: str) -> None:
        """
        Set engine by profile name.

        Profiles:
            - "enterprise": MiniLM V2 (RAG, classification)
            - "hybrid": MiniLM + SymbolU12 layers
            - "generative": Full LLM with Bhava
            - "cpu": Optimized for CPU
            - "edge": Tiny model for IoT
        """
        if profile.lower() not in ENGINE_PROFILES:
            raise ValueError(f"Unknown profile: {profile}. Available: {list(ENGINE_PROFILES.keys())}")
        self.set_engine(ENGINE_PROFILES[profile.lower()])

    def get_engine(self) -> Any:
        """
        Get the currently active engine instance.

        Returns:
            The active ontological engine (cached)
        """
        if self._engine_instance is None:
            self._engine_instance = self._create_engine()
        return self._engine_instance

    def _create_engine(self) -> Any:
        """Create engine instance based on current configuration."""
        from symbolu.ontological.engine_factory import (
            create_ontological_engine,
            OntologicalEngineType,
        )

        # Map EngineSwitch to OntologicalEngineType
        type_map = {
            EngineSwitch.MINILM_V2: OntologicalEngineType.MINILM_V2,
            EngineSwitch.SYMBOLU12_HYBRID: OntologicalEngineType.SYMBOLU12_HYBRID,
            EngineSwitch.SYMBOLU12_LLM: OntologicalEngineType.SYMBOLU12_LLM,
            EngineSwitch.SYMBOLU12_LLM_BHAVA: OntologicalEngineType.SYMBOLU12_LLM_BHAVA,
            EngineSwitch.SYMBOLU12_OPTIMIZED_BHAVA: OntologicalEngineType.SYMBOLU12_OPTIMIZED_BHAVA,
            EngineSwitch.SYMBOLU12_TINY_BHAVA: OntologicalEngineType.SYMBOLU12_TINY_BHAVA,
        }

        engine_type = type_map[self._active_engine]
        return create_ontological_engine(engine_type)

    @contextmanager
    def use_engine(self, engine: EngineSwitch):
        """
        Context manager for temporarily switching engines.

        Usage:
            with config.use_engine(EngineSwitch.SYMBOLU12_LLM_BHAVA):
                result = config.get_engine().analyze("text")
            # Automatically switches back after context
        """
        previous = self._active_engine
        previous_instance = self._engine_instance
        try:
            self._active_engine = engine
            self._engine_instance = None
            yield self.get_engine()
        finally:
            self._active_engine = previous
            self._engine_instance = previous_instance

    def info(self) -> dict:
        """Get information about current configuration."""
        return {
            "active_engine": self._active_engine.value,
            "profile": next(
                (k for k, v in ENGINE_PROFILES.items() if v == self._active_engine),
                "custom"
            ),
            "available_engines": [e.value for e in EngineSwitch],
            "available_profiles": list(ENGINE_PROFILES.keys()),
            "env_var": "SYMBOLU_ENGINE",
        }

    def __repr__(self) -> str:
        return f"OntologicalConfig(active={self._active_engine.value})"


# Global singleton instance
config = OntologicalConfig()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_engine() -> Any:
    """Get the currently configured engine."""
    return config.get_engine()


def set_engine(engine: EngineSwitch) -> None:
    """Set the active engine."""
    config.set_engine(engine)


def set_profile(profile: str) -> None:
    """Set engine by profile name."""
    config.set_profile(profile)


def analyze(text: str) -> dict:
    """Analyze text with the currently configured engine."""
    return config.get_engine().analyze(text)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("   SYMBOLU ENGINE CONFIGURATION")
    print("=" * 60)

    info = config.info()

    print(f"\nActive Engine: {info['active_engine']}")
    print(f"Profile: {info['profile']}")
    print(f"Environment Variable: {info['env_var']}")

    print("\nAvailable Engines:")
    for engine in EngineSwitch:
        marker = " [ACTIVE]" if engine == config.active_engine else ""
        print(f"  - {engine.value}{marker}")

    print("\nProfiles:")
    for name, engine in ENGINE_PROFILES.items():
        marker = " [ACTIVE]" if engine == config.active_engine else ""
        print(f"  - {name}: {engine.value}{marker}")

    print("\nUsage Examples:")
    print("""
    # Environment variable:
    export SYMBOLU_ENGINE=symbolu12_llm_bhava

    # Python:
    from symbolu.ontological.config import config, EngineSwitch

    # Switch engine
    config.set_engine(EngineSwitch.SYMBOLU12_LLM_BHAVA)

    # Or use profile
    config.set_profile("generative")

    # Get engine and use
    engine = config.get_engine()
    result = engine.analyze("What is consciousness?")

    # Temporary switch
    with config.use_engine(EngineSwitch.MINILM_V2):
        result = config.get_engine().analyze("text")
    """)
