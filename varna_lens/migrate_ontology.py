#!/usr/bin/env python3
"""One-shot migration: rename the moral polarity fields to the binding/liberating ontology.

  positive  ->  liberating_state   (sublimated, unbinding, expansive, dharma/mokṣa-oriented expression)
  negative  ->  binding_state      (worldly, contractive, attachment-forming, bondage-producing expression)

The varṇa MEANINGS are preserved verbatim — only their ontological ROLE label changes. No pole is ever
chosen from an external semantic judgment (good/bad, useful/useless, auspicious/inauspicious); the
phoneme chain alone determines which state is expressed. Key order is preserved so diffs stay minimal.
"""
import json, pathlib

JPATH = pathlib.Path(__file__).with_name("lexicon_authoritative.json")
RENAME = {"positive": "liberating_state", "negative": "binding_state"}


def _rename_entry(entry):
    out = {}
    for k, v in entry.items():
        out[RENAME.get(k, k)] = v
    return out


def main():
    data = json.loads(JPATH.read_text(encoding="utf-8"))

    for section in ("consonants", "vowels"):
        data[section] = {k: _rename_entry(v) for k, v in data[section].items()}

    data["_legend"] = {
        "liberating_state": ("liberating expression of the varṇa — sublimated, unbinding, expansive, "
                             "dharma/mokṣa-oriented (consonant), or the active acoustic essence (vowel)"),
        "binding_state": ("binding expression of the varṇa — worldly, contractive, attachment-forming, "
                          "bondage-producing (consonant), or the worldly acoustic essence (vowel)"),
        "_ontology_note": ("The framework asks ONE question of every acoustic tendency: does it BIND "
                           "consciousness (contractive, attachment-forming) or RELEASE it (expansive, "
                           "unbinding)? These are states of expression, NOT moral judgements. Poles are "
                           "never selected from external labels about the referent (good/bad, "
                           "useful/useless, auspicious/inauspicious). The phoneme chain determines the "
                           "expressed state; the whole-word reading is then labelled binding-dominant, "
                           "liberating-dominant, or mixed — derived, never supplied."),
        "_state_reference_note": ("The lens reads the WORLDLY (bīja) tendency of every varṇa by default. "
                                  "For a CONSONANT the worldly tendency is its binding_state (e.g. Ka=Hope, "
                                  "La=Cruelty); for a VOWEL the worldly tendency is its liberating_state "
                                  "(active essence, e.g. a=Birth, ai=Welfare). This field asymmetry is "
                                  "intentional. The +/− SIGN in a reading is affirmed(+)/dissolving(−) from "
                                  "sound-order, NOT a field swap; the dissolved worldly tendency eases "
                                  "toward the consonant's liberating_state counter-field."),
        "_source_corrected": data["_legend"].get("_source_corrected", ""),
    }

    data["_expanded_properties_note"] = (
        "expanded_properties = source acoustic-root literature (P.R. Sarkar, Varṇa Vijñāna) as "
        "INTERPRETIVE METADATA only. It enriches reading/authoring but does NOT affect the reading, "
        "which uses ONLY binding_state/liberating_state. Reading fields: binding_state, liberating_state. "
        "Metadata fields: expanded_properties, source_vritti, source_notes.")

    JPATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pos = json.dumps(data, ensure_ascii=False)
    print(f"migrated; remaining literal 'positive'/'negative' field tokens: "
          f"{pos.count(chr(34)+'positive'+chr(34))}/{pos.count(chr(34)+'negative'+chr(34))}")


if __name__ == "__main__":
    main()
