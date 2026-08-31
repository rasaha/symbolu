"""I8 — the documented public API agrees with the actual H3 package surface.

Rebuilds the public-API description straight from the installed
``ugence_agentic_proposer`` package and asserts it is equal to the committed
``public_api.json``. This catches an accidental export addition/removal, an
enum-value drift, or a model-field change that was not reflected in the
machine-readable contract snapshot. Regenerate the JSON (by re-running
``_actual_surface()`` and writing its result) whenever the curated API changes —
which, for this package, means a ratified amendment to
``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``.
"""
from __future__ import annotations

import enum
import inspect
import json
import pathlib
import typing

import pydantic

import ugence_agentic_proposer as ap

_PKG_ROOT = pathlib.Path(ap.__file__).resolve().parent
# tests/ -> packages/capabilities/agentic-proposer/
_DIST_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PUBLIC_API_JSON = _DIST_ROOT / "public_api.json"


def _kind(obj) -> str:
    if isinstance(obj, type):
        if issubclass(obj, enum.Enum):
            return "enum"
        if issubclass(obj, Exception):
            return "exception"
        if issubclass(obj, pydantic.BaseModel):
            return "model"
        # OD-7's injected-evaluator boundary is a ``typing.Protocol``. Recorded as its
        # own kind rather than folded into "class": a protocol declares a shape the
        # caller satisfies, and a snapshot that called it a class would not say that.
        if getattr(obj, "_is_protocol", False) or typing.Protocol in obj.__bases__:
            return "protocol"
        return "class"
    if inspect.isfunction(obj):
        return "function"
    return "constant"


def _constant_value(obj):
    if isinstance(obj, frozenset):
        return sorted(obj)
    return obj


def _actual_surface() -> dict:
    symbols: dict[str, dict] = {}
    for name in sorted(ap.__all__):
        obj = getattr(ap, name)
        kind = _kind(obj)
        entry: dict = {"kind": kind}
        if kind == "enum":
            entry["values"] = [m.value for m in obj]
        elif kind == "protocol":
            entry["methods"] = sorted(
                name for name in getattr(obj, "__protocol_attrs__", ())
                if not name.startswith("_"))
        elif kind == "model":
            entry["fields"] = list(obj.model_fields)
        elif kind == "constant":
            entry["value"] = _constant_value(obj)
        symbols[name] = entry
    return {
        "distribution": "ugence-agentic-proposer",
        "namespace": "ugence_agentic_proposer",
        "package_version": ap.__version__,
        "symbols": symbols,
    }


def test_documented_public_api_matches_actual():
    documented = json.loads(_PUBLIC_API_JSON.read_text())
    documented.pop("note", None)
    actual = _actual_surface()
    for key in ("distribution", "namespace", "package_version"):
        assert documented[key] == actual[key], key
    assert documented["symbols"] == actual["symbols"]


def test_curated_api_names_match_module_all():
    documented = json.loads(_PUBLIC_API_JSON.read_text())
    assert set(documented["symbols"]) == set(ap.__all__)


