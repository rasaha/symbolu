"""Integrity checks for the shadow harness (used by the top-level verifier).

These are pure checks over harness source and emitted fixture evidence — they never
import a live executor. Source scanning proves the harness core imports no live-executor
module/symbol and performs no credential/context auto-discovery; evidence checks prove
every decision is proposed-only, the ledger transmitted no write method, and no artifact
claims real-environment access.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, List

from .authorization_scenarios import run_all_scenarios
from .contracts import HpaInteraction
from .evidence import (
    FIXTURE_ARTIFACT_NAMES, load_schema, validate, scan_for_secret_material,
)
from .transport import BLOCKED_METHODS

# Operations submodules that carry execution/mutation capability. The harness core must
# not import any of these.
LIVE_EXECUTOR_MODULES = frozenset({
    "executors", "k8s_executor", "gate_executor", "rollback_coordinator",
    "orchestrator", "main", "action", "recommend", "observability", "shadow",
})
# Execution symbols that must never be imported into the harness core.
LIVE_EXECUTOR_SYMBOLS = frozenset({
    "ControlledScalingExecutor", "KubernetesScalingExecutor", "GateExecutor",
    "RollbackCoordinator", "ScalingBackend",
})
# Credential/context auto-discovery calls the harness must never make.
AUTODISCOVERY_NAMES = frozenset({
    "load_kube_config", "load_incluster_config", "load_config",
})

_PKG_DIR = Path(__file__).resolve().parent


def scan_harness_source(pkg_dir: Path = _PKG_DIR) -> List[str]:
    """Return violations: harness-core files importing a live executor or auto-discovery."""
    violations: List[str] = []
    for p in sorted(pkg_dir.glob("*.py")):
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                if mod.startswith("ugence_cloud_scaling_operations."):
                    sub = mod.split(".")[1]
                    if sub in LIVE_EXECUTOR_MODULES:
                        violations.append(f"{p.name}: imports ops.{sub}")
                if mod == "ugence_cloud_scaling_operations":
                    for a in node.names:
                        if a.name in LIVE_EXECUTOR_SYMBOLS:
                            violations.append(f"{p.name}: imports symbol {a.name}")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("ugence_cloud_scaling_operations."):
                        sub = a.name.split(".")[1]
                        if sub in LIVE_EXECUTOR_MODULES:
                            violations.append(f"{p.name}: imports ops.{sub}")
            # Auto-discovery call names.
            if isinstance(node, ast.Attribute) and node.attr in AUTODISCOVERY_NAMES:
                violations.append(f"{p.name}: references {node.attr}")
            if isinstance(node, ast.Name) and node.id in AUTODISCOVERY_NAMES:
                violations.append(f"{p.name}: references {node.id}")
    return violations


def _load_json(path: Path):
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> List[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_evidence_dir(evidence_dir: str) -> Dict[str, Any]:
    d = Path(evidence_dir)
    checks: List[Dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    present = [n for n in FIXTURE_ARTIFACT_NAMES if (d / n).exists()]
    add("all_fixture_artifacts_present", len(present) == len(FIXTURE_ARTIFACT_NAMES),
        f"{len(present)}/{len(FIXTURE_ARTIFACT_NAMES)}")

    # Every artifact bearing evidence markers must be labelled fake / not-real.
    real_claims = []
    fixture_labeled = True
    for p in d.glob("fixture_*.json"):
        obj = _load_json(p)
        if "evidence_class" in obj:
            if obj.get("evidence_class") != "FAKE_LOCAL_FIXTURE":
                fixture_labeled = False
            if obj.get("real_environment_observed") is True or obj.get("real_cluster_accessed") is True:
                real_claims.append(p.name)
    add("fixture_evidence_labeled", fixture_labeled)
    add("no_artifact_claims_real_access", not real_claims, ",".join(real_claims))

    # Decisions all proposed-only.
    decisions = _load_jsonl(d / "fixture_shadow_decisions.jsonl")
    all_shadow = all(x.get("execution_mode") == "SHADOW"
                     and x.get("execution_status") == "NOT_EXECUTED"
                     and x.get("proposed_only") is True for x in decisions)
    add("all_decisions_shadow_proposed_only", all_shadow, f"{len(decisions)} decisions")

    # Ledger: no transmitted write method.
    ledger = _load_jsonl(d / "fixture_request_method_ledger.jsonl")
    transmitted = [e["method"] for e in ledger
                   if e.get("allowed") and e.get("method", "").upper() in BLOCKED_METHODS]
    add("ledger_no_transmitted_write_methods", not transmitted, str(transmitted))
    add("request_method_ledger_complete", len(ledger) > 0, f"{len(ledger)} entries")

    # Authorization / stale / HPA.
    authz = _load_json(d / "fixture_authorization_validation.json")
    add("authorization_scenarios_all_ok", authz.get("all_ok") is True,
        f"{authz.get('total')} scenarios")
    stale = _load_json(d / "fixture_stale_state_results.json")
    add("stale_state_all_ok", stale.get("all_ok") is True)
    hpa = _load_json(d / "fixture_hpa_interaction_results.json")
    required_hpa = {HpaInteraction.NO_HPA.value, HpaInteraction.HPA_OBSERVED_COMPATIBLE.value,
                    HpaInteraction.HPA_BOUNDS_CONFLICT.value,
                    HpaInteraction.HPA_OBSERVED_CONFLICT.value,
                    HpaInteraction.HPA_STATE_INCOMPLETE.value}
    add("hpa_classifications_complete",
        required_hpa.issubset(set(hpa.get("classifications_present", []))))

    # Canaries.
    canary = _load_json(d / "fixture_mutation_canary_results.json")
    add("mutation_canaries_all_blocked", canary.get("all_blocked") is True,
        f"{canary.get('passed')}/{canary.get('total')}")
    add("canaries_no_transmitted_writes",
        not canary.get("transmitted_write_methods") and
        canary.get("real_network_transmissions", 0) == 0)

    # Network + redaction.
    net = _load_json(d / "fixture_network_failure_results.json")
    add("network_failures_contained", net.get("all_contained") is True)
    redaction = _load_json(d / "fixture_secret_redaction_report.json")
    add("secret_redaction_ok", redaction.get("all_ok") is True)

    # Secret material scan.
    hits = scan_for_secret_material(str(d))
    add("no_committed_secret_material", not hits, ",".join(hits))

    # Aggregate verdict.
    aggregate = _load_json(d / "fixture_aggregate_shadow_report.json")
    add("aggregate_verdict_ok",
        aggregate.get("verdict") == "CLOUD_SCALING_OPERATIONS_SHADOW_HARNESS_FIXTURE_OK",
        aggregate.get("verdict", ""))

    # Schema validation (representative artifacts).
    schema_ok = True
    schema_detail = ""
    try:
        validate(_load_json(d / "fixture_environment_manifest.json"),
                 load_schema("environment_manifest"))
        for dec in decisions:
            validate(dec, load_schema("shadow_decision"))
        for e in ledger:
            validate(e, load_schema("request_method_ledger"))
        validate(canary, load_schema("mutation_canary_results"))
        validate(aggregate, load_schema("aggregate_shadow_report"))
    except Exception as exc:  # noqa: BLE001
        schema_ok = False
        schema_detail = f"{type(exc).__name__}: {exc}"
    add("schemas_validate", schema_ok, schema_detail)

    # Package versions recorded.
    add("package_versions_recorded",
        bool(aggregate.get("operations_package_version"))
        and bool(aggregate.get("advisory_package_version")))
    add("source_revision_recorded", bool(aggregate.get("source_revision")))

    return {"checks": checks, "ok": all(c["passed"] for c in checks)}


def reproduce_scenarios() -> Dict[str, Any]:
    """Re-run authorization scenarios deterministically and confirm reproducibility."""
    a = [r.to_dict() for r in run_all_scenarios()]
    b = [r.to_dict() for r in run_all_scenarios()]
    return {"reproducible": a == b, "all_ok": all(r["ok"] for r in a), "count": len(a)}


__all__ = [
    "scan_harness_source", "verify_evidence_dir", "reproduce_scenarios",
    "LIVE_EXECUTOR_MODULES", "LIVE_EXECUTOR_SYMBOLS", "AUTODISCOVERY_NAMES",
]
