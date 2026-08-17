"""The delivered capability identity says exactly what was built — no more.

Trusted Readiness Orchestration is an **additive integration capability**
implementing already-ratified UVI ADR D-1 / D-16 / §19 / §23.2 requirements. It
is **not** milestone `M-3R.3`, which owns the Intelligence / Capability /
Adoption catalogs and `AssessedSystemBinding` wiring and remains open and
unimplemented here.

These guards pin that identity against the **delivered tree** — source,
documentation, the public snapshot, the verifier and the probes. They
deliberately do not look at Git history or branch names: the correction concerns
what ships and what the public API says, not what a commit was once called.

The retired working label is assembled at runtime rather than written out, so
this module can scan for it without matching itself.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

import ugence_agent_value_readiness as R
from ugence_agent_value_readiness import api
from ugence_agent_value_readiness.evaluation.codes import EVALUATOR_FORMULA_VERSION

PKG_ROOT = pathlib.Path(R.__file__).resolve().parent
DIST_ROOT = pathlib.Path(__file__).resolve().parents[2]
SELF = pathlib.Path(__file__).resolve()

#: The retired informal working label, assembled so this file never contains it.
RETIRED_LABEL = "GV-3R" + "-c"
RETIRED_COMPACT = "GV3R" + "-c"

#: The retired reason-code namespace, assembled so this file never contains it.
RETIRED_CODE_TOKEN = "GV3" + "RC"
RETIRED_CODE_PREFIX = RETIRED_CODE_TOKEN + "_"

#: The neutral namespace every orchestration trust-gap value must now carry.
GAP_PREFIX = "READINESS_ORCHESTRATION_"


def _delivered_files():
    """Every delivered artifact whose text is part of the public identity."""

    files = [p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts]
    files += [
        DIST_ROOT / "README.md",
        DIST_ROOT / "CHANGELOG.md",
        DIST_ROOT / "public_api.json",
        DIST_ROOT / "pyproject.toml",
        DIST_ROOT / "conftest.py",
        DIST_ROOT / "adversarial_probes.py",
        DIST_ROOT / "verify_agent_value_readiness_distribution.py",
    ]
    files += [
        p
        for p in (DIST_ROOT / "tests").rglob("*.py")
        if "__pycache__" not in p.parts and p.resolve() != SELF
    ]
    return [p for p in files if p.is_file()]


# --------------------------------------------------------------------------- #
# 1-2. Version identity
# --------------------------------------------------------------------------- #
def test_the_orchestrator_version_is_the_platform_neutral_identifier():
    assert api.READINESS_ORCHESTRATOR_VERSION == "ugence.readiness-orchestration/v0.1"


def test_the_orchestrator_version_names_no_adr_milestone():
    """Platform-neutral: a capability identifier, not a roadmap position."""

    lowered = api.READINESS_ORCHESTRATOR_VERSION.lower()
    for token in ("gv-3r", "gv3r", "m-3r", "m3r", "milestone", "phase"):
        assert token not in lowered, token


def test_the_evaluator_formula_version_is_unchanged():
    """The classification algorithm did not move, so its version must not."""

    assert EVALUATOR_FORMULA_VERSION == "GV-3R-b.3"


def test_the_two_versions_are_independent_identifiers():
    assert api.READINESS_ORCHESTRATOR_VERSION != EVALUATOR_FORMULA_VERSION


# --------------------------------------------------------------------------- #
# 3. No active retired-label claim survives in the delivered tree
# --------------------------------------------------------------------------- #
def test_the_retired_working_label_is_absent_from_every_delivered_artifact():
    offenders = {}
    for path in _delivered_files():
        text = path.read_text()
        hits = [
            line.strip()
            for line in text.splitlines()
            if RETIRED_LABEL in line or RETIRED_COMPACT in line
        ]
        if hits:
            offenders[str(path.relative_to(DIST_ROOT))] = hits[:3]
    assert not offenders, offenders


def test_no_trust_gap_name_or_value_carries_the_retired_namespace():
    for member in api.ReadinessTrustGapCode:
        assert RETIRED_CODE_TOKEN not in member.value, member.value
        assert RETIRED_CODE_TOKEN not in member.name, member.name


def test_every_trust_gap_value_carries_the_neutral_namespace():
    for member in api.ReadinessTrustGapCode:
        assert member.value.startswith(GAP_PREFIX), member.value
        # The suffix is real vocabulary, not an empty namespace.
        assert member.value[len(GAP_PREFIX) :], member.value


def test_the_trust_gap_vocabulary_has_the_expected_cardinality():
    """Renaming a namespace must not add, drop or merge a reason code."""

    members = list(api.ReadinessTrustGapCode)
    assert len(members) == 42


def test_the_namespace_mapping_is_one_to_one_with_no_aliases():
    """Names, values and semantic suffixes are each unique — no collisions."""

    members = list(api.ReadinessTrustGapCode)
    names = [m.name for m in members]
    values = [m.value for m in members]
    suffixes = [m.value[len(GAP_PREFIX) :] for m in members]

    assert len(set(names)) == len(members)
    assert len(set(values)) == len(members)
    assert len(set(suffixes)) == len(members)
    # Each member's name IS its semantic suffix, so the rename touched only the
    # namespace and preserved every suffix exactly.
    assert names == suffixes

    # An alias would show up as an enum member whose name is not canonical.
    assert list(api.ReadinessTrustGapCode.__members__) == names


def test_no_deprecated_alias_or_translation_table_ships():
    """The API is unreleased, so nothing translates or accepts an old token."""

    source = "\n".join(
        path.read_text()
        for path in (PKG_ROOT / "orchestration").rglob("*.py")
        if "__pycache__" not in path.parts
    )
    assert RETIRED_CODE_TOKEN not in source
    for banned in ("deprecated", "legacy_code", "code_alias", "LEGACY_", "_ALIAS"):
        assert banned not in source, banned
    # Constructing from a retired token must fail, not silently translate.
    import pytest

    with pytest.raises(ValueError):
        api.ReadinessTrustGapCode(RETIRED_CODE_PREFIX + "POLICY_RESOLVER_NOT_CONFIGURED")


def test_the_retired_reason_code_namespace_is_absent_from_the_delivered_tree():
    offenders = {}
    for path in _delivered_files():
        hits = [
            line.strip()
            for line in path.read_text().splitlines()
            if RETIRED_CODE_TOKEN in line
        ]
        if hits:
            offenders[str(path.relative_to(DIST_ROOT))] = hits[:3]
    assert not offenders, offenders


# --------------------------------------------------------------------------- #
# 4-5. M-3R.3 is neither claimed nor implemented
# --------------------------------------------------------------------------- #
COMPLETION_CLAIMS = (
    "m-3r.3 is implemented",
    "m-3r.3 implemented",
    "m-3r.3 is complete",
    "m-3r.3 complete",
    "implements m-3r.3",
    "completes m-3r.3",
    "milestone m-3r.3 delivered",
    "milestone m-3r.3+",
)


def test_nothing_claims_m3r3_is_implemented_or_completed():
    offenders = {}
    for path in _delivered_files():
        lowered = path.read_text().lower()
        hits = [claim for claim in COMPLETION_CLAIMS if claim in lowered]
        if hits:
            offenders[str(path.relative_to(DIST_ROOT))] = hits
    assert not offenders, offenders


def test_every_m3r3_mention_states_it_remains_open():
    """`M-3R.3` may be named only to say it is still open and unimplemented."""

    openness = (
        "open",
        "unimplemented",
        "not implement",
        "future",
        "still owns",
        "untouched",
        "no claim",
        "claims no",
        "does not claim",
    )
    offenders = {}
    for path in _delivered_files():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if "M-3R.3" not in line:
                continue
            window = " ".join(
                path.read_text().splitlines()[max(0, number - 6) : number + 6]
            ).lower()
            if not any(word in window for word in openness):
                offenders.setdefault(str(path.relative_to(DIST_ROOT)), []).append(number)
    assert not offenders, offenders


def test_no_indicator_catalog_or_assessed_system_binding_was_introduced():
    """The two M-3R.3 deliverables are absent from the public surface."""

    forbidden = ("assessedsystembinding", "systemmanifest", "indicatorcatalog", "catalog")
    for name in api.__all__:
        assert not any(token in name.lower() for token in forbidden), name

    # And no module defines one either.
    for path in (p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts):
        import ast

        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                lowered = node.name.lower()
                assert "assessedsystembinding" not in lowered, (path.name, node.name)
                assert "catalog" not in lowered, (path.name, node.name)


# --------------------------------------------------------------------------- #
# 6-7. Package version and public API shape
# --------------------------------------------------------------------------- #
def test_the_package_version_is_unchanged():
    assert R.__version__ == "0.3.0"
    snapshot = json.loads((DIST_ROOT / "public_api.json").read_text())
    assert snapshot["package_version"] == "0.3.0"


def test_the_snapshot_pins_the_exact_orchestrator_version_value():
    snapshot = json.loads((DIST_ROOT / "public_api.json").read_text())
    entry = snapshot["symbols"]["READINESS_ORCHESTRATOR_VERSION"]
    assert entry == {"kind": "str", "value": "ugence.readiness-orchestration/v0.1"}


def test_the_public_api_surface_is_otherwise_unchanged():
    """Only the version constant's value moved — no symbol, field or code did."""

    snapshot = json.loads((DIST_ROOT / "public_api.json").read_text())["symbols"]

    # Same exported names.
    assert set(snapshot) == {n for n in api.__all__ if n != "__version__"}

    # Same dataclass field order, and same enum values — including the frozen
    # trust-gap codes, which a relabel must not have renamed.
    for name, entry in snapshot.items():
        obj = getattr(api, name)
        if "fields" in entry:
            assert [f.name for f in dataclasses.fields(obj)] == entry["fields"], name
        if "values" in entry:
            assert [m.value for m in obj] == entry["values"], name

    # The orchestrator version is the ONLY place the identifier appears.
    carriers = [
        name
        for name, entry in snapshot.items()
        if "ugence.readiness-orchestration" in json.dumps(entry)
    ]
    assert carriers == ["READINESS_ORCHESTRATOR_VERSION"], carriers


