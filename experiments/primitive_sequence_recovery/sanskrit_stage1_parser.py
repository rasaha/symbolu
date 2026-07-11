"""Stage-1 native-Sanskrit parser — deterministic Devanāgarī → akṣara → atomic-varṇa decomposer.

Implements B1_STAGE1_SANSKRIT_PARSER_SPEC.md (rules R1–R12, defaults U1–U5) plus the audit corrections
(ZWJ/ZWNJ join-control policy, singleton boundary booleans, unsupported-nukta policy, virāma+independent-vowel
warning, single-token whitespace contract). This is NEUTRAL Stage-1 input infrastructure ONLY: it assigns no
binding/liberating meaning, chooses no polarity, aggregates no facets, scores nothing, and imports NO varṇa
polarity table, scoring module, Track-G evaluator, or English G2P utility.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. Emitting a phonological vowel here is a
structural fact and attaches NO meaning.

Schema version 1.1: atomic units carry scalar `position` plus authoritative boolean `is_initial`/`is_final`.

The spec file is authoritative; where any library or convention conflicts with it, the spec controls. Akṣara
segmentation is implemented explicitly (NOT via a generic grapheme-cluster library).
"""
import json
import unicodedata

SPEC_VERSION = "PARSER_SPEC_v1"
SCHEMA_VERSION = "1.1"

# ----------------------------------------------------------------------------------------------------------------
# Devanāgarī tables (canonical classical block). Unit ids are IAST varṇa keys; joining phonological atomic unit ids
# in order reconstructs IAST (e.g. ś + ā + n + t + i = śānti).
# ----------------------------------------------------------------------------------------------------------------
VIRAMA = "्"
ANUSVARA = "ं"
VISARGA = "ः"
CANDRABINDU = "ँ"
AVAGRAHA = "ऽ"
NUKTA = "़"
ZWJ = "\u200d"      # ZERO WIDTH JOINER
ZWNJ = "\u200c"     # ZERO WIDTH NON-JOINER
ZWSP = "\u200b"     # ZERO WIDTH SPACE
JOIN_CONTROLS = {ZWJ, ZWNJ}
WHITESPACE = {"\u0020", "\u0009", "\u000a", "\u000d"}

# consonants -> (iast_bare, aspirated)
CONSONANTS = {
    "क": ("k", False), "ख": ("kh", True), "ग": ("g", False), "घ": ("gh", True),
    "ङ": ("ṅ", False), "च": ("c", False), "छ": ("ch", True), "ज": ("j", False),
    "झ": ("jh", True), "ञ": ("ñ", False), "ट": ("ṭ", False), "ठ": ("ṭh", True),
    "ड": ("ḍ", False), "ढ": ("ḍh", True), "ण": ("ṇ", False), "त": ("t", False),
    "थ": ("th", True), "द": ("d", False), "ध": ("dh", True), "न": ("n", False),
    "प": ("p", False), "फ": ("ph", True), "ब": ("b", False), "भ": ("bh", True),
    "म": ("m", False), "य": ("y", False), "र": ("r", False), "ल": ("l", False),
    "व": ("v", False), "श": ("ś", False), "ष": ("ṣ", False), "स": ("s", False),
    "ह": ("h", False), "ळ": ("ḷ", False),  # ळ retroflex lateral (Vedic/Marathi)
}

# independent vowels -> (iast, length)
IND_VOWELS = {
    "अ": ("a", "short"), "आ": ("ā", "long"), "इ": ("i", "short"), "ई": ("ī", "long"),
    "उ": ("u", "short"), "ऊ": ("ū", "long"), "ऋ": ("ṛ", "short"), "ॠ": ("ṝ", "long"),
    "ऌ": ("l̥", "short"), "ॡ": ("l̥̄", "long"), "ए": ("e", "long"), "ऐ": ("ai", "long"),
    "ओ": ("o", "long"), "औ": ("au", "long"),
}

