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
    enums = {n for n, e in documented.items() if e["kind"] == "enum"}
    functions = {n for n, e in documented.items() if e["kind"] == "function"}
    exceptions = {n for n, e in documented.items() if e["kind"] == "exception"}
    constants = {n for n, e in documented.items() if e["kind"] == "constant"} - {
        "__version__"}

    contracts = {"AgentIdentityRef", "CognitiveRoleContract", "WorkMandate",
                "BoundedContextEnvelope", "ToolObservation", "AdvisoryCandidateSet",
                "ProposerAdvisory", "ProposerProcessRecord"}
    nested = {"CandidateAdvisory", "ProposerProcessStateTransition"}
    assert contracts | nested == models
    assert len(enums) == 10
    builders = {"build_candidate_advisory", "build_advisory_candidate_set",
               "build_proposer_advisory", "build_advisory_revision",
               "build_proposer_process_record"}
    equations = {"evaluate_eligibility", "evaluate_readiness"}
    identity_functions = {"compute_advisory_identity", "verify_advisory_identity"}
    verifiers = {"verify_candidate_eligibility", "verify_advisory_selection",
                "verify_observation_resolution"}
    assert builders | equations | identity_functions | verifiers == functions
    assert exceptions == {"EligibilityMismatchError", "CrossContractViolationError"}
    assert constants == {"RESERVED_AUTHORITY_VOCABULARY", "ADVISORY_KIND",
                         "ADVISORY_IDENTITY_SET_PATHS", "ADVISORY_IDENTITY_NFC_PATHS"}


def test_py_typed_marker_present():
    assert (_PKG_ROOT / "py.typed").is_file(), "PEP 561 py.typed marker missing"


def test_no_exported_name_begins_with_proposal_or_recommendation():
    """D7, restated against the snapshot: no exported name may begin with
    ``Proposal`` or ``Recommendation``."""
    documented = json.loads(_PUBLIC_API_JSON.read_text())["symbols"]
    offenders = [n for n in documented if n.startswith(("Proposal", "Recommendation"))]
    assert offenders == []
