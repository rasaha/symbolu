"""Declared recorded time — required where it belongs, absent where it does not."""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
from datetime import datetime, timedelta, timezone

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BenchmarkRegistryContractError,
    canonical_bytes,
    canonical_digest,
)

PKG = pathlib.Path(__file__).resolve().parents[2]
SRC = PKG / "src" / "ugence_benchmark_registry_authority"

EVENT_PAYLOADS = (
    ("BenchmarkSubmissionRecordPayload", fx.submission_record),
    ("BenchmarkAdmissionDecisionPayload", fx.admission_decision),
    ("BenchmarkPostAdmissionRejectionEventPayload", fx.post_admission_rejection),
    ("BenchmarkRegistrationEventPayload", fx.registration_event),
    ("BenchmarkRevocationEventPayload", fx.revocation_event),
    ("BenchmarkConflictRecordPayload", fx.conflict_record),
)

ENVELOPES = (
    ("BenchmarkPublisherSubmissionEnvelope", fx.publisher_envelope),
    ("BenchmarkApprovalEnvelope", fx.approval_envelope),
    ("BenchmarkRevocationEnvelope", fx.revocation_envelope),
)


def test_happy_every_registry_event_payload_carries_declared_recorded_at():
    for name, builder in EVENT_PAYLOADS:
        fields = {f.name for f in dataclasses.fields(builder())}
        assert "declared_recorded_at" in fields, name


def test_the_post_admission_rejection_event_carries_it_too():
    """Named explicitly: it is the payload the state-machine correction added."""

    fields = {f.name for f in dataclasses.fields(fx.post_admission_rejection())}
    assert "declared_recorded_at" in fields


@pytest.mark.parametrize("name,builder", EVENT_PAYLOADS)
def test_declared_recorded_at_is_required_not_defaulted(name, builder):
    genuine = builder()
    kwargs = {
        f.name: getattr(genuine, f.name)
        for f in dataclasses.fields(genuine)
        if f.name != "declared_recorded_at"
    }
    with pytest.raises(TypeError):
        type(genuine)(**kwargs)


@pytest.mark.parametrize("name,builder", EVENT_PAYLOADS)
def test_a_naive_declared_recorded_at_is_refused(name, builder):
    with pytest.raises(BenchmarkRegistryContractError):
        builder(declared_recorded_at=datetime(2026, 3, 1, 12, 0, 0))


@pytest.mark.parametrize("name,builder", EVENT_PAYLOADS)
def test_declared_recorded_at_participates_in_the_digest(name, builder):
    assert canonical_digest(
        builder(declared_recorded_at=fx.AS_OF)
    ) != canonical_digest(builder())


@pytest.mark.parametrize("name,builder", ENVELOPES)
def test_no_envelope_carries_declared_recorded_at(name, builder):
    """A publisher, an approver and a revoker do not observe the registry's clock."""

    attrs = {f.name for f in dataclasses.fields(builder())} | set(
        dir(type(builder()))
    )
    assert "declared_recorded_at" not in attrs, name


def test_the_revocation_envelope_carries_no_recorded_at_and_no_prev_event_digest():
    """§13: no field exists here merely to be populated later."""

    envelope = fx.revocation_envelope()
    names = {f.name for f in dataclasses.fields(envelope)}
    assert "recorded_at" not in names
    assert "declared_recorded_at" not in names
    assert "prev_event_digest" not in names
    assert not hasattr(envelope, "prev_event_digest")


def test_effective_at_and_declared_recorded_at_are_not_interchangeable():
    event = fx.revocation_event()
    assert event.effective_at == fx.EFFECTIVE_AT
    assert event.declared_recorded_at == fx.RECORDED_AT
    assert event.effective_at != event.declared_recorded_at
    assert "effective_at" not in {f.name for f in dataclasses.fields(event)}
    assert isinstance(type(event).effective_at, property)


