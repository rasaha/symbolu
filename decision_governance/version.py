"""Decision Governance Middleware — version & compatibility policy.

The kernel is versioned as an **independently released middleware product**.
Consuming domains and applications build against the public API surface
(``decision_governance.api``) and rely on the guarantees below.

Semantic versioning — ``MAJOR.MINOR.PATCH``:

* **PATCH** (``x.y.Z``) — backward-compatible corrections with **no** change to the
  public API surface, lifecycle semantics, serialization, hashes, or audit values.
  Bug fixes and documentation only.
* **MINOR** (``x.Y.0``) — backward-compatible **additive** changes: new contracts,
  new services, new optional fields (with defaults), new enum *members appended*,
  new ports. Existing serialization, hashes, lifecycle transitions, and audit
  event values are unchanged. Existing consumers keep working unmodified.
* **MAJOR** (``X.0.0``) — a change that can break an existing consumer. Every one
  of the following is **MAJOR** and must be intentional and documented:

  =========================  ==============================================
  Change class               Why it is MAJOR
  =========================  ==============================================
  behavioral change          an operation's outcome/validation changes
  lifecycle change           allowed transitions or terminal states change
  serialization change       a model's serialized shape/field name changes
  hash change                ``canonical_hash`` / ``content_hash`` changes
  port change                a port Protocol signature changes
  removal / rename           any public symbol removed or renamed
  enum value change          an existing enum member value renamed/removed
  =========================  ==============================================

Additive enum *members* are MINOR; changing or removing an existing member value
is MAJOR (it breaks pattern matches and persisted audit/records).

This file is the single source of truth for the kernel version. The compatibility
class constants below are used by the stabilization test-suite to classify and
guard changes.
"""

from __future__ import annotations

from enum import Enum

#: The kernel's current version. ``1.0.0`` marks the stabilization freeze: the
#: public API, lifecycle, serialization, hashes, and audit vocabulary are now
#: contractual. (Two independent domains already depend on this surface.)
__version__ = "1.0.0"

VERSION = __version__
VERSION_INFO: tuple[int, int, int] = tuple(int(p) for p in __version__.split("."))  # type: ignore[assignment]


class CompatibilityImpact(str, Enum):
    """The release class a kind of change requires."""

    PATCH = "PATCH"      # backward-compatible corrections, no surface change
    MINOR = "MINOR"      # backward-compatible additive change
    MAJOR = "MAJOR"      # potentially breaking change


#: Classification of change categories → the minimum release class they require.
CHANGE_CLASSIFICATION: dict[str, CompatibilityImpact] = {
    "additive_contract": CompatibilityImpact.MINOR,
    "additive_enum_member": CompatibilityImpact.MINOR,
    "additive_service": CompatibilityImpact.MINOR,
    "additive_optional_field": CompatibilityImpact.MINOR,
    "additive_port": CompatibilityImpact.MINOR,
    "bug_fix_no_surface_change": CompatibilityImpact.PATCH,
    "documentation": CompatibilityImpact.PATCH,
    "behavioral_change": CompatibilityImpact.MAJOR,
    "lifecycle_change": CompatibilityImpact.MAJOR,
    "serialization_change": CompatibilityImpact.MAJOR,
    "hash_change": CompatibilityImpact.MAJOR,
    "port_change": CompatibilityImpact.MAJOR,
    "removal_or_rename": CompatibilityImpact.MAJOR,
    "enum_value_change": CompatibilityImpact.MAJOR,
}


def classify_change(category: str) -> CompatibilityImpact:
    """Return the release class a change category requires."""
    return CHANGE_CLASSIFICATION[category]
