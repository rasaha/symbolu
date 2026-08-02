"""COMPATIBILITY-ONLY legacy namespace for the Model Selection product core.

Canonical package: ``ugence_model_selection`` (distribution ``ugence-model-selection``).
Model Selection is the deterministic policy capability that evaluates already-approved
model/provider candidates against mandatory eligibility constraints and policy-weighted
optimization criteria, then returns a policy-bounded selection or a no-eligible-model
outcome. It owns the two audited stages — **ExecutionGate** (eligibility) and
**ModelPolicy** (selection) — and NO model invocation, routing, retry, failover, load
balancing, action authorization, provider registration, or credential management.

The Model-Selection **product core** modules (``gate``, ``policy``, ``states``,
``model``, ``registry``, ``reason_codes``) no longer live here — they were moved,
verbatim, into the canonical package. This module makes the legacy dotted names
(``execution_gate.gate``, ``execution_gate.model`` …) resolve to the *same objects* in
the canonical package (object identity preserved), so existing
``import execution_gate...`` / ``from execution_gate... import ...`` statements keep
working unchanged — identical serialization, hashes, errors, and behavior. No product
business logic lives here.

The **research** modules that remain physically in this namespace (``harness``,
``baselines``, ``scenarios``, ``common_io``) are the capability's local evaluation
harness. They are NOT the product core; they are consumers of it (they import the
aliased product modules above). The frozen replay tree ``execution_gate/frozen/replay_v1``
is self-contained evidence and is untouched.

Mechanism: an explicit, eager alias of the canonical product submodules into
``sys.modules`` under the legacy dotted names — NOT a meta-path import hook. Aliasing an
already-imported module object never re-executes it, so no extra import side effects are
introduced beyond importing the canonical package once.
"""
from __future__ import annotations


def _ensure_canonical_core_importable() -> None:
    """Source-checkout bootstrap: put ``packages/capabilities/model-selection/src`` on
    ``sys.path`` only when the canonical package is not already importable. Installed as
    a wheel it is already importable and this is a no-op; only a bare source checkout
    needs it. No other effect.
    """
    import importlib.util

    if importlib.util.find_spec("ugence_model_selection") is not None:
        return
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "packages" / "capabilities" / "model-selection" / "src"
        if (cand / "ugence_model_selection" / "__init__.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            return


_ensure_canonical_core_importable()

import importlib as _il  # noqa: E402
import sys as _sys  # noqa: E402

import ugence_model_selection as _canon  # noqa: E402

# The Model-Selection product-core submodules to alias (leaf → identical objects under
# the legacy dotted names). The research modules (harness/baselines/scenarios/common_io)
# are NOT listed: they remain real files in this namespace and load normally.
_CORE_SUBMODULES = ("reason_codes", "states", "model", "gate", "policy", "registry")

for _name in _CORE_SUBMODULES:
    _mod = _il.import_module(f"{_canon.__name__}.{_name}")
    _sys.modules[f"{__name__}.{_name}"] = _mod  # identity: same object as canonical
    setattr(_sys.modules[__name__], _name, _mod)  # attribute access after ``import execution_gate``

# Curated top-level re-export (identity preserved) — mirror the canonical package.
from ugence_model_selection import __version__  # noqa: E402,F401

__all__ = ["__version__"]
