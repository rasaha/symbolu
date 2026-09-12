"""The offline validation harness (LP-7 ruling 11): the eighteen rows over injected fakes.

Every component is injected and fake: the adapter's transport is the adapter's own
:class:`FakeTransport`, custody leases an in-memory marker that this run generates and
never writes anywhere, the budget is the in-memory :class:`CallBudget`. Nothing here
opens a socket, reads a clock, reads the environment or touches a record file.

A row's outcome is ``OFFLINE_CONFORMANT``, ``OFFLINE_NONCONFORMANT`` or
``NOT_EXECUTABLE_OFFLINE``; there is no pass. Rows 12 and 18 are infrastructure-dependent
and are never executed here; rows 13, 14 and 15 need the deployment unit or the exchange
and say so. The prompt text the harness sends is synthetic and is excluded from every
report; the marker it leases is registered as a known secret so a report that carried it
would be refused.
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from ugence_model_egress_unit import (
    COMMISSIONING_STATUS,
    OPENAI_RESPONSES,
    CallBudget,
    CredentialLease,
    CredentialRequest,
    CustodyIdentity,
    CustodyRefusal,
    CustodyRefused,
    DestinationRefused,
    EgressRequest,
    MinimizedUnit,
    PinnedSecretVersionCustodyAdapter,
    ProvenanceKind,
    RefusalReason,
    ResultOutcome,
    reference_clearance,
)
from ugence_model_egress_unit import __version__ as unit_version
from ugence_model_egress_provider_openai import (
    DESIGNATED_MODEL,
    FakeTransport,
    OpenAIResponsesProvider,
    PreparedRequest,
    TransportOutcome,
)
from ugence_model_egress_provider_openai import __version__ as adapter_version

from .rows import ROWS, Row
from .version import __version__ as harness_version

__all__ = ["SYNTHETIC_PROMPT", "RowOutcome", "OfflineRun", "run_offline"]

#: Synthetic, non-sensitive, and never present in a report (the report generator asserts it).
SYNTHETIC_PROMPT = "ugence synthetic validation probe: the quick brown fox jumps over the lazy dog"
PROFILE = "ugence-meu-validation/openai"


@dataclass(frozen=True)
class RowOutcome:
    row: int
    scenario: str
    required: str
    status: str
    observed: str
    digests: Tuple[str, ...] = ()
    reason: Optional[str] = None
    infrastructure_dependent: bool = False


@dataclass
class OfflineRun:
    generated_at: datetime
    unit_version: str
    adapter_version: str
    harness_version: str
    commissioning_status: str
    outcomes: List[RowOutcome] = field(default_factory=list)
    #: In memory only, so the report generator can prove the leased marker leaked nowhere.
    known_markers: Tuple[str, ...] = field(default_factory=tuple, repr=False)

    def outcome(self, row: int) -> RowOutcome:
        return next(o for o in self.outcomes if o.row == row)


# --- fakes ---------------------------------------------------------------------------

class _MarkerCustody:
    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"
    custody_authority_id = "harness-marker-custody"
    credential_profile = PROFILE
    is_production_authoritative = False
    max_credential_age = timedelta(days=1)

    def __init__(self, marker: str, *, refuse: bool = False, expired: bool = False) -> None:
        self._marker = marker
        self._refuse = refuse
        self._expired = expired

    def materialize(self, request: CredentialRequest, *, now: datetime, production: bool = False) -> CredentialLease:
        if self._refuse:
            raise CustodyRefused(CustodyRefusal.CUSTODY_UNAVAILABLE, "no custody commissioned")
        issued = now - timedelta(minutes=10) if self._expired else now
        return CredentialLease(
            lease_id="harness-" + request.digest()[:12], custody_authority_id=self.custody_authority_id,
            credential_profile=self.credential_profile, vendor="openai", tenant_id=request.tenant_id,
            secret_version_ref="harness/fake/versions/1", issued_at=issued,
            expires_at=issued + timedelta(minutes=5), is_production_authoritative=False, _secret=self._marker)


def _request(now: datetime, *, text: str = SYNTHETIC_PROMPT, tokens: int = 16, model: str = DESIGNATED_MODEL,
             vendor: str = "openai", parameters: Optional[dict] = None, units: Optional[list] = None) -> EgressRequest:
    tenant = uuid.uuid4()
    return EgressRequest.create(
        request_id=uuid.uuid4(), tenant_id=tenant, correlation_id=uuid.uuid4(), submitted_at=now,
        not_valid_after=now + timedelta(hours=1),
        authorization=reference_clearance(tenant_id=tenant, vendor=vendor, model=model),
        minimized_context=units if units is not None else [MinimizedUnit("u-1", text, tokens)],
        parameters={"max_output_tokens": 64} if parameters is None else parameters)


def _provider(marker: str, *, transport: Optional[FakeTransport] = None, budget: Optional[CallBudget] = None,
              custody=None) -> OpenAIResponsesProvider:
    return OpenAIResponsesProvider(transport=transport or FakeTransport(), custody=custody or _MarkerCustody(marker),
                                   budget=budget or CallBudget(), credential_profile=PROFILE)


def _refusal_of(result) -> str:
    return result.refusal_reason.value if result.refusal_reason is not None else result.outcome.value


# --- scenarios -----------------------------------------------------------------------

Scenario = Callable[[datetime, str], Tuple[bool, str, Tuple[str, ...]]]


def _row_1(now, marker):
    result = _provider(marker, custody=_MarkerCustody(marker, refuse=True)).execute(_request(now), now=now)
    ok = result.outcome is ResultOutcome.REFUSED and result.refusal_reason is RefusalReason.CREDENTIAL_NOT_COMMISSIONED
    return ok, f"outcome={result.outcome.value} refusal={_refusal_of(result)} genuine_call={result.provenance['genuine_call']}", (result.digest(),)


def _row_3(now, marker):
    refused, accepted = [], []
    for url in ("http://api.openai.com/v1/responses", "https://api.openai.com/v1/chat/completions",
                "https://api.openai.com:8443/v1/responses", "https://api.openai.com.evil.example/v1/responses",
                "https://evil.example/v1/responses", "https://api.openai.com/v1/responses?x=1",
                "https://u@api.openai.com/v1/responses", "https://api.openai.com/v1/responses/"):
        try:
            PreparedRequest(url=url, body={"model": DESIGNATED_MODEL, "input": [{"role": "user", "content": "x"}],
                                           "max_output_tokens": 8, "store": False, "stream": False})
            accepted.append(url)
        except DestinationRefused:
            refused.append(url)
    ok = not accepted and len(refused) == 8 and OPENAI_RESPONSES.url == "https://api.openai.com/v1/responses"
    return ok, f"refused={len(refused)} accepted={len(accepted)} designated={OPENAI_RESPONSES.url}", ()


def _row_4(now, marker):
    transport = FakeTransport()
    request = _request(now)
    tampered = dataclasses.replace(request, minimized_context=(MinimizedUnit("u-1", "a substituted prompt", 16),))
    result = _provider(marker, transport=transport).execute(tampered, now=now)
    ok = result.refusal_reason is RefusalReason.CONTENT_DIGEST_MISMATCH and transport.dispatches == []
    return ok, f"refusal={_refusal_of(result)} dispatches={len(transport.dispatches)}", (request.digest(),)


def _row_5(now, marker):
    transport = FakeTransport()
    result = _provider(marker, transport=transport).execute(_request(now, model="gpt-5.4-mini"), now=now)
    ok = result.refusal_reason is RefusalReason.MODEL_NOT_PINNED and transport.dispatches == []
    return ok, f"refusal={_refusal_of(result)} dispatches={len(transport.dispatches)}", ()


def _row_6(now, marker):
    transport = FakeTransport()
    result = _provider(marker, transport=transport).execute(_request(now, tokens=8_193), now=now)
    ok = result.refusal_reason is RefusalReason.REQUEST_LIMIT_EXCEEDED and transport.dispatches == []
    return ok, f"refusal={_refusal_of(result)} tokens=8193 dispatches={len(transport.dispatches)}", ()


def _row_7(now, marker):
    transport = FakeTransport()
    result = _provider(marker, transport=transport).execute(_request(now, parameters={"max_output_tokens": 1_025}), now=now)
    ok = result.refusal_reason is RefusalReason.REQUEST_LIMIT_EXCEEDED and transport.dispatches == []
    return ok, f"refusal={_refusal_of(result)} max_output_tokens=1025 dispatches={len(transport.dispatches)}", ()


def _row_8(now, marker):
    transport = FakeTransport()
    seen = {}
    for feature, value in (("stream", True), ("store", True), ("tools", [{"type": "web_search"}]),
                           ("background", True), ("previous_response_id", "resp_1")):
        result = _provider(marker, transport=transport).execute(
            _request(now, parameters={"max_output_tokens": 8, feature: value}), now=now)
        seen[feature] = _refusal_of(result)
    ok = all(v == RefusalReason.REQUEST_LIMIT_EXCEEDED.value for v in seen.values()) and transport.dispatches == []
    return ok, " ".join(f"{k}={v}" for k, v in seen.items()) + f" dispatches={len(transport.dispatches)}", ()


def _row_9(now, marker):
    transport, budget = FakeTransport(), CallBudget()
    provider = _provider(marker, transport=transport, budget=budget)
    answered = sum(provider.execute(_request(now), now=now).outcome is ResultOutcome.ANSWERED for _ in range(10))
    eleventh = provider.execute(_request(now), now=now)
    concurrent_budget = CallBudget()
    concurrent_budget.in_flight = 1
    concurrent = _provider(marker, transport=FakeTransport(), budget=concurrent_budget).execute(_request(now), now=now)
    ok = (answered == 10 and eleventh.refusal_reason is RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED
          and len(transport.dispatches) == 10 and budget.cents_reserved == 2_500
          and concurrent.refusal_reason is RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED)
    return ok, (f"answered={answered} eleventh={_refusal_of(eleventh)} dispatches={len(transport.dispatches)} "
                f"cents_reserved={budget.cents_reserved} concurrent={_refusal_of(concurrent)}"), ()


def _row_10(now, marker):
    refusals = []
    try:
        PinnedSecretVersionCustodyAdapter(
            custody_authority_id="x", credential_profile=PROFILE, vendor="openai",
            secret_version_resource="projects/p/secrets/s/versions/latest",
            identity=CustodyIdentity("workload_identity_federation", "principal://x"), reader=lambda r: marker)
    except ValueError as exc:
        refusals.append("latest:" + type(exc).__name__)
    try:
        CustodyIdentity("service_account_key", "key.json")
    except ValueError as exc:
        refusals.append("service_account_key:" + type(exc).__name__)
    return len(refusals) == 2, " ".join(refusals), ()


def _row_11(now, marker):
    transport, budget = FakeTransport(), CallBudget()
    result = _provider(marker, transport=transport, budget=budget, custody=_MarkerCustody(marker, expired=True)).execute(_request(now), now=now)
    ok = (result.refusal_reason is RefusalReason.CREDENTIAL_NOT_COMMISSIONED and transport.dispatches == []
          and budget.calls_reserved == 0)
    return ok, f"refusal={_refusal_of(result)} dispatches={len(transport.dispatches)} reserved={budget.calls_reserved}", ()


def _row_16(now, marker):
    proven = TransportOutcome.transient_before_dispatch("ECONNREFUSED", no_bytes_dispatched=True)
    t1 = FakeTransport([proven])
    r1 = _provider(marker, transport=t1).execute(_request(now), now=now)
    t2 = FakeTransport([proven, proven, proven])
    r2 = _provider(marker, transport=t2).execute(_request(now), now=now)
    unproven = TransportOutcome.transient_before_dispatch("timeout", no_bytes_dispatched=False)
    t3 = FakeTransport([unproven])
    r3 = _provider(marker, transport=t3).execute(_request(now), now=now)
    ok = (r1.outcome is ResultOutcome.ANSWERED and len(t1.dispatches) == 2
          and r2.outcome is ResultOutcome.FAILED and len(t2.dispatches) == 2
          and r3.outcome is ResultOutcome.OUTCOME_UNKNOWN and len(t3.dispatches) == 1)
    return ok, (f"proven_then_ok={r1.outcome.value}/{len(t1.dispatches)} proven_x3={r2.outcome.value}/{len(t2.dispatches)} "
                f"unproven={r3.outcome.value}/{len(t3.dispatches)}"), (r1.digest(), r2.digest(), r3.digest())


def _row_17(now, marker):
    cases = {
        "vendor_error_429": TransportOutcome.responded(429, {"error": {"type": "rate_limit"}}),
        "timeout_after_dispatch": TransportOutcome.dispatched_no_response("read timeout after request left"),
        "malformed_answer": TransportOutcome.responded(200, {"output": "not a list"}),
    }
    seen, digests = {}, []
    for name, outcome in cases.items():
        result = _provider(marker, transport=FakeTransport([outcome])).execute(_request(now), now=now)
        seen[name] = result.outcome.value
        digests.append(result.digest())
    ok = (seen["vendor_error_429"] == ResultOutcome.FAILED.value and seen["timeout_after_dispatch"] == ResultOutcome.OUTCOME_UNKNOWN.value
          and seen["malformed_answer"] == ResultOutcome.FAILED.value)
    return ok, " ".join(f"{k}={v}" for k, v in seen.items()), tuple(digests)


SCENARIOS: Dict[int, Scenario] = {1: _row_1, 3: _row_3, 4: _row_4, 5: _row_5, 6: _row_6, 7: _row_7, 8: _row_8,
                                  9: _row_9, 10: _row_10, 11: _row_11, 16: _row_16, 17: _row_17}


def run_offline(*, now: datetime) -> OfflineRun:
    """Execute every offline-executable row with fake components; name every other row."""

    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    marker = "MARKER-HARNESS-LEASE-" + uuid.uuid4().hex
    run = OfflineRun(generated_at=now, unit_version=unit_version, adapter_version=adapter_version,
                     harness_version=harness_version, commissioning_status=COMMISSIONING_STATUS,
                     known_markers=(marker, SYNTHETIC_PROMPT))
    for row in ROWS:
        if row.row == 2:
            continue  # decided last, over everything this run observed
        if not row.offline:
            run.outcomes.append(RowOutcome(row.row, row.scenario, row.required, "NOT_EXECUTABLE_OFFLINE", "not executed",
                                           reason=row.reason_if_not_offline, infrastructure_dependent=row.infrastructure_dependent))
            continue
        ok, observed, digests = SCENARIOS[row.row](now, marker)
        run.outcomes.append(RowOutcome(row.row, row.scenario, row.required,
                                       "OFFLINE_CONFORMANT" if ok else "OFFLINE_NONCONFORMANT", observed, tuple(digests)))
    # row 2: the leased marker and the prompt appear in no observation of this run
    corpus = " ".join(o.observed + " " + " ".join(o.digests) + " " + (o.reason or "") for o in run.outcomes)
    leaked = [m for m in run.known_markers if m in corpus]
    row2 = next(r for r in ROWS if r.row == 2)
    run.outcomes.append(RowOutcome(2, row2.scenario, row2.required,
                                   "OFFLINE_CONFORMANT" if not leaked else "OFFLINE_NONCONFORMANT",
                                   f"observations scanned={len(run.outcomes)} leaks={len(leaked)}"))
    run.outcomes.sort(key=lambda o: o.row)
    return run
