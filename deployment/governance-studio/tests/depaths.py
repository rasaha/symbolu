"""Shared path constants for the P3E deployment tests (named to avoid clashing with
the repository-root ``conftest`` on sys.path)."""
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CERTS = os.path.join(os.path.dirname(__file__), "certs")

USERNAME = "operator"
PASSWORD = "demo-password-123"
FRONTEND_DIR = os.path.join(REPO, "apps", "ugence-governance-studio", "frontend", "dist")
SCENARIOS_ROOT = os.path.join(REPO, "apps", "ugence-governance-studio", "demo_data")
MANIFEST = os.path.join(REPO, "deployment", "governance-studio", "synthetic-scenarios-manifest.json")
OPENAPI = os.path.join(REPO, "apps", "ugence-governance-studio", "contracts", "openapi.json")
APPROVED_OPS = os.path.join(REPO, "apps", "ugence-governance-studio", "frontend", "security", "approved-api-operations.json")