def test_every_h3_category_is_present_in_the_snapshot():
    """H3's own headline counts, checked against the snapshot rather than trusted."""
    documented = json.loads(_PUBLIC_API_JSON.read_text())["symbols"]
    models = {n for n, e in documented.items() if e["kind"] == "model"}
    protocols = {n for n, e in documented.items() if e["kind"] == "protocol"}
    enums = {n for n, e in documented.items() if e["kind"] == "enum"}
    functions = {n for n, e in documented.items() if e["kind"] == "function"}
    exceptions = {n for n, e in documented.items() if e["kind"] == "exception"}
    constants = {n for n, e in documented.items() if e["kind"] == "constant"} - {
        "__version__"}

    contracts = {"AgentIdentityRef", "CognitiveRoleContract", "WorkMandate",
                "BoundedContextEnvelope", "ToolObservation", "AdvisoryCandidateSet",
                "ProposerAdvisory", "ProposerProcessRecord"}
    nested = {"CandidateAdvisory", "ProposerProcessStateTransition"}
    # OD-7's two call-boundary shapes, and S2-B's two, are pydantic models and appear
    # as such; none is a contract, which is why they are named separately here rather
    # than folded in. Neither pair carries a C2 common field, has an identity role, or
    # is ever stored, transported or reachable from ``P_unsigned``.
    boundary_shapes = {"DomainEvaluationRequest", "DomainEvaluationResponse",
                       "StrategyPolicyRequest", "StrategyPolicyResponse"}
    assert contracts | nested | boundary_shapes == models
    # Two injected protocols this package OWNS and does not implement: the domain
    # evaluator (OD-7 part 2) and the strategy-policy resolver (`S2B-S1-Q9=A`).
    assert protocols == {"DomainEvaluationProvider", "StrategyPolicyResolver"}
    assert len(enums) == 12
    builders = {"build_candidate_advisory", "build_advisory_candidate_set",
               "build_proposer_advisory", "build_advisory_revision",
               "build_proposer_process_record"}
    equations = {"evaluate_eligibility", "evaluate_readiness"}
    identity_functions = {"compute_advisory_identity", "verify_advisory_identity"}
    verifiers = {"verify_candidate_eligibility", "verify_advisory_selection",
                "verify_observation_resolution", "verify_domain_evaluation",
                "verify_deterministic_selection", "verify_strategy_permission"}
    assert builders | equations | identity_functions | verifiers == functions
    assert exceptions == {"EligibilityMismatchError", "CrossContractViolationError",
                          "DomainEvaluationProviderError"}
    assert constants == {"RESERVED_AUTHORITY_VOCABULARY", "ADVISORY_KIND",
                         "ADVISORY_IDENTITY_SET_PATHS", "ADVISORY_IDENTITY_NFC_PATHS"}


def test_the_snapshot_carries_exactly_the_fifty_one_authorized_names():
    """S2-B's public-API consequence, executed (`S2B-S1-Q6=A` with `S2B-R2-Q4=A`).

    Thirty-nine names were frozen at ``0.1.0``; OD-7 authorized seven more at
    ``0.2.0``; S2-B authorizes **exactly five** at ``0.3.0`` — the strategy vocabulary,
    the resolver protocol, the resolver request shape, the resolver response shape and
    the replay function. **No removals, no renames**, which this asserts by requiring
    the residue to be exactly the forty-six that came before. `ACC-AM-5` (the
    `OD-C1=B` amendment, ``0.4.0``) authorizes **zero** names: the surface stays at
    fifty-one, and the amendment moves field lists only.
    """
    documented = json.loads(_PUBLIC_API_JSON.read_text())
    assert documented["package_version"] == "0.4.0"
    assert len(documented["symbols"]) == 51
    od7_added = {"DomainEvaluationOutcome", "DomainEvaluationProvider",
                 "DomainEvaluationRequest", "DomainEvaluationResponse",
                 "DomainEvaluationProviderError", "verify_domain_evaluation",
                 "verify_deterministic_selection"}
    s2b_added = {"ReasoningStrategy", "StrategyPolicyResolver",
                 "StrategyPolicyRequest", "StrategyPolicyResponse",
                 "verify_strategy_permission"}
    assert len(s2b_added) == 5, "S2-B authorizes exactly five names, and no more"
    assert od7_added <= set(documented["symbols"])
    assert s2b_added <= set(documented["symbols"])
    assert len(set(documented["symbols"]) - s2b_added) == 46
    assert len(set(documented["symbols"]) - s2b_added - od7_added) == 39


def test_the_recorded_version_symbol_agrees_with_the_package_version():
    """`0.3.1`. The snapshot records the version twice — once as ``package_version``
    and once as the value of the ``__version__`` symbol — and a patch release that
    moved one and not the other would leave the file self-contradicting while every
    count above still passed."""
    documented = json.loads(_PUBLIC_API_JSON.read_text())
    assert documented["symbols"]["__version__"]["value"] == ap.__version__
    assert documented["package_version"] == ap.__version__


def test_py_typed_marker_present():
    assert (_PKG_ROOT / "py.typed").is_file(), "PEP 561 py.typed marker missing"


def test_no_exported_name_begins_with_proposal_or_recommendation():
    """D7, restated against the snapshot: no exported name may begin with
    ``Proposal`` or ``Recommendation``."""
    documented = json.loads(_PUBLIC_API_JSON.read_text())["symbols"]
    offenders = [n for n in documented if n.startswith(("Proposal", "Recommendation"))]
    assert offenders == []
