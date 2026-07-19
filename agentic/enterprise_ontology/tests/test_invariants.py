"""Unit tests for each cross-vertical invariant (violating + clean cases)."""

import pytest

from agentic.enterprise_ontology.events import (
    DecisionEffect, DependencyStatus, EnterpriseEventEnvelope, ExecutionRecord,
    VerticalDecision, VerticalDependency,
)
from agentic.enterprise_ontology.failure_classes import FailureClass as F
from agentic.enterprise_ontology.invariants import (
    inv_advisory_non_escalation, inv_authority_provenance, inv_core_preservation,
    inv_dependency_satisfaction, inv_execution_observation, inv_form_binding,
    inv_identity_authority, inv_purpose_consistency, inv_reconciliation,
    inv_universal_constraint, run_all_invariants,
)
from agentic.enterprise_ontology.scenarios._helpers import AR, EO, L, ST, V, VS, rec


def _env(records=(), decisions=(), executions=(), dependencies=(), recon="ok"):
    return EnterpriseEventEnvelope("e", "t", tuple(records), tuple(dependencies),
                                   tuple(decisions), tuple(executions), recon)


def _classes(findings):
    return {f.failure_class for f in findings}


# --- authority provenance + advisory non-escalation (the core invariant) -----

def test_authority_provenance_flags_missing_basis():
    d = VerticalDecision("d", V.SALES, DecisionEffect.ALLOW, "x",
                         supporting_record_ids=("adv",))
    adv = rec("adv", L.PURPOSE, V.SALES, {"objective": "x"},
              verify=VS.DECLARED, authority=AR.ADVISORY)
    env = _env(records=(adv,), decisions=(d,))
    assert F.MISSING_AUTHORITY_BASIS in _classes(inv_authority_provenance(env))


def test_advisory_cannot_authorize_but_authority_bearing_can():
    adv = rec("adv", L.COGNITION, V.SALES, {"score": 0.9},
              origin=EO.DERIVED_INTERPRETIVE, verify=VS.INFERRED, authority=AR.ADVISORY)
    auth = rec("auth", L.AGENCY, V.FINANCE, {"approved": True},
               origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
               authority=AR.AUTHORITY_BEARING)
    d_bad = VerticalDecision("db", V.SALES, DecisionEffect.WIDEN, "x",
                             supporting_record_ids=("adv",))
    d_ok = VerticalDecision("do", V.SALES, DecisionEffect.ALLOW, "x",
                            supporting_record_ids=("adv", "auth"))
    bad = _env(records=(adv, auth), decisions=(d_bad,))
    ok = _env(records=(adv, auth), decisions=(d_ok,))
    assert F.ADVISORY_AUTHORITY_ESCALATION in _classes(inv_advisory_non_escalation(bad))
    assert not inv_advisory_non_escalation(ok)  # authority-bearing present → clean


def test_declared_authority_bearing_is_not_trusted():
    # A record TAGGED authority_bearing but only DECLARED is not effective authority.
    fake = rec("fake", L.AGENCY, V.SALES, {"approved": True},
               origin=EO.SUPPLIED, verify=VS.DECLARED, authority=AR.AUTHORITY_BEARING)
    d = VerticalDecision("d", V.SALES, DecisionEffect.ALLOW, "x",
                         supporting_record_ids=("fake",))
    env = _env(records=(fake,), decisions=(d,))
    assert F.MISSING_AUTHORITY_BASIS in _classes(inv_authority_provenance(env))


# --- purpose consistency -----------------------------------------------------

def test_purpose_unverified_flagged():
    p = rec("p", L.PURPOSE, V.SALES, {"objective": "x"}, verify=VS.DECLARED,
            authority=AR.ADVISORY)
    d = VerticalDecision("d", V.SALES, DecisionEffect.ALLOW, "x",
                         supporting_record_ids=("p",))
    env = _env(records=(p,), decisions=(d,))
    assert F.MISSING_VERIFIED_PURPOSE in _classes(inv_purpose_consistency(env))


def test_purpose_verified_is_clean():
    p = rec("p", L.PURPOSE, V.HR, {"objective": "headcount"},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING)
    d = VerticalDecision("d", V.HR, DecisionEffect.ALLOW, "x",
                         supporting_record_ids=("p",))
    env = _env(records=(p,), decisions=(d,))
    assert F.MISSING_VERIFIED_PURPOSE not in _classes(inv_purpose_consistency(env))


# --- form binding ------------------------------------------------------------

def test_form_binding_mismatch():
    ex = ExecutionRecord("ex", V.IT, "CRM", "q1", authorized_form="quote",
                         executed_form="contract", resulting_state={})
    env = _env(executions=(ex,))
    assert F.FORM_EXECUTION_MISMATCH in _classes(inv_form_binding(env))


