#!/usr/bin/env python3
"""TAP-E7-BASE Independent Implementation A — verifier.

Authored clean-room from the published normative resources of the v1.1.0 package.
Consumes ONLY (ValidationRecord, CandidateArtifact, descriptor envelope) and produces
an AssuranceRecord. It imports NOTHING from the corpus builder, auditors, packaging
validator, or any expected-result / derivation logic. Dispatch never depends on
fixture id, group, purpose, or phenomenon.

Generic utilities (UTF-8 read, JSON, SHA-256, canonical ordering) are the only shared
concepts and are implemented locally here.
"""
import base64, hashlib, json, os, re, unicodedata
from fractions import Fraction

# ---------- generic utilities (locally implemented) ----------
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def sha_hex(b): return hashlib.sha256(b).hexdigest()
def sha_tag(b): return "sha-256:" + sha_hex(b)

# ---------- frozen taxonomy (transcribed from TAP-E7 §8 spec) ----------
POSITIVE_VIOLATION = {
 "FABRICATION","MEANING_DISTORTION","STATUS_UPGRADE","CERTAINTY_OVERSTATEMENT","SCOPE_EXPANSION",
 "QUALIFICATION_OMISSION","MISLEADING_CONTRADICTION_OMISSION","UNCERTAINTY_SUPPRESSION",
 "PROVENANCE_MISMATCH","CITATION_MISMATCH"}
EVALUATION_LIMITATION = {
 "CORRESPONDENCE_UNRESOLVED","UNSUPPORTED_MODALITY","INPUT_INTEGRITY_FAILURE","PROCESSING_FAILURE"}
def polarity(cat):
    if cat in POSITIVE_VIOLATION: return "POSITIVE_VIOLATION"
    if cat in EVALUATION_LIMITATION: return "EVALUATION_LIMITATION"
    raise ValueError("unknown category " + cat)
def aggregate_outcome(cats):  # TAP-E7 §8.1, implemented independently
    pols = {polarity(c) for c in cats}
    if "POSITIVE_VIOLATION" in pols: return "NOT_ASSURED"
    if "EVALUATION_LIMITATION" in pols: return "INDETERMINATE"
    return "ASSURED"

T_ACCEPT = Fraction(85, 100)
T_REJECT = Fraction(35, 100)
SUPPORTED_MODALITIES = {"text", "json"}
JSON_MAX_DEPTH = 64
JSON_MAX_FIELDS = 100000
JSON_MAX_STRING = 1048576


class Resources:
    """Loads the frozen resource tables from the package."""
    def __init__(self, pkg):
        self.pkg = pkg
        self.confusables = self._confusables("resources/normalization/unicode-confusables.tsv")
        self.invisible = self._invisible("resources/normalization/invisible-codepoints.tsv")
        self.function_class = self._pos("resources/language/pos-cues.tsv")
        self.irregular = self._irregular("resources/normalization/lemmatization-irregular.tsv")
        self.eng_core = self._lines("resources/language/eng-core.txt")
    def _read(self, rel):
        with open(os.path.join(self.pkg, rel), encoding="utf-8") as f: return f.read()
    def _lines(self, rel):
        return {l.strip() for l in self._read(rel).splitlines() if l.strip() and not l.startswith("#")}
    def _confusables(self, rel):
        out = {}
        for l in self._read(rel).splitlines():
            if not l.strip() or l.startswith("#"): continue
            c = l.split("\t"); out[int(c[0][2:], 16)] = {"skeleton": c[3], "suspicious": c[4] == "1"}
        return out
    def _invisible(self, rel):
        out = {}
        for l in self._read(rel).splitlines():
            if not l.strip() or l.startswith("#"): continue
            c = l.split("\t"); out[int(c[0][2:], 16)] = {"disposition": c[3], "suspicious": c[4] == "1"}
        return out
    def _pos(self, rel):
        out = {}
        for l in self._read(rel).splitlines():
            if not l.strip() or l.startswith("#"): continue
            c = l.split("\t"); out[c[0].strip()] = c[1].strip()
        return out
    def _irregular(self, rel):
        out = {}
        for l in self._read(rel).splitlines():
            if not l.strip() or l.startswith("#"): continue
            c = re.split(r"\t+", l.strip())
            if len(c) >= 2: out[c[0].lower()] = c[1].lower()
        return out


