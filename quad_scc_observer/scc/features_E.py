"""Hypothesis E — evidence support features (closed-world, read-only).

Evidence is ONLY the supplied MQAR context (no external retrieval). We measure whether the claim
(k_q -> v_pred) is supported by a symbolic lookup of the context:

  E_adjacency_support   : the context contains a key position with token k_q whose bound value == v_pred
                          (i.e. the claimed binding is present in the evidence)          {0,1}
  E_value_supported     : v_pred is some context value token                              {0,1}
  E_key_supported       : k_q is a context key token                                      {0,1}
  E_retrieved_binding   : the attention-retrieved key IS the query key AND its bound value == v_pred {0,1}
  E_support_count       : number of context bindings (k_q -> v_pred) present              (int)

NOTE (documented finding, not a bug): in a closed world with machine-checkable evidence,
`E_adjacency_support` reconstructs the true binding, so it is a near-ORACLE for correctness. This
is exactly why E and the evidence-grounding baseline coincide: E is grounded verification, not an
intrinsic-coherence signal. The open-world case (below) would require external grounding and is
deliberately NOT implemented.

Open-world evidence would require an external corpus / retrieval to verify claims against
real-world facts; that is a grounded-verification problem, categorically different from intrinsic
coherence, and substituting retrieval here would conflate the two. We therefore restrict E to the
closed-world (context-only) regime and treat the open-world case as out of scope by design.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from . import _paths  # noqa: F401

FEATURES = ["E_adjacency_support", "E_value_supported", "E_key_supported",
            "E_retrieved_binding", "E_support_count"]


def compute(records: List[Dict], rec: Dict, model) -> Dict[str, np.ndarray]:
    adj, valsup, keysup, retbind, cnt = [], [], [], [], []
    for r in records:
        supports = [1 for kp in r["kq_keypositions"] if r["val_for_keypos"].get(kp) == r["v_pred"]]
        adj.append(1.0 if supports else 0.0)
        cnt.append(float(len(supports)))
        valsup.append(1.0 if r["v_pred"] in r["value_token_set"] else 0.0)
        keysup.append(1.0 if r["k_q"] in r["key_token_set"] else 0.0)
        rk_tok = r["key_tokens"][r["key_positions"].index(r["retrieved_kp"])] \
            if r["retrieved_kp"] in r["key_positions"] else -1
        retbind.append(1.0 if (rk_tok == r["k_q"] and r["v_retrieved"] == r["v_pred"]) else 0.0)
    return {
        "E_adjacency_support": np.array(adj),
        "E_value_supported": np.array(valsup),
        "E_key_supported": np.array(keysup),
        "E_retrieved_binding": np.array(retbind),
        "E_support_count": np.array(cnt),
    }
