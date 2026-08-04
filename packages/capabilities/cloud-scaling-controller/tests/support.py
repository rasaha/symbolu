"""Shared helpers for the package-local suite: deterministic scenario replay and the
projection that excludes the pre-existing ``identity_deviation`` nondeterminism.

The projection MUST match the one used to generate
``artifacts/prepackaging_behavior_baseline.json`` so the parity hash is comparable.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import re
from typing import Any, Dict, List

from ugence_cloud_scaling_controller.controller import Controller
from ugence_cloud_scaling_controller.config import InfraControllerConfig

ROUND = 10
_ID_LINE = re.compile(r"\n  Identity Drift:.*?(?=\n)")

ARTIFACTS = pathlib.Path(__file__).resolve().parents[1] / "artifacts"
BASELINE_PATH = ARTIFACTS / "prepackaging_behavior_baseline.json"


def rnd(x: Any) -> Any:
    if isinstance(x, float):
        return round(x, ROUND)
    if isinstance(x, dict):
        return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v) for v in x]
    return x


def deterministic_explanation(text: str) -> str:
    return _ID_LINE.sub("\n  Identity Drift:      <nondeterministic:excluded>", text)


def project(result) -> Dict[str, Any]:
    """Deterministic projection of an ActionResult (identity_deviation excluded)."""
    d = rnd(dataclasses.asdict(result))
    d.pop("identity_deviation", None)
    d["identity_deviation"] = "<nondeterministic:excluded>"
    d["explanation"] = deterministic_explanation(result.explain())
    return d


def run_steps(steps: List[Dict[str, Any]], config: InfraControllerConfig = None) -> List[Dict[str, Any]]:
    """Replay input steps through a fresh controller, returning projected records."""
    ctrl = Controller(config or InfraControllerConfig())
    out: List[Dict[str, Any]] = []
    for s in steps:
        res = ctrl.step(
            metrics=s["metrics"],
            current_replicas=s["current_replicas"],
            deploy_active=s.get("deploy_active", False),
            phase=s.get("phase", "normal"),
            recent_pod_restarts=s.get("recent_pod_restarts", 0),
        )
        rec = project(res)
        rec["_input"] = {k: rnd(v) for k, v in s.items()}
        out.append(rec)
    return out


def load_baseline() -> Dict[str, Any]:
    return json.loads(BASELINE_PATH.read_text())


def scenarios_hash(scenarios: Dict[str, List[Dict[str, Any]]]) -> str:
    core = json.dumps({"scenarios": scenarios}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(core.encode()).hexdigest()
