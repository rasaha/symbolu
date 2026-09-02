"""Spec §7 (correction 30) and rows R52–R55: produced_at is required, timezone-aware
and caller-supplied; the engine reads no clock; digests behave as stated."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

import matrix_fixtures as fx
from ugence_readiness_comparison import compare
from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode


def digests(res):
    return [a.assessment_digest for a in res.assessments]


def test_r52_omitted_produced_at_raises_type_error():
    with pytest.raises(TypeError):
        compare(fx.two_method_request())  # type: ignore[call-arg]


def test_r53_naive_produced_at_refused():
    with pytest.raises(ContractError) as ei:
        compare(fx.two_method_request(), produced_at=datetime(2026, 9, 2, 12, 0))
    assert ei.value.code is ContractErrorCode.DATETIME_NAIVE
    with pytest.raises(ContractError) as ei:
        compare(fx.two_method_request(), produced_at="2026-09-02T12:00:00Z")  # type: ignore[arg-type]
    assert ei.value.code is ContractErrorCode.DATETIME_NAIVE


def test_r54_same_instant_identical_digests_and_offset_invariance():
    a = compare(fx.two_method_request(), produced_at=fx.NOW)
    b = compare(fx.two_method_request(), produced_at=fx.NOW)
    shifted = compare(fx.two_method_request(), produced_at=fx.NOW.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert a.result_digest == b.result_digest == shifted.result_digest
    assert digests(a) == digests(b) == digests(shifted)
    assert a.produced_at == shifted.produced_at


def test_r55_changing_the_instant_changes_assessment_digests_not_result_digest():
    a = compare(fx.two_method_request(), produced_at=fx.NOW)
    later = compare(fx.two_method_request(), produced_at=fx.NOW + timedelta(microseconds=1))
    assert a.result_digest == later.result_digest
    assert digests(a) != digests(later)
    assert all(x.assessed_at == later.produced_at for x in later.assessments)


def test_assessment_digests_identical_across_processes_and_hash_seeds():
    here = pathlib.Path(__file__).resolve().parent
    contract_tests = here.parents[2] / "reasoning-method-governance" / "tests"
    code = (
        "import sys; sys.path[:0]=[%r]\n"
        "import matrix_fixtures as fx\n"
        "from ugence_readiness_comparison import compare\n"
        "r = compare(fx.two_method_request(), produced_at=fx.NOW)\n"
        "print(r.result_digest, *[a.assessment_digest for a in r.assessments])\n"
    ) % str(contract_tests)
    outs = set()
    for seed in ("0", "1", "2", "random"):
        env = {"PYTHONHASHSEED": seed, "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": ":".join(sys.path)}
        outs.add(subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True, env=env).stdout.strip())
    local = compare(fx.two_method_request(), produced_at=fx.NOW)
    assert outs == {" ".join([local.result_digest, *digests(local)])}
