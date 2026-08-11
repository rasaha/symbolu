#!/usr/bin/env python3
"""Reproducible proof that ``ugence-context-minimization-token-accounting-runtime``
installs and operates from its DECLARED dependencies alone, in a fresh virtualenv with
no monorepo path.

This is an *integration* layer: it legitimately depends on two first-party wheels
(ugence-context-minimization, ugence-agent-runtime), both of which are zero-third-party
leaves. The verifier builds a local wheelhouse of the FIRST-PARTY wheels and installs the
integration package from it with ``--no-index`` (no third-party wheel is needed at all).

It then proves, inside that clean env:

  * the package imports from site-packages (not the repo checkout);
  * an end-to-end translation runs: a neutral Agent Runtime ProviderAttempt becomes a
    Context Minimization ApiCallTokenRecord via an injected normalizer;
  * a failed/unknown-usage attempt records usage-unavailable (never zero);
  * H22-D budget settlement uses measured usage, falls back to conservative settlement
    when usage is unavailable, and surfaces BudgetEstimateExceeded on an overrun;
  * NO provider SDK / tokenizer is importable;
  * NO out-of-scope monorepo package is importable.

Run:  python packages/integration/context-minimization-token-accounting-runtime/scripts/verify_isolated_install.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/integration/<pkg> -> repo

FIRST_PARTY = [
    REPO / "packages" / "capabilities" / "context-minimization",
    REPO / "packages" / "runtime" / "agent-runtime",
    PKG,
]

_PROBE = r"""
import importlib.util, pathlib

import ugence_cm_token_accounting_runtime as itg
loc = pathlib.Path(itg.__file__).resolve()
assert "site-packages" in loc.parts, f"not installed from site-packages: {loc}"

from ugence_cm_token_accounting_runtime import (
    MappingUsageNormalizer, translate_attempt, derive_attempt_id, RuntimeTokenAccountingBridge,
    settle_budget_from_usage, BudgetEstimateExceeded,
)
from ugence_agent_runtime.observability.attempts import ProviderAttempt, ProviderAttemptStatus
from ugence_agent_runtime.orchestration import BudgetCoordinator, BudgetRequirement, PortfolioBudget
from ugence_context_minimization.api import (
    Context, ContextUnit, OracleEvaluation, minimize_context,
    prepare_api_call_measurement, aggregate_logical_request_usage,
    AttemptStatus, UsageAvailability, ProviderTokenUsage,
    RequestAttribution, InMemoryTokenAccountingSink,
)

# ---- a real minimization result (measurement A) ---------------------------
class _Oracle:
    def evaluate(self, context, *, evaluation_time=None):
        present = sorted({k for u in context.units for k in ("deploy",) if k in u.text.lower()})
        return OracleEvaluation(equivalence_key="|".join(present), oracle_id="o",
                                contract_version="1.0", correlation_id=context.correlation_id)

ctx = Context(id="c", correlation_id="corr", units=(
    ContextUnit(id="crit", text="deploy anchor", source_type="state_fact"),
    ContextUnit(id="f", text="filler one two three", source_type="log_event"),
))
res = minimize_context(ctx, oracle=_Oracle(), target_reduction=0.5, evaluation_time=1.0)
prep = prepare_api_call_measurement(minimization_result=res, logical_request_id="lr",
                                    provider_id="vendor", model_id="m1")

norm = MappingUsageNormalizer(
    {"input_tokens": "prompt_tokens", "output_tokens": "completion_tokens", "total_tokens": "total_tokens"},
    schema_name="vendor.v1", adapter_id="ad", adapter_version="1",
)

def _att(n, status, usage):
    return ProviderAttempt(provider_id="vendor", operation="op", attempt_number=n, status=status,
                           ok=(status is ProviderAttemptStatus.SUCCEEDED), provider_invoked=True,
                           instance_id="wf", task_id="t", correlation_id="corr", neutral_usage=usage)

# success with usage -> AVAILABLE
r1 = translate_attempt(prep, _att(1, ProviderAttemptStatus.SUCCEEDED,
                                  {"prompt_tokens": 2337, "completion_tokens": 428, "total_tokens": 2765}),
                       normalizer=norm)
assert r1.usage_availability is UsageAvailability.AVAILABLE, r1.usage_availability
assert r1.provider_usage.input_tokens == 2337 and r1.provider_usage.output_tokens == 428

# exception with no usage -> unknown (not zero); retry_of derived in the SAME scheme (F3)
att2 = _att(2, ProviderAttemptStatus.EXCEPTION, None)
r2 = translate_attempt(prep, att2, normalizer=norm)
assert r2.provider_usage is None and r2.usage_availability is not UsageAvailability.AVAILABLE
assert r2.retry_of_attempt_id == derive_attempt_id(_att(1, ProviderAttemptStatus.EXCEPTION, None),
                                                   logical_request_id="lr")
assert r2.attempt_id.startswith("cmta1/")
# F3: missing/blank identity is rejected (no placeholder fallback)
_bad = _att(1, ProviderAttemptStatus.SUCCEEDED, None)
_bad = ProviderAttempt(provider_id="vendor", operation="op", attempt_number=1,
                       status=ProviderAttemptStatus.SUCCEEDED, ok=True, provider_invoked=True,
                       instance_id=None, task_id="t", correlation_id="corr")
