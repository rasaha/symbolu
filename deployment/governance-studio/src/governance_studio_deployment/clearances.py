"""Clearance export (ADR_UGENCE_CLEARANCE_EXPORT_SCOPING.md CE-7): the seeded
received-clearance source.

    THIS ROOT READS PINNED FIXTURE FILES AND HANDS THEM ON. IT EVALUATES NO
    CLEARANCE, WRITES NOTHING, AND GRANTS NOTHING.

CE-7 rules that the deployment seeds a receipt store from pinned fixtures **inside
the existing ``SYNTHETIC_DEMONSTRATION_ONLY`` manifest discipline rather than beside
it**. That is why the fixtures live in the scenario directories under
``UGENCE_STUDIO_SCENARIOS_ROOT`` and are named ``clearance_receipts.json``: every
file in a scenario directory is already covered by ``hash_scenario``, so a receipt
edited after the manifest was pinned fails ``verify_bundle`` exactly as an edited
scenario does. No second manifest, no second hash, no second fail-closed path.

**Seeding is composition, not a route** (§13.3). This module is called once while the
application is being built, from files that shipped in the image. Nothing at runtime
can add a receipt: the source below has two reads and no write, matching the port,
and no v2 operation accepts a receipt.

**What a seeded receipt is.** Demonstration data. It exercises the export path and
the verifier and is evidence about nothing else — no authority granted it, it confers
no approval, and it says nothing about whether the platform can produce a real
clearance, which per ADR §11.2 it cannot. Every artifact built from one carries
``SYNTHETIC_DEMONSTRATION_ONLY``, and the export package refuses to build one that
does not.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Sequence

from ugence_clearance_export import (
    ClearanceReceiptBody,
    ContractViolation,
    NotAReceivedClearance,
    receipt_body_from_dict,
)

from .config import DeploymentConfigError

__all__ = [
    "RECEIPT_FIXTURE_FILENAME",
    "SEEDED_CLEARANCE_CLASSIFICATION",
    "SeededClearanceSource",
    "open_received_clearances",
]

#: The fixture file a scenario directory may carry. Inside the scenario, so the
#: existing manifest hash covers it.
RECEIPT_FIXTURE_FILENAME = "clearance_receipts.json"

#: Stated here as well as in the artifact, so a reader of the deployment code sees
#: it without opening the export package.
SEEDED_CLEARANCE_CLASSIFICATION = "SYNTHETIC_DEMONSTRATION_ONLY"


class SeededClearanceSource:
    """Read-only access to the receipts this deployment shipped with.

    Implements ``ugence_clearance_export.ReceivedClearanceSource``: two reads, no
    write. The mapping is built once at composition time and never mutated, so there
    is no method here — public or private — through which a running deployment could
    come to hold a clearance it was not shipped.
    """

    def __init__(self, receipts: Sequence[ClearanceReceiptBody], *, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self._by_id: Dict[str, ClearanceReceiptBody] = {
            receipt.receipt_id: receipt for receipt in receipts
        }

    def read_receipt(
        self, *, tenant_id: str, receipt_id: str
    ) -> Optional[ClearanceReceiptBody]:
        found = self._by_id.get(receipt_id)
        if found is None or found.tenant_id != tenant_id:
            return None
        return found

    def list_receipt_ids(self, *, tenant_id: str) -> List[str]:
        return sorted(i for i, r in self._by_id.items() if r.tenant_id == tenant_id)

    def __len__(self) -> int:
        return len(self._by_id)


def _load_fixture(path: str, *, tenant_id: str) -> List[ClearanceReceiptBody]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise DeploymentConfigError(
            f"the seeded clearance fixture {path} could not be read: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("data_classification") != (
            SEEDED_CLEARANCE_CLASSIFICATION):
        raise DeploymentConfigError(
            f"{path} must declare data_classification "
            f"{SEEDED_CLEARANCE_CLASSIFICATION}: a seeded clearance is demonstration "
            "data and the fixture says so before anything reads it")

    receipts: List[ClearanceReceiptBody] = []
    for entry in payload.get("receipts", []):
        try:
            receipt = receipt_body_from_dict(entry)
        except (ContractViolation, NotAReceivedClearance, KeyError, TypeError,
                ValueError) as exc:
            raise DeploymentConfigError(
                f"{path} carries an entry that is not a clearance receipt: {exc}"
            ) from exc
        if receipt.tenant_id != tenant_id:
            # Skipped, not rebound. The tenant is part of what the receipt says and
            # part of its fingerprint: rewriting it here would forge a clearance for
            # a tenant nobody evaluated one for. A deployment whose tenant matches no
            # shipped receipt simply holds none, and the studio says exactly that.
            continue
        receipts.append(receipt)
    return receipts


def open_received_clearances(
    scenarios_root: str, *, tenant_id: str
) -> Optional[SeededClearanceSource]:
    """The seeded source, or ``None`` when no scenario ships a fixture.

    ``None`` is deliberate rather than an empty source: absent a fixture the studio
    reports the capability as unavailable and names the gap, instead of answering as
    though the tenant simply held no clearances (CE-5's read has to tell those two
    apart).

    Called only after ``synthetic.enforce`` has verified the bundle, so every file
    read here is one the pinned manifest already covered.
    """
    if not scenarios_root or not os.path.isdir(scenarios_root):
        return None

    receipts: List[ClearanceReceiptBody] = []
    for name in sorted(os.listdir(scenarios_root)):
        scenario = os.path.join(scenarios_root, name)
        if not os.path.isdir(scenario) or name.startswith("__"):
            continue
        fixture = os.path.join(scenario, RECEIPT_FIXTURE_FILENAME)
        if os.path.isfile(fixture):
            receipts.extend(_load_fixture(fixture, tenant_id=tenant_id))

    if not receipts:
        return None
    return SeededClearanceSource(receipts, tenant_id=tenant_id)