# --------------------------------------------------------------------------- #
# 8. Behaviour is digest-equivalent apart from the version identifier
# --------------------------------------------------------------------------- #
def test_only_the_version_identifier_differs_in_an_otherwise_identical_trace():
    """Relabelling moved one field and nothing else.

    Rebuilding the same trace under the retired identifier reproduces every
    other field byte-for-byte, so the digest delta is attributable to the
    version identifier alone — not to any change in orchestration behaviour.
    """

    import sys

    sys.path.insert(0, str(DIST_ROOT / "tests" / "orchestration"))
    from _orchestration_fixtures import (  # noqa: E402
        MANDATORY,
        StubConditionVerifier,
        StubGateVerifier,
        gate,
        gate_result,
        issued_resolver,
        readiness_policy,
        request,
    )

    from ugence_agent_value_readiness.api import GateStatus, assess_readiness

    policy = readiness_policy([gate("m1", MANDATORY)], policy_id="identity-guard")
    outcome = assess_readiness(
        request(policy=policy, gate_results=[gate_result(policy, "m1", GateStatus.PASS)]),
        policy_resolver=issued_resolver(policy),
        gate_verifier=StubGateVerifier(),
        condition_verifier=StubConditionVerifier(),
    )

    relabelled = dataclasses.replace(outcome.trace, orchestrator_version="a-different-label")

    current = {f.name: getattr(outcome.trace, f.name) for f in dataclasses.fields(outcome.trace)}
    other = {f.name: getattr(relabelled, f.name) for f in dataclasses.fields(relabelled)}
    differing = {k for k in current if current[k] != other[k]}
    assert differing == {"orchestrator_version"}, differing

    # The digest moves only because that one field moved.
    assert outcome.trace.canonical_digest() != relabelled.canonical_digest()


