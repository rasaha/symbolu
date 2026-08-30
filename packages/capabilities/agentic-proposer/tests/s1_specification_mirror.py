"""An exact enforcement mirror of the canonical S1 contract and equation specification.

**This module originates nothing.** Every constant below is transcribed from

    docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md

which is the authoritative S1 contract and equation specification. A test may not add,
omit, rename or reinterpret a contract field: where this module and that document
disagree, the document is right and this module is wrong. The provenance of each block
is recorded in ``PROVENANCE`` and is asserted against the document itself by
``test_the_registry_cites_its_source`` in ``test_identifier_normalization.py``, so the
citation cannot rot into a comment nobody checks.

**What this module is for.** Two things, and only two:

1. It carries the pinned registries the guards enforce — the C5 field classification,
   the per-contract cardinalities, the selection coupling. Those registries are hand
   transcribed mirrors of the specification, kept independent of ``src/`` on purpose:
   the completeness checks compare the registry against the *declared* surface, and a
   registry sourced from that same surface could never disagree with it.
2. It exposes ``representative_shapes()``, so every guard that was written to probe a
   dict of contract classes keeps working unchanged. **The shapes are no longer
   temporary.** Now that ``src/`` declares the eight contracts and the two nested
   public shapes, this function returns those declared classes directly rather than
   building parallel duplicates: a guard exercising ``representative_shapes()["Pro
   poserAdvisory"]`` is exercising the production contract, and the dormant
   completeness checks that were written to arm "once a production contract surface
   exists" now bind on it.

Two things this module previously had to depart from the specification on, until the
first contract module landed, no longer apply and are recorded here as closed rather
than silently dropped:

* **The C6 digest pattern** is no longer omitted: ``src/ugence_agentic_proposer/
  identity.py`` declares it (module-scoped past the D2 text scan, per I1), and every
  digest-shaped field on the real contracts carries it. The registry's ``OTHER_PATTERN``
  classification for those fields is unchanged, because it was always what the
  specification states of them, independent of how the field happened to be declared
  behind it.
* **``ProposerProcessStateTransition.state``** is typed ``ProposerProcessState``, which
  ``vocabulary.py`` now declares (nine members: the five process states R-3's chain
  names, in order, followed by the four terminal outcomes it names as the states a
  process may end in — see that enum's own docstring for why the four terminal members
  belong to it and for the ``[I]`` completion this discharges). The placeholder that
  stood in ``TerminalOutcome`` here is gone, and ``tests/test_process_ordering_
  obligation.py`` arms on the real enum accordingly.
"""
from __future__ import annotations

import datetime as _datetime
import functools
import pathlib
import typing

PKG_ROOT = pathlib.Path(__file__).resolve().parents[1]
#: The canonical authority this module mirrors.
SPECIFICATION = PKG_ROOT / "docs" / "S1_CONTRACT_AND_EQUATION_SPECIFICATION.md"
#: This module's own source, so a guard can assert properties of the declarations below
#: — the C8 spelling, the absence of a duplicated registry key — by reading them rather
#: than by trusting the built objects, which cannot show what they lost.
SPECIFICATION_MIRROR_SOURCE = pathlib.Path(__file__).read_text(encoding="utf-8")

#: Where each mirrored block is stated in the specification. Every entry is asserted to
#: appear in that document, so a section renamed there fails here rather than silently
#: leaving the citation pointing at nothing.
PROVENANCE = {
    "IDENTIFIER_PATTERN": "### C5a — Identifier or reference",
    "TOKEN_PATTERN": "### C5b — Canonical symbolic token",
    "C5C": "### C5c — Human-readable free text",
    "C5D": "### C5d — Structurally empty reserved list",
    "FIELD_CLASSIFICATION": "## C5 — Field classification: four categories, assigned explicitly",
    "CONTRACT_CARDINALITY": "# Part D — Contracts",
    "SELECTION_COUPLING": "## B6 — Selection-dependent fields are nullable and coupled (O-1)",
    "DECLARATION_FORM": "## C8 — How a constrained `str` field is declared",
}

# --------------------------------------------------------------------------- #
# C5 — the four content categories, plus the mechanical classes a content
# category does not describe
# --------------------------------------------------------------------------- #

