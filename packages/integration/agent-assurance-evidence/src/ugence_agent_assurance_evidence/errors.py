"""Typed errors. Every one is a *refusal*; none is ever promoted to a permission."""

from __future__ import annotations


class AgentAssuranceEvidenceError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(AgentAssuranceEvidenceError, ValueError):
    """A caller supplied structurally invalid or mismatched input.

    A naive datetime, a blank reference, a wrong type, a look-alike binding,
    evidence reference or label, a chosen rather than derived id, a tenant that
    disagrees with the binding's or the evidence's tenant, or an evidence
    reference whose subject disagrees with the binding's subject.
    """


class DeclarationSupersessionError(AgentAssuranceEvidenceError, ValueError):
    """A superseding declaration is inadmissible.

    It names no predecessor, crosses a tenant, concerns a different system, or
    re-declares exactly what the predecessor already declared — an unchanged
    declaration has nothing to supersede.
    """
