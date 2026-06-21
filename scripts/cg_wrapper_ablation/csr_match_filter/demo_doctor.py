#!/usr/bin/env python3
"""demo_doctor.py — end-to-end demo of the C×R×S MATCH-filter wrapper.

Shows that for "Is a doctor a healer or an authority figure?":
  doctor → medicine/healing = primary
  doctor → authority         = secondary or weak
  doctor → fruit/commerce    = reject (S firewall)
and that the prompt frame leads with medicine/healing, authority secondary, fruit absent.

No LLM required (Mode A scoring + framing). Run:
  python scripts/cg_wrapper_ablation/csr_match_filter/demo_doctor.py
"""

import sys
from pathlib import Path

# allow `python demo_doctor.py` and `python -m ...csr_match_filter.demo_doctor`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import (  # noqa: E402
    CSRMatchFilterWrapper,
    build_prompt_frame,
    compute_12d_profile,
    dominant_layers,
    make_demo_adapter,
)


def main() -> int:
    query = "Is a doctor more of a healer or an authority figure?"
    terms = ["doctor"]
    domains = ["medicine", "care", "authority", "law", "service", "commerce", "fruit"]

    # canonical example uses the DEMO fixtures (curated glosses + curated S) for clean numbers;
    # see demo_unknown_term.py for the scalable embedding path with no curation.
    wrapper = CSRMatchFilterWrapper(llm=None, domains=domains, adapter=make_demo_adapter())
    trace = wrapper.analyze(query, terms=terms)

    vec = compute_12d_profile("doctor")
    print(f"Query: {query}")
    print(f"Term 'doctor' 12D realization profile (NOT meaning) — dominant: {dominant_layers(vec)}\n")

    print(f"{'domain':<12}{'C':>7}{'R':>7}{'S':>7}{'MATCH':>8}   decision")
    print("-" * 56)
    for s in sorted(trace.scores, key=lambda x: -x.match):
        print(f"{s.domain:<12}{s.C:>7.3f}{s.R:>7.3f}{s.S:>7.3f}{s.match:>8.3f}   {s.decision}")

    # group-level R trace for the winning domain (which family of structure is active?)
    med = next(s for s in trace.scores if s.domain == "medicine")
    if med.r_groups:
        print("\nGroup-aware R trace — doctor vs medicine "
              f"(R={med.r_groups['R']}, reward={med.r_groups['reward']}, "
              f"penalty={med.r_groups['penalty']}):")
        for g, gd in med.r_groups["groups"].items():
            print(f"  {g:<10} term={gd['term_emphasis']:.2f} domain={gd['domain_emphasis']:.2f} "
                  f"w={gd['weight']:.2f} match={gd['match']:.2f} -> {gd['contribution']:.3f}")

    print("\nFrame:")
    print(f"  primary   = {trace.primary_domains}")
    print(f"  secondary = {trace.secondary_domains}")
    print(f"  rejected  = {trace.rejected_domains}")
    print(f"  retrieval-kept (hook 1) = {wrapper.filtered_domains(trace)}")

    print("\n" + "=" * 56 + "\nPrompt frame handed to the LLM:\n" + "=" * 56)
    print(build_prompt_frame(trace))

    # sanity narration (the demo asserts the conceptual outcome, not exact numbers)
    assert "medicine" in trace.primary_domains, "expected medicine as primary"
    assert "fruit" in trace.rejected_domains, "expected fruit rejected by the S firewall"
    print("OK: medicine is primary; fruit is rejected by the S firewall.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