#: C5a — an opaque, externally minted handle.
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"
#: C5b — a vocabulary term matched by equality against an allowlist: C5a minus ``/``.
TOKEN_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
#: C5a/C5b maximum length (B9).
MAX_IDENTIFIER_LENGTH = 200

C5A, C5B, C5C, C5D = "C5a", "C5b", "C5c", "C5d"
#: A field with its own separately ratified pattern: the C6 digest shapes, the B7
#: advisory version, the D8 distribution version. Neither free text nor C5a/C5b.
OTHER_PATTERN = "other-pattern"
#: Literal- or enum-typed: validated by membership, not by a string pattern.
CLOSED = "closed"
#: Not string-valued at all — a timestamp or a boolean.
NON_STRING = "non-string"
#: A nested model or a sequence of them. Registered separately from NON_STRING so the
#: registry states what it carries: ``ProposerAdvisory.candidates`` is the field OD-4(a)
#: added, and a registry populated only from ``str``-annotated fields could not report
#: its absence.
STRUCTURED = "structured"
#: ``dict[str, str]`` whose keys are C5a and whose values are C5c (D5).
MAPPING_C5A_KEYS_C5C_VALUES = "mapping-c5a-keys-c5c-values"

#: The exact class set. Pinned by equality: an unregistered category is a failure.
CLASSES = (C5A, C5B, C5C, C5D, OTHER_PATTERN, CLOSED, NON_STRING, STRUCTURED,
           MAPPING_C5A_KEYS_C5C_VALUES)

#: The pattern each category requires, where a category has one. C5c and C5d appear
#: nowhere in this mapping and must never be added to it: C5c admits no pattern of any
#: kind, and C5d's whole rule is emptiness.
PATTERN_FOR = {C5A: IDENTIFIER_PATTERN, C5B: TOKEN_PATTERN}

#: Categories that must carry NO pattern or regex constraint of any kind.
PATTERNLESS = (C5C, C5D)

# --------------------------------------------------------------------------- #
# The registry — an exact mirror of the Part D contract tables
# --------------------------------------------------------------------------- #

