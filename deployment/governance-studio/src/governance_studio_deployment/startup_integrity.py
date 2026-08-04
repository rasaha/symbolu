"""Fail-closed startup integrity gate (P3E §19).

Runs before the application port is bound. On any failure it returns a precise code
and the caller must exit nonzero without listening. Produces a machine-readable
report (hashes + versions, never secrets).
"""
from __future__ import annotations

import hashlib
import json
import os
import ssl
from dataclasses import dataclass, field
from typing import List, Optional

from . import (
    API_CONTRACT,
    BACKEND_API_VERSION,
    DEPLOYMENT_NAME,
    DEPLOYMENT_VERSION,
    FRONTEND_VERSION,
    OPENAPI_SHA256,
)
from .config import DeploymentConfig
from .passwords import is_valid_hash_format
from .synthetic import SyntheticManifest, verify_bundle


def cert_not_after_seconds(cert_path: str) -> Optional[float]:
    """Epoch seconds of a PEM certificate's notAfter, or None if unparseable."""
    try:
        decoded = ssl._ssl._test_decode_cert(cert_path)  # type: ignore[attr-defined]
        return float(ssl.cert_time_to_seconds(decoded["notAfter"]))
    except Exception:  # noqa: BLE001
        return None


def is_cert_expired(cert_path: str, now: float) -> bool:
    """True when the certificate's notAfter is in the past relative to ``now``."""
    not_after = cert_not_after_seconds(cert_path)
    return not_after is not None and not_after < now


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class IntegrityInputs:
    config: DeploymentConfig
    openapi_path: str
    approved_ops_path: str
    frontend_build_marker: str  # JSON {"version","build_hash"} produced at packaging


@dataclass
class IntegrityResult:
    ok: bool
    code: str
    checks: dict = field(default_factory=dict)
    report: dict = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)


