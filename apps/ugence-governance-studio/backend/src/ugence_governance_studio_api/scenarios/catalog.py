"""Read-only scenario catalog and safe fixture loading (§8, §20, §21).

The catalog loads the four committed Governance Studio demo scenarios (the frozen
P3A ``demo_data`` inputs, ``expected_outputs`` oracles and MANIFEST) plus the
AWC P2.1 ``governance_studio_v2`` conformance fixtures. Everything is loaded
**read-only** from bundled package data; requests never receive a shared mutable
object (every accessor returns a deep copy), and fixture files are never written.

This module contains NO policy logic. Inputs are validated with the AWC public
model classes' ``model_validate`` — there is no bespoke deserialization.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import ugence_agent_workforce_composer.api as awc

from ..serialization.canonical import sha256_hex
from ..version import (
    SUPPORTED_AWC_MAX_EXCLUSIVE,
    SUPPORTED_AWC_MIN,
    awc_version_supported,
)

# Recorded manifest of every bundled fixture's sha256 (packaging protection P2).
BUNDLED_FIXTURE_MANIFEST = "BUNDLED_FIXTURE_MANIFEST.json"

# Logical time is a pinned property of the frozen scenarios (matches P3A's
# ``scenario_authoring.LOGICAL_TIME``); it is an input artifact, not runtime state.
LOGICAL_TIME: float = 1_000_000.0

SCENARIO_IDS: Tuple[str, ...] = (
    "procurement",
    "customer_support",
    "cybersecurity_success",
    "cybersecurity_no_feasible_team",
)

# Presentation metadata (title / domain / description). Domain facts come from the
# frozen manifest's demonstration block; these labels are display-only.
_SCENARIO_META: Dict[str, Dict[str, str]] = {
    "procurement": {
        "title": "Procurement Sourcing Workforce",
        "domain": "procurement",
        "description": "Non-greedy agent team selection under provider concentration limits.",
    },
    "customer_support": {
        "title": "Customer Support Triage & Response",
        "domain": "customer_support",
        "description": "Clean feasible support team; a cyber specialist is eliminated, not mis-assigned.",
    },
    "cybersecurity_success": {
        "title": "Cybersecurity Incident Response (Feasible)",
        "domain": "cybersecurity",
        "description": "Feasible incident-response team; single-holder roles have no fallback.",
    },
    "cybersecurity_no_feasible_team": {
        "title": "Cybersecurity Incident Response (No Feasible Team)",
        "domain": "cybersecurity",
        "description": "NO_FEASIBLE_TEAM: only one approved provider is cleared to clearance level 4.",
    },
}

_SUPPORTED_OPERATIONS: Tuple[str, ...] = (
    "adapt", "eligibility", "ranking", "composition", "plan",
    "permissions", "fallback", "explanations", "replay", "compare",
    "what-if", "export",
)

# Policy fixture filenames → AWC public model classes (same mapping P3A uses, but
# re-declared here so the API never imports P3A test helpers).
_POLICY_FILES: Dict[str, Tuple[str, Any]] = {
    "enterprise_policy": ("enterprise_agent_policy.json", awc.EnterpriseAgentPolicy),
    "eligibility_policy": ("eligibility_policy.json", awc.EligibilityPolicy),
    "ranking_policy": ("ranking_policy.json", awc.AgentRankingPolicy),
    "composition_policy": ("composition_policy.json", awc.TeamCompositionPolicy),
    "permission_policy": ("permission_policy.json", awc.PermissionBoundingPolicy),
    "fallback_policy": ("fallback_policy.json", awc.AgentFallbackPolicy),
}

# v2 conformance policy filenames (the conformance bundle names them without the
# "agent"/"team" prefixes P3A demo_data uses).
_V2_POLICY_FILES: Dict[str, Tuple[str, Any]] = {
    "enterprise_policy": ("enterprise_policy.json", awc.EnterpriseAgentPolicy),
    "eligibility_policy": ("eligibility_policy.json", awc.EligibilityPolicy),
    "ranking_policy": ("ranking_policy.json", awc.AgentRankingPolicy),
    "composition_policy": ("composition_policy.json", awc.TeamCompositionPolicy),
    "permission_policy": ("permission_policy.json", awc.PermissionBoundingPolicy),
    "fallback_policy": ("fallback_policy.json", awc.AgentFallbackPolicy),
}


class ScenarioNotFound(KeyError):
    """Raised when an unknown scenario id is requested."""


def _bundled_data_root() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@dataclass(frozen=True)
class ScenarioRoots:
    demo_data: str
    expected_output: str
    conformance_v2: str


class ScenarioCatalog:
    """Immutable, read-only catalog over the frozen scenario fixtures.

    A single catalog instance is shared across requests. It caches parsed inputs
    but never hands out the cached objects directly — every ``inputs``/``registry``
    accessor returns a fresh deep copy so concurrent requests cannot leak state.
    """

    def __init__(self, roots: Optional[ScenarioRoots] = None):
        self._roots = roots or self._default_roots()
        self._manifest: Optional[dict] = None
        self._raw_inputs: Dict[str, dict] = {}

    # -- root resolution -------------------------------------------------- #
    @staticmethod
    def _default_roots() -> ScenarioRoots:
        data = _bundled_data_root()
        return ScenarioRoots(
            demo_data=os.path.join(data, "demo_data"),
            expected_output=os.path.join(data, "expected_outputs"),
            conformance_v2=os.path.join(data, "conformance_v2"),
        )

    @classmethod
    def from_settings(cls, settings) -> "ScenarioCatalog":
        data = _bundled_data_root()
        roots = ScenarioRoots(
            demo_data=settings.scenario_root or os.path.join(data, "demo_data"),
            expected_output=settings.expected_output_root or os.path.join(data, "expected_outputs"),
            conformance_v2=os.path.join(data, "conformance_v2"),
        )
        return cls(roots)

    @property
    def roots(self) -> ScenarioRoots:
        return self._roots

    @property
    def scenario_ids(self) -> Tuple[str, ...]:
        return SCENARIO_IDS

    def _require(self, scenario_id: str) -> None:
        if scenario_id not in SCENARIO_IDS:
            raise ScenarioNotFound(scenario_id)

    # -- manifest / metadata --------------------------------------------- #
    def manifest(self) -> dict:
        if self._manifest is None:
            self._manifest = _read_json(os.path.join(self._roots.expected_output, "MANIFEST.json"))
        return json.loads(json.dumps(self._manifest))  # defensive copy

    def scenario_manifest(self, scenario_id: str) -> dict:
        self._require(scenario_id)
        return _read_json(os.path.join(self._roots.demo_data, scenario_id, "scenario_manifest.json"))

    def metadata(self, scenario_id: str) -> dict:
        """Concise scenario metadata for the list endpoint (§8)."""
        self._require(scenario_id)
        sm = self.scenario_manifest(scenario_id)
        meta = _SCENARIO_META[scenario_id]
        return {
            "scenario_id": scenario_id,
            "title": meta["title"],
            "domain": meta["domain"],
            "description": meta["description"],
            "workflow_contract_version": "workflow_ir.v1",
            "fixture_version": sm.get("awc_version"),
            "expected_plan_state": sm["demonstration"]["expected_plan_state"],
            "synthetic_data": True,
            "supported_operations": list(_SUPPORTED_OPERATIONS),
        }

    def list_metadata(self) -> List[dict]:
        return [self.metadata(sid) for sid in SCENARIO_IDS]

    def expected(self, scenario_id: str, artifact: str) -> dict:
        self._require(scenario_id)
        return _read_json(os.path.join(self._roots.expected_output, scenario_id, artifact))

    def expected_fingerprints(self, scenario_id: str) -> dict:
        return self.expected(scenario_id, "fingerprints.json")

    # -- raw workflow / overlay ------------------------------------------ #
    def raw_workflow(self, scenario_id: str) -> dict:
        self._require(scenario_id)
        return _read_json(os.path.join(self._roots.demo_data, scenario_id, "compiled_workflow.json"))

    def raw_overlay(self, scenario_id: str) -> dict:
        self._require(scenario_id)
        return _read_json(os.path.join(self._roots.demo_data, scenario_id, "enterprise_role_overlay.json"))

    # -- validated inputs (deep-copied per call) ------------------------- #
    def inputs(self, scenario_id: str) -> dict:
        """Return a fresh set of validated AWC input models for a scenario.

        Every call re-parses (or deep-copies) so no two requests share a mutable
        object — a hard requirement for the concurrency + immutability tests.
        """
        self._require(scenario_id)
        base = os.path.join(self._roots.demo_data, scenario_id)
        s: Dict[str, Any] = {
            "scenario_id": scenario_id,
            "workflow": _read_json(os.path.join(base, "compiled_workflow.json")),
            "overlay": _read_json(os.path.join(base, "enterprise_role_overlay.json")),
            "registry": awc.AgentRegistrySnapshot.model_validate(
                _read_json(os.path.join(base, "agent_registry_snapshot.json"))),
        }
        for key, (fname, cls) in _POLICY_FILES.items():
            s[key] = cls.model_validate(_read_json(os.path.join(base, fname)))
        return s

    def v2_inputs(self, scenario_id: str) -> dict:
        """Validated v1 + v2 inputs from the AWC P2.1 conformance bundle."""
        self._require(scenario_id)
        base = os.path.join(self._roots.conformance_v2, scenario_id)
        s: Dict[str, Any] = {
            "scenario_id": scenario_id,
            "v1_workflow": _read_json(os.path.join(base, "v1_workflow.json")),
            "v2_workflow": _read_json(os.path.join(base, "v2_workflow.json")),
            "v1_overlay": _read_json(os.path.join(base, "v1_overlay.json")),
            "v2_overlay": _read_json(os.path.join(base, "v2_overlay.json")),
            "registry": awc.AgentRegistrySnapshot.model_validate(
                _read_json(os.path.join(base, "registry.json"))),
        }
        for key, (fname, cls) in _V2_POLICY_FILES.items():
            s[key] = cls.model_validate(_read_json(os.path.join(base, fname)))
        return s

    def equivalence_manifest(self) -> dict:
        return _read_json(os.path.join(self._roots.conformance_v2, "EQUIVALENCE_MANIFEST.json"))

    # -- readiness / integrity ------------------------------------------- #
    def verify_fixture_hashes(self) -> Tuple[bool, List[str]]:
        """Verify every committed input/output file matches the MANIFEST sha256.

        Returns (ok, mismatches). Used by ``/ready`` and the readiness test. The
        MANIFEST paths are repo-relative (``demo_data/...`` / ``expected_outputs/...``)
        so we map each onto the configured roots.
        """
        problems: List[str] = []
        manifest = self.manifest()
        app_root_of = {
            "demo_data": self._roots.demo_data,
            "expected_outputs": self._roots.expected_output,
        }
        for section in ("inputs", "outputs"):
            for rel, expected_hash in manifest.get(section, {}).items():
                top = rel.split("/", 1)[0]
                root = app_root_of.get(top)
                if root is None:
                    problems.append(f"unknown root for {rel}")
                    continue
                path = os.path.join(root, rel.split("/", 1)[1])
                if not os.path.isfile(path):
                    problems.append(f"missing {rel}")
                    continue
                with open(path, "rb") as fh:
                    actual = sha256_hex(fh.read())
                if actual != expected_hash:
                    problems.append(f"hash mismatch {rel}")
        return (not problems, problems)

    def bundled_fixture_manifest(self) -> dict:
        """The recorded manifest of every bundled fixture's sha256 (protection P2)."""
        path = os.path.join(_bundled_data_root(), BUNDLED_FIXTURE_MANIFEST)
        return _read_json(path)

    def verify_bundled_fixture_manifest(self) -> Tuple[bool, List[str]]:
        """Verify every bundled fixture file matches its recorded manifest hash.

        This is the runtime ``packaged == recorded`` leg of the three-way drift
        protection (protection P2). Covers all bundled scenario manifests,
        workflows, registries, policies, expected outputs, replay records and v2
        conformance artifacts. The full ``canonical source == packaged ==
        recorded`` equality is proven by the blocking test / CI verifier (which
        additionally has the P3A + AWC source trees available).
        """
        data_root = _bundled_data_root()
        manifest = self.bundled_fixture_manifest()
        files = manifest.get("files", {})
        problems: List[str] = []
        if not files:
            return (False, ["bundled fixture manifest is empty"])
        for rel, expected_hash in files.items():
            path = os.path.join(data_root, rel)
            if not os.path.isfile(path):
                problems.append(f"missing bundled {rel}")
                continue
            with open(path, "rb") as fh:
                actual = sha256_hex(fh.read())
            if actual != expected_hash:
                problems.append(f"bundled hash mismatch {rel}")
        # Also confirm no extra bundled fixture escaped the manifest.
        recorded = set(files)
        for dirpath, _dirs, fnames in os.walk(data_root):
            for fname in fnames:
                if fname == BUNDLED_FIXTURE_MANIFEST or not fname.endswith(".json"):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fname), data_root)
                if rel not in recorded:
                    problems.append(f"unrecorded bundled fixture {rel}")
        return (not problems, problems)

    def readiness(self) -> dict:
        """Structured readiness result (§7)."""
        checks: Dict[str, Any] = {}
        # 1. manifests load
        try:
            self.manifest()
            for sid in SCENARIO_IDS:
                self.scenario_manifest(sid)
            checks["scenario_manifests_load"] = True
        except Exception as exc:  # pragma: no cover - defensive
            checks["scenario_manifests_load"] = False
            checks["manifest_error"] = str(exc)
        # 2. fixture hashes match
        try:
            ok_hashes, mismatches = self.verify_fixture_hashes()
        except Exception as exc:  # missing root / unreadable manifest
            ok_hashes, mismatches = False, [str(exc)]
        checks["fixture_hashes_match"] = ok_hashes
        if mismatches:
            checks["fixture_hash_mismatches"] = mismatches[:10]
        # 3. AWC public package imports + contracts present
        checks["awc_import_ok"] = True
        checks["supported_contracts_present"] = (
            "workflow_ir.v1" in awc.SUPPORTED_COMPILER_CONTRACTS
            and "workflow_ir.v2" in awc.SUPPORTED_COMPILER_CONTRACTS
        )
        # 3b. installed AWC version is within the supported range (protection P1).
        # Readiness FAILS CLOSED when AWC is outside [SUPPORTED_AWC_MIN, MAX).
        installed_awc = awc.__version__
        in_range = awc_version_supported(installed_awc)
        checks["awc_version_in_supported_range"] = in_range
        if not in_range:
            checks["awc_version_error"] = (
                f"installed AWC {installed_awc} outside supported range "
                f">={SUPPORTED_AWC_MIN},<{SUPPORTED_AWC_MAX_EXCLUSIVE}"
            )
        # 3c. bundled fixtures match their recorded manifest (protection P2).
        try:
            bundle_ok, bundle_problems = self.verify_bundled_fixture_manifest()
        except Exception as exc:  # missing/unreadable bundled manifest
            bundle_ok, bundle_problems = False, [str(exc)]
        checks["bundled_fixture_manifest_ok"] = bundle_ok
        if bundle_problems:
            checks["bundled_fixture_problems"] = bundle_problems[:10]
        # 4. no mutable external service dependency (constant — API is offline)
        checks["no_external_service_dependency"] = True
        ready = all(v for k, v in checks.items() if isinstance(v, bool))
        return {"ready": ready, "checks": checks}


@lru_cache(maxsize=1)
def default_catalog() -> ScenarioCatalog:
    return ScenarioCatalog()