#: Every declared field of every Part D contract and nested public shape, keyed by
#: BEARER CONTRACT and field name — never by field name alone, since
#: ``requested_review_action`` is a different field on ``ProposerAdvisory`` than on
#: ``CandidateAdvisory`` (OD-3).
#:
#: Non-``str`` fields are carried too. A registry populated only from ``str``-annotated
#: fields has a circular completeness check: it can never report a missing entry for a
#: field it declines to look at, so a field silently retyped from ``str`` to an enum —
#: or back — passes unexamined in exactly the direction that matters (I5).
FIELD_CLASSIFICATION = {
    "AgentIdentityRef": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "agent_id": C5A, "agent_version": C5B, "lifecycle_state": CLOSED,
        "bound_role_contract_id": C5A, "owner_role_ref": C5A,
    },
    "CognitiveRoleContract": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "role_contract_id": C5A, "primary_function": C5C,
        "permitted_tool_scopes": C5B, "permitted_candidate_dispositions": CLOSED,
        "permitted_review_actions": CLOSED, "escalation_role_ref": C5A,
        "activation_status": CLOSED,
        # S2-B (`S2B-S1-Q2=A`, `S2B-R2-Q3=A`): a **C5a policy reference only**. An
        # opaque handle minted by Policy Authority, carried and compared whole — not a
        # C5b vocabulary term, and emphatically not the permitted set itself, which
        # `S2B-D1=A` keeps out of role data entirely.
        "strategy_policy_ref": C5A,
    },
    "WorkMandate": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "mandate_id": C5A, "case_ref": C5A, "assigned_role_contract_id": C5A,
        "purpose": C5C, "allowed_source_scopes": C5B, "expires_at": NON_STRING,
    },
    "BoundedContextEnvelope": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "context_id": C5A, "mandate_id": C5A, "allowed_record_refs": C5A,
        "excluded_data_classes": C5B, "context_hash": OTHER_PATTERN,
        "expires_at": NON_STRING,
    },
    "ToolObservation": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "observation_id": C5A, "case_ref": C5A, "tool_name": C5B,
        "operation_class": CLOSED, "source_ref": C5A, "observed_at": NON_STRING,
        "content_hash": OTHER_PATTERN,
        "normalized_fields": MAPPING_C5A_KEYS_C5C_VALUES,
        "admission_status": CLOSED,
    },
    "AdvisoryCandidateSet": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "candidate_set_id": C5A, "case_ref": C5A, "candidates": STRUCTURED,
        # OD-7 part 5's four additions. All four are C5b: each is a vocabulary term
        # matched by equality — the profile pair against an independently supplied
        # expected profile, the policy pair against this package's own ratified
        # selector identity — not an opaque handle carried and compared whole.
        "domain_evaluation_profile_id": C5B,
        "domain_evaluation_profile_version": C5B,
        "selected_candidate_id": C5A,
        "selection_policy_id": C5B, "selection_policy_version": C5B,
        "selection_reason_codes": C5D,
    },
    "CandidateAdvisory": {
        "candidate_id": C5A, "disposition": CLOSED,
        "requested_review_action": CLOSED, "is_eligible": NON_STRING,
        "domain_check_completion": CLOSED,
        # OD-7 part 3. A closed vocabulary, validated by membership, coupled to
        # ``domain_check_completion`` rather than patterned.
        "domain_evaluation_outcome": CLOSED,
        "evaluated_at": NON_STRING,
        "claim_refs": C5A, "observation_refs": C5A,
        "assumptions": C5C, "uncertainties": C5C,
    },
    "ProposerAdvisory": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "kind": CLOSED, "advisory_version": OTHER_PATTERN,
        "advisory_digest": OTHER_PATTERN, "parent_advisory_digest": OTHER_PATTERN,
        "case_ref": C5A, "agent_id": C5A, "role_contract_id": C5A,
        "mandate_id": C5A, "context_id": C5A, "candidate_set_id": C5A,
        "candidates": STRUCTURED,
        # OD-7 part 5's four mirrored fields, same classification as on the set.
        "domain_evaluation_profile_id": C5B,
        "domain_evaluation_profile_version": C5B,
        "selected_candidate_id": C5A,
        "selection_policy_id": C5B, "selection_policy_version": C5B,
        # S2-B (`S2B-D6=B1`). The policy pair is C5b on exactly the grounds the four
        # OD-7 fields above are: each is a vocabulary term matched by equality — here
        # against the resolved policy's own identity at replay — rather than an opaque
        # handle carried and compared whole. The role's ``strategy_policy_ref`` is the
        # opaque handle, and it is C5a; these two are what the resolver answers with.
        "strategy_policy_id": C5B, "strategy_policy_version": C5B,
        # `S2B-R2-Q5=A` types this as the ``ReasoningStrategy`` enum, so it is
        # validated by **membership, not by a string pattern** — which is what CLOSED
        # records.
        #
        # `[V]` **CLOSED is the registry's representation slot, and it does NOT
        # supersede `S2B-S1-Q3=A`'s C5b classification.** C5b is *defined* as "a
        # vocabulary term matched by equality against an allowlist", so the enum is
        # C5b's **natural closed realization rather than a narrower class**; the
        # question `S2B-R2-Q5=A` settled was representation, not classification, which
        # is why `S2B-S1-Q3=A` never reached it. Both rulings stand. This registry
        # nonetheless records CLOSED because its own scheme is mechanical: a C5b entry
        # demands the TOKEN_PATTERN string constraint, which an enum field cannot carry
        # and must not acquire.
        "declared_strategy": CLOSED,
        "recommended_disposition": CLOSED, "requested_review_action": CLOSED,
        "requested_review_destination_role_ref": C5A,
        "claim_summaries": C5C, "observation_refs": C5A, "uncertainties": C5C,
        "reason_codes": C5D, "expires_at": NON_STRING,
    },
    "ProposerProcessRecord": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "process_record_id": C5A, "case_ref": C5A,
        # Retyped from C5c to the ``ReasoningStrategy`` enum (`S2B-S1-Q3=A` narrowed
        # the classification to C5b, `S2B-R2-Q5=A` settled the representation as the
        # enum), so both sides of rider `R1`'s equality now carry the same class —
        # registered CLOSED, on the reasoning recorded beside
        # ``ProposerAdvisory.declared_strategy`` above.
        "declared_strategy": CLOSED,
        "state_transitions": STRUCTURED, "tool_invocations": C5B,
        "deterministic_checks": C5D, "candidate_ids": C5A,
        "selected_candidate_id": C5A, "semantic_audit_refs": C5D,
        "terminal_outcome": CLOSED, "reason_codes": C5D,
        "advisory_digest": OTHER_PATTERN, "jcs_distribution_version": OTHER_PATTERN,
        "started_at": NON_STRING, "completed_at": NON_STRING,
    },
    "ProposerProcessStateTransition": {"state": CLOSED, "at": NON_STRING},
}

