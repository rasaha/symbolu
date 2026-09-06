"""The confusable comparison contract, and the inert ports and descriptor."""

from __future__ import annotations

import dataclasses

import pytest

from _milestones import (
    SUBPHASE_LADDER,
    VERSION_SUBPHASE,
    banned_capability_tokens,
)

from ugence_benchmark_registry_authority import api
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS,
    BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT,
    BENCHMARK_PRODUCTION_ADAPTER_ADMISSION_REQUIREMENT,
    BENCHMARK_REGISTRY_DECLARED_CONSISTENCY,
    BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES,
    BenchmarkApprovalVerifierPort,
    BenchmarkClockPort,
    BenchmarkConfusableNormalizationPosture,
    BenchmarkPublisherTrustDirectoryPort,
    BenchmarkRegistryCompositionError,
    BenchmarkRegistryConsistencyClaim,
    BenchmarkRegistryConsistencyScope,
    BenchmarkRegistryContractError,
    BenchmarkRegistryRefusalReason,
    BenchmarkRegistryStoreConsistencyDescriptor,
    BenchmarkRegistryStorePort,
)

PORTS = (
    BenchmarkRegistryStorePort,
    BenchmarkPublisherTrustDirectoryPort,
    BenchmarkApprovalVerifierPort,
    BenchmarkClockPort,
)

#: Implementation-shaped names no exported symbol may carry, mapped to the
#: subphase that may first ship one — D-19's milestone-conditional form, the
#: same discipline ``test_milestone_boundary.py`` applies to the tree-wide list.
#:
#: ``None`` is a permanent ban rather than a deferral. A stub, fake, dummy,
#: no-op or null implementation is never correct at *any* subphase, and that
#: ruling has no expiry date. **This map is the enforcement, and it is a name
#: ban.** §17 is *Registry and resolution semantics* — fourteen rules on lookup,
#: registration, revocation and supersession, plus §17.1 on historical
#: resolution — and it bans no placeholder; the word appears nowhere else in the
#: ADR. The five permanent entries below are the whole of what stops one, they
#: stop it by name only, and they sit in the same self-attested one-file
#: two-literal pattern ADR §35.2 D-37 and D-38 rule.
EXPORTED_IMPLEMENTATION_UNLOCK = {
    "denyall": "BR-2C-RC",
    "deny_all": "BR-2C-RC",
    "verifier": "BR-2C-RC",
    "trust_store": "BR-2C-RC",
    "inmemory": "BR-2D",
    "in_memory": "BR-2D",
    "adapter": "BR-2D",
    "compositionroot": "BR-2D",
    "composition_root": "BR-2D",
    "registry_impl": "BR-2D",
    "engine": "BR-2D",
    "resolver": "BR-2D",
    "signer": "BR-2D",
    "stub": None,
    "fake": None,
    "dummy": None,
    "noop": None,
    "null_": None,
}

#: The exact token set BR-2A froze, pinned independently so a restructuring
#: cannot drop one unnoticed.
BR2A_FROZEN_EXPORT_TOKENS = frozenset(
    {
        "denyall",
        "deny_all",
        "inmemory",
        "in_memory",
        "stub",
        "fake",
        "dummy",
        "noop",
        "null_",
        "adapter",
        "compositionroot",
        "composition_root",
        "registry_impl",
        "engine",
        "resolver",
        "verifier",
        "signer",
        "trust_store",
    }
)

EXPORTED_IMPLEMENTATION_TOKENS = tuple(
    sorted(
        banned_capability_tokens(
            VERSION_SUBPHASE[api.__version__], EXPORTED_IMPLEMENTATION_UNLOCK
        )
    )
)


#: The four exported-surface tokens D-33 records as BR-2C's. The candidate
#: rung's ratified release transition lifts exactly these at ``BR-2C-RC``.
BR2C_EXPORT_TOKENS = frozenset({"denyall", "deny_all", "verifier", "trust_store"})