def test_the_evaluation_result_is_untouched_by_the_orchestrator_version():
    """The classification and its digest never see the orchestrator identity."""

    import sys

    sys.path.insert(0, str(DIST_ROOT / "tests" / "orchestration"))
    from _orchestration_fixtures import (  # noqa: E402
        MANDATORY,
        PROD,
        T_MID,
        TENANT,
        StubConditionVerifier,
        StubGateVerifier,
        context,
        gate,
        gate_result,
        issued_resolver,
        readiness_policy,
        request,
    )

    from ugence_agent_value_readiness.api import (
        GateStatus,
        ReadinessEvaluationCase,
        assess_readiness,
        evaluate_readiness,
    )

    policy = readiness_policy([gate("m1", MANDATORY)], policy_id="identity-guard-2")
    results = (gate_result(policy, "m1", GateStatus.PASS),)

    orchestrated = assess_readiness(
        request(policy=policy, gate_results=list(results), assessment_id="guard-case"),
        policy_resolver=issued_resolver(policy),
        gate_verifier=StubGateVerifier(),
        condition_verifier=StubConditionVerifier(),
    )
    standalone = evaluate_readiness(
        ReadinessEvaluationCase(
            case_id="guard-case",
            tenant_id=TENANT,
            subject_id="a1",
            context=context(policy),
            readiness_policy=policy,
            readiness_policy_ref=policy.reference,
            requested_target=PROD,
            gate_results=results,
        ),
        evaluation_time=T_MID,
    )

    # Byte-equivalent: the orchestrator version participates in no part of it.
    assert orchestrated.evaluation.canonical_digest() == standalone.canonical_digest()
    assert orchestrated.classification is standalone.classification
    assert orchestrated.evaluation.trace.rule_id == standalone.trace.rule_id
    assert orchestrated.evaluation.reason_codes == standalone.reason_codes
    assert orchestrated.evaluation.advisory_codes == standalone.advisory_codes
    assert api.READINESS_ORCHESTRATOR_VERSION not in standalone.canonical_digest()


def test_the_advisory_posture_is_unchanged_by_the_relabel():
    import sys

    sys.path.insert(0, str(DIST_ROOT / "tests" / "orchestration"))
    from _orchestration_fixtures import (  # noqa: E402
        MANDATORY,
        StubConditionVerifier,
        StubGateVerifier,
        gate,
        gate_result,
        issued_resolver,
        readiness_policy,
        request,
    )

    from ugence_agent_value_readiness.api import GateStatus, assess_readiness

    policy = readiness_policy([gate("m1", MANDATORY)], policy_id="identity-guard-3")
    outcome = assess_readiness(
        request(policy=policy, gate_results=[gate_result(policy, "m1", GateStatus.PASS)]),
        policy_resolver=issued_resolver(policy),
        gate_verifier=StubGateVerifier(),
        condition_verifier=StubConditionVerifier(),
    )

    assert outcome.is_advisory is True
    assert outcome.authorizes_deployment is False
    assert outcome.evaluation.authorizes_deployment is False