# dependent vowel signs -> (iast, length)
DEP_VOWELS = {
    "ा": ("ā", "long"), "ि": ("i", "short"), "ी": ("ī", "long"), "ु": ("u", "short"),
    "ू": ("ū", "long"), "ृ": ("ṛ", "short"), "ॄ": ("ṝ", "long"), "ॢ": ("l̥", "short"),
    "ॣ": ("l̥̄", "long"), "े": ("e", "long"), "ै": ("ai", "long"), "ो": ("o", "long"),
    "ौ": ("au", "long"),
}
INHERENT_A = ("a", "short")

VEDIC_ACCENTS = {"॑", "॒", "॓", "॔", "᳚", "᳛"}
JIHVA_UPADHMA = {"ᳵ": "ẖ", "ᳶ": "ḫ"}  # jihvāmūlīya / upadhmānīya (visarga allophones)
DANDA = {"।", "॥"}
NUMERALS = {chr(c) for c in range(0x0966, 0x0970)}
PRECOMPOSED_NUKTA = {chr(c) for c in range(0x0958, 0x0960)} | {"ऩ", "ऱ", "ऴ"}


def _cp(ch):
    return f"U+{ord(ch):04X}"


def classify(ch):
    if ch in CONSONANTS:
        return "consonant"
    if ch in IND_VOWELS:
        return "independent_vowel"
    if ch in DEP_VOWELS:
        return "dependent_vowel_sign"
    if ch == VIRAMA:
        return "virama"
    if ch == ANUSVARA:
        return "anusvara"
    if ch == VISARGA:
        return "visarga"
    if ch == CANDRABINDU:
        return "candrabindu"
    if ch == AVAGRAHA:
        return "avagraha"
    if ch == NUKTA:
        return "nukta"
    if ch in JOIN_CONTROLS:
        return "join_control"
    if ch == ZWSP:
        return "zero_width_space"
    if ch in WHITESPACE:
        return "whitespace"
    if ch in VEDIC_ACCENTS:
        return "vedic_accent"
    if ch in JIHVA_UPADHMA:
        return "visarga_allophone"
    if ch in DANDA:
        return "danda"
    if ch in NUMERALS:
        return "numeral"
    if ch in PRECOMPOSED_NUKTA:
        return "precomposed_nukta"
    return "unrecognized"


def _unit(index, unit, deva, utype, origin, aspirated, vowel_length, inherent, ortho_src, aksh_index):
    # fixed field order -> byte-stable serialization
    return {
        "index": index,
        "unit": unit,
        "devanagari": deva,
        "type": utype,
        "origin": origin,
        "aspirated": aspirated,
        "vowel_length": vowel_length,
        "inherent_inserted": inherent,
        "orthographic_source": ortho_src,
        "position": None,       # onset|final(len>1)|medial
        "is_initial": None,     # authoritative boundary role
        "is_final": None,       # authoritative boundary role
        "source_akshara_index": aksh_index,
    }


