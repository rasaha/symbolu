"""
shadow_volume_validation.py — real SHADOW-volume flip-readiness validation.

Assembles the broadest realistic OFFLINE corpus available in this repo, drives it through
`SafeMCPGateway` in **SHADOW** mode (legacy still decides and executes; the trust core is
computed in parallel and recorded), persists every decision to a durable
`GovernanceAuditStore`, exports JSONL, and runs `shadow_report` to produce a flip-readiness
verdict from the persisted `trust_shadow` data.

This NEVER flips trust_core, changes policy, or adds an observable. It only produces the
evidence needed to decide whether a flip can be *considered*.

Corpus (all real fixtures; no fabricated model signals, no accuracy metric):
  * parity authority corpus      — every mapped authority (forbidden HARD_VETO, confidence
                                   floor, confidence-risk gap, raw-entropy buckets, JEPA
                                   DENY/DEFER, domain allow/confirm/block, shadow allow/block,
                                   approval).                          (experiments.trust_signal)
  * AgentDojo / InjecAgent minis — committed benchmark decision points.   (signal_gov.external)
  * signal_gov handbuilt + pilot — enterprise/action-risk + injection.    (signal_gov.dataset)
  * confident-unsafe pairs       — surface-matched safe/poisoned twins.    (signal_gov)

External/benchmark scenarios are mapped STRUCTURALLY to unsanctioned-asset gateway calls at
their declared risk level; the real gateway authorities decide. The flip gate is the
`shadow_report` verdict: exits non-zero on any unsafe_relaxation (and, with
--fail-on-unintended, on any unintended).

Run:
    PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.shadow_volume_validation
    PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.shadow_volume_validation \
        --policy reviewed --jsonl /tmp/shadow_volume.jsonl --fail-on-unintended
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from agentic.agentic_framework.mcp_gateway import ToolRiskLevel
from agentic.agentic_framework.trust.parity import PARITY_POLICY, REVIEWED_POLICY
from experiments.trust_signal import shadow_report
from experiments.trust_signal.parity_harness import (
    CORPUS,
    Scenario,
    _RISK_BY_NAME,
    external_scenarios,
    run_harness,
)

_POLICIES = {"parity": PARITY_POLICY, "reviewed": REVIEWED_POLICY}


# =============================================================================
# Corpus assembly (real fixtures only)
# =============================================================================

def _to_gateway_scenario(s, source: str, i: int) -> Scenario:
    """Map a signal_gov `Scenario` to a structural unsanctioned-asset gateway call.

    No model signals are fabricated (raw_entropy/verbalized_safety left unset); the real
    gateway authorities (shadow / domain / etc.) decide. min_confidence=0 so the base floor
    never coincidentally blocks — the governance authorities are what's exercised.
    """
    risk = _RISK_BY_NAME.get(getattr(s, "tool_risk_level", "write"), ToolRiskLevel.WRITE)
    tool = f"{source}_{i}_{getattr(s, 'proposed_tool', 'tool')}"[:64]
    return Scenario(
        name=f"{source}:{getattr(s, 'category', 'scn')}:{i}",
        tool=tool, risk=risk, profile="shadow_basic",
        authority=f"ext:{getattr(s, 'category', 'scn')}", scope="external",
        raw_entropy=None, min_confidence=0.0)


def signalgov_scenarios() -> List[Scenario]:
    """Map signal_gov handbuilt + pilot + confident-unsafe datasets (graceful if absent)."""
    out: List[Scenario] = []
    try:
        from experiments.signal_gov import dataset as sg_dataset
    except Exception:
        return out

    sources = []
    for loader_name, label in (("load_handbuilt", "handbuilt"),):
        loader = getattr(sg_dataset, loader_name, None)
        if loader:
            try:
                sources.append((label, loader()))
            except Exception:
                pass
    # pilot JSONL (if present)
    try:
        pilot = sg_dataset.DATA_DIR / "pilot_30_50.jsonl"
        if pilot.exists():
            sources.append(("pilot", sg_dataset.load_scenarios_jsonl(pilot)))
    except Exception:
        pass
    # confident-unsafe twins
    try:
        from experiments.signal_gov.confident_unsafe import load_confident_unsafe
        sources.append(("confunsafe", load_confident_unsafe()))
    except Exception:
        pass

    for label, scns in sources:
        for i, s in enumerate(scns):
            out.append(_to_gateway_scenario(s, label, i))
    return out


def assemble_corpus(*, include_external: bool = True,
                    include_signalgov: bool = True) -> List[Scenario]:
    """Assemble the broadest available realistic corpus from committed fixtures."""
    corpus: List[Scenario] = list(CORPUS)              # mapped-authority coverage
    if include_external:
        corpus += external_scenarios()                 # AgentDojo / InjecAgent minis
    if include_signalgov:
        corpus += signalgov_scenarios()                # handbuilt + pilot + confident-unsafe
    return corpus


# =============================================================================
# Run: drive SHADOW → persist → export → report
# =============================================================================

def run_validation(*, policy=REVIEWED_POLICY, corpus: Optional[List[Scenario]] = None,
                   db_path: str, jsonl_path: Optional[str] = None) -> dict:
    """Drive the corpus through SHADOW into a durable store, export JSONL, build the report.

    Returns a dict with the GovernanceAuditStore, the shadow_report.ShadowReport, and the
    jsonl path (if exported). The gateway acts on LEGACY throughout — behaviour unchanged.
    """
    from agentic.ledger.governance_audit_store import GovernanceAuditStore

    corpus = assemble_corpus() if corpus is None else corpus
    store = GovernanceAuditStore(db_path)
    run_harness(policy, corpus, audit_store=store)
    if jsonl_path:
        store.export_jsonl(jsonl_path)
    rep = shadow_report.build_report(shadow_report.load_records(store_path=db_path))
    return {"store": store, "report": rep, "jsonl": jsonl_path, "n": len(corpus)}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Real SHADOW-volume flip-readiness validation (no flip).")
    parser.add_argument("--policy", choices=list(_POLICIES), default="reviewed",
                        help="authority policy to validate (default reviewed = flip candidate)")
    parser.add_argument("--db", help="GovernanceAuditStore path (default: temp file)")
    parser.add_argument("--jsonl", help="also export the audit JSONL to this path")
    parser.add_argument("--no-external", action="store_true",
                        help="exclude AgentDojo/InjecAgent minisets")
    parser.add_argument("--no-signalgov", action="store_true",
                        help="exclude signal_gov handbuilt/pilot/confident-unsafe")
    parser.add_argument("--fail-on-unintended", action="store_true",
                        help="exit non-zero on any unintended mismatch (not just unsafe)")
    parser.add_argument("--max-examples", type=int, default=15)
    args = parser.parse_args(argv)

    corpus = assemble_corpus(include_external=not args.no_external,
                             include_signalgov=not args.no_signalgov)

    tmp = None
    db_path = args.db
    if db_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        db_path = tmp.name

    res = run_validation(policy=_POLICIES[args.policy], corpus=corpus,
                         db_path=db_path, jsonl_path=args.jsonl)
    rep = res["report"]
    store = res["store"]

    print(f"# Real SHADOW-volume validation  (policy={args.policy}, "
          f"scenarios={len(corpus)}, chain_valid={store.verify_chain().valid})\n")
    print(shadow_report.render(rep, max_examples=args.max_examples,
                               fail_on_unintended=args.fail_on_unintended,
                               include_entropy=True))
    store.close()
    if tmp is not None:
        Path(tmp.name).unlink(missing_ok=True)
    return shadow_report.verdict(rep, fail_on_unintended=args.fail_on_unintended)["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
