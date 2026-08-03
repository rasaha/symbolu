#!/usr/bin/env python3
"""Product-neutral, dependency-free demo of Context Minimization.

Shows the four behaviours a caller relies on, using a tiny DETERMINISTIC fake
oracle (no real model, no ActionGate):

  1. structural duplicate removal (protected retained),
  2. oracle-verified safe removal,
  3. changed-equivalence restoration,
  4. fail-closed fallback on an oracle exception.

Run:  python examples/standalone_demo.py
"""

from __future__ import annotations

from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    OracleEvaluation,
    minimize_context,
    structural_minimize,
)


class KeywordOracle:
    """Equivalence = the set of 'critical' keywords present. Opaque to the core."""

    KEYWORDS = ("deploy", "backup", "approval")

    def evaluate(self, context, *, evaluation_time=None):
        present = sorted(
            {k for u in context.units for k in self.KEYWORDS if k in u.text.lower()}
        )
        return OracleEvaluation(
            equivalence_key="|".join(present),
            oracle_id="demo-keyword-oracle",
            contract_version="1.0",
            correlation_id=context.correlation_id,
        )


class RaisingOracle:
    def evaluate(self, context, *, evaluation_time=None):
        raise RuntimeError("simulated oracle outage")


def _ctx() -> Context:
    return Context(
        id="demo",
        correlation_id="corr-1",
        units=(
            ContextUnit(id="p", text="deploy service X to prod",
                        source_type="state_fact", protected=True),
            ContextUnit(id="dup", text="deploy service X to prod", source_type="state_fact"),
            ContextUnit(id="crit", text="backup verified restorable", source_type="state_fact"),
            ContextUnit(id="fill", text="weekly sprint planning chatter", source_type="log_event"),
        ),
    )


def main() -> None:
    ctx = _ctx()

    print("1) structural minimize (no oracle):")
    s = structural_minimize(ctx, protected_ids=["p"])
    print("   surviving:", s.surviving_ids, "removed:", s.removed_ids)

    print("2) oracle-verified minimize (drop filler, keep critical + protected):")
    o = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.5,
                         protected_ids=["p"], evaluation_time=1.0)
    print("   surviving:", o.surviving_ids, "status:", o.equivalence_status.value,
          "reduction:", round(o.achieved_reduction, 3))

    print("3) changed-equivalence restoration (a critical filler-hinted span is restored):")
    ctx2 = Context(id="demo2", correlation_id="c", units=(
        ContextUnit(id="keep", text="unrelated note", source_type="state_fact"),
        ContextUnit(id="c1", text="historical deploy record", source_type="log_event"),
    ))
    r = minimize_context(ctx2, oracle=KeywordOracle(), target_reduction=1.0, evaluation_time=1.0)
    print("   surviving:", r.surviving_ids, "restored:", r.restored_ids,
          "status:", r.equivalence_status.value)

    print("4) fail-closed fallback on oracle exception:")
    f = minimize_context(ctx, oracle=RaisingOracle(), target_reduction=0.5, evaluation_time=1.0)
    print("   surviving:", f.surviving_ids, "fell_back:", f.fell_back,
          "reasons:", f.reason_codes)


if __name__ == "__main__":
    main()