def test_effective_at_lives_only_on_the_revocation_envelope():
    declarations = [
        name
        for name, builder in fx.PINNED_VECTOR_BUILDERS
        if "effective_at" in {f.name for f in dataclasses.fields(builder())}
    ]
    assert declarations == ["BenchmarkRevocationEnvelope"]


def test_both_timestamps_participate_independently_in_the_revocation_digest():
    baseline = canonical_digest(fx.revocation_event())
    moved_effective = canonical_digest(
        fx.revocation_event(
            revocation_envelope=fx.revocation_envelope(effective_at=fx.AS_OF)
        )
    )
    moved_recorded = canonical_digest(
        fx.revocation_event(declared_recorded_at=fx.AS_OF)
    )
    assert len({baseline, moved_effective, moved_recorded}) == 3


def test_a_utc_offset_spelling_of_one_instant_does_not_move_a_digest():
    shifted = fx.RECORDED_AT.astimezone(timezone(timedelta(hours=-8)))
    assert canonical_digest(
        fx.submission_record(declared_recorded_at=shifted)
    ) == canonical_digest(fx.submission_record())


def test_caller_construction_never_establishes_timestamp_authority():
    record = fx.submission_record(declared_recorded_at=fx.AS_OF)
    assert record.authority_verified is False
    assert record.registry_admission_established is False


def test_no_br2a_callable_reads_a_clock_anywhere_in_the_source_tree():
    """A source-tree scan, the way the frozen BR-1 layer's no-clock test does it."""

    forbidden = (
        r"\bdatetime\.now\b",
        r"\bdatetime\.utcnow\b",
        r"\bdatetime\.today\b",
        r"\btime\.time\b",
        r"\btime\.monotonic\b",
        r"\btime\.perf_counter\b",
        r"\bdate\.today\b",
    )
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        source = path.read_text()
        code = "\n".join(
            line
            for line in source.splitlines()
            if not line.strip().startswith("#")
        )
        # Strip docstrings so prose describing a future clock does not trip it.
        code = re.sub(r'"""..*?"""', "", code, flags=re.S)
        for pattern in forbidden:
            if re.search(pattern, code):
                offenders.append(f"{path.name}: {pattern}")
    assert offenders == [], offenders


def _absolute_imports(path):
    """Every absolute (non-relative) module imported by ``path``, via the AST.

    Parsed rather than pattern-matched: a regex over source text also matches
    the words "import" and "from" inside docstrings, which is how a prose
    sentence about a future clock ends up reported as a dependency.
    """

    tree = ast.parse(path.read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
    return modules


def test_no_module_imports_a_source_of_nondeterminism():
    """No import of a random, environment, filesystem, process or network module.

    Relative imports are excluded by construction, so this package's own
    ``contracts.requests`` module is never confused with the third-party HTTP
    client of the same name.
    """

    forbidden = {
        "random",
        "secrets",
        "uuid",
        "os",
        "socket",
        "requests",
        "urllib",
        "http",
        "pathlib",
        "subprocess",
        "time",
        "importlib",
    }
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        for module in sorted(_absolute_imports(path) & forbidden):
            offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


def test_the_only_non_stdlib_import_anywhere_is_the_frozen_br1_layer():
    """Every absolute import is either the standard library or BR-1.

    This is the import-graph half of the dependency boundary: the declared
    metadata names exactly one runtime dependency, and the code imports exactly
    that one.
    """

    allowed_stdlib = {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "json",
        "re",
        "types",
        "typing",
        "unicodedata",
    }
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        for module in sorted(_absolute_imports(path)):
            if module in allowed_stdlib or module == "ugence_benchmark_registry":
                continue
            offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


def test_astimezone_is_never_called_with_no_argument():
    """The zero-argument form would infer the machine's local zone."""

    for path in sorted(SRC.rglob("*.py")):
        assert ".astimezone()" not in path.read_text(), path.name


def test_the_encoder_renders_microseconds_and_a_trailing_z():
    raw = canonical_bytes(
        fx.submission_record(
            declared_recorded_at=fx.RECORDED_AT.replace(microsecond=7)
        )
    ).decode()
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.000007Z", raw)