def test_the_exported_implementation_ban_is_exactly_what_the_transition_leaves():
    """Milestone-conditional; at the candidate rung BR-2A's set minus BR-2C's four.

    Both directions: a BR-2D or permanent token that unlocked early is a missing
    element, a BR-2C token still banned is an extra one.
    """

    assert set(EXPORTED_IMPLEMENTATION_TOKENS) == (
        BR2A_FROZEN_EXPORT_TOKENS - BR2C_EXPORT_TOKENS
    )
    assert set(EXPORTED_IMPLEMENTATION_UNLOCK) == BR2A_FROZEN_EXPORT_TOKENS
    assert {
        token for token, unlock in EXPORTED_IMPLEMENTATION_UNLOCK.items()
        if unlock == "BR-2C-RC"
    } == BR2C_EXPORT_TOKENS
    assert banned_capability_tokens("BR-2C-0", EXPORTED_IMPLEMENTATION_UNLOCK) == (
        BR2A_FROZEN_EXPORT_TOKENS
    )


def test_a_placeholder_implementation_name_is_banned_at_every_subphase():
    """The five permanent entries above never lift — a name ban, not §17."""

    permanent = {
        token
        for token, unlock in EXPORTED_IMPLEMENTATION_UNLOCK.items()
        if unlock is None
    }
    assert permanent == {"stub", "fake", "dummy", "noop", "null_"}
    for subphase in SUBPHASE_LADDER:
        still = banned_capability_tokens(subphase, EXPORTED_IMPLEMENTATION_UNLOCK)
        assert permanent <= still, subphase


# --------------------------------------------------------------------------- #
# Confusable comparison contract
# --------------------------------------------------------------------------- #
def test_happy_the_contract_names_the_nine_locator_elements():
    assert len(BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS) == 9
    assert BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT["compared_elements"] == (
        BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS
    )


def test_normalization_is_explicitly_prohibited_not_merely_unimplemented():
    assert BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT["normalization_posture"] == (
        BenchmarkConfusableNormalizationPosture.EXPLICITLY_PROHIBITED.value
    )
    assert BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT["rewrite_permitted"] is False


def test_the_posture_enum_admits_exactly_one_member():
    assert [p.value for p in BenchmarkConfusableNormalizationPosture] == [
        "EXPLICITLY_PROHIBITED"
    ]


def test_no_complete_unicode_algorithm_is_claimed_and_the_slot_is_empty():
    """An honest empty slot beats a partial implementation presented as complete."""

    contract = BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT
    assert contract["algorithm_identifier"] is None
    assert contract["unicode_version"] is None
    assert contract["completeness_claim"].startswith("NONE")


def test_the_outcome_is_rejection_only():
    assert "rejection only" in BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT["outcome"]
    assert BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT["refusal_reason"] == (
        BenchmarkRegistryRefusalReason.CONFUSABLE_COORDINATE.value
    )


def test_the_publisher_is_not_among_the_compared_elements():
    """Comparing it would partition the namespace and make squatting easier."""

    for element in BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS:
        assert "publisher" not in element


def test_the_contract_is_immutable():
    with pytest.raises(TypeError):
        BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT["algorithm_identifier"] = "x"


def test_no_casefold_or_nkfc_call_exists_anywhere_in_the_package():
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[2] / "src"
    for path in src.rglob("*.py"):
        code = "\n".join(
            line
            for line in path.read_text().splitlines()
            if not line.strip().startswith("#")
        )
        assert ".casefold(" not in code, path.name
        assert '"NFKC"' not in code, path.name
        assert ".lower()" not in code, path.name


# --------------------------------------------------------------------------- #
# Inert ports
# --------------------------------------------------------------------------- #
def test_all_four_ports_are_protocols():
    for port in PORTS:
        assert getattr(port, "_is_protocol", False), port.__name__


def test_no_port_can_be_instantiated():
    for port in PORTS:
        with pytest.raises(TypeError):
            port()