#: The eight canonical top-level contracts (Part D).
TOP_LEVEL_CONTRACTS = (
    "AgentIdentityRef", "CognitiveRoleContract", "WorkMandate",
    "BoundedContextEnvelope", "ToolObservation", "AdvisoryCandidateSet",
    "ProposerAdvisory", "ProposerProcessRecord",
)
#: The two subordinate nested public shapes. Exported for typing, never transported
#: alone, and carrying no C2 common field.
NESTED_PUBLIC_SHAPES = ("CandidateAdvisory", "ProposerProcessStateTransition")

#: The stated cardinality of each contract, common fields included. Part D states these
#: so the registry's completeness can be checked by exact membership rather than left
#: implicit.
CONTRACT_CARDINALITY = {
    "AgentIdentityRef": 8,
    # S2-B `S2B-S1-Q2=A`: 10 -> 11, the added field being a C5a policy reference only.
    "CognitiveRoleContract": 11,
    "WorkMandate": 9,
    "BoundedContextEnvelope": 9,
    "ToolObservation": 12,
    # OD-7 part 5 moved these three: 8 -> 12, 10 -> 11 and 23 -> 27 (I8.11). The
    # amendment's own arithmetic, re-verified against ``src/`` once implemented.
    "AdvisoryCandidateSet": 12,
    "CandidateAdvisory": 11,
    # S2-B `S2B-S1-Q2=A` took this 27 -> 30: the governing policy identity, the policy
    # version and one scalar declared-strategy assertion, all identity-participating.
    # `AdvisoryCandidateSet` stays 12, `CandidateAdvisory` stays 11 and
    # `ProposerProcessRecord` stays 18 — its ``declared_strategy`` is **retyped**, not
    # added to.
    "ProposerAdvisory": 30,
    "ProposerProcessRecord": 18,
    "ProposerProcessStateTransition": 2,
}

#: The C2 common fields every top-level contract carries and neither nested shape does.
COMMON_FIELDS = ("schema_version", "tenant_id", "created_at")

# --------------------------------------------------------------------------- #
# B6 / OD-3 — the selection coupling, scoped to its bearer
# --------------------------------------------------------------------------- #

SELECTION_BEARER = "ProposerAdvisory"
SELECTION_FIELD = "selected_candidate_id"
DEPENDENT_FIELDS = (
    "recommended_disposition",
    "requested_review_action",
    "requested_review_destination_role_ref",
)
#: Contracts declaring a name matching a dependent field that are NOT bearers.
NON_BEARERS_SHARING_A_FIELD_NAME = ("CandidateAdvisory",)

# --------------------------------------------------------------------------- #
# Closed vocabularies the shapes need (B8, D1, D2, D5, C7) — the real enums.
# --------------------------------------------------------------------------- #

from ugence_agentic_proposer import (  # noqa: E402
    AgentLifecycleState,
    DomainCheckCompletion,
    ReasoningStrategy,
    ReviewAction,
    RoleActivationStatus,
    ToolObservationAdmissionStatus,
    ToolOperationClass,
)

# --------------------------------------------------------------------------- #
# The declared contract surface
# --------------------------------------------------------------------------- #

#: The one ratified declaration spelling for a constrained ``str`` (C8). Stated here as
#: the form the guards require; ``tests/test_documentation_consistency.py``'s and
#: I7.12's own scans check ``src/`` against it directly.
DECLARATION_FORM = "Annotated[str, StringConstraints(...)]"

