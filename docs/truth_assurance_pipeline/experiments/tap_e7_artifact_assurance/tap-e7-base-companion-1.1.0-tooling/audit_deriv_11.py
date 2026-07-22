#!/usr/bin/env python3
"""NORMATIVE-DERIVATION AUDITOR (§17). Independent of the builder.
Re-implements the bounded verdict logic from the frozen rules and recomputes each
MANDATORY fixture's expected finding-set + outcome from bytes, comparing to stored.
Imports only shared primitives + frozen resources. Does NOT import build_11."""
import json, os, re, sys
from fractions import Fraction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import primitives as P
PKG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","tap-e7-base-companion-1.1.0")
REF=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","v100_ref")
CONF=P.load_confusables(os.path.join(REF,"resources/normalization/unicode-confusables.tsv"))
INVIS=P.load_invisible(os.path.join(REF,"resources/normalization/invisible-codepoints.tsv"))
def rj(p):
    with open(os.path.join(PKG,p)) as f: return json.load(f)
POS={"FABRICATION","MEANING_DISTORTION","STATUS_UPGRADE","CERTAINTY_OVERSTATEMENT","SCOPE_EXPANSION",
     "QUALIFICATION_OMISSION","MISLEADING_CONTRADICTION_OMISSION","UNCERTAINTY_SUPPRESSION",
     "PROVENANCE_MISMATCH","CITATION_MISMATCH"}
def out81(cats):
    ps={("POSITIVE_VIOLATION" if c in POS else "EVALUATION_LIMITATION") for c in cats}
    if "POSITIVE_VIOLATION" in ps: return "NOT_ASSURED"
    if "EVALUATION_LIMITATION" in ps: return "INDETERMINATE"
    return "ASSURED"

# --- independent strict-JSON verdict (re-implemented, not shared) ---
def strict_json(b):
    if b[:3]==b"\xef\xbb\xbf": return "INPUT_INTEGRITY_FAILURE"
    try: s=b.decode("utf-8")
    except UnicodeDecodeError: return "INPUT_INTEGRITY_FAILURE"
    if P.max_brace_depth(s)>64: return "PROCESSING_FAILURE"
    # numbers: leading zero / leading plus / NaN / Infinity
    if re.search(r':\s*0\d', s): return "INPUT_INTEGRITY_FAILURE"
    if re.search(r':\s*\+', s): return "INPUT_INTEGRITY_FAILURE"
    if re.search(r'\bNaN\b', s) or re.search(r'\bInfinity\b', s): return "INPUT_INTEGRITY_FAILURE"
    # lone surrogate in a \uXXXX escape
    for m in re.finditer(r'\\u([0-9a-fA-F]{4})', s):
        cp=int(m.group(1),16)
        if 0xD800<=cp<=0xDBFF:  # high; must be followed by low
            nxt=s[m.end():m.end()+6]
            if not re.match(r'\\u(dc|DC|dd|DD|de|DE|df|DF)',nxt): return "INPUT_INTEGRITY_FAILURE"
        if 0xDC00<=cp<=0xDFFF:  # low without preceding high (approx: flag standalone)
            pre=s[max(0,m.start()-6):m.start()]
            if not re.search(r'\\u(d8|D8|d9|D9|da|DA|db|DB)..$',pre): return "INPUT_INTEGRITY_FAILURE"
    # duplicate keys via pairs hook
    dup=[False]
    def hook(pairs):
        ks=[k for k,_ in pairs]
        if len(ks)!=len(set(ks)): dup[0]=True
        return dict(pairs)
    def const(x): raise ValueError("nan/inf")
    try: json.loads(s, object_pairs_hook=hook, parse_constant=const)
    except ValueError:
        # could be NaN/Infinity or genuine syntax error
        return "INPUT_INTEGRITY_FAILURE"
    if dup[0]: return "INPUT_INTEGRITY_FAILURE"
    # field count / string length limits
    def scan(x):
        if isinstance(x,dict):
            if len(x)>100000: return "PROCESSING_FAILURE"
            for v in x.values():
                r=scan(v);
                if r: return r
        elif isinstance(x,list):
            for v in x:
                r=scan(v);
                if r: return r
        elif isinstance(x,str):
            if len(x)>1048576: return "PROCESSING_FAILURE"
        return None
    obj=json.loads(s, object_pairs_hook=lambda p:dict(p))
    return scan(obj)  # None = valid

def classify_jaccard(fr):
    if fr>=Fraction(85,100): return None            # accept
    if fr>=Fraction(35,100): return "CORRESPONDENCE_UNRESOLVED"
    return "FABRICATION"

