"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package.
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Frozen contract identity of the draft record shape.
CONTRACT_VERSION = "workflow_draft.v1"

#: The only lifecycle state a record here can ever carry. There is no field, method or
#: transition that could move a draft anywhere else: approval, compilation, publication,
#: export and runtime consumption are refused structurally, not by discipline (owner
#: ruling, Bring Your Workflow phase 3A).
LIFECYCLE = "DRAFT"

#: What any claimed owner on a draft is worth: a typed opaque handle the caller
#: presented, never an authenticated identity, and never proof that anyone accepted
#: the role. Phase 3B, behind AP-3, is where a proven owner would enter.
CLAIMED_OWNER_ASSURANCE = "PRESENTED_UNPROVEN"

#: Maturity, stated once and machine-readable. Suitable for synthetic and demonstration
#: content only until the production identity and data-handling posture is separately
#: verified (owner ruling, phase 3A).
MATURITY = "REFERENCE_GRADE"
ENFORCEMENT_ENABLED = False
