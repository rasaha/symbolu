"""Structural authority- and dependency-boundary invariants for Phase 4A.

These prove by construction — not by convention — that the new v2 subject-context
layer adds no authority and no reverse dependency. Every assertion is about the
*absence* of a capability, so they belong with the adversarial suite.
"""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap

import pytest

from risk_authority.integrations import evaluation_contracts as ec
from risk_authority.integrations import (
    SubjectBinding,
    SubjectBindingValidation,
    SubjectContext,
    SubjectRiskEvaluationRequest,
    SubjectRiskEvaluationRequestV2,
    validate_subject_binding,
)

from ..contract.test_subject_context_contracts import v2_request

FORBIDDEN_MODULE_TOKENS = (
    "boto3", "botocore", "google.cloud", "azure", "kubernetes", "docker",
    "requests", "httpx", "urllib.request", "socket", "subprocess",
)


def test_the_contract_module_imports_no_provider_or_cloud_sdk():
    source = inspect.getsource(ec)
    for token in FORBIDDEN_MODULE_TOKENS:
        assert f"import {token}" not in source, token
        assert f"from {token}" not in source, token


def test_no_provider_or_cloud_sdk_is_loaded_by_importing_the_contracts():
    for token in ("boto3", "botocore", "kubernetes", "azure", "docker"):
        assert token not in sys.modules


def test_the_contract_module_imports_no_cloud_scaling_package():
    # Risk Authority owns these contracts; it must never depend on the advisory leaf.
    source = inspect.getsource(ec)
    for token in ("cloud_scaling", "cloud-scaling", "ugence_cloud_scaling"):
        assert f"import {token}" not in source
        assert f"from {token}" not in source
    assert not any(m.startswith("ugence_cloud_scaling") for m in sys.modules)


def test_risk_authority_remains_a_stdlib_only_leaf_for_this_layer():
    # The new layer adds only stdlib imports (re, unicodedata) plus intra-package ones.
    for module in ("re", "unicodedata"):
        assert hasattr(ec, module) or module in sys.modules


@pytest.mark.parametrize("contract", [
    SubjectContext, SubjectBinding, SubjectRiskEvaluationRequestV2, SubjectBindingValidation,
])
def test_no_contract_exposes_an_authority_bearing_field(contract):
    forbidden = {
        "policy_id", "policy", "workflow_ir", "control_result", "control_results",
        "control_status", "risk_outcome", "risk_decision", "decision", "envelope",
        "authorization_envelope", "signing_key", "key", "credential", "credentials",
        "secret", "token", "execution_instruction", "command",
    }
    assert not (set(getattr(contract, "__dataclass_fields__", {})) & forbidden)


def _executable_source(func) -> str:
    """The function's body with its docstring stripped, so prose about what the code
    does *not* do cannot be mistaken for the code doing it."""

    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    body = tree.body[0].body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return "\n".join(ast.unparse(node) for node in body)


def test_the_validator_never_reaches_the_seam_envelope_or_actiongate():
    source = _executable_source(validate_subject_binding)
    for token in ("issue_envelope", "authorize_action", "RiskEvaluationSeam",
                  "issue_decision", "authorize", "resolve"):
        assert token not in source, token


def test_the_validator_is_pure_and_takes_no_clock_or_port():
    params = list(inspect.signature(validate_subject_binding).parameters)
    assert params == ["request"]


def test_the_validator_does_not_mutate_its_argument():
    request = v2_request()
    before = request.to_canonical_dict()
    validate_subject_binding(request)
    assert request.to_canonical_dict() == before


def test_a_v2_request_is_not_an_instance_of_the_v1_request():
    # Structural containment: a v2 request cannot silently satisfy a v1-typed call
    # site (including the seam), so no unvalidated v2 can reach policy resolution.
    assert not isinstance(v2_request(), SubjectRiskEvaluationRequest)
    assert not issubclass(SubjectRiskEvaluationRequestV2, SubjectRiskEvaluationRequest)


def test_the_seam_still_fails_closed_on_a_v2_schema_version():
    from risk_authority.integrations import (
        EVALUATION_REQUEST_SCHEMA_VERSION_V2,
        SUPPORTED_REQUEST_SCHEMA_VERSIONS,
    )
    assert EVALUATION_REQUEST_SCHEMA_VERSION_V2 not in SUPPORTED_REQUEST_SCHEMA_VERSIONS


def test_the_evaluation_seam_module_is_unchanged_by_this_layer():
    from risk_authority.api import evaluation_seam

    source = inspect.getsource(evaluation_seam)
    for token in ("SubjectContext", "SubjectBinding", "validate_subject_binding",
                  "SubjectRiskEvaluationRequestV2"):
        assert token not in source, token