def test_form_binding_clean_when_equal():
    ex = ExecutionRecord("ex", V.IT, "CRM", "q1", authorized_form="quote",
                         executed_form="quote", resulting_state={})
    assert not inv_form_binding(_env(executions=(ex,)))


# --- dependency satisfaction -------------------------------------------------

def test_dependency_failure_when_proceeded_without_upstream():
    dep = VerticalDependency(V.MARKETING, V.PRIVACY, "c", DependencyStatus.DENIED, "consent")
    ex = ExecutionRecord("ex", V.MARKETING, "Ads", "c1", None, None, {})
    env = _env(executions=(ex,), dependencies=(dep,))
    assert F.CROSS_VERTICAL_DEPENDENCY_FAILURE in _classes(inv_dependency_satisfaction(env))


def test_dependency_clean_when_satisfied():
    dep = VerticalDependency(V.MARKETING, V.PRIVACY, "c", DependencyStatus.SATISFIED, "")
    ex = ExecutionRecord("ex", V.MARKETING, "Ads", "c1", None, None, {})
    assert not inv_dependency_satisfaction(_env(executions=(ex,), dependencies=(dep,)))


# --- core / universal --------------------------------------------------------

def test_core_breach():
    c = rec("c", L.CORE, V.FINANCE, {"invariant": "margin", "preserved": False},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED, authority=AR.AUTHORITY_BEARING)
    assert F.CORE_INVARIANT_BREACH in _classes(inv_core_preservation(_env(records=(c,))))


def test_universal_breach_with_local_permit():
    u = rec("u", L.UNIVERSAL, V.FINANCE, {"constraint": "conc", "breached": True},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED, authority=AR.AUTHORITY_BEARING)
    d = VerticalDecision("d", V.PROCUREMENT, DecisionEffect.ALLOW, "x")
    assert F.UNIVERSAL_CONSTRAINT_BREACH in _classes(
        inv_universal_constraint(_env(records=(u,), decisions=(d,))))


# --- execution vs observation + reconciliation -------------------------------

def test_execution_observation_mismatch():
    obs = rec("obs", L.OBSERVATION, V.FINANCE, {"amount": 58000}, verify=VS.VERIFIED)
    ex = ExecutionRecord("ex", V.FINANCE, "PO", "po1", "po", "po",
                         resulting_state={"amount": 60000}, observation_ref="obs")
    env = _env(records=(obs,), executions=(ex,))
    assert F.EXECUTION_OBSERVATION_MISMATCH in _classes(inv_execution_observation(env))


def test_reconciliation_mismatch_across_systems():
    e1 = ExecutionRecord("e1", V.IT, "CRM", "q1", None, None, {"price": 80})
    e2 = ExecutionRecord("e2", V.FINANCE, "ERP", "q1", None, None, {"price": 100})
    assert F.STATE_RECONCILIATION_FAILURE in _classes(inv_reconciliation(_env(executions=(e1, e2))))


def test_reconciliation_clean_when_agree():
    e1 = ExecutionRecord("e1", V.IT, "CRM", "q1", None, None, {"price": 100})
    e2 = ExecutionRecord("e2", V.FINANCE, "ERP", "q1", None, None, {"price": 100})
    assert not inv_reconciliation(_env(executions=(e1, e2), recon="ok"))


# --- identity authority ------------------------------------------------------

def test_identity_authority_violation():
    idr = rec("id", L.IDENTITY, V.HR, "candidate:x", verify=VS.UNKNOWN)
    d = VerticalDecision("d", V.HR, DecisionEffect.ALLOW, "hire")
    assert F.IDENTITY_AUTHORITY_VIOLATION in _classes(
        inv_identity_authority(_env(records=(idr,), decisions=(d,))))


def test_identity_authority_clean_when_verified():
    idr = rec("id", L.IDENTITY, V.HR, "candidate:x", verify=VS.VERIFIED)
    d = VerticalDecision("d", V.HR, DecisionEffect.ALLOW, "hire")
    assert not inv_identity_authority(_env(records=(idr,), decisions=(d,)))


# --- fully clean event produces no findings ----------------------------------

def test_clean_event_has_no_findings():
    p = rec("p", L.PURPOSE, V.HR, {"objective": "headcount"},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED, authority=AR.AUTHORITY_BEARING)
    idr = rec("id", L.IDENTITY, V.HR, "x", verify=VS.VERIFIED)
    d = VerticalDecision("d", V.HR, DecisionEffect.ALLOW, "x",
                         supporting_record_ids=("p",))
    ex = ExecutionRecord("ex", V.HR, "HRIS", "e1", "std", "std", {"ok": True})
    dep = VerticalDependency(V.HR, V.FINANCE, None, DependencyStatus.SATISFIED, "")
    env = _env(records=(p, idr), decisions=(d,), executions=(ex,), dependencies=(dep,))
    assert run_all_invariants(env) == []
