"""Legacy compatibility facades preserve identity and carry no business logic."""

from __future__ import annotations

import ast
import pathlib

import ugence_procurement as up


def test_legacy_domain_root_imports_resolve():
    import domains.procurement  # noqa: F401
    import domains.procurement.errors  # noqa: F401
    import domains.procurement.requests  # noqa: F401
    import domains.procurement.policies  # noqa: F401


def test_legacy_deep_imports_resolve():
    from domains.procurement.requests.contracts import PurchaseRequest  # noqa: F401
    from domains.procurement.policies.assessment import ProcurementAssessmentService  # noqa: F401
    from domains.procurement.suppliers.adapter import SupplierExecutionAdapter  # noqa: F401
    from applications.procurement.platform import build_in_memory_platform  # noqa: F401
    from applications.procurement.api.routes import ProcurementAPI  # noqa: F401


def test_canonical_and_legacy_object_identity():
    from ugence_procurement.requests.contracts import PurchaseRequest as C1
    from domains.procurement.requests.contracts import PurchaseRequest as L1
    assert C1 is L1

    from ugence_procurement.policies.budget_authority import BudgetAuthorityAdapter as C2
    from domains.procurement.policies import BudgetAuthorityAdapter as L2
    assert C2 is L2

    from ugence_procurement.suppliers.outcomes import SupplierOutcome as C3
    from domains.procurement.suppliers import SupplierOutcome as L3
    assert C3 is L3

    from ugence_procurement.platform import build_in_memory_platform as C4
    from applications.procurement.platform import build_in_memory_platform as L4
    from applications.procurement import build_in_memory_platform as L4b
    assert C4 is L4 is L4b

    from ugence_procurement.routes import ProcurementAPI as C5
    from applications.procurement.api.routes import ProcurementAPI as L5
    from applications.procurement.api import ProcurementAPI as L5b
    assert C5 is L5 is L5b

    from ugence_procurement.errors import SupplierNotKnownError as C6
    from domains.procurement.errors import SupplierNotKnownError as L6
    assert C6 is L6


def _facade_files():
    root = pathlib.Path(up.__file__).resolve().parents[1]
    # Facades shipped under src/domains and src/applications, or resolved from the
    # monorepo trees. Locate whichever is importable.
    import domains.procurement as dp
    import applications.procurement as ap
    import applications.procurement.api as apa
    return [pathlib.Path(m.__file__) for m in (dp, ap, apa)]


def test_facades_define_no_business_logic():
    """A compatibility facade may re-export/alias, but must define no class and no
    top-level policy/service function (no duplicate implementation)."""
    for f in _facade_files():
        tree = ast.parse(f.read_text())
        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        assert not classes, f"{f} defines classes {classes} — not logic-free"
        # Only the bootstrap helper function is permitted.
        funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        assert set(funcs) <= {"_ensure_canonical_importable"}, f"{f}: {funcs}"


def test_single_physical_implementation():
    """The canonical class lives in ugence_procurement.*, never domains/applications."""
    from ugence_procurement.requests.contracts import PurchaseRequest
    from ugence_procurement.platform import ProcurementPlatform
    assert PurchaseRequest.__module__.startswith("ugence_procurement.")
    assert ProcurementPlatform.__module__.startswith("ugence_procurement.")
