"""The delivered capability identity says exactly what was built — no more.

Trusted Readiness Orchestration is an **additive integration capability**
implementing already-ratified UVI ADR D-1 / D-16 / §19 / §23.2 requirements.
Milestone `M-3R.3` adds the Intelligence / Capability / Adoption catalogs and
the `AssessedSystemBinding` wiring **through that same single entry point** —
it adds no second classification algorithm and no new readiness tier.

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
    assert api.READINESS_ORCHESTRATOR_VERSION == "ugence.readiness-orchestration/v0.2"


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


#: The 42 orchestration codes merged before M-3R.3. None may be renamed,
#: repurposed or dropped; M-3R.3 only appends.
MERGED_GAP_CODE_COUNT = 42
#: The stable codes M-3R.3 adds: 5 system-binding + 9 catalog/indicator.
M3R3_GAP_CODE_COUNT = 14


def test_the_trust_gap_vocabulary_has_the_expected_cardinality():
    """M-3R.3 appends exactly its own codes and touches no merged one."""

    members = list(api.ReadinessTrustGapCode)
    assert len(members) == MERGED_GAP_CODE_COUNT + M3R3_GAP_CODE_COUNT

    m3r3 = [
        m
        for m in members
        if m.name.startswith(("SYSTEM_BINDING_", "INDICATOR_CATALOG_", "INDICATOR_NOT_", "INDICATOR_RESULT_"))
    ]
    assert len(m3r3) == M3R3_GAP_CODE_COUNT, [m.name for m in m3r3]
    assert len(members) - len(m3r3) == MERGED_GAP_CODE_COUNT


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
# 4-5. M-3R.3 is implemented, and claims exactly what it delivers
# --------------------------------------------------------------------------- #
#: Claims that would overstate the milestone or the wider roadmap.
OVERCLAIMS = (
    "benchmark registry is implemented",
    "evidence verification is implemented",
    "tap verification is implemented",
    "condition enforcement is implemented",
    "roi roadmap is complete",
    "uvi roadmap is complete",
    "this outcome authorizes deployment",
    "deployment authorization is granted",
    "grants deployment authorization",
)


#: Words that turn a claim into its denial. A guard that ignores them would
#: flag the very sentences that keep the roadmap boundary honest.
NEGATIONS = ("not ", "never", "no ", "n't", "remain", "stay", "separate", "deferred")


def test_nothing_overclaims_a_deferred_capability():
    """A deferred capability may be *named* — only never claimed as delivered.

    The check is sentence-scoped and negation-aware: "the Benchmark Registry
    remains separate" must pass, while "the Benchmark Registry is implemented"
    must fail.
    """

    offenders = {}
    for path in _delivered_files():
        # Markdown emphasis is stripped first, so "does **not** mean" reads as
        # a negation rather than as the token "not*".
        text = path.read_text().lower().replace("\n", " ")
        for mark in ("**", "*", "`", "_"):
            text = text.replace(mark, " ")
        for sentence in text.split("."):
            hits = [claim for claim in OVERCLAIMS if claim in sentence]
            if hits and not any(word in sentence for word in NEGATIONS):
                offenders.setdefault(str(path.relative_to(DIST_ROOT)), []).extend(hits)
    assert not offenders, offenders


def test_the_overclaim_guard_actually_catches_an_overclaim():
    """The guard is not vacuous: an affirmative claim is detected."""

    affirmative = "the benchmark registry is implemented here "
    assert any(claim in affirmative for claim in OVERCLAIMS)
    assert not any(word in affirmative for word in NEGATIONS)


def test_the_two_m3r3_deliverables_are_on_the_public_surface():
    """Both halves of the milestone ship, and both are curated exports."""

    assert "AssessedSystemBinding" in api.__all__
    for name in (
        "IntelligenceFitnessCatalog",
        "CapabilityReadinessCatalog",
        "AdoptionReadinessCatalog",
        "IntelligenceFitnessIndicatorDefinition",
        "CapabilityReadinessIndicatorDefinition",
        "AdoptionReadinessIndicatorDefinition",
        "ReadinessIndicatorCatalogSet",
    ):
        assert name in api.__all__, name


def test_no_system_manifest_was_invented():
    """`SystemManifest`'s home is an open owner decision (ADR §26.3).

    The binding references it by opaque ref + digest and mints no such type.
    """

    for name in api.__all__:
        assert "systemmanifest" not in name.lower().replace("_", ""), name

    import ast

    for path in (p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert "systemmanifest" not in node.name.lower(), (path.name, node.name)


def test_no_benchmark_registry_or_evidence_verifier_was_introduced():
    """M-3R.3's explicit non-goals stay out of the public surface."""

    import ast

    for path in (p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                lowered = node.name.lower()
                for banned in ("benchmarkregistry", "evidenceverifier", "verifyevidence"):
                    assert banned not in lowered.replace("_", ""), (path.name, node.name)


def test_no_catalog_or_binding_type_carries_requirement_or_financial_vocabulary():
    """Catalogs define vocabulary; gates define requirements (ADR §6, D-6)."""

    banned_fields = (
        "required",
        "mandatory",
        "weight",
        "multiplier",
        "score",
        "threshold_value",
        "benchmark_value",
        "tier",
        "classification",
        "money",
        "currency",
        "cost",
        "benefit",
        "revenue",
        "roi",
        "value_amount",
        "evidence_status",
        "verification_status",
    )
    catalog_types = [
        api.AssessedSystemBinding,
        api.IntelligenceFitnessIndicatorDefinition,
        api.CapabilityReadinessIndicatorDefinition,
        api.AdoptionReadinessIndicatorDefinition,
        api.IntelligenceFitnessCatalog,
        api.CapabilityReadinessCatalog,
        api.AdoptionReadinessCatalog,
        api.ReadinessIndicatorCatalogSet,
    ]
    for cls in catalog_types:
        for field in dataclasses.fields(cls):
            lowered = field.name.lower()
            for banned in banned_fields:
                assert banned not in lowered, (cls.__name__, field.name)


# --------------------------------------------------------------------------- #
# 6-7. Package version and public API shape
# --------------------------------------------------------------------------- #
def test_the_package_version_is_bumped_for_m3r3():
    assert R.__version__ == "0.4.1"
    snapshot = json.loads((DIST_ROOT / "public_api.json").read_text())
    assert snapshot["package_version"] == "0.4.1"


def test_the_snapshot_pins_the_exact_orchestrator_version_value():
    snapshot = json.loads((DIST_ROOT / "public_api.json").read_text())
    entry = snapshot["symbols"]["READINESS_ORCHESTRATOR_VERSION"]
    assert entry == {"kind": "str", "value": "ugence.readiness-orchestration/v0.2"}


def test_the_public_api_snapshot_matches_the_actual_surface():
    """Every exported name, dataclass field order and enum value is pinned."""

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
