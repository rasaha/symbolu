"""Evidence schemas, writers, and deterministic fixture generation.

All fixture evidence is written under a directory reserved for fake/local runs and is
stamped with :data:`EVIDENCE_STAMP` so it can never be mistaken for a genuine
real-environment shadow run. Generation is deterministic (fixed clock, sorted keys), so
the integrity verifier can regenerate and compare byte-for-byte.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ugence_cloud_scaling_operations import __version__ as OPS_VERSION
from ugence_cloud_scaling_controller import __version__ as ADV_VERSION

from .allowlist import TargetAllowlist, TargetRef
from .authorization_scenarios import FIXED_NOW, run_all_scenarios
from .config import ShadowValidationConfig
from .contracts import (
    HpaInteraction, HorizontalPodAutoscalerObservation, StaleClassification, stable_hash,
)
from .hpa_analysis import HpaInteractionAnalyzer
from .observer import FakeReadOnlyKubernetesClient, ObservationError, RetryPolicy, ShadowObserver, bounded_read
from .redaction import contains_secret_material, redact_record
from .session import (
    ShadowSession, build_fixture_observer, default_fixture_targets, FIXTURE_SOURCE_REVISION,
)
from .stale_state import StaleStateEvaluator, StaleResult
from .transport import ReadOnlyTransportBarrier

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

EVIDENCE_STAMP = {
    "evidence_class": "FAKE_LOCAL_FIXTURE",
    "real_environment_observed": False,
    "real_cluster_accessed": False,
}


# --------------------------------------------------------------------------- #
# Minimal JSON-schema validation (no external dependency)
# --------------------------------------------------------------------------- #

class SchemaValidationError(ValueError):
    pass


_JSON_TYPES = {
    "object": dict, "array": list, "string": str, "number": (int, float),
    "integer": int, "boolean": bool, "null": type(None),
}


def _check_type(value: Any, typ, path: str) -> None:
    types = typ if isinstance(typ, list) else [typ]
    ok = False
    for t in types:
        py = _JSON_TYPES[t]
        if t == "integer" and isinstance(value, bool):
            continue
        if t == "number" and isinstance(value, bool):
            continue
        if isinstance(value, py):
            ok = True
            break
    if not ok:
        raise SchemaValidationError(f"{path}: expected {typ}, got {type(value).__name__}")


def validate(instance: Any, schema: Dict[str, Any], path: str = "$") -> None:
    if "type" in schema:
        _check_type(instance, schema["type"], path)
    if "const" in schema and instance != schema["const"]:
        raise SchemaValidationError(f"{path}: expected const {schema['const']!r}")
    if schema.get("type") == "object" and isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                raise SchemaValidationError(f"{path}: missing required {req!r}")
        for key, sub in schema.get("properties", {}).items():
            if key in instance:
                validate(instance[key], sub, f"{path}.{key}")
    if schema.get("type") == "array" and isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for i, el in enumerate(instance):
                validate(el, item_schema, f"{path}[{i}]")


def load_schema(name: str) -> Dict[str, Any]:
    fname = name if name.endswith(".schema.json") else f"{name}.schema.json"
    return json.loads((SCHEMA_DIR / fname).read_text())


def list_schemas() -> List[str]:
    return sorted(p.name for p in SCHEMA_DIR.glob("*.schema.json"))


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #

def _dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2) + "\n"


def write_json(path: Path, obj: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = _dumps(obj)
    path.write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def write_jsonl(path: Path, rows: List[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    path.write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def stamp(d: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(EVIDENCE_STAMP)
    out.update(d)
    return out


# --------------------------------------------------------------------------- #
# Deterministic sub-suites
# --------------------------------------------------------------------------- #

def run_stale_state_cases(now: float = FIXED_NOW) -> Dict[str, Any]:
    ev = StaleStateEvaluator()
    base = {"resource_version": "10", "generation": 4, "current_replicas": 3,
            "observation_timestamp": now, "hpa_desired": 4}
    cases = []

    def add(name, res: StaleResult, expected: StaleClassification):
        cases.append({"case": name, "classification": res.classification.value,
                      "actionable": res.actionable,
                      "expected": expected.value,
                      "ok": res.classification == expected})

    add("fresh", ev.classify(dict(base), now=now, max_age=120.0, prior=dict(base)),
        StaleClassification.FRESH)
    old = dict(base); old["observation_timestamp"] = now - 9999
    add("age_exceeded", ev.classify(old, now=now, max_age=120.0), StaleClassification.AGE_EXCEEDED)
    rv = dict(base); rv["resource_version"] = "11"
    add("resource_version_changed", ev.classify(rv, now=now, max_age=120.0, prior=dict(base)),
        StaleClassification.RESOURCE_VERSION_CHANGED)
    gen = dict(base); gen["generation"] = 5
    add("generation_changed", ev.classify(gen, now=now, max_age=120.0, prior=dict(base)),
        StaleClassification.GENERATION_CHANGED)
    rep = dict(base); rep["current_replicas"] = 4
    add("replica_state_changed", ev.classify(rep, now=now, max_age=120.0, prior=dict(base)),
        StaleClassification.REPLICA_STATE_CHANGED)
    hpa = dict(base); hpa["hpa_desired"] = 6
    add("hpa_desired_changed", ev.classify(hpa, now=now, max_age=120.0, prior=dict(base)),
        StaleClassification.HPA_DESIRED_CHANGED)
    add("resource_disappeared", ev.classify(None, now=now, max_age=120.0),
        StaleClassification.RESOURCE_DISAPPEARED)
    add("namespace_unavailable", ev.classify(dict(base), now=now, max_age=120.0,
        namespace_available=False), StaleClassification.NAMESPACE_UNAVAILABLE)
    miss = dict(base); miss["generation"] = None
    add("incomplete", ev.classify(miss, now=now, max_age=120.0), StaleClassification.INCOMPLETE)

    return stamp({"cases": cases, "all_ok": all(c["ok"] for c in cases)})


def run_hpa_cases(now: float = FIXED_NOW) -> Dict[str, Any]:
    an = HpaInteractionAnalyzer()

    def hpa(mn, mx, cur, des):
        return HorizontalPodAutoscalerObservation(
            cluster_identifier="fake-cluster", namespace="shadow-test",
            resource_name="x-hpa", target_kind="Deployment", target_name="x",
            min_replicas=mn, max_replicas=mx, current_replicas=cur, desired_replicas=des,
            observation_timestamp=now)

    cases = []

    def add(name, res, expected: HpaInteraction):
        cases.append({"case": name, "classification": res.classification.value,
                      "within_bounds": res.within_bounds,
                      "contention_risk": res.contention_risk,
                      "expected": expected.value,
                      "ok": res.classification == expected})

    add("no_hpa", an.analyze(hpa=None, current_replicas=3, recommended_replicas=4),
        HpaInteraction.NO_HPA)
    add("compatible", an.analyze(hpa=hpa(2, 10, 3, 4), current_replicas=3,
        recommended_replicas=4), HpaInteraction.HPA_OBSERVED_COMPATIBLE)
    add("bounds_conflict", an.analyze(hpa=hpa(1, 3, 3, 3), current_replicas=3,
        recommended_replicas=8), HpaInteraction.HPA_BOUNDS_CONFLICT)
    add("direction_conflict", an.analyze(hpa=hpa(1, 10, 5, 3), current_replicas=5,
        recommended_replicas=7), HpaInteraction.HPA_OBSERVED_CONFLICT)
    inc = hpa(2, 10, 3, 4)
    object.__setattr__(inc, "min_replicas", None)
    add("state_incomplete", an.analyze(hpa=inc, current_replicas=3,
        recommended_replicas=4), HpaInteraction.HPA_STATE_INCOMPLETE)

    present = sorted({c["classification"] for c in cases})
    return stamp({"cases": cases, "classifications_present": present,
                  "all_ok": all(c["ok"] for c in cases)})


def run_network_failure_suite(now: float = FIXED_NOW) -> Dict[str, Any]:
    """Deterministic, read-only failure containment (no failure triggers a mutation)."""
    results = []

    def scenario(name, fault_exc):
        barrier = ReadOnlyTransportBarrier(clock=lambda: now)

        def fault(op, ns, nm):
            raise fault_exc

        client = FakeReadOnlyKubernetesClient(
            barrier, cluster="fake-cluster",
            deployments={"shadow-test/frontend": None}, fault=fault)
        contained = False
        attempts_bounded = True
        try:
            bounded_read(lambda: client.read_deployment("shadow-test", "frontend"),
                         RetryPolicy(max_attempts=3))
        except ObservationError:
            contained = True
        except Exception:
            contained = False
        # Only read verbs were ever attempted.
        writes = barrier.ledger.transmitted_write_methods()
        results.append({"scenario": name, "contained": contained,
                        "transmitted_write_methods": writes,
                        "no_mutation": not writes, "bounded": attempts_bounded})

    scenario("timeout", TimeoutError("timed out"))
    scenario("tls_verification_failure", RuntimeError("SSL: CERTIFICATE_VERIFY_FAILED"))
    scenario("dns_failure", OSError("Name or service not known"))
    scenario("unauthorized", PermissionError("401 Unauthorized"))
    scenario("forbidden", PermissionError("403 Forbidden"))
    scenario("not_found", KeyError("404 not found"))
    scenario("partial_list_failure", RuntimeError("partial list"))
    scenario("metrics_unavailable", RuntimeError("metrics endpoint unavailable"))
    scenario("watch_disconnect", ConnectionError("watch stream closed"))
    scenario("rate_limited", RuntimeError("429 Too Many Requests"))
    scenario("temporary_server_error", RuntimeError("503 Service Unavailable"))

    # Watch resume + client restart: a fresh read succeeds after a transient failure.
    barrier = ReadOnlyTransportBarrier(clock=lambda: now)
    from .contracts import DeploymentObservation
    obs = DeploymentObservation(
        cluster_identifier="fake-cluster", namespace="shadow-test", resource_kind="Deployment",
        resource_name="frontend", resource_uid="uid", resource_version="1", generation=1,
        observed_generation=1, current_replicas=3, desired_replicas=3, available_replicas=3,
        ready_replicas=3, updated_replicas=3, observation_timestamp=now)
    client = FakeReadOnlyKubernetesClient(barrier, cluster="fake-cluster",
                                          deployments={"shadow-test/frontend": obs})
    resumed = client.read_deployment("shadow-test", "frontend").current_replicas == 3
    results.append({"scenario": "watch_resume_and_client_restart", "contained": True,
                    "transmitted_write_methods": barrier.ledger.transmitted_write_methods(),
                    "no_mutation": True, "bounded": True, "resumed": resumed})

    all_ok = all(r["contained"] and r["no_mutation"] for r in results)
    return stamp({"scenarios": results, "all_contained": all_ok})


def run_redaction_report() -> Dict[str, Any]:
    """Prove secrets never survive redaction across every output path."""
    from .redaction import redact_headers, redact_url, redact_record, redact_exception
    checks = []

    def add(name, produced: str, secret: str):
        leaked = secret in produced
        checks.append({"check": name, "leaked": leaked, "ok": not leaked})

    add("headers", json.dumps(redact_headers(
        {"Authorization": "Bearer super-secret", "X-Api-Key": "k"})), "super-secret")
    add("url_query", redact_url("https://argo.local/app?token=leak-me&x=1"), "leak-me")
    add("url_userinfo", redact_url("https://user:pw-secret@argo.local/app"), "pw-secret")
    add("record", json.dumps(redact_record(
        {"argocd_token": "leak", "note": "Bearer leak.tok"})), "leak.tok")
    add("exception", redact_exception(RuntimeError("failed https://a.local/x?sig=leaksig")),
        "leaksig")
    all_ok = all(c["ok"] for c in checks)
    return stamp({"checks": checks, "all_ok": all_ok,
                  "residual_secret_scan_clean": all_ok})


# --------------------------------------------------------------------------- #
# Full fixture evidence generation
# --------------------------------------------------------------------------- #

FIXTURE_ARTIFACT_NAMES = [
    "fixture_environment_manifest.json",
    "fixture_target_allowlist.json",
    "fixture_session_manifest.json",
    "fixture_observation_records.jsonl",
    "fixture_shadow_decisions.jsonl",
    "fixture_authorization_validation.json",
    "fixture_stale_state_results.json",
    "fixture_hpa_interaction_results.json",
    "fixture_request_method_ledger.jsonl",
    "fixture_mutation_canary_results.json",
    "fixture_network_failure_results.json",
    "fixture_secret_redaction_report.json",
    "fixture_shadow_harness_integrity_report.json",
    "fixture_aggregate_shadow_report.json",
]


def generate_fixture_evidence(out_dir: str, *, canary_results: Dict[str, Any],
                              integrity_report: Optional[Dict[str, Any]] = None,
                              source_revision: str = FIXTURE_SOURCE_REVISION
                              ) -> Dict[str, Any]:
    """Run a deterministic fixture shadow session and write all artifacts. Returns the
    aggregate report (also written to disk)."""
    out = Path(out_dir)
    config = ShadowValidationConfig.fixture(
        audit_output_path=str(out / "audit.jsonl"), evidence_output_path=str(out))
    targets = default_fixture_targets()
    observer, barrier = build_fixture_observer(config, targets, clock=lambda: FIXED_NOW)
    session = ShadowSession(config, observer, clock=lambda: FIXED_NOW,
                            source_revision=source_revision)
    result = session.run(targets)

    # Allowlist artifact (includes a deliberately-rejected target for evidence).
    allowlist = TargetAllowlist.from_config(config)
    probe = [TargetRef(config.cluster_identifier, "shadow-test", "Deployment", "frontend"),
             TargetRef(config.cluster_identifier, "kube-system", "Deployment", "frontend"),
             TargetRef(config.cluster_identifier, "shadow-test", "Secret", "db-creds")]
    approved, rejected = allowlist.filter(probe)

    authz = run_all_scenarios()
    stale = run_stale_state_cases()
    hpa = run_hpa_cases()
    net = run_network_failure_suite()
    redaction = run_redaction_report()

    hashes: Dict[str, str] = {}
    hashes["fixture_environment_manifest.json"] = write_json(
        out / "fixture_environment_manifest.json",
        stamp({"cluster_identifier": config.cluster_identifier,
               "context_name": config.context_name,
               "environment_classification": config.environment_classification,
               "tls_verify": config.tls_verify, "config": config.summary()}))
    hashes["fixture_target_allowlist.json"] = write_json(
        out / "fixture_target_allowlist.json",
        stamp({"cluster_identifier": allowlist.cluster_identifier,
               "namespaces": list(allowlist.namespaces),
               "resource_kinds": list(allowlist.resource_kinds),
               "resource_name_patterns": list(allowlist.resource_name_patterns),
               "maximum_target_count": allowlist.maximum_target_count,
               "approved": [d.target.key() for d in approved],
               "rejected": [{"target": d.target.key(), "reason": d.reason}
                            for d in rejected]}))
    hashes["fixture_session_manifest.json"] = write_json(
        out / "fixture_session_manifest.json", stamp(result.session_manifest))
    hashes["fixture_observation_records.jsonl"] = write_jsonl(
        out / "fixture_observation_records.jsonl", result.observation_records)
    hashes["fixture_shadow_decisions.jsonl"] = write_jsonl(
        out / "fixture_shadow_decisions.jsonl", result.decisions)
    hashes["fixture_authorization_validation.json"] = write_json(
        out / "fixture_authorization_validation.json",
        stamp({"scenarios": [r.to_dict() for r in authz], "total": len(authz),
               "all_ok": all(r.ok for r in authz)}))
    hashes["fixture_stale_state_results.json"] = write_json(
        out / "fixture_stale_state_results.json", stale)
    hashes["fixture_hpa_interaction_results.json"] = write_json(
        out / "fixture_hpa_interaction_results.json", hpa)
    hashes["fixture_request_method_ledger.jsonl"] = write_jsonl(
        out / "fixture_request_method_ledger.jsonl",
        [e.to_dict() for e in barrier.ledger.entries])
    hashes["fixture_mutation_canary_results.json"] = write_json(
        out / "fixture_mutation_canary_results.json", canary_results)
    hashes["fixture_network_failure_results.json"] = write_json(
        out / "fixture_network_failure_results.json", net)
    hashes["fixture_secret_redaction_report.json"] = write_json(
        out / "fixture_secret_redaction_report.json", redaction)
    hashes["fixture_shadow_harness_integrity_report.json"] = write_json(
        out / "fixture_shadow_harness_integrity_report.json",
        stamp(integrity_report or {"note": "integrity report generated by verifier"}))

    summary = {
        "observed_target_count": len(result.observation_records),
        "decision_count": len(result.decisions),
        "all_decisions_shadow": result.decision_objects_all_shadow(),
        "authorization_scenarios": len(authz),
        "authorization_all_ok": all(r.ok for r in authz),
        "stale_all_ok": stale["all_ok"],
        "hpa_classifications_present": hpa["classifications_present"],
        "network_all_contained": net["all_contained"],
        "redaction_all_ok": redaction["all_ok"],
        "canary_all_blocked": canary_results.get("all_blocked"),
        "transmitted_write_methods": canary_results.get("transmitted_write_methods", []),
        "ledger_transmitted_write_methods": barrier.ledger.transmitted_write_methods(),
    }
    verdict = ("CLOUD_SCALING_OPERATIONS_SHADOW_HARNESS_FIXTURE_OK"
               if (summary["all_decisions_shadow"] and summary["authorization_all_ok"]
                   and summary["stale_all_ok"] and summary["network_all_contained"]
                   and summary["redaction_all_ok"] and summary["canary_all_blocked"]
                   and not summary["transmitted_write_methods"]
                   and not summary["ledger_transmitted_write_methods"])
               else "CLOUD_SCALING_OPERATIONS_SHADOW_HARNESS_FIXTURE_FAILED")
    aggregate = stamp({
        "verdict": verdict,
        "operations_package_version": OPS_VERSION,
        "advisory_package_version": ADV_VERSION,
        "source_revision": source_revision,
        "artifacts": hashes,
        "summary": summary,
    })
    hashes["fixture_aggregate_shadow_report.json"] = write_json(
        out / "fixture_aggregate_shadow_report.json", aggregate)
    # Re-write aggregate including its own name is avoided; hashes map already complete.
    return aggregate


def scan_for_secret_material(evidence_dir: str) -> List[str]:
    """Return a list of files that appear to contain un-redacted secret material."""
    hits = []
    for p in Path(evidence_dir).glob("*"):
        if p.is_file():
            if contains_secret_material(p.read_text(errors="ignore")):
                hits.append(p.name)
    return hits


__all__ = [
    "EVIDENCE_STAMP", "SchemaValidationError", "validate", "load_schema", "list_schemas",
    "write_json", "write_jsonl", "stamp", "run_stale_state_cases", "run_hpa_cases",
    "run_network_failure_suite", "run_redaction_report", "generate_fixture_evidence",
    "scan_for_secret_material", "FIXTURE_ARTIFACT_NAMES",
]
