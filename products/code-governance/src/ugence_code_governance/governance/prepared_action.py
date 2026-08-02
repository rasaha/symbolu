"""Product-owned immutable prepared action.

``PreparedMergeAction`` is the exact proposed action submitted to ActionGate for
shadow evaluation. **It is not an authorization** and it is deliberately NOT
named ``ExactChangeAuthorization``. It binds the exact artifact identity plus the
governance references (decision, CER) so ActionGate evaluates the precise action
that would land — nothing more is implied.

Its fingerprint changes whenever the head SHA, base SHA, or merge method changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional, Tuple

from ..fingerprints import domain_hash
from ..models.enums import MergeMethod

_DOMAIN = "prepared_merge_action.v1"


@dataclass(frozen=True)
class PreparedMergeAction:
    """The exact proposed merge action. Not authorization; input to ActionGate."""

    tenant_id: str
    repository: str
    pull_request_number: int
    base_sha: str
    head_sha: str
    merge_method: MergeMethod
    target_branch: str
    change_fingerprint: str
    decision_record_id: str
    cer_id: str
    cer_content_hash: str
    policy_refs: Tuple[str, ...]
    expiry: Optional[datetime] = None
    expected_tree_sha: Optional[str] = None

    @property
    def requested_parameters(self) -> Mapping[str, str]:
        """The exact SHA/merge parameter VALUES carried to ActionGate.

        Values (specific SHAs, merge method) live here and in the product
        envelope — never misrepresented as CER parameter-name fields.
        """
        params = {
            "repository": self.repository,
            "pull_request_number": str(self.pull_request_number),
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "merge_method": self.merge_method.value,
            "target_branch": self.target_branch,
        }
        if self.expected_tree_sha:
            params["expected_tree_sha"] = self.expected_tree_sha
        return params

    @property
    def fingerprint(self) -> str:
        """Content-derived fingerprint of the exact artifact that would land.

        Derived only from the exact-artifact identity + policy context, so it is
        deterministic across runs (replay-stable) and changes with head/base/merge
        method. The DecisionRecord and CER references are *bound as fields* on this
        record (for chain linkage), but they are service-minted provenance ids —
        they are deliberately NOT part of the identity fingerprint, which must
        remain content-derived.
        """
        return domain_hash(
            _DOMAIN,
            {
                "tenant_id": self.tenant_id,
                "repository": self.repository,
                "pull_request_number": self.pull_request_number,
                "base_sha": self.base_sha,
                "head_sha": self.head_sha,
                "merge_method": self.merge_method.value,
                "target_branch": self.target_branch,
                "change_fingerprint": self.change_fingerprint,
                "expected_tree_sha": self.expected_tree_sha,
                "policy_refs": sorted(self.policy_refs),
            },
        )


__all__ = ["PreparedMergeAction"]
