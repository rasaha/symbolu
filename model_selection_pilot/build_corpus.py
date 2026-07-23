"""Build a versioned document-intelligence corpus with explicit ground truth.

Domain: document intelligence for enterprise operations. All documents are
SYNTHETIC (no real PII), generated deterministically so ground truth is exact and
scoring is rule-based. 7 task classes; ~64 tasks; deterministic dev/shadow split.

Each task carries a hidden `_oracle` (ground truth) used by the deterministic
scorers and by the offline stub mock. The routing policy never reads `_oracle`
(enforced by the routing-time information-boundary test).
"""
from __future__ import annotations

import os

from common import CORPUS_VERSION, DATA_DIR, approx_tokens, det_unit, save_json

VENDORS = ["Acme Supplies", "Globex Ltd", "Initech Corp", "Umbrella Services", "Wayne Logistics",
           "Stark Materials", "Soylent Foods", "Hooli Cloud"]
CATEGORIES = ["billing", "technical_support", "account_access", "shipping", "compliance", "refund"]
CLAUSE_TYPES = ["termination", "liability", "confidentiality", "payment_terms", "indemnity", "governance"]


def _para(seed: str, n_words: int) -> str:
    words = ("the party shall provide services under this agreement subject to review and audit "
             "with reasonable notice and in accordance with applicable enterprise policy").split()
    out = []
    for i in range(n_words):
        out.append(words[int(det_unit(seed, i) * len(words)) % len(words)])
    return " ".join(out).capitalize() + "."


def _priority(seed):
    return ["quality_first", "balanced", "cost_first", "latency_first"][int(det_unit(seed, "prio") * 4) % 4]


def make_extraction(i):
    seed = f"ex{i}"
    vendor = VENDORS[i % len(VENDORS)]
    inv = f"INV-{2026000 + i}"
    total = round(1000 + det_unit(seed, "t") * 9000, 2)
    fields = {"invoice_no": inv, "vendor": vendor, "date": f"2026-0{(i % 9) + 1}-15",
              "total": f"{total:.2f}", "currency": "USD", "po_number": f"PO-{5000 + i}"}
    text = (f"INVOICE\nVendor: {vendor}\nInvoice No: {inv}\nDate: 2026-0{(i % 9) + 1}-15\n"
            f"PO Number: PO-{5000 + i}\nAmount Due: USD {total:.2f}\n"
            f"Terms: Net 30. Please remit to accounts payable. {_para(seed, 40)}")
    return dict(task_class="structured_extraction",
                required_schema={"type": "object", "fields": list(fields.keys())},
                input_text=text, _oracle={"fields": fields},
                min_acceptable_quality=0.70)


def make_schema_gen(i):
    seed = f"sg{i}"
    fields = {"ticket_id": f"TK-{9000 + i}", "severity": ["low", "medium", "high"][i % 3],
              "component": ["auth", "billing", "api"][i % 3], "owner": f"team-{i % 4}"}
    text = (f"Create a normalized ticket record. Raw note: severity {fields['severity']} issue in "
            f"the {fields['component']} component, assigned to {fields['owner']}, id {fields['ticket_id']}. "
            f"{_para(seed, 25)}")
    return dict(task_class="schema_constrained_generation",
                required_schema={"type": "object", "fields": list(fields.keys()), "strict": True},
                input_text=text, _oracle={"fields": fields},
                hard_constraints={"require_structured_strict": True},
                min_acceptable_quality=0.75)


def make_classification(i):
    seed = f"cl{i}"
    label = CATEGORIES[int(det_unit(seed, "l") * len(CATEGORIES)) % len(CATEGORIES)]
    text = {"billing": "I was charged twice for my subscription this month.",
            "technical_support": "The dashboard returns a 500 error when I export data.",
            "account_access": "I cannot log in; my password reset link never arrives.",
            "shipping": "My order shipped two weeks ago and still has not arrived.",
            "compliance": "Please provide a copy of your SOC 2 report for our audit.",
            "refund": "I would like a refund for the annual plan I did not use."}[label]
    return dict(task_class="classification", label_set=CATEGORIES,
                required_schema={"type": "object", "fields": ["label"]},
                input_text=text + " " + _para(seed, 20), _oracle={"label": label},
                min_acceptable_quality=0.70)


def make_summarization(i):
    seed = f"su{i}"
    facts = [f"Outage began at 0{(i % 8) + 1}:00 UTC", f"Root cause was a {['config','network','disk'][i % 3]} failure",
             f"{(i % 5) + 1} services were affected", "Service was restored within 3 hours",
             "A post-incident review is scheduled"]
    text = "INCIDENT REPORT. " + " ".join(facts) + ". " + _para(seed, 60)
    return dict(task_class="summarization",
                required_schema={"type": "object", "fields": ["summary_points"]},
                input_text=text,
                _oracle={"key_facts": facts, "distractor": "the CEO resigned"},
                min_acceptable_quality=0.65)