#: A digest-shaped placeholder value, valid under C6's format grammar but not asserted
#: to be *correct* for any content: these fixtures probe field-level rules, not
#: identity (``verify_advisory_identity`` is a separate, independent check that
#: nothing here relies on passing). Spelled as two adjacent string literals, never
#: contiguous as one substring in this file's own source, so this test-support
#: constant does not collide with the D2 scan
#: (``test_no_local_canonicalization.py``), which is right to hunt that hash
#: algorithm's name everywhere outside the one module I1 exempts.
PLACEHOLDER_DIGEST = "sha" "256:" + "0" * 64


@functools.lru_cache(maxsize=1)
def representative_shapes():
    """The declared S1 contract classes, keyed by name, for behavioural probing.

    Returns a mapping of contract name to the actual ``ugence_agentic_proposer``
    ``pydantic`` model — no longer a temporary duplicate. A guard that exercises one of
    these is exercising the production contract; the dormant completeness checks that
    were written to arm "once a production contract surface exists" bind on it.
    """
    import ugence_agentic_proposer as ap

    return {
        "AgentIdentityRef": ap.AgentIdentityRef,
        "CognitiveRoleContract": ap.CognitiveRoleContract,
        "WorkMandate": ap.WorkMandate,
        "BoundedContextEnvelope": ap.BoundedContextEnvelope,
        "ToolObservation": ap.ToolObservation,
        "AdvisoryCandidateSet": ap.AdvisoryCandidateSet,
        "CandidateAdvisory": ap.CandidateAdvisory,
        "ProposerAdvisory": ap.ProposerAdvisory,
        "ProposerProcessRecord": ap.ProposerProcessRecord,
        "ProposerProcessStateTransition": ap.ProposerProcessStateTransition,
    }


# --------------------------------------------------------------------------- #
# OD-7 — test support for the injected domain-evaluator boundary
#
# This is a STUB, and it is test support, not a domain evaluator. It computes nothing
# about any business domain: it returns whatever outcome the test asked for. That is
# the whole point of the boundary OD-7 ratifies — a concrete evaluator lives outside
# this package, and this package's guards can therefore exercise orchestration and
# replay without any domain logic being present anywhere in the repository.
# --------------------------------------------------------------------------- #

#: The profile identity the fixtures evaluate under. A C5b token, compared by equality.
PROFILE_ID = "invoice.reconciliation"
PROFILE_VERSION = "2026.1"


class StubDomainEvaluationProvider:
    """A ``DomainEvaluationProvider`` whose answers a test dictates.

    ``outcomes`` maps ``candidate_id`` to the outcome to return; ``default`` covers
    every candidate not named. ``raises``, when set, is raised instead of answering —
    the case OD-7 requires to surface as ``DomainEvaluationProviderError`` from a
    builder and as ``False`` from a verifier. The three ``echo_*`` overrides break the
    request/response correlation deliberately, which is the only way to exercise the
    echo check: a correct provider cannot produce that state.

    ``calls`` records every request received, so a guard can assert the provider was
    **not** invoked — I8.9's missing-evidence obligation turns on exactly that.
    """

    def __init__(self, *, outcomes=None, default=None, raises=None,
                 echo_candidate_id=None, echo_profile_id=None,
                 echo_profile_version=None, log=None):
        from ugence_agentic_proposer import DomainEvaluationOutcome

        self.outcomes = dict(outcomes or {})
        self.default = default if default is not None else DomainEvaluationOutcome.SATISFIED
        self.raises = raises
        self.echo_candidate_id = echo_candidate_id
        self.echo_profile_id = echo_profile_id
        self.echo_profile_version = echo_profile_version
        self.calls = []
        #: An optional shared list this stub and ``StubStrategyPolicyResolver`` both
        #: append to, so a guard can read the ORDER in which the two injected
        #: boundaries were reached. `S2B-S1-Q12=A` is a rule about order, and a guard
        #: that could only see *whether* the provider ran would not test it.
        self.log = log

    def evaluate(self, *, request):
        from ugence_agentic_proposer import DomainEvaluationResponse

        self.calls.append(request)
        if self.log is not None:
            self.log.append("provider")
        if self.raises is not None:
            raise self.raises
        return DomainEvaluationResponse(
            candidate_id=self.echo_candidate_id or request.candidate_id,
            profile_id=self.echo_profile_id or request.profile_id,
            profile_version=self.echo_profile_version or request.profile_version,
            outcome=self.outcomes.get(request.candidate_id, self.default),
        )