def parse(word):
    """Return the complete canonical Stage-1 record for a single Devanāgarī surface word."""
    original = word
    normalized = unicodedata.normalize("NFC", word)
    cps = list(normalized)
    n = len(cps)

    atomic = []
    aksharas = []
    warnings = []

    # ---- single-token whitespace contract (R-contract): classify occurrences, never tokenize -------------
    def _ws_run(k, step):
        j = k + step
        while 0 <= j < n:
            if classify(cps[j]) not in ("whitespace", "zero_width_space"):
                return False
            j += step
        return True

    def add_akshara(start_cp, end_cp, atom_start, atom_end):
        idx = len(aksharas)
        aksharas.append({
            "index": idx,
            "devanagari": "".join(cps[start_cp:end_cp]),
            "translit": "".join(u["unit"] for u in atomic[atom_start:atom_end]
                                if u["type"] in ("consonant", "vowel", "anusvara", "visarga", "nasalization")),
            "codepoints": [_cp(c) for c in cps[start_cp:end_cp]],
            "source_span": [start_cp, end_cp],
            "atomic_varna_indices": list(range(atom_start, atom_end)),
        })
        return idx

    def consume_trailing_marks(i, aksh_index):
        """Consume anusvāra / visarga / candrabindu / visarga-allophone / vedic accents after a base."""
        while i < n:
            cl = classify(cps[i])
            if cl == "anusvara":
                atomic.append(_unit(len(atomic), "ṃ", ANUSVARA, "anusvara", "anusvara", None, None, False,
                                    "combining_mark", aksh_index))
                i += 1
            elif cl == "visarga":
                atomic.append(_unit(len(atomic), "ḥ", VISARGA, "visarga", "visarga", None, None, False,
                                    "combining_mark", aksh_index))
                i += 1
            elif cl == "candrabindu":
                atomic.append(_unit(len(atomic), "m̐", CANDRABINDU, "nasalization", "nasalization", None, None,
                                    False, "combining_mark", aksh_index))
                i += 1
            elif cl == "visarga_allophone":
                atomic.append(_unit(len(atomic), JIHVA_UPADHMA[cps[i]], cps[i], "visarga", "visarga", None, None,
                                    False, "combining_mark", aksh_index))
                warnings.append({"class": "visarga_allophone", "codepoint": _cp(cps[i]),
                                 "action": "emitted_visarga_class_unit", "atomic_index": len(atomic) - 1})
                i += 1
            elif cl == "vedic_accent":
                warnings.append({"class": "vedic_accent_recorded", "codepoint": _cp(cps[i]),
                                 "action": "recorded_as_metadata_not_varna", "bearing_atomic_index": len(atomic) - 1})
                i += 1
            else:
                break
        return i

    def _skip_join_controls(j, sink):
        """Advance past ZWJ/ZWNJ, appending their positions to sink; return first non-join-control index."""
        while j < n and classify(cps[j]) == "join_control":
            sink.append(j)
            j += 1
        return j

    if n == 0:
        warnings.append({"class": "empty_input", "action": "no_content"})

    i = 0
    while i < n:
        ch = cps[i]
        cl = classify(ch)
        start_cp = i
        atom_start = len(atomic)

        if cl == "independent_vowel":
            iast, length = IND_VOWELS[ch]
            atomic.append(_unit(len(atomic), iast, ch, "vowel", "independent_vowel", None, length, False,
                                "independent_vowel", len(aksharas)))
            i += 1
            i = consume_trailing_marks(i, len(aksharas))
            add_akshara(start_cp, i, atom_start, len(atomic))

        elif cl == "consonant":
            aksh_index = len(aksharas)
            while True:
                c = cps[i]
                # unsupported / non-classical nukta base: NOT a recognized Sanskrit consonant (R10 + audit fix 3)
                if i + 1 < n and cps[i + 1] == NUKTA:
                    base = c + NUKTA
                    i += 2
                    dep = None
                    if i < n and classify(cps[i]) == "dependent_vowel_sign":
                        dep = DEP_VOWELS[cps[i]][0]
                        base += cps[i]
                        i += 1
                    atomic.append(_unit(len(atomic), base, base, "unsupported", "unresolved_nukta_base", None, None,
                                        False, "nukta_base", aksh_index))
                    warnings.append({"class": "non_classical_nukta", "codepoint": f"{_cp(c)}+{_cp(NUKTA)}",
                                     "action": "no_canonical_atomic_consonant_identity", "atomic_index": len(atomic) - 1,
                                     "dependent_vowel_metadata": dep, "inherent_a_suppressed": True})
                    # NO inherent अ, NO invented consonant. Continue a conjunct only if virāma+consonant follows.
                    if i < n and cps[i] == VIRAMA:
                        jc = []
                        j = _skip_join_controls(i + 1, jc)
                        if j < n and classify(cps[j]) == "consonant":
                            for p in jc:
                                warnings.append({"class": "join_control_in_conjunct", "codepoint": _cp(cps[p]),
                                                 "action": "orthographic_join_metadata_not_varna", "source_index": p})
                            i = j
                            continue
                    break
                iast, asp = CONSONANTS[c]
                atomic.append(_unit(len(atomic), iast, c, "consonant", "consonant", asp, None, False,
                                    "base_letter", aksh_index))
                cons_idx = len(atomic) - 1
                i += 1
                # continuation / vowel resolution for this recognized-consonant slot
                if i < n and cps[i] == VIRAMA:
                    jc = []
                    j = _skip_join_controls(i + 1, jc)          # ZWJ/ZWNJ are transparent join controls (fix 1)
                    if j < n and classify(cps[j]) == "consonant":
                        atomic[cons_idx]["origin"] = "virama_terminated"
                        atomic[cons_idx]["orthographic_source"] = "conjunct_constituent"
                        for p in jc:
                            warnings.append({"class": "join_control_in_conjunct", "codepoint": _cp(cps[p]),
                                             "action": "orthographic_join_metadata_not_varna", "source_index": p})
                        i = j                                    # jump to next conjunct consonant; no inherent अ
                        continue
                    # word-final / non-consonant continuation
                    atomic[cons_idx]["origin"] = "virama_terminated"
                    atomic[cons_idx]["orthographic_source"] = "virama_terminated"
                    i += 1                                       # consume the virāma only (join controls handled next loop)
                    if j < n and classify(cps[j]) == "independent_vowel":
                        warnings.append({"class": "virama_before_independent_vowel", "codepoint": _cp(cps[j]),
                                         "action": "anomalous_no_consonantal_continuation", "source_index": j})
                    break
                elif i < n and classify(cps[i]) == "dependent_vowel_sign":
                    iast_v, length = DEP_VOWELS[cps[i]]
                    atomic.append(_unit(len(atomic), iast_v, cps[i], "vowel", "dependent_vowel_sign", None, length,
                                        False, "dependent_vowel_sign", aksh_index))
                    i += 1
                    break
                else:
                    atomic.append(_unit(len(atomic), INHERENT_A[0], "", "vowel", "inherent_a", None, INHERENT_A[1],
                                        True, "inherent", aksh_index))
                    break
            i = consume_trailing_marks(i, aksh_index)
            add_akshara(start_cp, i, atom_start, len(atomic))

        elif cl == "join_control":
            # join control OUTSIDE a valid virāma-linked context: retain in source, warn, emit NO atomic varṇa (fix 1)
            i += 1
            warnings.append({"class": "join_control_out_of_context", "codepoint": _cp(ch),
                             "action": "retained_in_source_not_varna", "source_index": start_cp})
            add_akshara(start_cp, i, atom_start, len(atomic))    # empty atomic slice; keeps span lossless

        elif cl in ("whitespace", "zero_width_space"):
            # single-token contract (fix 5): never emit whitespace as a varṇa; classify + warn; do not tokenize
            i += 1
            if cl == "zero_width_space":
                wclass = "zero_width_space_retained"
            elif _ws_run(start_cp, -1) or _ws_run(start_cp, +1):
                wclass = "leading_trailing_whitespace"
            else:
                wclass = "multiple_tokens_or_whitespace"
            warnings.append({"class": wclass, "codepoint": _cp(ch), "action": "retained_in_source_not_varna",
                             "source_index": start_cp})
            add_akshara(start_cp, i, atom_start, len(atomic))    # empty atomic slice

        elif cl == "avagraha":
            atomic.append(_unit(len(atomic), "'", AVAGRAHA, "marker", "marker", None, None, False,
                                "combining_mark", len(aksharas)))
            warnings.append({"class": "avagraha_elision", "codepoint": _cp(ch),
                             "action": "marker_no_varna", "atomic_index": len(atomic) - 1})
            i += 1
            add_akshara(start_cp, i, atom_start, len(atomic))

        elif cl == "visarga_allophone":
            atomic.append(_unit(len(atomic), JIHVA_UPADHMA[ch], ch, "visarga", "visarga", None, None, False,
                                "combining_mark", len(aksharas)))
            warnings.append({"class": "visarga_allophone", "codepoint": _cp(ch),
                             "action": "emitted_visarga_class_unit", "atomic_index": len(atomic) - 1})
            i += 1
            add_akshara(start_cp, i, atom_start, len(atomic))

        elif cl == "danda":
            atomic.append(_unit(len(atomic), ch, ch, "marker", "marker", None, None, False, "punctuation",
                                len(aksharas)))
            warnings.append({"class": "punctuation_boundary", "codepoint": _cp(ch), "action": "marker_no_varna",
                             "atomic_index": len(atomic) - 1})
            i += 1
            add_akshara(start_cp, i, atom_start, len(atomic))

        elif cl == "numeral":
            atomic.append(_unit(len(atomic), ch, ch, "unsupported", "unsupported", None, None, False, "numeral",
                                len(aksharas)))
            warnings.append({"class": "numeral_unsupported", "codepoint": _cp(ch), "action": "retained_no_varna",
                             "atomic_index": len(atomic) - 1})
            i += 1
            add_akshara(start_cp, i, atom_start, len(atomic))

        elif cl in ("dependent_vowel_sign", "virama", "anusvara", "visarga", "candrabindu", "nukta", "vedic_accent"):
            atomic.append(_unit(len(atomic), ch, ch, "unsupported", "unsupported", None, None, False,
                                "combining_mark", len(aksharas)))
            warnings.append({"class": "orphan_combining_mark", "codepoint": _cp(ch),
                             "action": "retained_no_base", "atomic_index": len(atomic) - 1, "mark_class": cl})
            i += 1
            add_akshara(start_cp, i, atom_start, len(atomic))

        else:  # unrecognized or precomposed_nukta surviving NFC
            klass = "non_classical_nukta" if cl == "precomposed_nukta" else "unrecognized_codepoint"
            atomic.append(_unit(len(atomic), ch, ch, "unsupported", "unsupported", None, None, False,
                                "unsupported", len(aksharas)))
            warnings.append({"class": klass, "codepoint": _cp(ch), "action": "retained_raw",
                             "atomic_index": len(atomic) - 1})
            i += 1
            add_akshara(start_cp, i, atom_start, len(atomic))

    # boundary roles (fix 2): scalar position + authoritative booleans
    length = len(atomic)
    for k, u in enumerate(atomic):
        u["position"] = "onset" if k == 0 else "final" if k == length - 1 else "medial"
        u["is_initial"] = (k == 0)
        u["is_final"] = (k == length - 1)

    varna_counts = {}
    for u in atomic:
        varna_counts[u["unit"]] = varna_counts.get(u["unit"], 0) + 1
    geminations = []
    run_start, run_len = 0, 1
    for k in range(1, len(atomic) + 1):
        same = (k < len(atomic) and atomic[k]["type"] == "consonant"
                and atomic[k]["unit"] == atomic[run_start]["unit"] and atomic[k - 1]["unit"] == atomic[run_start]["unit"]
                and atomic[run_start]["type"] == "consonant")
        if same:
            run_len += 1
        else:
            if run_len >= 2 and atomic[run_start]["type"] == "consonant":
                geminations.append({"unit": atomic[run_start]["unit"], "start_atomic_index": run_start, "count": run_len})
            run_start, run_len = k, 1

    inherent_indices = [u["index"] for u in atomic if u["inherent_inserted"]]
    translit = "".join(u["unit"] for u in atomic
                       if u["type"] in ("consonant", "vowel", "anusvara", "visarga", "nasalization"))

    return {
        "word_devanagari": original,
        "normalized_devanagari": normalized,
        "transliteration_iast": translit,
        "normalization": {"form": "NFC", "changed": normalized != original, "notes": []},
        "aksharas": aksharas,
        "atomic_varnas": atomic,
        "inherent_vowel_insertions": {"count": len(inherent_indices), "atomic_indices": inherent_indices},
        "multiplicity": {"varna_counts": varna_counts, "geminations": geminations},
        "derived_noncanonical": {"resolved_pronunciation_candidate": None},
        "warnings": warnings,
        "parser_spec_version": SPEC_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


def canonical_structure(record):
    """Normalization-independent structural projection: everything EXCEPT the original-input echo and the
    normalization metadata. Used to compare NFC- vs NFD-form inputs (audit fix 6, invariant 9)."""
    return {k: v for k, v in record.items() if k not in ("word_devanagari", "normalization")}


def serialize(record):
    """Deterministic, byte-stable JSON serialization (fixed field order; unicode preserved; trailing newline)."""
    return json.dumps(record, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


if __name__ == "__main__":
    import sys
    for w in sys.argv[1:]:
        print(serialize(parse(w)))