def make_long_qa(i):
    seed = f"qa{i}"
    answer = f"{(i % 5) + 1} business days"
    ev_id = f"para_{3 + (i % 4)}"
    paras = []
    for p in range(8):
        if f"para_{p}" == ev_id:
            paras.append(f"[{ev_id}] Refund requests are processed within {answer} of approval. {_para(seed, 30)}")
        else:
            paras.append(f"[para_{p}] {_para(seed + str(p), 120)}")
    text = "ENTERPRISE POLICY MANUAL\n" + "\n".join(paras)
    return dict(task_class="long_document_qa",
                required_schema={"type": "object", "fields": ["answer", "evidence_id"]},
                input_text=text,
                _oracle={"answer": answer, "wrong_answer": "10 business days",
                         "evidence_id": ev_id, "question": "How long do refund requests take to process?"},
                question="How long do refund requests take to process?",
                min_acceptable_quality=0.70)


def make_comparison(i):
    seed = f"cmp{i}"
    a_days, b_days = 30, 60
    verdict = "A_stricter"
    text = (f"Compare two SLAs. Contract A: termination requires {a_days} days notice. "
            f"Contract B: termination requires {b_days} days notice. Which imposes the stricter "
            f"(shorter) notice period? {_para(seed, 20)}")
    return dict(task_class="grounded_comparison",
                required_schema={"type": "object", "fields": ["verdict"]},
                input_text=text,
                _oracle={"verdict": verdict, "wrong_verdict": "B_stricter"},
                min_acceptable_quality=0.70)


def make_clause(i):
    seed = f"cla{i}"
    target = CLAUSE_TYPES[i % len(CLAUSE_TYPES)]
    candidate_ids = [f"c{j}" for j in range(6)]
    present = [f"c{j}" for j in range(6) if det_unit(seed, j) < 0.4] or ["c0"]
    clauses = []
    for j in range(6):
        kind = target if f"c{j}" in present else CLAUSE_TYPES[(i + j + 1) % len(CLAUSE_TYPES)]
        clauses.append(f"[c{j}] This {kind} clause states that {_para(seed + str(j), 18)}")
    text = f"SERVICE AGREEMENT. Identify all '{target}' clauses.\n" + "\n".join(clauses)
    return dict(task_class="clause_identification",
                required_schema={"type": "object", "fields": ["clause_ids"]},
                input_text=text, candidate_clause_ids=candidate_ids,
                _oracle={"clause_ids": sorted(present), "target_type": target},
                min_acceptable_quality=0.65)


GENERATORS = [make_extraction, make_schema_gen, make_classification, make_summarization,
              make_long_qa, make_comparison, make_clause]


def build() -> dict:
    tasks = []
    idx = 0
    per_class = 9
    for gen in GENERATORS:
        for k in range(per_class):
            idx += 1
            t = gen(k)
            t["task_id"] = f"p{idx:03d}_{t['task_class']}"
            t.setdefault("hard_constraints", {})
            t.setdefault("business_priority", _priority(t["task_id"]))
            t["input_tokens_k"] = round(approx_tokens(t["input_text"]) / 1000.0, 3)
            tasks.append(t)

    # attach a spread of hard constraints / limits deterministically
    for t in tasks:
        s = t["task_id"]
        if det_unit(s, "cost") < 0.25:
            t["hard_constraints"]["max_cost"] = 0.02
        if det_unit(s, "lat") < 0.20:
            t["hard_constraints"]["max_latency_ms"] = 1500
        if det_unit(s, "priv") < 0.12:
            t["hard_constraints"]["require_on_prem"] = True  # no eligible model -> abstain test
        t["business_priority"] = t.get("business_priority", _priority(s))

    # deterministic dev/shadow split (~50/50), stratified by class
    dev, shadow = [], []
    counts = {}
    for t in sorted(tasks, key=lambda x: x["task_id"]):
        c = counts.get(t["task_class"], 0)
        (dev if c % 2 == 0 else shadow).append(t)
        counts[t["task_class"]] = c + 1

    meta = {"version": CORPUS_VERSION, "domain": "document-intelligence-enterprise-operations",
            "n_total": len(tasks), "n_dev": len(dev), "n_shadow": len(shadow),
            "task_classes": sorted({t["task_class"] for t in tasks}),
            "note": "SYNTHETIC documents, no real PII; ground truth in _oracle (policy must not read it)."}
    return {"meta": meta, "dev": dev, "shadow": shadow}


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    corpus = build()
    save_json(os.path.join(DATA_DIR, "corpus_dev.json"),
              {"meta": corpus["meta"], "tasks": corpus["dev"]})
    save_json(os.path.join(DATA_DIR, "corpus_shadow.json"),
              {"meta": corpus["meta"], "tasks": corpus["shadow"]})
    print(f"wrote corpus: {corpus['meta']['n_dev']} dev / {corpus['meta']['n_shadow']} shadow")


if __name__ == "__main__":
    main()
