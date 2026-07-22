#!/usr/bin/env python3
"""SHARED canonicalization primitives ONLY (§18-permitted shared layer).
Contains: canonical JSON, sha, content tokenization, Jaccard fraction,
JSON canonical-form + brace-depth scan, and loaders for the frozen Unicode
resource tables. Contains NO finding-derivation / expected-result generation:
those live in the builder and are RE-IMPLEMENTED independently in the auditors."""
import hashlib, json, re, unicodedata
from fractions import Fraction

def cjson(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def sha_bytes(b): return "sha-256:" + hashlib.sha256(b).hexdigest()
def sha_text(s): return sha_bytes(s.encode("utf-8"))

# ---- content tokenization (BASE-TOK): open-class content tokens only ----
# Function-word classes (token-classes.tsv is_content=NO). For the corrected
# lexical fixtures we use only open-class singular nouns, so this minimal
# function-word set is sufficient and faithful; tokens are lemma-stable.
FUNCTION_WORDS = {
 "the","a","an","and","or","but","if","then","of","to","in","on","for","with","by","from",
 "is","are","was","were","be","been","being","it","its","this","that","these","those","not",
 "no","may","must","can","could","should","would","will","shall","as","at","into","about"}
def content_tokens(text):
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in toks if t not in FUNCTION_WORDS}

def jaccard(a, b):
    a = set(a); b = set(b)
    if not a and not b: return Fraction(0, 1)  # empty_union = 0.0
    return Fraction(len(a & b), len(a | b))

# ---- Unicode resource loaders (frozen tables) ----
def load_confusables(path):
    rows = {}
    for ln in open(path, encoding="utf-8").read().splitlines():
        if not ln.strip() or ln.startswith("#"): continue
        c = ln.split("\t")
        cp = int(c[0][2:], 16)
        rows[cp] = {"name": c[1], "script": c[2], "skeleton": c[3], "suspicious": c[4]}
    return rows
def load_invisible(path):
    rows = {}
    for ln in open(path, encoding="utf-8").read().splitlines():
        if not ln.strip() or ln.startswith("#"): continue
        c = ln.split("\t")
        cp = int(c[0][2:], 16)
        rows[cp] = {"name": c[1], "class": c[2], "disposition": c[3], "suspicious": c[4]}
    return rows

def codepoints(text): return [ord(ch) for ch in text]

# ---- JSON structural primitives (no verdict, just structure) ----
def max_brace_depth(s):
    """Max nesting depth of {}/[] ignoring string contents. Structure only."""
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

def has_bom(raw_bytes): return raw_bytes[:3] == b"\xef\xbb\xbf"
def decodes_utf8(raw_bytes):
    try: raw_bytes.decode("utf-8"); return True
    except UnicodeDecodeError: return False

# ---- deterministic input reconstruction (§7 recipe support) ----
import base64 as _b64
def reconstruct_input(inp):
    """Return the exact raw bytes a harness must parse, from a fixture input spec.
    Deterministic; identical output for identical spec. No verdict is produced."""
    k = inp["kind"]
    if k == "raw":                       # literal UTF-8 string
        return inp["raw"].encode("utf-8")
    if k == "raw_bytes_hex":             # arbitrary bytes (e.g. invalid UTF-8, BOM)
        return bytes.fromhex(inp["hex"])
    if k == "base64":
        return _b64.b64decode(inp["raw_input_base64"])
    if k == "recipe":
        r = inp["recipe"]; t = r["type"]
        if t == "nested_object": return (b'{"a":' * r["depth"]) + b"1" + (b"}" * r["depth"])
        if t == "nested_array":  return (b"[" * r["depth"]) + b"1" + (b"]" * r["depth"])
        if t == "flat_object":
            return b"{" + b",".join(b'"f%d":0' % i for i in range(r["fields"])) + b"}"
        if t == "string_value": return b'{"s":"' + (b"a" * r["length"]) + b'"}'
        raise ValueError("unknown recipe " + t)
    raise ValueError("unknown input kind " + k)
