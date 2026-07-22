"""Hypothesis R — relational preservation features (read-only, structural).

Whether the claim preserves the entities/relations/structure of the context:

  R_key_present        : the query key exists as a context key (entity preservation)   {0,1}
  R_pred_is_ctx_value  : the predicted value is a real context value (not a spurious token) {0,1}
  R_pred_eq_retrieved  : the predicted value equals the value bound to the attention-retrieved key
                         (relation consistency between the logit head and the retrieval)  {0,1}
  R_key_unique         : the query key occurs exactly once as a context key (no relational ambiguity) {0,1}
  R_num_candidates     : number of candidate keys (relational load / structural difficulty)

These are progressively stronger relational checks; R_pred_eq_retrieved is the strongest (it tests
internal relational consistency of the two retrieval pathways). None use the ground-truth label.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from . import _paths  # noqa: F401

FEATURES = ["R_key_present", "R_pred_is_ctx_value", "R_pred_eq_retrieved",
            "R_key_unique", "R_num_candidates"]


def compute(records: List[Dict], rec: Dict, model) -> Dict[str, np.ndarray]:
    key_present, pred_is_val, pred_eq_retr, key_unique, ncand = [], [], [], [], []
    for r in records:
        key_present.append(1.0 if r["k_q"] in r["key_token_set"] else 0.0)
        pred_is_val.append(1.0 if r["v_pred"] in r["value_token_set"] else 0.0)
        pred_eq_retr.append(1.0 if r["v_pred"] == r["v_retrieved"] else 0.0)
        key_unique.append(1.0 if len(r["kq_keypositions"]) == 1 else 0.0)
        ncand.append(float(r["num_candidates"]))
    return {
        "R_key_present": np.array(key_present),
        "R_pred_is_ctx_value": np.array(pred_is_val),
        "R_pred_eq_retrieved": np.array(pred_eq_retr),
        "R_key_unique": np.array(key_unique),
        "R_num_candidates": np.array(ncand),
    }