try:
    translate_attempt(prep, _bad, normalizer=norm)
    raise AssertionError("expected rejection for missing instance identity")
except ValueError:
    pass

# ---- N1: two tenants, identical tenant-local ids, one shared sink -> both retained ----
_tsink = InMemoryTokenAccountingSink()
_tatt = ProviderAttempt(provider_id="vendor", operation="op", attempt_number=1,
                        status=ProviderAttemptStatus.SUCCEEDED, ok=True, provider_invoked=True,
                        instance_id="wf-1", task_id="t1", correlation_id="corr")
_pA = prepare_api_call_measurement(minimization_result=res, logical_request_id="req-1",
                                   provider_id="vendor", attribution=RequestAttribution(tenant_id="tenantA"))
_pB = prepare_api_call_measurement(minimization_result=res, logical_request_id="req-1",
                                   provider_id="vendor", attribution=RequestAttribution(tenant_id="tenantB"))
_rA = translate_attempt(_pA, _tatt, sink=_tsink)
_rB = translate_attempt(_pB, _tatt, sink=_tsink)
assert _rA.attempt_id != _rB.attempt_id, "tenant-bound derivation must differ"
assert len(_tsink.records) == 2, "both tenants must be retained in a shared sink"
assert derive_attempt_id(_tatt, logical_request_id="req-1", tenant_id="tenantA") != \
       derive_attempt_id(_tatt, logical_request_id="req-1", tenant_id="tenantB")
# whitespace tenant rejected
try:
    RequestAttribution(tenant_id="   ")
    raise AssertionError("expected whitespace tenant rejection")
except Exception:
    pass

# ---- F1: total provenance is never blended --------------------------------
r1b = translate_attempt(prep, _att(1, ProviderAttemptStatus.SUCCEEDED,
                                   {"prompt_tokens": 100, "completion_tokens": 40}),  # no total reported
                        normalizer=norm)
summ = aggregate_logical_request_usage([r1b])
assert summ.provider_reported_total_tokens == 0        # none reported -> zero reported (not derived)
assert summ.derived_total_tokens == 140                # 100 + 40, derived
assert summ.settlement_token_units == 140              # falls back to derived
assert not hasattr(summ, "provider_total_tokens")      # ambiguous blended field is gone

# ---- H22-D budget settlement ----------------------------------------------
coord = BudgetCoordinator(PortfolioBudget({"token_units": 10000.0}))
coord.reserve("wf", BudgetRequirement({"token_units": 5000.0}))
s = settle_budget_from_usage(coord, "wf", ProviderTokenUsage(input_tokens=2000, output_tokens=300, total_tokens=2300))
assert s.actual_known is True and coord.consumed("token_units") == 2300.0

coord2 = BudgetCoordinator(PortfolioBudget({"token_units": 10000.0}))
coord2.reserve("wf", BudgetRequirement({"token_units": 5000.0}))
s2 = settle_budget_from_usage(coord2, "wf", None)  # unavailable -> conservative
assert s2.actual_known is False and coord2.consumed("token_units") == 5000.0

coord3 = BudgetCoordinator(PortfolioBudget({"token_units": 10000.0}))
coord3.reserve("wf", BudgetRequirement({"token_units": 1000.0}))
try:
    settle_budget_from_usage(coord3, "wf", ProviderTokenUsage(input_tokens=2000, output_tokens=500, total_tokens=2500))
    raise AssertionError("expected BudgetEstimateExceeded")
except BudgetEstimateExceeded:
    pass

# ---- NO provider SDK / tokenizer / out-of-scope package importable ---------
for mod in ("openai", "anthropic", "google", "tiktoken", "transformers", "torch",
            "ugence_console_api", "risk_authority", "symbolu", "experiments", "pydantic"):
    assert importlib.util.find_spec(mod) is None, ("unexpected package present: " + mod)

print("ISOLATED CM-TA1 INTEGRATION VERIFICATION OK")
"""


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def main() -> int:
    wheelhouse = PKG / "_dist_wheels"
    if wheelhouse.exists():
        shutil.rmtree(wheelhouse)
    wheelhouse.mkdir()

    print("[1/4] build the two first-party core wheels + the integration wheel")
    for project in FIRST_PARTY:
        _run([sys.executable, "-m", "build", str(project), "-o", str(wheelhouse)])

    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"

        print("[2/4] install the integration package from the first-party wheelhouse (--no-index)")
        _run([str(py), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(wheelhouse),
              "ugence-context-minimization-token-accounting-runtime"])

        print("[3/4] run the end-to-end translation + budget-settlement proof")
        _run([str(py), "-c", _PROBE], cwd=str(td))

        print("[4/4] confirm metadata name/version from the installed distribution")
        _run([str(py), "-c",
              "import importlib.metadata as m; "
              "d=m.distribution('ugence-context-minimization-token-accounting-runtime'); "
              "assert d.version=='0.1.0', d.version; print('metadata', d.metadata['Name'], d.version)"])

    shutil.rmtree(wheelhouse, ignore_errors=True)
    print("\nISOLATED CM-TA1 INTEGRATION DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
