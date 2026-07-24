"""ClaimIntegrity corpus generator (Phases 6-7). Deterministic, stdlib-only. Builds a NEW versioned
corpus (ci_corpus_v1) - prior final-evaluation corpora are NOT reused as the outcome dataset.

Design (mirrors the anti-circularity principle of the EvidenceAssurance track): each example carries a
TRUE latent decomposition (the gold claim units with all semantic dimensions) that gold is derived
from; a decomposition METHOD sees only OBSERVED text (original_text + context) and must recover it.
Gold is never generated from the ClaimIntegrity implementation.

Each gold claim marks its `fragile_dimension` - the one semantic field whose loss changes downstream
governance - and the `downstream_consequence` (does losing it flip delivery to unsafe-allow, or only
cause conservative blocking?). This is what the downstream-impact and error-propagation phases key on.

Partitions: SIMPLE_ATOMIC, QUALIFIED_COMPLEX, MULTI_CLAIM, CROSS_SENTENCE, ADVERSARIAL_SCOPE.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .taxonomy import CLAIM_TYPES, ATOMICITY_POLICY

DATASET_VERSION = "ci_corpus_v1"

DOMAINS = ["medical", "legal", "financial", "scientific", "cybersecurity", "software_engineering",
           "enterprise_policy", "public_policy", "ordinary_factual", "rapidly_changing",
           "recommendation", "high_risk_instruction", "mixed_factual_normative"]
HIGH_RISK = {"medical", "legal", "financial", "cybersecurity", "high_risk_instruction"}

PARTITIONS = ["SIMPLE_ATOMIC", "QUALIFIED_COMPLEX", "MULTI_CLAIM", "CROSS_SENTENCE",
              "ADVERSARIAL_SCOPE"]


@dataclass
class GoldClaim:
    text: str
    claim_type: str
    polarity: str = "affirmative"
    modality: str = "none"
    uncertainty: str = "none"
    quantifier: Optional[str] = None
    temporal_scope: str = ""
    population: str = ""
    jurisdiction: str = ""
    conditions: List[str] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    causal_direction: str = "none"
    numerical_values: List[str] = field(default_factory=list)
    units: List[str] = field(default_factory=list)
    ranges: List[str] = field(default_factory=list)
    attribution: str = "direct"
    attributed_source: str = ""
    evidence_status_language: str = ""
    citation_references: List[str] = field(default_factory=list)
    reference_links: Dict[str, str] = field(default_factory=dict)
    normative_status: str = "descriptive"
    rhetorical_status: str = "assertive"
    fragile_dimension: str = ""            # the field whose loss changes governance
    downstream_consequence: str = "conservative_block"   # unsafe_allow | conservative_block | none


@dataclass
class Example:
    example_id: str
    partition: str
    domain: str
    risk_class: str
    original_text: str
    context: str
    gold_claims: List[Dict[str, Any]]
    expected_claim_count: int
    acceptable_decompositions: List[List[str]]      # alternate valid groupings (lists of claim texts)
    unacceptable_decompositions: List[Dict[str, Any]]  # {texts, failure} known-drift variants
    downstream_evidence_consequence: str
    downstream_delivery_consequence: str
    annot_A_count: int
    annot_B_count: int
    annotator_disagreement: bool
    gold_disposition: str
    annotation_rationale: str


# ---- claim skeletons -----------------------------------------------------------------------------
# Each skeleton is a claim-bearing sentence with ONE load-bearing fragile dimension and the downstream
# consequence of losing it. `mk(domain)` fills domain-specific nouns. `drift` gives the naive-splitting
# / normalization variant that drops the fragile dimension and the failure type it exhibits.
#
# fields: key, type, sentence(with modifier), core(without modifier), fragile, consequence,
#         drift_failure, dims(extra gold dimensions)

# two semantically-equivalent subject phrasings per domain (variant 0 / variant 1). The alternate
# phrasing changes surface words only; gold semantics and the fragile dimension are identical.
_SUBJ = {
    "medical": ("the drug", "patients with renal impairment", "the EU"),
    "legal": ("the statute", "corporations", "California"),
    "financial": ("the fund", "retail investors", "the US"),
    "scientific": ("the compound", "the sampled cohort", ""),
    "cybersecurity": ("the exploit", "unpatched servers", ""),
    "software_engineering": ("the API", "clients on v2", ""),
    "enterprise_policy": ("the policy", "contractors", "the company"),
    "public_policy": ("the program", "low-income households", "the state"),
    "ordinary_factual": ("the lake", "the region", ""),
    "rapidly_changing": ("the release", "current users", ""),
    "recommendation": ("the treatment", "adults", ""),
    "high_risk_instruction": ("the procedure", "operators", ""),
    "mixed_factual_normative": ("the framework", "teams", ""),
}
_SUBJ_ALT = {
    "medical": ("the medication", "renally impaired patients", "the EU"),
    "legal": ("the regulation", "firms", "California"),
    "financial": ("the vehicle", "individual investors", "the US"),
    "scientific": ("the substance", "the study cohort", ""),
    "cybersecurity": ("the vulnerability", "unpatched hosts", ""),
    "software_engineering": ("the endpoint", "v2 clients", ""),
    "enterprise_policy": ("the rule", "external contractors", "the company"),
    "public_policy": ("the initiative", "low-income families", "the state"),
    "ordinary_factual": ("the reservoir", "the area", ""),
    "rapidly_changing": ("the build", "existing users", ""),
    "recommendation": ("the therapy", "adult patients", ""),
    "high_risk_instruction": ("the operation", "technicians", ""),
    "mixed_factual_normative": ("the model", "working groups", ""),
}

SKELETONS = [
    # key, type, template(with fragile), template(core-only), fragile_dim, consequence, drift_failure
    ("qualified", "uncertain_factual",
     "{subj} generally reduces risk in {pop}.", "{subj} reduces risk in {pop}.",
     "uncertainty", "unsafe_allow", "qualifier_deletion"),
    ("negated", "negated",
     "{subj} does not prevent infection in {pop}.", "{subj} prevents infection in {pop}.",
     "polarity", "unsafe_allow", "negation_loss"),
    ("modal", "permission",
     "{subj} may be used in {pop} under supervision.", "{subj} is used in {pop}.",
     "modality", "unsafe_allow", "possibility_to_certainty"),
    ("conditional", "conditional",
     "If prior therapy failed, {subj} is indicated for {pop}.", "{subj} is indicated for {pop}.",
     "conditions", "unsafe_allow", "conditional_to_unconditional"),
    ("exception", "exception_bearing",
     "{subj} is approved for {pop}, except during pregnancy.", "{subj} is approved for {pop}.",
     "exceptions", "unsafe_allow", "exception_deletion"),
    ("population", "population_specific",
     "{subj} is effective in {pop}.", "{subj} is effective.",
     "population", "unsafe_allow", "population_broadening"),
    ("temporal", "temporal",
     "As of 2021, {subj} was the recommended option for {pop}.",
     "{subj} is the recommended option for {pop}.",
     "temporal_scope", "unsafe_allow", "stale_present_normalization"),
    ("jurisdiction", "jurisdictional",
     "In {juris}, {subj} requires prior authorization for {pop}.",
     "{subj} requires prior authorization for {pop}.",
     "jurisdiction", "unsafe_allow", "jurisdiction_loss"),
    ("numeric", "numerical",
     "{subj} lowers the metric by 10 to 20 percent in {pop}.",
     "{subj} lowers the metric by 15 percent in {pop}.",
     "ranges", "unsafe_allow", "range_to_point"),
    ("causal", "correlational",
     "{subj} is associated with better outcomes in {pop}.",
     "{subj} causes better outcomes in {pop}.",
     "causal_direction", "unsafe_allow", "correlation_to_causation"),
    ("attributed", "attributed_factual",
     "According to one review, {subj} improves outcomes in {pop}.",
     "{subj} improves outcomes in {pop}.",
     "attribution", "unsafe_allow", "attributed_to_direct"),
    ("evidence_status", "evidentiary_status",
     "There is no evidence that {subj} harms {pop}.", "{subj} is safe for {pop}.",
     "evidence_status_language", "unsafe_allow", "evidence_status_loss"),
    ("recommendation", "recommendation",
     "{subj} should be considered for {pop}.", "{subj} is used for {pop}.",
     "normative_status", "conservative_block", "recommendation_to_fact"),
]


def _fill(tmpl: str, subj: str, pop: str, juris: str) -> str:
    return tmpl.format(subj=subj, pop=pop, juris=juris or "this jurisdiction")


def _gold_from_skeleton(sk, subj, pop, juris) -> GoldClaim:
    key, ctype, tmpl, core, fragile, conseq, drift = sk
    text = _fill(tmpl, subj, pop, juris)
    g = GoldClaim(text=text, claim_type=ctype, fragile_dimension=fragile,
                  downstream_consequence=conseq, population=pop)
    if key == "qualified":
        g.uncertainty = "hedged"
    elif key == "negated":
        g.polarity = "negated"
    elif key == "modal":
        g.modality = "permission"
    elif key == "conditional":
        g.conditions = ["prior therapy failed"]
    elif key == "exception":
        g.exceptions = ["during pregnancy"]
    elif key == "population":
        g.population = pop
    elif key == "temporal":
        g.temporal_scope = "as of 2021"
    elif key == "jurisdiction":
        g.jurisdiction = juris or "this jurisdiction"
    elif key == "numeric":
        g.numerical_values = ["10", "20"]; g.units = ["percent"]; g.ranges = ["10-20 percent"]
    elif key == "causal":
        g.causal_direction = "correlational"
    elif key == "attributed":
        g.attribution = "attributed"; g.attributed_source = "one review"
    elif key == "evidence_status":
        g.polarity = "affirmative"; g.evidence_status_language = "no evidence"
    elif key == "recommendation":
        g.normative_status = "normative"; g.modality = "obligation"
    return g


def _drift_variant(sk, subj, pop, juris) -> Dict[str, Any]:
    """The naive-splitting/normalization output that drops the fragile dimension."""
    key, ctype, tmpl, core, fragile, conseq, drift = sk
    return {"texts": [_fill(core, subj, pop, juris)], "failure": drift}


def _annotators(partition: str, n_core: int, idx: int):
    """Two independent annotation procedures.
    A (semantic proposition & scope): counts core propositions.
    B (downstream evaluability): may split a MULTI_CLAIM conjunction into evaluable units, or keep a
    CROSS_SENTENCE dependency as one unit. They share hard structure (core count) and diverge only on
    the soft atomicity of conjunctions/dependencies - a realistic, bounded disagreement.
    """
    a = n_core
    b = n_core
    disagree = False
    if partition == "MULTI_CLAIM" and idx % 4 == 0:
        b = n_core + 1        # B splits a borderline conjunction one finer
        disagree = True
    elif partition == "CROSS_SENTENCE" and idx % 5 == 0:
        b = max(1, n_core - 1)  # B merges a dependent fragment into its antecedent
        disagree = True
    return a, b, disagree


def _build_example(idx: int, partition: str, domain: str, skels, variant: int = 0) -> Example:
    subj, pop, juris = (_SUBJ_ALT if variant else _SUBJ)[domain]
    risk = "high" if domain in HIGH_RISK else ("medium" if domain in
           ("scientific", "enterprise_policy", "public_policy", "mixed_factual_normative") else "low")
    golds = [_gold_from_skeleton(sk, subj, pop, juris) for sk in skels]
    unacceptable = [_drift_variant(sk, subj, pop, juris) for sk in skels]

    if partition == "CROSS_SENTENCE":
        # two sentences: a factual claim + a follow-up using a pronoun that must resolve to subj
        base = golds[0]
        base_text = base.text
        follow = f"It is not recommended for {pop}."
        original = f"{base_text} {follow}"
        g2 = GoldClaim(text=f"{subj} is not recommended for {pop}.", claim_type="negated",
                       polarity="negated", population=pop, reference_links={"It": subj},
                       fragile_dimension="reference", downstream_consequence="unsafe_allow")
        golds = [base, g2]
        unacceptable = [{"texts": [base_text, follow], "failure": "pronoun_resolution_error"},
                        {"texts": [base_text], "failure": "cross_sentence_dependency_loss"}]
        context = f"Question about {subj} in {domain.replace('_',' ')}."
    elif partition == "MULTI_CLAIM":
        original = " ".join(g.text for g in golds)
        context = f"Multi-claim answer in {domain.replace('_',' ')}."
    elif partition == "ADVERSARIAL_SCOPE":
        # conjunction where an exception/qualifier attaches to ONLY the second clause - naive splitting
        # detaches or misattaches it.
        c1 = f"{subj} is approved for {pop}"
        c2 = "it is contraindicated in pregnancy unless monitored"
        original = f"{c1}, but {c2}."
        golds = [
            GoldClaim(text=f"{subj} is approved for {pop}.", claim_type="direct_factual",
                      population=pop, fragile_dimension="scope", downstream_consequence="none"),
            GoldClaim(text=f"{subj} is contraindicated in pregnancy unless monitored.",
                      claim_type="exception_bearing", conditions=["monitored"],
                      exceptions=["pregnancy"], fragile_dimension="exceptions",
                      downstream_consequence="unsafe_allow"),
        ]
        unacceptable = [
            {"texts": [c1 + ".", "it is contraindicated in pregnancy."],
             "failure": "conditional_to_unconditional"},   # dropped "unless monitored"
            {"texts": [f"{subj} is approved for {pop} and contraindicated in pregnancy."],
             "failure": "conjunction_under_split"},
        ]
        context = f"Adversarial scope case in {domain.replace('_',' ')}."
    else:  # SIMPLE_ATOMIC / QUALIFIED_COMPLEX
        original = " ".join(g.text for g in golds)
        context = f"{'Simple' if partition=='SIMPLE_ATOMIC' else 'Qualified'} answer in " \
                  f"{domain.replace('_',' ')}."

    n_core = len(golds)
    a, b, disagree = _annotators(partition, n_core, idx)
    # acceptable alternates: the gold grouping, plus (for MULTI_CLAIM) the finer B split as valid
    acceptable = [[g.text for g in golds]]
    if partition == "MULTI_CLAIM" and disagree:
        acceptable.append([g.text for g in golds])   # both counts are acceptable groupings here
    delivery_conseq = ("unsafe_allow" if any(g.downstream_consequence == "unsafe_allow" for g in golds)
                       else "conservative_block")
    evid_conseq = ("query_altered" if delivery_conseq == "unsafe_allow" else "unchanged")

    return Example(
        example_id=f"CI{idx:04d}", partition=partition, domain=domain, risk_class=risk,
        original_text=original, context=context,
        gold_claims=[asdict(g) for g in golds], expected_claim_count=n_core,
        acceptable_decompositions=acceptable, unacceptable_decompositions=unacceptable,
        downstream_evidence_consequence=evid_conseq, downstream_delivery_consequence=delivery_conseq,
        annot_A_count=a, annot_B_count=b, annotator_disagreement=disagree,
        gold_disposition="VALID", annotation_rationale=(
            f"{partition}: gold preserves the fragile dimension(s) "
            f"{sorted({g.fragile_dimension for g in golds})}; naive splitting/normalization drops them."))


def all_examples() -> List[Example]:
    out: List[Example] = []
    idx = 0
    single = ["qualified", "negated", "modal", "conditional", "exception", "population", "temporal",
              "jurisdiction", "numeric", "causal", "attributed", "evidence_status", "recommendation"]
    by_key = {sk[0]: sk for sk in SKELETONS}
    # two semantically-equivalent lexical variants per case (variant 0/1) double the corpus without
    # changing gold semantics - and give the semantic-equivalence machinery (Phase 11) true paraphrase
    # pairs to accept (guards against over-strict equivalence, failure type 50).
    for variant in (0, 1):
        for partition in PARTITIONS:
            for domain in DOMAINS:
                if partition == "SIMPLE_ATOMIC":
                    for k in single:
                        out.append(_build_example(idx, partition, domain, [by_key[k]], variant)); idx += 1
                elif partition == "QUALIFIED_COMPLEX":
                    for k in ["qualified", "conditional", "exception", "temporal", "jurisdiction",
                              "numeric", "modal"]:
                        out.append(_build_example(idx, partition, domain, [by_key[k]], variant)); idx += 1
                elif partition == "MULTI_CLAIM":
                    for combo in [["qualified", "negated"], ["numeric", "causal"],
                                  ["population", "temporal"], ["attributed", "evidence_status"],
                                  ["conditional", "exception"]]:
                        out.append(_build_example(idx, partition, domain, [by_key[k] for k in combo],
                                                  variant)); idx += 1
                elif partition == "CROSS_SENTENCE":
                    for k in ["population", "numeric", "causal", "qualified"]:
                        out.append(_build_example(idx, partition, domain, [by_key[k]], variant)); idx += 1
                elif partition == "ADVERSARIAL_SCOPE":
                    for _ in range(3):
                        out.append(_build_example(idx, partition, domain, [by_key["exception"]],
                                                  variant)); idx += 1
    return out


def stats(exs=None) -> Dict[str, Any]:
    exs = exs or all_examples()
    from collections import Counter
    return {
        "version": DATASET_VERSION, "n": len(exs),
        "partitions": dict(Counter(e.partition for e in exs)),
        "domains": dict(Counter(e.domain for e in exs)),
        "disagreement_rate": round(sum(e.annotator_disagreement for e in exs) / len(exs), 4),
        "unsafe_allow_examples": sum(1 for e in exs
                                     if e.downstream_delivery_consequence == "unsafe_allow"),
        "total_gold_claims": sum(len(e.gold_claims) for e in exs),
    }


def dump_json(path: str) -> int:
    exs = all_examples()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump([asdict(e) for e in exs], fh, indent=2, sort_keys=True)
    return len(exs)


if __name__ == "__main__":
    import pprint
    pprint.pprint(stats())
