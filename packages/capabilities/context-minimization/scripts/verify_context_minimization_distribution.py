#!/usr/bin/env python3
"""Reproducible proof that Context Minimization installs and operates as a single,
self-contained leaf wheel with NO other Ugence package (and no model/tokenizer) on
the path.

Builds ``ugence-context-minimization`` only, installs it into a fresh virtualenv
with no system site packages and no monorepo path (``--no-index`` — the package
declares zero third-party dependencies), then proves inside that env:

  * ``ugence_context_minimization`` imports from site-packages;
  * the curated public API resolves and versions are correct;
  * ``py.typed`` ships and is installed;
  * a product-neutral demo runs against a small deterministic FAKE oracle showing:
      - structural duplicate removal,
      - oracle-verified safe removal,
      - changed-equivalence restoration,
      - protected-unit retention,
      - fail-closed fallback on an oracle exception;
  * NO ActionGate / experiment / robotics / product / console / model / tokenizer
    package is importable (the minimizer is a leaf that pulls nothing else in).

Run:  python packages/capabilities/context-minimization/scripts/verify_context_minimization_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]

_CHECK = r'''
import importlib.util, sys

import ugence_context_minimization as cm
assert cm.__version__ == "0.2.0", cm.__version__
assert cm.CONTRACT_VERSION == "1.1.0", cm.CONTRACT_VERSION
assert "site-packages" in cm.__file__, cm.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(cm.__file__).resolve().parent / "py.typed").is_file(), "py.typed not installed"

from ugence_context_minimization.api import (
    Context, ContextUnit, OracleEvaluation, ProtectionResult,
    structural_minimize, minimize_context, deduplicate_context,
    MinimizationMode, EquivalenceStatus, InvarianceOracle, OracleRequiredError,
    InvalidRequestError, InvalidUnitError, REASON_CODES,
)
import math as _math

# ---- product-neutral deterministic fake oracle ----------------------------
class FakeOracle:
    # equivalence = the set of 'critical' keywords surviving; opaque to the core.
    KW = ("deploy", "backup")
    def evaluate(self, context, *, evaluation_time=None):
        present = sorted({k for u in context.units for k in self.KW if k in u.text.lower()})
        return OracleEvaluation(equivalence_key="|".join(present), oracle_id="fake",
                                contract_version="1.0", correlation_id=context.correlation_id)

class Boom:
    def evaluate(self, context, *, evaluation_time=None):
        raise RuntimeError("boom")

units = (
    ContextUnit(id="p", text="deploy prod", source_type="state_fact", protected=True),
    ContextUnit(id="dup", text="deploy prod", source_type="state_fact"),         # dup of protected
    ContextUnit(id="crit", text="backup verified", source_type="state_fact"),
    ContextUnit(id="fill", text="weekly sprint filler note", source_type="log_event"),
)
ctx = Context(id="demo", units=units, correlation_id="corr-1")

# 1) structural duplicate removal (protected retained)
s = structural_minimize(ctx, protected_ids=["p"])
assert "p" in s.surviving_ids and "dup" in s.removed_ids, s
assert s.mode is MinimizationMode.STRUCTURAL

# 2) oracle-verified safe removal (filler drops, critical carriers kept)
o = minimize_context(ctx, oracle=FakeOracle(), target_reduction=0.5,
                     protected_ids=["p"], evaluation_time=1.0)
assert not o.fell_back and "fill" in o.removed_ids, o
assert "p" in o.surviving_ids and "crit" in o.surviving_ids
assert o.equivalence_status in (EquivalenceStatus.VERIFIED, EquivalenceStatus.RESTORED)

# 3) changed-equivalence restoration: a critical carrier forced into removal is restored
ctx2 = Context(id="demo2", correlation_id="c", units=(
    ContextUnit(id="keep", text="note", source_type="state_fact"),
    ContextUnit(id="c1", text="historical deploy record", source_type="log_event"),
))
r = minimize_context(ctx2, oracle=FakeOracle(), target_reduction=1.0, evaluation_time=1.0)
assert r.equivalence_status is EquivalenceStatus.RESTORED and "c1" in r.restored_ids, r

# 4) protected-unit retention under maximal pressure
pr = minimize_context(ctx, oracle=FakeOracle(), target_reduction=1.0,
                      protected_ids=["p"], evaluation_time=1.0)
assert "p" in pr.surviving_ids, pr

# 5) fail-closed fallback on oracle exception
f = minimize_context(ctx, oracle=Boom(), target_reduction=0.5, evaluation_time=1.0)
assert f.fell_back and f.surviving_ids == f.original_ids, f

# 6) oracle required for oracle mode
try:
    minimize_context(ctx, oracle=None, target_reduction=0.5)
    raise AssertionError("expected OracleRequiredError")
except OracleRequiredError:
    pass

assert isinstance(REASON_CODES, tuple) and "JOINT_EFFECT_FALLBACK" in REASON_CODES

# 7) v0.1.1 corrections, proven on the installed wheel
from ugence_context_minimization.api import OracleEvaluation as _OE

class HorizonOracle:
    def evaluate(self, context, *, evaluation_time=None):
        return _OE("k", "horizon", "1.0", correlation_id=context.correlation_id, valid_until=10.0)

# inclusive expiry: exact instant fails closed
ex = minimize_context(ctx, oracle=HorizonOracle(), target_reduction=0.5, evaluation_time=10.0)
assert ex.fell_back and "ORACLE_EVALUATION_EXPIRED" in ex.reason_codes, ex
# missing evaluation_time with a horizon fails closed
mt = minimize_context(ctx, oracle=HorizonOracle(), target_reduction=0.5, evaluation_time=None)
assert mt.fell_back and "ORACLE_EVALUATION_TIME_REQUIRED" in mt.reason_codes, mt

class MissingCorr:
    def evaluate(self, context, *, evaluation_time=None):
        return _OE("k", "mc", "1.0")  # omits correlation
mc = minimize_context(ctx, oracle=MissingCorr(), target_reduction=0.5, evaluation_time=1.0)
assert mc.fell_back and "ORACLE_CORRELATION_MISSING" in mc.reason_codes, mc

# requested_reduction preserved on fallback; two distinct fingerprints; alias holds
assert ex.requested_reduction == 0.5, ex
assert o.run_fingerprint and o.outcome_fingerprint and o.run_fingerprint != o.outcome_fingerprint
assert o.fingerprint == o.outcome_fingerprint

# 8) v0.1.2 timestamp + numeric hardening, proven on the installed wheel
# malformed caller evaluation_time raises before the oracle is reached
for _bad in (True, _math.nan, _math.inf, "later"):
    try:
        minimize_context(ctx, oracle=FakeOracle(), target_reduction=0.5, evaluation_time=_bad)
        raise AssertionError("expected InvalidRequestError for evaluation_time=%r" % (_bad,))
    except InvalidRequestError:
        pass

class BadHorizon:
    def __init__(self, vu): self.vu = vu
    def evaluate(self, context, *, evaluation_time=None):
        return _OE("k", "bh", "1.0", correlation_id=context.correlation_id, valid_until=self.vu)
for _bad in (True, _math.nan, _math.inf, "later", object()):
    r_bad = minimize_context(ctx, oracle=BadHorizon(_bad), target_reduction=0.5, evaluation_time=1.0)
    assert r_bad.fell_back and "ORACLE_RESULT_MALFORMED" in r_bad.reason_codes, (_bad, r_bad)
    assert r_bad.surviving_ids == r_bad.original_ids

# malformed token counts rejected deterministically
for _bad in (-1, True, 1.5, _math.nan, "3"):
    try:
        ContextUnit(id="z", text="t", token_count=_bad)
        raise AssertionError("expected InvalidUnitError for token_count=%r" % (_bad,))
    except InvalidUnitError:
        pass

# non-scalar metadata rejected
try:
    ContextUnit(id="z", text="t", metadata={"k": [1, 2]})
    raise AssertionError("expected InvalidUnitError for non-scalar metadata")
except InvalidUnitError:
    pass

# canonical fingerprint serialization rejects non-finite numbers
from ugence_context_minimization.fingerprint import _canonical_json
try:
    _canonical_json({"x": _math.inf})
    raise AssertionError("expected ValueError for non-finite in canonical JSON")
except ValueError:
    pass

# 9) CM-TA1 token accounting, proven on the installed wheel (three distinct measurements)
from ugence_context_minimization.api import (
    prepare_api_call_measurement, reconcile_api_call_measurement,
    aggregate_logical_request_usage, ProviderTokenUsage, AttemptStatus,
    UsageAvailability, RequestComponents, TokenCountBasis, InMemoryTokenAccountingSink,
)
# A: context reduction is copied from a real MinimizationResult (o, from step 2 above).
_prep = prepare_api_call_measurement(
    minimization_result=o, logical_request_id="lr-demo", provider_id="fake-prov",
    request_components=RequestComponents(system_text="you are helpful",
                                         minimized_context_tokens=o.resulting_tokens,
                                         tool_definition_texts=("tool def blob",)),
    model_id="demo-model",
)
assert _prep.context_tokens_before == o.original_tokens
assert _prep.context_tokens_after == o.resulting_tokens
assert _prep.minimization_run_fingerprint == o.run_fingerprint
# B: the full-request estimate is DEFAULT_APPROXIMATE and distinct from context alone.
assert _prep.request_estimate.basis is TokenCountBasis.DEFAULT_APPROXIMATE
assert _prep.request_estimate.is_approximate is True
assert _prep.request_estimate.estimated_input_tokens > _prep.context_tokens_after
_sink = InMemoryTokenAccountingSink()
# C: a FAILED attempt with no usage is unknown (not zero), a retry SUCCEEDS with usage.
reconcile_api_call_measurement(_prep, attempt_id="d1", attempt_number=1,
                               status=AttemptStatus.FAILED, sink=_sink)
reconcile_api_call_measurement(_prep, attempt_id="d2", attempt_number=2,
                               status=AttemptStatus.SUCCEEDED, retry_of_attempt_id="d1",
                               provider_usage=ProviderTokenUsage(input_tokens=2337,
                                                                 cached_input_tokens=1500,
                                                                 output_tokens=428),
                               sink=_sink)
_recs = _sink.records
assert len(_recs) == 2
assert _recs[0].usage_availability is UsageAvailability.UNAVAILABLE_PROVIDER_ERROR
assert _recs[0].provider_usage is None  # unknown, never fabricated as zero
_summ = aggregate_logical_request_usage(_recs)
assert _summ.attempt_count == 2 and _summ.attempts_usage_unknown == 1 and _summ.complete is False
assert _summ.provider_input_tokens == 2337 and _summ.provider_output_tokens == 428
# malformed provider token counts fail closed on the installed wheel
for _bad in (-1, True, 1.5, _math.nan, _math.inf, "5"):
    try:
        ProviderTokenUsage(input_tokens=_bad)
        raise AssertionError("expected rejection for provider input_tokens=%r" % (_bad,))
    except (InvalidUnitError, InvalidRequestError):
        pass

# ---- NO unrelated package importable in this clean env --------------------
for mod in ("action_gate_ref", "action_gateway", "actiongate_context_ablation",
            "ugence_console_api", "robotics_reliability_bench", "experiments",
            "cyber_security", "torch", "transformers", "pydantic", "numpy"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

print("ISOLATED SINGLE-WHEEL CONTEXT-MINIMIZATION VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _foreign_members(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as z:
        tops = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    return {t for t in tops if not (t == "ugence_context_minimization" or t.endswith(".dist-info"))}


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/5] build the single context-minimization wheel + sdist")
    _run([sys.executable, "-m", "build", str(PKG), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_context_minimization-*.whl")
    sdist = _latest(findlinks, "ugence_context_minimization-*.tar.gz")
    print(f"      built {wheel.name} + {sdist.name}")

    print("[2/5] assert the wheel bundles no foreign top-level package + ships py.typed")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
    assert "ugence_context_minimization/py.typed" in names, "wheel is missing py.typed"
    print("      wheel contains only ugence_context_minimization/ (+ py.typed) + dist-info")

    print("[3/5] create an isolated venv and install ONLY this wheel (--no-index)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(findlinks), "ugence-context-minimization"])

        print("[4/5] run the isolated product-neutral demo (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

        print("[5/5] confirm metadata name/version from the installed distribution")
        _run([str(py), "-c",
              "import importlib.metadata as m; "
              "d=m.distribution('ugence-context-minimization'); "
              "assert d.version=='0.2.0', d.version; print('metadata', d.metadata['Name'], d.version)"])

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED SINGLE-WHEEL CONTEXT-MINIMIZATION DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
