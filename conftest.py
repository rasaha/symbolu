"""
Pytest configuration for the symbolu project.

Adds the project root to sys.path so that tests can import from docs.experiments.
"""
import sys
from pathlib import Path

# Add project root to sys.path for tests
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Canonical migrated packages live under packages/<name>/src. Put them on the
# path so a source checkout resolves them without an editable install (e.g. the
# governance_providers contract shims import ugence_governance_contracts).
for _src in (project_root / "packages" / "jcs" / "src",
             project_root / "packages" / "governance-contracts" / "src",
             project_root / "packages" / "governance-provider-framework" / "src",
             project_root / "packages" / "providers" / "tap" / "src",
             project_root / "packages" / "providers" / "actiongate" / "src",
             project_root / "packages" / "capabilities" / "storygraph" / "src",
             project_root / "packages" / "capabilities" / "decision-authority" / "src",
             project_root / "packages" / "capabilities" / "model-selection" / "src",
             project_root / "packages" / "capabilities" / "context-minimization" / "src",
             project_root / "packages" / "capabilities" / "cloud-scaling-controller" / "src",
             project_root / "packages" / "capabilities" / "cloud-scaling-operations" / "src",
             project_root / "packages" / "capabilities" / "llm-steering-controller" / "src",
             project_root / "packages" / "runtime" / "agent-runtime" / "src",
             project_root / "packages" / "products" / "procurement" / "src",
             # Ugence Value Intelligence: the readiness engine, its policy
             # dependencies, and the governed-value kernel. Required by
             # tests/test_readiness_governed_value_doc_drift.py.
             project_root / "packages" / "uvi-policy-contracts" / "src",
             project_root / "packages" / "policy-authority" / "src",
             project_root / "packages" / "capabilities" / "agent-value-readiness" / "src",
             project_root / "packages" / "governed-value" / "src",
             # Reasoning Method Governance slice 1: the shared contracts and the
             # comparison engine. Required by both packages' tests and by
             # tests/experiments/workflow_fit_study/test_governed_adapter.py.
             project_root / "packages" / "capabilities" / "reasoning-method-governance" / "src",
             project_root / "packages" / "capabilities" / "readiness-comparison" / "src"):
    if _src.is_dir() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