# ---------- strict JSON validation (token-first, duplicate-preserving) ----------
class StrictJson:
    """Independent strict-JSON validator per BASE-JSON profile. Returns a finding
    category string, or None if the bytes are a valid JSON value within limits."""
    def validate(self, raw: bytes):
        if raw[:3] == b"\xef\xbb\xbf":
            return "INPUT_INTEGRITY_FAILURE"           # BOM rejected
        try:
            s = raw.decode("utf-8")
        except UnicodeDecodeError:
            return "INPUT_INTEGRITY_FAILURE"           # malformed UTF-8
        if self._max_depth(s) > JSON_MAX_DEPTH:
            return "PROCESSING_FAILURE"
        # number grammar: leading zero / leading plus / NaN / Infinity
        if re.search(r'(?<![\d.])[:\[,]\s*0\d', s):
            return "INPUT_INTEGRITY_FAILURE"
        if re.search(r'[:\[,]\s*\+', s):
            return "INPUT_INTEGRITY_FAILURE"
        if re.search(r'\bNaN\b', s) or re.search(r'\bInfinity\b', s) or re.search(r'-Infinity', s):
            return "INPUT_INTEGRITY_FAILURE"
        # surrogate escapes
        r = self._surrogates(s)
        if r: return r
        # duplicate keys (any depth) via pairs hook
        dup = [False]
        def hook(pairs):
            keys = [k for k, _ in pairs]
            if len(keys) != len(set(keys)): dup[0] = True
            return dict(pairs)
        def bad_const(_): raise ValueError("nan/inf")
        try:
            obj = json.loads(s, object_pairs_hook=hook, parse_constant=bad_const)
        except ValueError:
            return "INPUT_INTEGRITY_FAILURE"           # syntax / number / constant
        if dup[0]:
            return "INPUT_INTEGRITY_FAILURE"
        lim = self._limits(obj)
        return lim                                     # PROCESSING_FAILURE or None
    def _max_depth(self, s):
        depth = mx = 0; in_str = False; esc = False
        for ch in s:
            if in_str:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': in_str = False
                continue
            if ch == '"': in_str = True
            elif ch in "{[": depth += 1; mx = max(mx, depth)
            elif ch in "}]": depth -= 1
        return mx
    def _surrogates(self, s):
        i = 0
        for m in re.finditer(r'\\u([0-9a-fA-F]{4})', s):
            cp = int(m.group(1), 16)
            if 0xD800 <= cp <= 0xDBFF:
                nxt = s[m.end():m.end() + 6]
                m2 = re.match(r'\\u([0-9a-fA-F]{4})', nxt)
                if not (m2 and 0xDC00 <= int(m2.group(1), 16) <= 0xDFFF):
                    return "INPUT_INTEGRITY_FAILURE"
            elif 0xDC00 <= cp <= 0xDFFF:
                pre = s[max(0, m.start() - 6):m.start()]
                m2 = re.search(r'\\u([0-9a-fA-F]{4})$', pre)
                if not (m2 and 0xD800 <= int(m2.group(1), 16) <= 0xDBFF):
                    return "INPUT_INTEGRITY_FAILURE"
        return None
    def _limits(self, x):
        if isinstance(x, dict):
            if len(x) > JSON_MAX_FIELDS: return "PROCESSING_FAILURE"
            for v in x.values():
                r = self._limits(v)
                if r: return r
        elif isinstance(x, list):
            for v in x:
                r = self._limits(v)
                if r: return r
        elif isinstance(x, str):
            if len(x) > JSON_MAX_STRING: return "PROCESSING_FAILURE"
        return None