#: The two classes the candidate rung ships against the approval-verifier
#: port, and the only two. Pinned by name so a third implementation — or one
#: against any other port — is a reviewed change rather than a silent one.
VERIFIER_IMPLEMENTATIONS = frozenset(
    {"BenchmarkDenyAllVerifier", "BenchmarkEd25519Verifier"}
)


def test_exactly_the_two_candidate_verifiers_satisfy_the_verifier_port_and_nothing_else():
    """Structurally, by method-name coverage, so nothing satisfies one by accident.

    At the candidate rung exactly two exported classes satisfy
    ``BenchmarkApprovalVerifierPort`` — the candidate verifier and the exact
    deny-all default — and **no** class satisfies the store, trust-directory or
    clock port: no store, no anchor directory and no clock ship here, and BR-2D
    owns all three.
    """

    import inspect

    import ugence_benchmark_registry_authority as pkg

    concrete = {
        name: value
        for name in pkg.__all__
        for value in [getattr(pkg, name)]
        if inspect.isclass(value) and not getattr(value, "_is_protocol", False)
    }
    assert concrete, "the scan found no classes at all"
    for port in PORTS:
        required = {
            name
            for name in dir(port)
            if not name.startswith("_") and callable(getattr(port, name, None))
        }
        assert required, port.__name__
        satisfying = {
            name
            for name, cls in concrete.items()
            if required <= {n for n in dir(cls) if not n.startswith("_")}
        }
        if port is pkg.BenchmarkApprovalVerifierPort:
            assert satisfying == VERIFIER_IMPLEMENTATIONS, satisfying
            for name in satisfying:
                assert isinstance(concrete[name], type)
                assert issubclass(concrete[name], object)
        else:
            assert satisfying == set(), (port.__name__, satisfying)


def test_no_placeholder_or_later_milestone_implementation_ships():
    """The ban is on shipping an implementation, so it is checked on **callables**.

    At the candidate rung ``denyall`` and ``verifier`` are lifted — the exact
    deny-all default and the candidate verifier ship — and every BR-2D token
    and every permanent placeholder token stays banned on the exported surface.

    §17 explicitly permits documentation to state the ratified identity-checked
    allow-list requirement, and forbids implementing or simulating it. A string
    constant stating the requirement is therefore correct and must not be
    flagged; a class or function carrying one of these names would be the
    executable placeholder the section prohibits.
    """

    import inspect

    import ugence_benchmark_registry_authority as pkg

    banned = EXPORTED_IMPLEMENTATION_TOKENS
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if not (inspect.isclass(value) or inspect.isfunction(value)):
            continue
        # A Protocol is a declaration of a shape, not an implementation of one.
        # ``BenchmarkApprovalVerifierPort`` names the seam a verifier must fit;
        # the previous test proves nothing in this package fits it.
        if getattr(value, "_is_protocol", False):
            continue
        lowered = symbol.lower()
        for token in banned:
            assert token not in lowered, symbol


def test_the_only_adapter_named_symbol_is_a_documentation_constant():
    import ugence_benchmark_registry_authority as pkg

    adapter_symbols = [s for s in pkg.__all__ if "adapter" in s.lower()]
    assert adapter_symbols == ["BENCHMARK_PRODUCTION_ADAPTER_ADMISSION_REQUIREMENT"]
    assert isinstance(
        pkg.BENCHMARK_PRODUCTION_ADAPTER_ADMISSION_REQUIREMENT, str
    )


def test_no_port_method_has_an_executable_body_anywhere_in_the_package():
    """A Protocol member is ``...``; a ``NotImplementedError`` body would be a lie."""

    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[2] / "src"
    offenders = []
    for path in src.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                target = node.exc
                if isinstance(target, ast.Call):
                    target = target.func
                if isinstance(target, ast.Name) and target.id == (
                    "NotImplementedError"
                ):
                    offenders.append(path.name)
    assert offenders == [], offenders


