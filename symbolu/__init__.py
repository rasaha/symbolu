"""
Symbolu — Backwards-compatibility shim.

This package redirects imports to their new locations:
  - symbolu_core/   (SUPPLY modules: formulas, mechanical, resonance, etc.)
  - agentic/        (CORE + INTEGRATE: agentic_framework, safety, policy, etc.)
  - symbolu_extensions/ (INDEPENDENT: vision, voice, intent, phases, etc.)
  - symbolu_training/   (TRAINING: training, jepa, losses, etc.)

New code should import directly from the target package.
This shim exists only for backwards compatibility.
"""
import importlib
import sys

# Mapping of submodule names to their new package locations
_ROUTING = {
    # SUPPLY → symbolu_core
    "formulas": "symbolu_core",
    "ontological": "symbolu_core",
    "resonance": "symbolu_core",
    "name_resonance": "symbolu_core",
    "ppv": "symbolu_core",
    "rag": "symbolu_core",
    "service": "symbolu_core",
    "orchestration": "symbolu_core",
    "presentation": "symbolu_core",
    "renderer": "symbolu_core",
    "providers": "symbolu_core",
    "licensing": "symbolu_core",
    "adapter": "symbolu_core",
    "common": "symbolu_core",
    "mechanical": "symbolu_core",
    "hybrid": "symbolu_core",
    "engine": "symbolu_core",
    # STANDALONE PRODUCT → top-level package (same name)
    "cloud_controller": "",  # empty = top-level, no prefix needed
    "phase_transformer": "symbolu_core",
    "config": "symbolu_core",
    "inference_rag": "symbolu_core",
    # CORE + INTEGRATE → agentic
    "agentic_framework": "agentic",
    "safety": "agentic",
    "policy": "agentic",
    "posture": "agentic",
    "ledger": "agentic",
    "entropy": "agentic",
    "core": "agentic",
    "identity": "agentic",
    "motivation": "agentic",
    "sovereign": "agentic",
    "inference": "agentic",
    "chitta_vritti": "agentic",
    "temporal": "agentic",
    "guna_modulation": "agentic",
    "dha": "agentic",
    "llm": "agentic",
    "api": "agentic",
    "tools": "agentic",
    "dynamics": "agentic",
    "ontology": "agentic",
    "experiments": "agentic",
    # INDEPENDENT → symbolu_extensions
    "vision": "symbolu_extensions",
    "voice": "symbolu_extensions",
    "image_gen": "symbolu_extensions",
    "benchmarks": "symbolu_extensions",
    "experimental": "symbolu_extensions",
    "intent": "symbolu_extensions",
    "phases": "symbolu_extensions",
    # TRAINING → symbolu_training
    "training": "symbolu_training",
    "jepa": "symbolu_training",
    "losses": "symbolu_training",
    "diagnostics": "symbolu_training",
    "monitors": "symbolu_training",
}


class _SymboluFinder:
    """
    Meta-path finder that redirects symbolu.X imports to the correct package.
    """

    @classmethod
    def find_module(cls, fullname, path=None):
        if fullname.startswith("symbolu."):
            parts = fullname.split(".", 2)
            submod = parts[1] if len(parts) > 1 else None
            if submod in _ROUTING:
                return cls
        return None

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        # Modern import machinery (and pytest) call find_spec directly on
        # meta_path finders. Only claim modules that are actually routed;
        # returning None lets the normal path-based finder resolve real
        # subpackages such as ``symbolu.lightweight_phase``.
        if fullname.startswith("symbolu."):
            parts = fullname.split(".", 2)
            submod = parts[1] if len(parts) > 1 else None
            if submod in _ROUTING:
                import importlib.util

                return importlib.util.spec_from_loader(fullname, cls)
        return None

    @classmethod
    def create_module(cls, spec):
        # load_module caches under the symbolu.* name and returns the real module.
        return cls.load_module(spec.name)

    @classmethod
    def exec_module(cls, module):  # module already fully initialized by load_module
        return None

    @classmethod
    def load_module(cls, fullname):
        if fullname in sys.modules:
            return sys.modules[fullname]

        parts = fullname.split(".", 2)
        submod = parts[1]
        target_pkg = _ROUTING[submod]

        # Build the target module name
        # symbolu.X.Y.Z -> target_pkg.X.Y.Z
        # If target_pkg is empty, the module is top-level: symbolu.X.Y -> X.Y
        remainder = ".".join(parts[1:])
        if target_pkg:
            target_name = f"{target_pkg}.{remainder}"
        else:
            target_name = remainder

        # Import the real module
        real_module = importlib.import_module(target_name)

        # Cache under the symbolu.* name too
        sys.modules[fullname] = real_module
        return real_module


# Install the finder
if not any(isinstance(f, type) and f is _SymboluFinder for f in sys.meta_path):
    sys.meta_path.insert(0, _SymboluFinder)