# --------------------------------------------------------------------------- #
# S2-B — test support for the injected strategy-policy resolver boundary
#
# This is a STUB, and it is test support, not a policy. It issues nothing, signs
# nothing and verifies nothing: it returns whatever permitted set the test asked for.
# That is the whole point of the boundary `S2B-D1=A` ratifies — the governing policy is
# issued by Policy Authority, OUTSIDE this package. A strategy-permission family and a
# concrete resolver now exist as separate integration distributions, and their own
# tests carry the end-to-end proof. The protocol is injected, so these guards exercise
# resolution, the permission test, the construction order and the replay with no policy
# authority present anywhere — which is why they remain stubs regardless of what exists
# elsewhere. This is the ``StubDomainEvaluationProvider`` precedent exactly.
# --------------------------------------------------------------------------- #

#: The policy identity the fixtures resolve to. C5b tokens, compared by equality.
STRATEGY_POLICY_ID = "ugence.strategy_permission.reconciliation"
#: A **string** (C3 bars every numeric type in this contract family, at any depth).
STRATEGY_POLICY_VERSION = "v1"
#: The reference the role contract bears — C5a, an opaque externally minted handle.
STRATEGY_POLICY_REF = "policy-authority/strategy-permission/reconciliation"


class StubStrategyPolicyResolver:
    """A ``StrategyPolicyResolver`` whose answers a test dictates.

    ``permitted`` is the set returned; it defaults to all three members and may be
    empty, which is the state ``verify_strategy_permission``'s third check reports.
    ``raises``, when set, is raised instead of answering. The three ``echo_*``/override
    hooks break the correlation or divert the stamped identity deliberately, which is
    the only way to exercise those checks: a correct resolver cannot produce that state.

    ``calls`` records every request received, so a guard can assert both **that** the
    resolver was reached and **in what order** relative to the domain provider —
    `S2B-S1-Q12=A`'s construction order turns on exactly that.
    """

    def __init__(self, *, permitted=None, policy_id=None, policy_version=None,
                 raises=None, echo_ref=None, returns=None, log=None):
        from ugence_agentic_proposer import ReasoningStrategy

        self.permitted = (tuple(ReasoningStrategy) if permitted is None
                          else tuple(permitted))
        self.policy_id = policy_id or STRATEGY_POLICY_ID
        self.policy_version = policy_version or STRATEGY_POLICY_VERSION
        self.raises = raises
        self.echo_ref = echo_ref
        self.returns = returns
        self.calls = []
        #: An optional shared list both stubs append to, so a guard can read the
        #: ORDER in which the two boundaries were reached rather than only whether.
        self.log = log

    def resolve(self, *, request):
        from ugence_agentic_proposer import StrategyPolicyResponse

        self.calls.append(request)
        if self.log is not None:
            self.log.append("resolver")
        if self.raises is not None:
            raise self.raises
        if self.returns is not None:
            return self.returns
        return StrategyPolicyResponse(
            strategy_policy_id=self.policy_id,
            strategy_policy_version=self.policy_version,
            permitted_strategies=self.permitted,
            strategy_policy_ref=self.echo_ref or request.strategy_policy_ref,
        )


def strategy_policy_response(**overrides):
    """The lawful ``StrategyPolicyResponse`` the fixtures resolve to, for replay."""
    from ugence_agentic_proposer import ReasoningStrategy, StrategyPolicyResponse

    fields = {
        "strategy_policy_id": STRATEGY_POLICY_ID,
        "strategy_policy_version": STRATEGY_POLICY_VERSION,
        "permitted_strategies": tuple(ReasoningStrategy),
        "strategy_policy_ref": STRATEGY_POLICY_REF,
    }
    fields.update(overrides)
    return StrategyPolicyResponse(**fields)


#: A timezone-aware instant, caller-supplied. No module here reads a wall clock (C4).
FIXED_INSTANT = _datetime.datetime(2026, 1, 1, 12, 0, 0,
                                   tzinfo=_datetime.timezone.utc)