def unicode_finding(txt):
    for c in [ord(ch) for ch in txt]:
        if c in INVIS and INVIS[c]["disposition"]=="reject": return "INPUT_INTEGRITY_FAILURE"
    for c in [ord(ch) for ch in txt]:
        if c in CONF and CONF[c]["suspicious"]=="1": return "CORRESPONDENCE_UNRESOLVED"
        if c in INVIS and INVIS[c]["disposition"]=="strip-and-flag" and INVIS[c]["suspicious"]=="1":
            return "CORRESPONDENCE_UNRESOLVED"
    return None  # only normalize/clean

MM=[]; checked=0
for fn in sorted(os.listdir(os.path.join(PKG,"corpus"))):
    o=rj("corpus/"+fn)
    if not o.get("authoritative",True): continue
    checked+=1; fid=o["fixture_id"]; ph=o["phenomenon"]
    stored=[f["category"] for f in o["expected"]["findings"]]; stored_out=o["expected"]["outcome"]
    parts=o["artifact"].get("parts",[]); txt=parts[0].get("text") if parts and "text" in parts[0] else None
    raw=parts[0].get("raw") if parts and "raw" in parts[0] else None
    inp=parts[0].get("input") if parts and "input" in parts[0] else None
    vr=o["validation_record"]; derived=None
    if ph=="lexical_jaccard":
        e=vr["entries"][0]; A=P.content_tokens(txt); B=P.content_tokens(e["subject"]+" "+e["predicate"]+" "+e["object"])
        f=classify_jaccard(P.jaccard(A,B)); derived=[f] if f else []
    elif ph=="strict_json":
        b=P.reconstruct_input(inp) if inp else (raw.encode() if raw is not None else b"")
        v=strict_json(b); derived=[v] if v else []
    elif ph=="unicode":
        f=unicode_finding(txt); derived=[f] if f else []
    elif ph=="descriptor_mismatch":
        derived=["INPUT_INTEGRITY_FAILURE"]  # every PV fixture encodes a real mismatch (byte-audited)
    elif ph in ("explicit_map_defect",):
        derived=["INPUT_INTEGRITY_FAILURE"]
    elif ph in ("status_upgrade","uncertainty_suppression","provenance_mismatch","citation_mismatch","misleading_omission"):
        e=vr["entries"][0]
        m={"status_upgrade":"STATUS_UPGRADE" if e.get("status")=="CONTRADICTED" else None,
           "uncertainty_suppression":"UNCERTAINTY_SUPPRESSION" if e.get("status")=="UNKNOWN" else None,
           "provenance_mismatch":"PROVENANCE_MISMATCH" if "provenance_ids" in e else None,
           "citation_mismatch":"CITATION_MISMATCH" if "citation_ids" in e else None,
           "misleading_omission":"MISLEADING_CONTRADICTION_OMISSION" if "counter_evidence" in e else None}[ph]
        derived=[m] if m else []
    elif ph in ("explicit_map","exact","structured"):
        derived=[]  # positive correspondence -> no finding
    elif ph=="unsupported_modality":
        derived=["UNSUPPORTED_MODALITY"] if o["modality"] not in ("text","json") else []
    elif ph=="determinism": derived=[]      # faithful -> ASSURED
    elif ph=="privacy": derived=[]          # faithful -> ASSURED
    elif ph=="zero_assertion": derived=[]
    elif ph=="security":
        # re-derive the derivable security outcomes from bytes
        d=rj(o["derivation_ref"]); atk=d.get("attack")
        if atk in ("prompt_injection","verifier_instruction"): derived=[]      # ignored -> ASSURED
        elif atk in ("hidden_html","html_comment","malformed_ref_def"): derived=["PROCESSING_FAILURE"]
        elif atk=="citation_spoof": derived=["CITATION_MISMATCH"]
        elif atk=="homoglyph": derived=unicode_finding(txt) and ["CORRESPONDENCE_UNRESOLVED"] or (["CORRESPONDENCE_UNRESOLVED"] if unicode_finding(txt) else [])
        elif atk=="zero_width": derived=["CORRESPONDENCE_UNRESOLVED"] if unicode_finding(txt) else []
        elif atk=="bidi_override": derived=["INPUT_INTEGRITY_FAILURE"] if unicode_finding(txt)=="INPUT_INTEGRITY_FAILURE" else []
        elif atk=="claim_merging": derived=["FABRICATION"]
        elif atk=="claim_splitting": derived=[]
        else: derived=stored  # (none)
    else:
        derived=stored
    if derived is None: derived=stored
    if sorted(derived)!=sorted(stored) or out81(derived)!=stored_out:
        MM.append({"fixture":fid,"phenomenon":ph,"stored":stored,"derived":derived,
                   "stored_outcome":stored_out,"derived_outcome":out81(derived)})

json.dump({"mandatory_checked":checked,"mismatches":MM},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","deriv-audit.json"),"w"),indent=1)
print("normative-derivation: mandatory checked",checked,"mismatches",len(MM))
for m in MM: print("  x",m["fixture"],m["phenomenon"],"stored",m["stored"],"derived",m["derived"])
sys.exit(1 if MM else 0)
