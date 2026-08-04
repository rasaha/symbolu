"""Shadow session orchestration (fixture-capable, deterministic).

Ties the read-only observer, the advisory recommendation engine, policy/staleness/
authorization/HPA evaluation, and audit + evidence emission into a single bounded run
that produces **proposed-only** :class:`ShadowDecision` objects. Nothing here imports or
invokes a live executor: the required flow is

    observation -> advisory recommendation -> policy/safety -> local shadow authorization
    -> proposed shadow decision -> audit evidence

A recommendation, an approval Boolean, or a confidence score never becomes execution
authority, and a valid shadow authorization produces no mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation
from ugence_cloud_scaling_operations.audit import AuditEvent, InMemoryAuditSink
from ugence_cloud_scaling_operations import __version__ as OPS_VERSION
from ugence_cloud_scaling_controller import __version__ as ADV_VERSION

from .allowlist import TargetAllowlist, TargetRef
from .authorization_scenarios import (
    AUTHORIZED_FOR_SHADOW_PLAN,
    EXPECTED_POLICY_VERSION,
    EXPECTED_TENANT,
    FIXED_NOW,
    evaluate_shadow_authorization,
    _base_authz,
    _base_request,
    _verifier,
    AUTHORIZED_KIND,
)
from .config import ShadowValidationConfig
from .contracts import (
    DeploymentObservation,
    EXECUTION_MODE_SHADOW,
    EXECUTION_STATUS_NOT_EXECUTED,
    HorizontalPodAutoscalerObservation,
    ShadowDecision,
    stable_hash,
)
from .hpa_analysis import HpaInteractionAnalyzer
from .observer import (
    FakeReadOnlyKubernetesClient, RetryPolicy, ShadowObserver,
)
from .redaction import redact_record
from .stale_state import StaleStateEvaluator, snapshot
from .transport import ReadOnlyTransportBarrier

FIXTURE_SOURCE_REVISION = "FIXTURE_LOCAL"


@dataclass
class FixtureTarget:
    """Declarative fixture workload used to drive a deterministic shadow run."""

    namespace: str
    resource_kind: str
    resource_name: str
    current_replicas: int
    metrics: Dict[str, float]
    resource_version: str = "1"
    generation: int = 1
    hpa: Optional[Tuple[int, int, int, int]] = None  # (min, max, current, desired)
    authorization: str = "valid"                      # "valid" | "missing"
    stale: bool = False


@dataclass
class ShadowSessionResult:
    session_manifest: dict
    observation_records: List[dict]
    decisions: List[dict]
    audit_events: List[dict]

    def decision_objects_all_shadow(self) -> bool:
        return all(
            d["execution_mode"] == EXECUTION_MODE_SHADOW
            and d["execution_status"] == EXECUTION_STATUS_NOT_EXECUTED
            and d["proposed_only"] is True
            for d in self.decisions
        )


class ShadowSession:
    def __init__(self, config: ShadowValidationConfig, observer: ShadowObserver, *,
                 session_id: str = "shadow-session-fixture-1",
                 clock: Callable[[], float] = lambda: FIXED_NOW,
                 source_revision: str = FIXTURE_SOURCE_REVISION):
        self._config = config
        self._observer = observer
        self._session_id = session_id
        self._clock = clock
        self._source_revision = source_revision
        self._allowlist = TargetAllowlist.from_config(config)
        self._stale = StaleStateEvaluator()
        self._hpa = HpaInteractionAnalyzer()
        self._audit = InMemoryAuditSink()

    def run(self, targets: List[FixtureTarget]) -> ShadowSessionResult:
        now = self._clock()
        observations: List[dict] = []
        decisions: List[dict] = []
        verifier = _verifier()

        for idx, t in enumerate(targets):
            ref = TargetRef(self._config.cluster_identifier, t.namespace,
                            t.resource_kind, t.resource_name)
            allow = self._allowlist.evaluate(ref)
            if not allow.allowed:
                continue  # rejected targets are recorded by the allowlist artifact

            dep = self._observer.observe_deployment(ref)
            hpa = self._observer.observe_hpa(ref)
            observations.append(dep.to_dict())

            # Advisory recommendation (fresh controller -> deterministic decision).
            rec = CloudScalingController().recommend(ScalingObservation(
                metrics=t.metrics, current_replicas=dep.current_replicas))
            recommended = int(rec.recommended_replicas)

            # Policy: allowlisted + within configured bounds already enforced by allowlist.
            policy_result = "within_policy"

            # Staleness.
            cur_snap = snapshot(dep, hpa_desired=(hpa.desired_replicas if hpa else None))
            prior_snap = None
            if t.stale:
                prior_snap = dict(cur_snap)
                prior_snap["resource_version"] = cur_snap["resource_version"] + "-prev"
            stale_res = self._stale.classify(
                cur_snap, now=now,
                max_age=self._config.maximum_observation_age_seconds, prior=prior_snap)

            # Local shadow authorization (synthetic).
            authz = None if t.authorization == "missing" else _base_authz(
                target_namespace=t.namespace, target_resource=t.resource_name,
                current_replicas=dep.current_replicas,
                maximum_replicas=max(10, recommended))
            req = _base_request(
                target_namespace=t.namespace, target_resource=t.resource_name,
                current_replicas=dep.current_replicas, target_replicas=recommended,
                observed_at=now - 5.0)
            authz_result, authz_code, authz_reason = evaluate_shadow_authorization(
                authz, req, now=now, verifier=verifier,
                expected_tenant=EXPECTED_TENANT,
                expected_policy_version=EXPECTED_POLICY_VERSION,
                authorized_kind=AUTHORIZED_KIND, request_kind=t.resource_kind)

            # HPA interaction.
            hpa_res = self._hpa.analyze(hpa=hpa, current_replicas=dep.current_replicas,
                                        recommended_replicas=recommended)

            decision = ShadowDecision(
                session_id=self._session_id,
                observation_id=f"obs-{idx}",
                recommendation_id=req.recommendation_id,
                decision_id=f"dec-{idx}",
                authorization_test_id=(authz.authorization_id if authz else None),
                cluster_identifier=self._config.cluster_identifier,
                namespace=t.namespace,
                resource_kind=t.resource_kind,
                resource_name=t.resource_name,
                current_replicas=dep.current_replicas,
                recommended_replicas=recommended,
                hpa_state=hpa_res.classification.value,
                policy_result=policy_result,
                staleness_result=stale_res.classification.value,
                authorization_result=authz_result,
                proposed_action=f"scale->{recommended}",
                not_executed_reason="shadow mode: proposed only, never executed",
                timestamp=now,
            )
            decisions.append(decision.to_dict())

            self._audit.emit(AuditEvent(
                event_id=f"ev-{idx}", timestamp=now, tenant_id=EXPECTED_TENANT,
                actor_id="shadow", authorization_id=(authz.authorization_id if authz else None),
                decision_id=decision.decision_id, recommendation_id=req.recommendation_id,
                target=ref.key(), requested_action="scale",
                authorized_bounds=(f"[{authz.minimum_replicas},{authz.maximum_replicas}]"
                                   if authz else None),
                execution_mode="shadow", pre_state=dep.current_replicas, post_state=None,
                result="shadowed_proposed_only", denial_reason=authz_reason,
                retry_count=0, rollback_reference=None, package_version=OPS_VERSION,
                source_revision=self._source_revision,
                extra=redact_record({
                    "hpa": hpa_res.to_dict(), "staleness": stale_res.to_dict(),
                    "authorization_result": authz_result,
                    "authorization_code": authz_code})))

        manifest = {
            "session_id": self._session_id,
            "evidence_class": "FAKE_LOCAL_FIXTURE",
            "real_environment_observed": False,
            "real_cluster_accessed": False,
            "cluster_identifier": self._config.cluster_identifier,
            "context_name": self._config.context_name,
            "environment_classification": self._config.environment_classification,
            "operations_package_version": OPS_VERSION,
            "advisory_package_version": ADV_VERSION,
            "source_revision": self._source_revision,
            "observed_target_count": len(observations),
            "decision_count": len(decisions),
            "timestamp": now,
        }
        manifest["decisions_hash"] = stable_hash(decisions)
        manifest["observations_hash"] = stable_hash(observations)

        audit_events = [e.to_dict() for e in self._audit.events]
        return ShadowSessionResult(manifest, observations, decisions, audit_events)


def build_fixture_observer(
    config: ShadowValidationConfig, targets: List[FixtureTarget], *,
    barrier: Optional[ReadOnlyTransportBarrier] = None,
    fault=None, clock: Callable[[], float] = lambda: FIXED_NOW,
) -> Tuple[ShadowObserver, ReadOnlyTransportBarrier]:
    """Construct a fake-client observer whose data matches ``targets`` (deterministic)."""
    barrier = barrier or ReadOnlyTransportBarrier(clock=clock)
    now = clock()
    deployments: Dict[str, DeploymentObservation] = {}
    hpas: Dict[str, HorizontalPodAutoscalerObservation] = {}
    for t in targets:
        key = f"{t.namespace}/{t.resource_name}"
        deployments[key] = DeploymentObservation(
            cluster_identifier=config.cluster_identifier, namespace=t.namespace,
            resource_kind=t.resource_kind, resource_name=t.resource_name,
            resource_uid=f"uid-{t.resource_name}", resource_version=t.resource_version,
            generation=t.generation, observed_generation=t.generation,
            current_replicas=t.current_replicas, desired_replicas=t.current_replicas,
            available_replicas=t.current_replicas, ready_replicas=t.current_replicas,
            updated_replicas=t.current_replicas, observation_timestamp=now,
            cpu_utilization=t.metrics.get("cpu"))
        if t.hpa is not None:
            mn, mx, cur, des = t.hpa
            hpas[key] = HorizontalPodAutoscalerObservation(
                cluster_identifier=config.cluster_identifier, namespace=t.namespace,
                resource_name=f"{t.resource_name}-hpa", target_kind=t.resource_kind,
                target_name=t.resource_name, min_replicas=mn, max_replicas=mx,
                current_replicas=cur, desired_replicas=des, observation_timestamp=now)
    client = FakeReadOnlyKubernetesClient(
        barrier, cluster=config.cluster_identifier, deployments=deployments,
        hpas=hpas, fault=fault)
    observer = ShadowObserver(client, TargetAllowlist.from_config(config),
                              retry=RetryPolicy(), clock=clock)
    return observer, barrier


def default_fixture_targets() -> List[FixtureTarget]:
    """A small, deterministic fixture workload set (no-HPA, HPA, stale)."""
    return [
        FixtureTarget("shadow-test", "Deployment", "frontend", current_replicas=3,
                      metrics={"cpu": 0.82, "latency_p99": 0.6}, resource_version="10",
                      generation=4, hpa=(2, 10, 3, 4)),
        FixtureTarget("shadow-test", "Deployment", "worker", current_replicas=5,
                      metrics={"cpu": 0.2, "queue_depth": 0.1}, resource_version="7",
                      generation=2),  # no HPA
        FixtureTarget("shadow-test", "Deployment", "api", current_replicas=4,
                      metrics={"cpu": 0.9, "error_rate": 0.3}, resource_version="3",
                      generation=1, hpa=(1, 3, 4, 3), stale=True),  # stale + bounds
    ]


__all__ = [
    "FixtureTarget",
    "ShadowSession",
    "ShadowSessionResult",
    "build_fixture_observer",
    "default_fixture_targets",
    "FIXTURE_SOURCE_REVISION",
]