def test_the_composition_error_exists_and_is_raised_by_nothing_here():
    import ast
    import pathlib

    assert issubclass(BenchmarkRegistryCompositionError, BenchmarkRegistryContractError)
    src = pathlib.Path(__file__).resolve().parents[2] / "src"
    raisers = []
    for path in src.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                target = node.exc
                if isinstance(target, ast.Call):
                    target = target.func
                if (
                    isinstance(target, ast.Name)
                    and target.id == "BenchmarkRegistryCompositionError"
                ):
                    raisers.append(path.name)
    assert raisers == [], raisers


# --------------------------------------------------------------------------- #
# The consistency descriptor
# --------------------------------------------------------------------------- #
def test_the_descriptor_has_exactly_one_field_and_it_is_a_closed_scope():
    fields = dataclasses.fields(BENCHMARK_REGISTRY_DECLARED_CONSISTENCY)
    assert [f.name for f in fields] == ["scope"]
    assert [s.value for s in BenchmarkRegistryConsistencyScope] == [
        "PROCESS_LOCAL_ONLY"
    ]


def test_no_boolean_capability_field_exists_anywhere_on_the_descriptor():
    """D-15 retires ``is_production_grade``: there is no flag, because no flag."""

    for f in dataclasses.fields(BENCHMARK_REGISTRY_DECLARED_CONSISTENCY):
        assert f.type is not bool
        assert "is_" not in f.name
        assert "grade" not in f.name
        assert "production" not in f.name


def test_exactly_two_guarantees_are_claimed_and_five_are_disclaimed():
    descriptor = BENCHMARK_REGISTRY_DECLARED_CONSISTENCY
    claimed = [
        descriptor.process_local_atomicity,
        descriptor.read_after_write,
    ]
    assert all(
        c is BenchmarkRegistryConsistencyClaim.CLAIMED_WITHIN_DECLARED_SCOPE
        for c in claimed
    )
    assert len(BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES) == 5
    for name in BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES:
        assert getattr(descriptor, name) is (
            BenchmarkRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED
        )


def test_the_five_disclaimers_are_the_ratified_five():
    assert set(BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES) == {
        "durability",
        "multi_process_coordination",
        "distributed_strong_consistency",
        "eventual_consistency_safety",
        "cross_process_atomic_revocation",
    }


def test_no_guarantee_answer_can_be_flipped():
    descriptor = BenchmarkRegistryStoreConsistencyDescriptor()
    for name in BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES:
        with pytest.raises(AttributeError):
            object.__setattr__(descriptor, name, "CLAIMED_WITHIN_DECLARED_SCOPE")
        assert getattr(descriptor, name) is (
            BenchmarkRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED
        )


def test_an_over_claiming_descriptor_is_unconstructible_not_merely_refused():
    """There is no DURABLE scope member to pass, so the claim cannot be spelled."""

    scopes = {s.name for s in BenchmarkRegistryConsistencyScope}
    for absent in ("DURABLE", "DISTRIBUTED", "PRODUCTION", "MULTI_PROCESS"):
        assert absent not in scopes
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkRegistryStoreConsistencyDescriptor(scope="PROCESS_LOCAL_ONLY")


def test_the_descriptor_is_not_canonicalizable():
    """It declares something about a future port; it is not an artifact."""

    from ugence_benchmark_registry_authority.api import (
        BenchmarkRegistryCanonicalizationError,
        canonical_bytes,
    )

    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(BENCHMARK_REGISTRY_DECLARED_CONSISTENCY)


def test_the_allow_list_requirement_is_documented_and_not_implemented():
    text = BENCHMARK_PRODUCTION_ADAPTER_ADMISSION_REQUIREMENT
    assert "interpreter identity" in text
    assert "implemented nowhere in this distribution" in text
    import ugence_benchmark_registry_authority as pkg

    for symbol in pkg.__all__:
        assert "allow_list" not in symbol.lower()
        assert "allowlist" not in symbol.lower()