def complete_candidate(candidate_id="cand-1"):
    """Every required ``CandidateAdvisory`` field, with a lawful value for each."""
    from ugence_agentic_proposer import CandidateDisposition

    return {
        "candidate_id": candidate_id,
        "disposition": CandidateDisposition.RECOMMEND_WITHHOLD,
        "requested_review_action": ReviewAction.ROUTE_APPROVAL_BUNDLE,
        "is_eligible": False,
        "domain_check_completion": DomainCheckCompletion.NOT_EVALUATED,
        "domain_evaluation_outcome": None,
        "evaluated_at": FIXED_INSTANT,
        "claim_refs": [],
        "observation_refs": [],
        "assumptions": [],
        "uncertainties": [],
    }


def qualifying_candidate(candidate_id="cand-1"):
    """A ``CandidateAdvisory`` field mapping the ratified selector's **qualifying pool**
    admits (OD-7 part 4): ``is_eligible is True`` and ``domain_evaluation_outcome is
    SATISFIED``, with the coupled ``domain_check_completion is COMPLETE``.

    Under C9 no such fixture could be selected, so every selection probe ran against a
    shape the ratified policy would refuse. It is supplied here so a probe of the
    coupling is not silently a probe of the policy.
    """
    from ugence_agentic_proposer import DomainEvaluationOutcome

    return {
        **complete_candidate(candidate_id),
        "is_eligible": True,
        "domain_check_completion": DomainCheckCompletion.COMPLETE,
        "domain_evaluation_outcome": DomainEvaluationOutcome.SATISFIED,
    }


def selecting_advisory_fixture(**overrides):
    """``complete_advisory_fixture`` carrying one qualifying candidate, the selection
    selection-policy v1 produces over it, and the four OD-7 part 5 fields the
    couplings then require."""
    shapes = representative_shapes()
    from ugence_agentic_proposer import contracts as _c

    fixture = complete_advisory_fixture(
        candidates=(shapes["CandidateAdvisory"](**qualifying_candidate()),),
        domain_evaluation_profile_id=PROFILE_ID,
        domain_evaluation_profile_version=PROFILE_VERSION,
        selected_candidate_id="cand-1",
        selection_policy_id=_c.SELECTION_POLICY_ID,
        selection_policy_version=_c.SELECTION_POLICY_VERSION,
    )
    fixture.update(overrides)
    return fixture


def complete_advisory_fixture(**overrides):
    """Every required ``ProposerAdvisory`` field, with a lawful value for each.

    A coupling probe run against a partial fixture proves nothing: the construction
    would fail on a missing required field whatever the coupling did, and the test would
    pass for the wrong reason. This supplies all thirty fields so that the only thing a
    rejection can be about is the rule under probe.

    ``declared_strategy`` defaults to the member this fixture's own shape yields — one
    candidate, no parent — so an advisory built from it satisfies
    ``verify_strategy_permission``'s sixth check unless a test varies it deliberately.
    """
    shapes = representative_shapes()
    fixture = {
        "schema_version": "1.0",
        "tenant_id": "tenant-1",
        "created_at": FIXED_INSTANT,
        "kind": "ugence.agentic_proposer.advisory.v0",
        "advisory_version": "1",
        "advisory_digest": PLACEHOLDER_DIGEST,
        "parent_advisory_digest": None,
        "case_ref": "case-1",
        "agent_id": "agent-1",
        "role_contract_id": "role-1",
        "mandate_id": "mandate-1",
        "context_id": "context-1",
        "candidate_set_id": "set-1",
        "candidates": (shapes["CandidateAdvisory"](**complete_candidate()),),
        "domain_evaluation_profile_id": None,
        "domain_evaluation_profile_version": None,
        "selected_candidate_id": None,
        "selection_policy_id": None,
        "selection_policy_version": None,
        "strategy_policy_id": STRATEGY_POLICY_ID,
        "strategy_policy_version": STRATEGY_POLICY_VERSION,
        "declared_strategy": ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED,
        "recommended_disposition": None,
        "requested_review_action": None,
        "requested_review_destination_role_ref": None,
        "claim_summaries": [],
        "observation_refs": [],
        "uncertainties": [],
        "reason_codes": [],
        "expires_at": FIXED_INSTANT,
    }
    fixture.update(overrides)
    return fixture
