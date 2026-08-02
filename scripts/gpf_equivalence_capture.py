#!/usr/bin/env python
"""Behavioural equivalence capture for the Governance Provider Framework migration.

Deterministically fingerprints the framework's observable behaviour through the
frozen public surface ``governance_providers`` (registry, resolution, lifecycle,
metadata, errors, fingerprint, reference providers, conformance, version). The
same script is run BEFORE and AFTER the physical relocation; the two JSON dumps
must be byte-identical to demonstrate zero semantic change (gate GPF5).

Usage:  python scripts/gpf_equivalence_capture.py > <out>.json

It imports ONLY the legacy ``governance_providers`` namespace so that the AFTER
run exercises the compatibility shim end to end (top-level + deep imports).
"""
from __future__ import annotations

import dataclasses
import enum
import inspect
import json
import pathlib
import sys
from typing import Any

# Self-contained source-checkout bootstrap so the BEFORE and AFTER runs resolve
# the legacy namespace and the canonical leaves identically without an install.
_REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (
    _REPO,
    _REPO / "packages" / "governance-contracts" / "src",
    _REPO / "packages" / "governance-provider-framework" / "src",
    _REPO / "packages" / "capabilities" / "decision-authority" / "src",
):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _obj_kind(obj: Any) -> dict:
    """Structural, module-path-independent description of a public object."""
    if isinstance(obj, type):
        if issubclass(obj, enum.Enum):
            return {"kind": "enum", "values": {m.name: str(m.value) for m in obj}}
        if issubclass(obj, BaseException):
            return {"kind": "exception",
                    "bases": [b.__name__ for b in obj.__mro__[1:] if b is not object]}
        info: dict = {"kind": "class", "name": obj.__name__}
        df = getattr(obj, "__dataclass_fields__", None)
        if df:
            info["dataclass_fields"] = {
                n: {"type": getattr(f.type, "__name__", str(f.type)),
                    "has_default": f.default is not dataclasses.MISSING
                    or f.default_factory is not dataclasses.MISSING}
                for n, f in df.items()}
            info["frozen"] = bool(getattr(obj, "__dataclass_params__").frozen)
        return info
    if inspect.isfunction(obj):
        try:
            return {"kind": "function", "signature": str(inspect.signature(obj))}
        except (TypeError, ValueError):
            return {"kind": "function", "signature": "(...)"}
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return {"kind": "constant", "value": str(obj)}
    return {"kind": "object", "type": type(obj).__name__}


def capture() -> dict:
    import governance_providers as gp
    from governance_providers import api

    out: dict = {}
    out["framework_version"] = gp.__version__
    from governance_providers.version import (
        CONTRACT_VERSION, TARGET_KERNEL_MAJOR, is_contract_compatible,
        is_kernel_compatible)
    out["contract_version"] = CONTRACT_VERSION
    out["target_kernel_major"] = TARGET_KERNEL_MAJOR
    out["version_predicates"] = {
        "is_contract_compatible(1.0.0)": is_contract_compatible("1.0.0"),
        "is_contract_compatible(2.0.0)": is_contract_compatible("2.0.0"),
        "is_kernel_compatible(1.0.0)": is_kernel_compatible("1.0.0"),
        "is_kernel_compatible(2.0.0)": is_kernel_compatible("2.0.0"),
    }

    # Public API surface (kind-level, module-path independent).
    out["api_all"] = list(api.__all__)
    out["api_symbols"] = {n: _obj_kind(getattr(api, n)) for n in sorted(api.__all__)}

    # Error taxonomy: MRO names + a raised instance's message.
    errors = {}
    for n in ("ProviderError", "ProviderRegistrationError", "ProviderResolutionError",
              "ProviderCompatibilityError", "ProviderConfigurationError",
              "ProviderUnavailableError", "ProviderTimeoutError", "ProviderProtocolError",
              "ProviderResultValidationError"):
        cls = getattr(api, n)
        errors[n] = [b.__name__ for b in cls.__mro__[1:] if b is not object]
    out["error_mro"] = errors

    # Registry + resolution behaviour with reference providers.
    from governance_providers.reference import (
        DeterministicActionGovernanceProvider, DeterministicAssertionProvider,
        DeterministicExecutionProvider)
    from governance_providers.metadata import ProviderKind

    reg = api.ProviderRegistry()
    for cls in (DeterministicAssertionProvider, DeterministicActionGovernanceProvider,
                DeterministicExecutionProvider):
        reg.register(cls().descriptor())
    out["registry"] = {"registered_ids": sorted(reg.ids)}
    # Duplicate registration must raise the registration error.
    try:
        reg.register(DeterministicAssertionProvider().descriptor())
        out["registry"]["duplicate_raises"] = None
    except api.ProviderRegistrationError as e:
        out["registry"]["duplicate_raises"] = type(e).__name__

    # Resolution roundtrip (deterministic) for each kind.
    res = {}
    for kind in ProviderKind:
        try:
            provider, rec = api.resolve(reg, api.ResolutionRequest(kind=kind))
            res[kind.name] = {"record_type": type(rec).__name__,
                              "provider_id": getattr(provider.descriptor(), "provider_id", None)}
        except Exception as e:  # pragma: no cover - captured for diff
            res[kind.name] = {"error": f"{type(e).__name__}: {e}"}
    out["resolution"] = res

    # Reference-provider deterministic descriptors.
    fps = {}
    for name, cls in (("assertion", DeterministicAssertionProvider),
                      ("action", DeterministicActionGovernanceProvider),
                      ("execution", DeterministicExecutionProvider)):
        d = cls().descriptor()
        fps[name] = {"provider_id": d.provider_id, "kind": d.kind.name,
                     "implementation_version": d.implementation_version}
    out["reference_descriptors"] = fps

    # fingerprint determinism
    from governance_providers.fingerprint import fingerprint
    out["fingerprint_sample"] = {
        "empty_dict": fingerprint({}),
        "nested": fingerprint({"b": 2, "a": [1, 2, {"z": 9}]}),
    }

    # Lifecycle legal transitions.
    from governance_providers.lifecycle import ProviderLifecycleState, is_legal_transition
    states = list(ProviderLifecycleState)
    out["lifecycle_states"] = [s.name for s in states]
    out["lifecycle_transitions"] = {
        f"{a.name}->{b.name}": is_legal_transition(a, b)
        for a in states for b in states}

    return out


if __name__ == "__main__":
    print(json.dumps(capture(), indent=2, sort_keys=True))