class Verifier:
    def __init__(self, pkg):
        self.pkg = pkg
        self.res = Resources(pkg)
        self.sj = StrictJson()

    # ---------- input reconstruction (recipe support per fixture schema) ----------
    def reconstruct(self, part):
        if "raw" in part: return part["raw"].encode("utf-8")
        if "text" in part: return part["text"].encode("utf-8")
        inp = part["input"]; k = inp["kind"]
        if k == "raw": return inp["raw"].encode("utf-8")
        if k == "raw_bytes_hex": return bytes.fromhex(inp["hex"])
        if k == "base64": return base64.b64decode(inp["raw_input_base64"])
        if k == "recipe":
            r = inp["recipe"]; t = r["type"]
            if t == "nested_object": return (b'{"a":' * r["depth"]) + b"1" + (b"}" * r["depth"])
            if t == "nested_array": return (b"[" * r["depth"]) + b"1" + (b"]" * r["depth"])
            if t == "flat_object": return b"{" + b",".join(b'"f%d":0' % i for i in range(r["fields"])) + b"}"
            if t == "string_value": return b'{"s":"' + (b"a" * r["length"]) + b'"}'
        raise ValueError("unknown part")

    # ---------- tokenization / lemmatization (content-token set) ----------
    def lemma(self, tok):
        if tok in self.res.irregular: return self.res.irregular[tok]
        for suf, repl in (("ies", "y"), ("sses", "ss"), ("ing", ""), ("ed", ""), ("s", "")):
            if tok.endswith(suf) and len(tok) - len(suf) >= 3:
                return tok[:len(tok) - len(suf)] + repl
        return tok
    def content_tokens(self, text):
        text = unicodedata.normalize("NFC", text)
        # strip citation markers [..]
        text = re.sub(r"\[[^\]]*\]", " ", text)
        toks = re.findall(r"\w+", text.lower(), re.UNICODE)
        out = set()
        for t in toks:
            cls = self.res.function_class.get(t)
            if cls in ("MODAL", "NEGATION", "DETERMINER", "AUXILIARY", "PREPOSITION", "CONJUNCTION"):
                continue
            out.add(self.lemma(t))
        return out
    def entry_tokens(self, e):
        return self.content_tokens(" ".join(str(e.get(k, "")) for k in ("subject", "predicate", "object")))
    def jaccard(self, a, b):
        a, b = set(a), set(b)
        if not a and not b: return Fraction(0, 1)
        return Fraction(len(a & b), len(a | b))

    # ---------- unicode scan ----------
    def unicode_finding(self, text):
        cps = [ord(c) for c in text]
        for c in cps:
            iv = self.res.invisible.get(c)
            if iv and iv["disposition"] == "reject":
                return "INPUT_INTEGRITY_FAILURE"
        for c in cps:
            cf = self.res.confusables.get(c)
            if cf and cf["suspicious"]:
                return "CORRESPONDENCE_UNRESOLVED"
            iv = self.res.invisible.get(c)
            if iv and iv["disposition"] == "strip-and-flag" and iv["suspicious"]:
                return "CORRESPONDENCE_UNRESOLVED"
        return None

    # ---------- BASE-MD unsupported / malformed construct scan ----------
    def md_unsupported(self, text):
        if re.search(r"<!--", text): return True            # HTML comment
        if re.search(r"</?[a-zA-Z][^>]*>", text): return True  # raw HTML tag
        if re.search(r"(?m)^\s*\[[^\]]*\]:\s*$", text): return True  # malformed ref def (empty target)
        return False

    # ---------- sentence segmentation (BASE-SEG, bounded) ----------
    ABBR = {"e.g", "i.e", "etc", "mr", "mrs", "dr", "vs", "fig", "no"}
    def sentences(self, text):
        # strip heading markers / list markers, keep clause text
        text = re.sub(r"(?m)^#{1,6}\s*", "", text)
        parts = re.split(r"(?<=[.?!])\s+", text.strip())
        return [p.strip() for p in parts if p.strip()]

    def assertive_sentences(self, text, vr_entities):
        """Yield assertive sentences; drop fenced code and heading-only fragments (BASE-SEG S-BLOCK)."""
        text = re.sub(r"(?s)```.*?```", " ", text)          # remove fenced code blocks
        out = []
        for line in text.split("\n"):
            if re.match(r"^\s*#{1,6}\s+", line):             # heading = label fragment, non-assertive
                continue
            for sent in self.sentences(line):
                if self.is_assertive(sent, vr_entities):
                    out.append(sent)
        return out

    def is_assertive(self, sent, vr_entities):
        s = sent.strip()
        if not s: return False
        if s.endswith("?"): return False                      # interrogative
        low = s.lower()
        # imperative / instruction heuristic (bounded): starts with a bare verb-like
        # instruction and shares no record entity token. Documented limitation.
        first = re.findall(r"[a-z0-9]+", low)
        INSTRUCTION_LEADS = {"ignore", "disregard", "mark", "delete", "system", "note",
                             "review", "click", "run", "execute", "print", "output"}
        toks = self.content_tokens(s)
        if first and first[0] in INSTRUCTION_LEADS and not (toks & vr_entities):
            return False
        return True

    # ---------- correspondence + fidelity ----------
    def fidelity(self, entry, artifact_meta):
        """Return finding category or None, from structural comparison to a matched entry."""
        status = entry.get("status", "SUPPORTED")
        if status == "CONTRADICTED": return "STATUS_UPGRADE"
        if status == "UNKNOWN": return "UNCERTAINTY_SUPPRESSION"
        if "counter_evidence" in entry: return "MISLEADING_CONTRADICTION_OMISSION"
        if "provenance_ids" in entry and artifact_meta.get("attributed_source"):
            if artifact_meta["attributed_source"] not in entry["provenance_ids"]:
                return "PROVENANCE_MISMATCH"
        if "citation_ids" in entry and artifact_meta.get("citation"):
            if artifact_meta["citation"] not in entry["citation_ids"]:
                return "CITATION_MISMATCH"
        return None

    # ---------- main entry point ----------
    def evaluate(self, submission):
        """submission = {modality, validation_record, artifact, profile_ref, release_ref}"""
        findings = []            # document-level extra findings
        units = []               # per-assertion correspondence units
        vr = submission.get("validation_record", {}) or {}
        entries = vr.get("entries", [])
        # 1. descriptor / integrity envelope
        pr = submission.get("profile_ref") or {}
        rel = submission.get("release_ref")
        if (not pr) or pr.get("profile_id") != "tap-e7-base" or \
           str(pr.get("profile_version", "")).split(".")[0] != "1" or \
           rel != "tap-e7-base-companion/1.1.0":
            findings.append("INPUT_INTEGRITY_FAILURE")
            return self._assemble(units, findings)
        # 2. modality
        mod = submission.get("modality")
        if mod not in SUPPORTED_MODALITIES:
            findings.append("UNSUPPORTED_MODALITY")
            return self._assemble(units, findings)
        parts = submission.get("artifact", {}).get("parts", [])
        if mod == "json":
            if not parts:
                return self._assemble(units, findings)     # zero-assertion
            raw = self.reconstruct(parts[0])
            sjf = self.sj.validate(raw)
            if sjf:
                findings.append(sjf); return self._assemble(units, findings)
            obj = json.loads(raw.decode("utf-8"))
            self._json_assertion(obj, entries, units, findings)
        else:  # text
            raw = self.reconstruct(parts[0]); text = raw.decode("utf-8")
            # reject-disposition code points are a document-level integrity failure
            for c in [ord(ch) for ch in text]:
                iv = self.res.invisible.get(c)
                if iv and iv["disposition"] == "reject":
                    findings.append("INPUT_INTEGRITY_FAILURE"); return self._assemble(units, findings)
            if self.md_unsupported(text):
                findings.append("PROCESSING_FAILURE"); return self._assemble(units, findings)
            suspicious = self._suspicious_unicode(text)
            vr_ent_tokens = set()
            for e in entries: vr_ent_tokens |= self.content_tokens(str(e.get("subject", "")))
            for sent in self.assertive_sentences(text, vr_ent_tokens):
                if suspicious:
                    units.append({"kind": "unresolved"})       # assertion present but not safely resolvable
                else:
                    cit = re.search(r"\[([^\]]+)\]", sent)
                    meta = {"citation": cit.group(1)} if cit else {}
                    self._text_assertion(sent, entries, units, meta)
        return self._assemble(units, findings)

    def _suspicious_unicode(self, text):
        for c in [ord(ch) for ch in text]:
            cf = self.res.confusables.get(c)
            if cf and cf["suspicious"]: return True
            iv = self.res.invisible.get(c)
            if iv and iv["disposition"] == "strip-and-flag" and iv["suspicious"]: return True
        return False

    def _json_assertion(self, obj, entries, units, findings):
        if not isinstance(obj, dict) or not any(k in obj for k in ("statement", "subject", "validation_entry_id")):
            return  # zero-assertion (empty/array/metadata-only)
        meta = {"attributed_source": obj.get("attributed_source"), "citation": obj.get("citation")}
        if "validation_entry_id" in obj:
            vid = obj["validation_entry_id"]
            if isinstance(vid, list) or not isinstance(vid, str) or vid == "":
                findings.append("INPUT_INTEGRITY_FAILURE"); return
            entry = next((e for e in entries if e.get("entry_id") == vid), None)
            if entry is None:
                findings.append("INPUT_INTEGRITY_FAILURE"); return
            # proposition consistency
            prop = obj.get("statement") or " ".join(str(obj.get(k, "")) for k in ("subject", "predicate", "object"))
            if self.jaccard(self.content_tokens(prop), self.entry_tokens(entry)) < T_REJECT:
                findings.append("INPUT_INTEGRITY_FAILURE"); return
            fid = self.fidelity(entry, meta)
            units.append({"kind": "evaluated", "method": "explicit", "finding": fid, "entry": entry.get("entry_id")})
            return
        if all(k in obj for k in ("subject", "predicate", "object")):
            for e in entries:
                if all(str(obj[k]).lower() == str(e.get(k, "")).lower() for k in ("subject", "predicate", "object")):
                    units.append({"kind": "evaluated", "method": "structured", "finding": self.fidelity(e, meta), "entry": e.get("entry_id")})
                    return
        # statement-only: exact/lexical
        self._text_assertion(obj.get("statement", ""), entries, units, meta)

    def _text_assertion(self, prop, entries, units, meta=None):
        meta = meta or {}
        at = self.content_tokens(prop)
        # exact normalized
        for e in entries:
            if " ".join(sorted(at)) == " ".join(sorted(self.entry_tokens(e))) and at:
                units.append({"kind": "evaluated", "method": "exact", "finding": self.fidelity(e, meta), "entry": e.get("entry_id")})
                return
        # lexical best
        best = None; bj = Fraction(-1)
        for e in entries:
            j = self.jaccard(at, self.entry_tokens(e))
            if j > bj: bj, best = j, e
        if bj >= T_ACCEPT:
            units.append({"kind": "evaluated", "method": "lexical", "finding": self.fidelity(best, meta), "entry": best.get("entry_id")})
        elif bj >= T_REJECT:
            units.append({"kind": "unresolved"})
        else:
            units.append({"kind": "fabrication"})

    # ---------- assemble AssuranceRecord ----------
    def _assemble(self, units, extra_findings):
        findings = []
        total = len(units); ev = 0; un = 0
        mc = {"explicit": 0, "exact": 0, "structured": 0, "lexical": 0}
        add = {"unresolved": 0, "no_match": 0}; corr = 0
        for u in units:
            if u["kind"] == "evaluated":
                ev += 1; corr += 1; mc[u["method"]] += 1
                if u.get("finding"):
                    findings.append({"finding_index": len(findings), "category": u["finding"],
                                     "polarity": polarity(u["finding"]), "validation_ref": u.get("entry")})
            elif u["kind"] == "unresolved":
                un += 1; corr += 1; add["unresolved"] += 1
                findings.append({"finding_index": len(findings), "category": "CORRESPONDENCE_UNRESOLVED",
                                 "polarity": "EVALUATION_LIMITATION"})
            elif u["kind"] == "fabrication":
                un += 1; corr += 1; add["no_match"] += 1
                findings.append({"finding_index": len(findings), "category": "FABRICATION",
                                 "polarity": "POSITIVE_VIOLATION"})
        for c in extra_findings:
            findings.append({"finding_index": len(findings), "category": c, "polarity": polarity(c)})
        cats = [f["category"] for f in findings]
        outcome = aggregate_outcome(cats)
        es = {"total_assertive": total, "evaluated_assertive": ev, "unevaluated_assertive": un,
              "positive_violations": sum(1 for c in cats if polarity(c) == "POSITIVE_VIOLATION"),
              "evaluation_limitations": sum(1 for c in cats if polarity(c) == "EVALUATION_LIMITATION"),
              "x-tap-e7-base-evaluation-summary": {"correspondence_units_total": corr,
                "correspondence_method_counts": dict(mc), "companion_method_counts": dict(add)}}
        pi = {"outcome": outcome,
              "findings": [{"category": f["category"], "polarity": f["polarity"]} for f in findings],
              "evaluation_summary": {k: es[k] for k in ("total_assertive", "evaluated_assertive",
                                     "unevaluated_assertive", "positive_violations", "evaluation_limitations")}}
        return {"outcome": outcome, "findings": findings, "evaluation_summary": es,
                "projection_pi": pi, "projection_pi_sha256": sha_tag((canon(pi) + "\n").encode())}

    # ---------- trace + redaction ----------
    def trace(self, submission, record, redacted=False):
        parts = submission.get("artifact", {}).get("parts", [])
        raw = self.reconstruct(parts[0]) if parts else b""
        node = {"outcome": record["outcome"],
                "findings": [f["category"] for f in record["findings"]],
                "artifact_ptr": "/artifact/parts/0",
                "artifact_sha256": sha_tag(raw)}
        if not redacted:
            try: node["artifact_text"] = raw.decode("utf-8")
            except UnicodeDecodeError: node["artifact_text"] = "<binary>"
        return node

    def projection(self, record): return record["projection_pi"], record["projection_pi_sha256"]