def run_startup_integrity(inputs: IntegrityInputs) -> IntegrityResult:
    cfg = inputs.config
    checks: dict = {}
    failures: List[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks[name] = bool(ok)
        if not ok:
            failures.append(f"{name}{(': ' + detail) if detail else ''}")

    # config first (credentials, TLS, hosts, packaged assets, mode)
    for err in cfg.validate():
        failures.append(f"config: {err}")
    checks["config_valid"] = not any(f.startswith("config:") for f in failures)
    check("credentials_configured", bool(cfg.username) and is_valid_hash_format(cfg.password_hash or ""))
    check("allowed_hosts_configured", bool(cfg.allowed_hosts) or not cfg.is_production)
    # production must not reuse committed development material (test cert) or bind loopback
    dev_material = ("tests/certs" in cfg.tls_cert_file.replace(os.sep, "/")) or cfg.bind_host.startswith("127.")
    check("no_dev_mode_in_production", not (cfg.is_production and dev_material))

    # frontend build
    index_ok = bool(cfg.frontend_dir) and os.path.isfile(os.path.join(cfg.frontend_dir, "index.html"))
    check("frontend_build_exists", index_ok)
    fe_version = None
    fe_hash = None
    if os.path.isfile(inputs.frontend_build_marker):
        try:
            marker = json.load(open(inputs.frontend_build_marker, encoding="utf-8"))
            fe_version, fe_hash = marker.get("version"), marker.get("build_hash")
        except (OSError, ValueError):
            pass
    check("frontend_version_0_2_0", fe_version == FRONTEND_VERSION, f"marker={fe_version}")

    # backend identity (imported from the frozen package)
    backend_version = None
    backend_contract = None
    try:
        from ugence_governance_studio_api.version import VERSION as _bv, API_CONTRACT_VERSION as _bc  # type: ignore
        backend_version, backend_contract = _bv, _bc
    except Exception:  # noqa: BLE001
        pass
    check("backend_api_version_0_1_0", backend_version == BACKEND_API_VERSION, f"got={backend_version}")
    check("api_contract_governance_studio_api_v1", backend_contract == API_CONTRACT, f"got={backend_contract}")

    # OpenAPI freeze
    openapi_hash = _sha256_file(inputs.openapi_path) if os.path.isfile(inputs.openapi_path) else None
    check("openapi_hash_unchanged", openapi_hash == OPENAPI_SHA256, f"got={openapi_hash}")

    # approved-operation manifest valid (hash matches frozen contract, has 17 approved)
    approved_ok = False
    approved_count = 0
    if os.path.isfile(inputs.approved_ops_path):
        try:
            am = json.load(open(inputs.approved_ops_path, encoding="utf-8"))
            approved_count = len(am.get("approved_operation_ids", []))
            approved_ok = am.get("openapi_sha256") == OPENAPI_SHA256 and approved_count == 17 and am.get("contract") == API_CONTRACT
        except (OSError, ValueError):
            approved_ok = False
    check("approved_operation_manifest_valid", approved_ok, f"count={approved_count}")

    # synthetic bundle + fixture hashes
    synthetic_violations: List[str] = ["manifest missing"]
    if cfg.manifest_path and os.path.isfile(cfg.manifest_path) and cfg.scenarios_root and os.path.isdir(cfg.scenarios_root):
        synthetic_violations = verify_bundle(SyntheticManifest.load(cfg.manifest_path), cfg.scenarios_root)
    check("synthetic_bundle_valid", not synthetic_violations, "; ".join(synthetic_violations))

    # scenario_root override guard: the running scenario root must equal the pinned one
    pinned_root = os.path.abspath(cfg.scenarios_root) if cfg.scenarios_root else ""
    env_override = os.environ.get("UGS_API_SCENARIO_ROOT")
    override_ok = env_override is None or os.path.abspath(env_override) == pinned_root
    check("no_external_fixture_override", override_ok)

    # TLS material parses (cert/key load fails on mismatch); subject/expiry reported
    tls_ok = False
    cert_subject = cert_expiry = None
    try:
        if os.path.isfile(cfg.tls_cert_file) and os.path.isfile(cfg.tls_key_file):
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.load_cert_chain(cfg.tls_cert_file, cfg.tls_key_file)  # fails on cert/key mismatch
            tls_ok = True
            try:  # best-effort human-readable cert facts (no private key material)
                decoded = ssl._ssl._test_decode_cert(cfg.tls_cert_file)  # type: ignore[attr-defined]
                cert_subject = "/".join("=".join(p) for rdn in decoded.get("subject", ()) for p in rdn)
                cert_expiry = decoded.get("notAfter")
            except Exception:  # noqa: BLE001
                pass
    except (ssl.SSLError, OSError):
        tls_ok = False
    check("tls_certificate_valid", tls_ok)
    import time as _time
    check("tls_certificate_not_expired", tls_ok and not is_cert_expired(cfg.tls_cert_file, _time.time()))

    ok = not failures
    code = "OK" if ok else _classify(failures)
    report = {
        "deployment": DEPLOYMENT_NAME,
        "deployment_version": DEPLOYMENT_VERSION,
        "frontend_version": FRONTEND_VERSION,
        "frontend_build_hash": fe_hash,
        "backend_api_version": backend_version,
        "api_contract": API_CONTRACT,
        "openapi_sha256": openapi_hash,
        "synthetic_bundle_hash": _bundle_hash_of(cfg),
        "checks": checks,
        "result": "PASS" if ok else "FAIL",
        "failure_code": code,
        "cert_subject": cert_subject,
        "cert_expiry": cert_expiry,
    }
    return IntegrityResult(ok=ok, code=code, checks=checks, report=report, failures=failures)


def _bundle_hash_of(cfg: DeploymentConfig) -> Optional[str]:
    try:
        return SyntheticManifest.load(cfg.manifest_path).bundle_hash
    except Exception:  # noqa: BLE001
        return None


def _classify(failures: List[str]) -> str:
    joined = " ".join(failures)
    if "synthetic" in joined or "fixture" in joined or "override" in joined:
        return "SYNTHETIC_DATA_BOUNDARY_FAILED"
    if "tls" in joined.lower() or "certificate" in joined.lower():
        return "GOVERNANCE_STUDIO_P3E_HTTPS_FAILED"
    if "credential" in joined or "config:" in joined or "allowed_hosts" in joined:
        return "GOVERNANCE_STUDIO_P3E_ACCESS_CONTROL_FAILED"
    if "openapi" in joined:
        return "GOVERNANCE_STUDIO_P3E_OPENAPI_DRIFT"
    return "STARTUP_INTEGRITY_FAILED"


def write_report(result: IntegrityResult, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result.report, fh, indent=2, sort_keys=True)
        fh.write("\n")
