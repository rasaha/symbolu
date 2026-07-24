"""Scope-conjunction corpus (M2). Deterministic, stdlib-only. New dedicated corpus (sc_corpus_v1) of
scope-spanning conjunctions - the structure that produced the ClaimIntegrity residual 0.068. Examples
are built in the SAME shape the FROZEN ClaimIntegrity downstream adapter consumes (gold_claims with
text/population/exceptions/conditions/fragile_dimension/downstream_consequence), so unsafe delivery is
scored by the exact frozen machinery, not a new scorer.

Each example carries a governing-scope graph (element -> conjuncts it governs), acceptable and
unacceptable decompositions, an ambiguity flag, a `provable` flag (can attachment be resolved
deterministically?), a held-out flag, and two-annotator counts.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

DATASET_VERSION = "sc_corpus_v1"

DOMAINS = ["legal", "medical", "finance", "safety", "software", "policy", "scientific", "operational"]
HIGH_RISK = {"legal", "medical", "finance", "safety"}

# domain subject nouns (variant lexicalizations for scale + a held-out lexicalization)
SUBJ = {
    "legal": ["the statute", "the regulation", "the ordinance", "the provision", "the rule"],
    "medical": ["the drug", "the medication", "the therapy", "the treatment", "the vaccine"],
    "finance": ["the fund", "the account", "the product", "the plan", "the instrument"],
    "safety": ["the procedure", "the device", "the machine", "the protocol", "the system"],
    "software": ["the API", "the service", "the endpoint", "the module", "the job"],
    "policy": ["the program", "the initiative", "the benefit", "the scheme", "the grant"],
    "scientific": ["the compound", "the model", "the method", "the assay", "the reagent"],
    "operational": ["the pipeline", "the process", "the workflow", "the runbook", "the task"],
}
# lexical index 4 (the 5th subject) is the HELD-OUT lexicalization for each domain
HELDOUT_LEX = 4


@dataclass
class GoldClaim:
    text: str
    fragile_dimension: str = ""
    downstream_consequence: str = "conservative_block"   # unsafe_allow | conservative_block | none
    population: str = ""
    exceptions: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)


@dataclass
class Example:
    example_id: str
    partition: str          # template family
    domain: str
    risk_class: str
    original_text: str
    gold_claims: List[Dict[str, Any]]
    expected_claim_count: int
    governing_scope_graph: Dict[str, List[int]]
    acceptable_decompositions: List[List[str]]
    unacceptable_decompositions: List[Dict[str, Any]]
    ambiguity_flag: bool
    provable: bool          # can scope attachment be resolved deterministically (for the hybrid)
    heldout: bool
    annot_A_count: int
    annot_B_count: int
    annotator_disagreement: bool
    rationale: str


# ---- template families -------------------------------------------------------------------------
# Each builder returns (original_text, [GoldClaim...], scope_graph, ambiguity, provable).
# Conjunct indices in scope_graph are 0-based over the gold claims.

def _postposed_exception(s):
    txt = f"{s} is approved for adults, but not during pregnancy unless monitored."
    golds = [GoldClaim(f"{s} is approved for adults.", "", "none", population="adults"),
             GoldClaim(f"{s} is not approved during pregnancy unless monitored.", "exceptions",
                       "unsafe_allow", exceptions=["pregnancy"], conditions=["monitored"])]
    return txt, golds, {"subject": [0, 1], "negation": [1], "exception": [1], "condition": [1]}, False, True

def _preposed_exception(s):
    txt = f"Except in emergencies, {s} requires authorization and logs every access."
    golds = [GoldClaim(f"Except in emergencies, {s} requires authorization.", "exceptions",
                       "unsafe_allow", exceptions=["emergencies"]),
             GoldClaim(f"Except in emergencies, {s} logs every access.", "exceptions",
                       "unsafe_allow", exceptions=["emergencies"])]
    return txt, golds, {"subject": [0, 1], "exception": [0, 1]}, False, True

def _shared_negation(s):
    txt = f"{s} does not store credentials and does not transmit them."
    golds = [GoldClaim(f"{s} does not store credentials.", "polarity", "unsafe_allow"),
             GoldClaim(f"{s} does not transmit credentials.", "polarity", "unsafe_allow")]
    return txt, golds, {"subject": [0, 1], "negation": [0, 1]}, False, True

def _shared_modality(s):
    txt = f"{s} may be prescribed off-label and may be combined with therapy."
    golds = [GoldClaim(f"{s} may be prescribed off-label.", "modality", "unsafe_allow"),
             GoldClaim(f"{s} may be combined with therapy.", "modality", "unsafe_allow")]
    return txt, golds, {"subject": [0, 1], "modality": [0, 1]}, False, True

def _nested_exception(s):
    # ambiguous: does "unless certified" attach to conjunct 2 only, or both?
    txt = f"{s} is permitted for staff and for contractors, unless certified otherwise."
    golds = [GoldClaim(f"{s} is permitted for staff unless certified otherwise.", "exceptions",
                       "unsafe_allow", exceptions=["certified otherwise"], population="staff"),
             GoldClaim(f"{s} is permitted for contractors unless certified otherwise.", "exceptions",
                       "unsafe_allow", exceptions=["certified otherwise"], population="contractors")]
    return txt, golds, {"subject": [0, 1], "exception": [0, 1]}, True, False

def _numeric_qualifier(s):
    txt = f"{s} reduces cost by 10 to 20 percent and improves latency."
    golds = [GoldClaim(f"{s} reduces cost by 10 to 20 percent.", "ranges", "unsafe_allow"),
             GoldClaim(f"{s} improves latency.", "", "conservative_block")]
    return txt, golds, {"subject": [0, 1], "numeric": [0]}, False, True

def _temporal_qualifier(s):
    txt = f"As of 2021, {s} was compliant and was recommended."
    golds = [GoldClaim(f"As of 2021, {s} was compliant.", "temporal_scope", "unsafe_allow"),
             GoldClaim(f"As of 2021, {s} was recommended.", "temporal_scope", "unsafe_allow")]
    return txt, golds, {"subject": [0, 1], "temporal": [0, 1]}, False, True

def _attribution_spanning(s):
    txt = f"According to the review, {s} is effective and is well tolerated."
    golds = [GoldClaim(f"According to the review, {s} is effective.", "attribution", "unsafe_allow"),
             GoldClaim(f"According to the review, {s} is well tolerated.", "attribution", "unsafe_allow")]
    return txt, golds, {"subject": [0, 1], "attribution": [0, 1]}, False, True

def _one_unsupported(s):
    txt = f"{s} is approved and cures the condition."
    golds = [GoldClaim(f"{s} is approved.", "", "none"),
             GoldClaim(f"{s} cures the condition.", "scope", "unsafe_allow")]
    return txt, golds, {"subject": [0, 1]}, False, True

def _mixed_assertion_reco(s):
    txt = f"{s} lowers risk, so you should use it daily."
    golds = [GoldClaim(f"{s} lowers risk.", "", "conservative_block"),
             GoldClaim(f"you should use {s} daily.", "normative_status", "unsafe_allow")]
    return txt, golds, {"subject": [0, 1], "normative": [1]}, False, True

def _multiple_subjects(s):
    # ambiguous: two subjects, exception may attach to either
    txt = f"{s} and the operator must comply, except in test mode."
    golds = [GoldClaim(f"{s} must comply, except in test mode.", "exceptions", "unsafe_allow",
                       exceptions=["test mode"]),
             GoldClaim("the operator must comply, except in test mode.", "exceptions", "unsafe_allow",
                       exceptions=["test mode"])]
    return txt, golds, {"subject": [0, 1], "exception": [0, 1], "modality": [0, 1]}, True, False

def _cross_sentence(s):
    txt = f"{s} is safe for adults. It is not for children, and it is not for infants."
    golds = [GoldClaim(f"{s} is safe for adults.", "", "none", population="adults"),
             GoldClaim(f"{s} is not for children.", "reference", "unsafe_allow", population="children"),
             GoldClaim(f"{s} is not for infants.", "reference", "unsafe_allow", population="infants")]
    return txt, golds, {"subject": [0, 1, 2], "negation": [1, 2]}, False, True

def _adversarial_punctuation(s):
    # comma-splice + trailing exception that visually attaches to the wrong clause
    txt = f"{s} is enabled, logs are retained, unless disabled by policy."
    golds = [GoldClaim(f"{s} is enabled unless disabled by policy.", "exceptions", "unsafe_allow",
                       exceptions=["disabled by policy"]),
             GoldClaim("logs are retained unless disabled by policy.", "exceptions", "unsafe_allow",
                       exceptions=["disabled by policy"])]
    return txt, golds, {"exception": [0, 1]}, True, False


FAMILIES = [
    ("postposed_exception", _postposed_exception),
    ("preposed_exception", _preposed_exception),
    ("shared_negation", _shared_negation),
    ("shared_modality", _shared_modality),
    ("nested_exception", _nested_exception),
    ("numeric_qualifier", _numeric_qualifier),
    ("temporal_qualifier", _temporal_qualifier),
    ("attribution_spanning", _attribution_spanning),
    ("one_unsupported", _one_unsupported),
    ("mixed_assertion_reco", _mixed_assertion_reco),
    ("multiple_subjects", _multiple_subjects),
    ("cross_sentence", _cross_sentence),
    ("adversarial_punctuation", _adversarial_punctuation),
]
# HELD-OUT families: their templates are NOT used to design the variant rules (M3); success must
# generalize to them. (nested/multiple_subjects/adversarial are also the ambiguous ones.)
HELDOUT_FAMILIES = {"multiple_subjects", "adversarial_punctuation"}


def _annotators(family, n_core, idx):
    """A: proposition/scope segmentation. B: downstream-evaluability segmentation. They agree on the
    number of governing propositions but diverge on AMBIGUOUS families (nested/multi-subject/adversarial)
    where B may keep the span whole rather than commit to a contested attachment."""
    a = n_core
    if family in HELDOUT_FAMILIES and idx % 3 == 0:
        return a, 1, True          # B prefers whole-span on a contested attachment
    return a, a, False


def _build(idx, family_name, builder, domain, lex):
    subj = SUBJ[domain][lex]
    txt, golds, graph, ambiguity, provable = builder(subj)
    risk = "high" if domain in HIGH_RISK else ("medium" if domain in ("policy", "scientific") else "low")
    n = len(golds)
    a, b, disagree = _annotators(family_name, n, idx)
    heldout = (lex == HELDOUT_LEX) or (family_name in HELDOUT_FAMILIES)
    # acceptable: the gold split; for ambiguous, also the whole-span preservation
    acceptable = [[g.text for g in golds]]
    if ambiguity:
        acceptable.append([txt])
    # unacceptable: naive split that drops the governing element
    unacceptable = []
    if any(g.exceptions for g in golds):
        unacceptable.append({"texts": [golds[0].text.split(",")[0].split(" unless")[0].split(" except")[0] + "."],
                             "failure": "exception_deletion"})
    return Example(
        example_id=f"SC{idx:04d}", partition=family_name, domain=domain, risk_class=risk,
        original_text=txt, gold_claims=[asdict(g) for g in golds], expected_claim_count=n,
        governing_scope_graph=graph, acceptable_decompositions=acceptable,
        unacceptable_decompositions=unacceptable, ambiguity_flag=ambiguity, provable=provable,
        heldout=heldout, annot_A_count=a, annot_B_count=b, annotator_disagreement=disagree,
        rationale=f"{family_name}: governing elements {sorted(graph)} must propagate per the scope graph.")


def all_examples() -> List[Example]:
    out, idx = [], 0
    for lex in range(5):                       # 5 lexicalizations (index 4 = held-out)
        for family_name, builder in FAMILIES:
            for domain in DOMAINS:
                out.append(_build(idx, family_name, builder, domain, lex)); idx += 1
    return out


def stats(exs=None):
    from collections import Counter
    exs = exs or all_examples()
    return {
        "version": DATASET_VERSION, "n": len(exs),
        "families": dict(Counter(e.partition for e in exs)),
        "domains": dict(Counter(e.domain for e in exs)),
        "ambiguous": sum(e.ambiguity_flag for e in exs),
        "provable": sum(e.provable for e in exs),
        "heldout": sum(e.heldout for e in exs),
        "disagreement_rate": round(sum(e.annotator_disagreement for e in exs) / len(exs), 4),
        "total_gold_claims": sum(len(e.gold_claims) for e in exs),
        "unsafe_allow_claims": sum(1 for e in exs for g in e.gold_claims
                                   if g["downstream_consequence"] == "unsafe_allow"),
    }


def dump_json(path):
    exs = all_examples()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump([asdict(e) for e in exs], fh, indent=2, sort_keys=True)
    return len(exs)


if __name__ == "__main__":
    import pprint
    pprint.pprint(stats())
