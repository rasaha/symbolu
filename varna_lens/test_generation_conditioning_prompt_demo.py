"""Tests for the generation-conditioning PROMPT demo — NO MODEL, NO GENERATION, NO SCORING, NO NETWORK.

Hermetic: patches the g2p function so no nltk/cmudict is needed. Proves: no ML libs; all six arms
A/R/S/C/X/D printed; identical wrapper across arms; required banner present; no forbidden ontology/
Sanskrit/semantic-truth claims; no generated-answer field; dictionary-only arm is clearly separate
from the real resonance arm; no result files written.

    python3 varna_lens/test_generation_conditioning_prompt_demo.py
"""
from __future__ import annotations
import os as _os, sys as _sys
# RETIRED historical-regression: validates the retired Layer-2 bridge, defined only under the pre-B1.12
# lexicon. Skips under the active B1.12 mapping; runs its original assertions under the old-lexicon
# fixture. See experiments/retired/layer2_bridge/README.md.
if not _os.environ.get("VARNA_LENS_MAPPING", "").endswith("lexicon_authoritative.json"):
    if "pytest" in _sys.modules:
        import pytest as _pytest
        _pytest.skip("retired Layer-2 bridge test (needs old-lexicon fixture)", allow_module_level=True)
    else:
        print("SKIP: retired Layer-2 bridge test (set VARNA_LENS_MAPPING=<repo>/varna_lens/lexicon_authoritative.json to run)")
        raise SystemExit(0)

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import varna_lens as V                               # noqa: E402  (g2p lives here)
import sample_text_rule_harness as H                 # noqa: E402
import generation_conditioning_prompt_demo as G      # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


_FAKE = {
    "love": ([("C", "la", "L"), ("V", "a", "AH1"), ("C", "va", "V")], []),
    "mercy": ([("C", "ma", "M"), ("V", "a", "ER1"), ("C", "sa", "S"), ("V", "ii", "IY0")], []),
    "anger": ([("V", "a", "AE1"), ("C", "nga", "NG"), ("C", "ga", "G"), ("V", "a", "ER0")], []),
    "peace": ([("C", "pa", "P"), ("V", "ii", "IY1"), ("C", "sa", "S")], []),
}


def _fake_cmudict(word):
    return _FAKE.get(word.lower(), ([], [f"'{word}' not in cmudict"]))


def _with_fake(fn):
    orig = V.phonemes_cmudict
    V.phonemes_cmudict = _fake_cmudict            # harness g2p_units() calls V.phonemes_cmudict
    try:
        return fn()
    finally:
        V.phonemes_cmudict = orig


def test_all_six_arms_built():
    prompts = _with_fake(lambda: G.build_prompts("Write about love.", "love"))
    _check("all six arms A/R/S/C/X/D present", set(prompts) == set(G.ARMS))


def test_identical_wrapper_across_arms():
    prompts = _with_fake(lambda: G.build_prompts("Write about love.", "love"))
    for arm, p in prompts.items():
        _check(f"arm {arm} starts with the shared frame header",
               p.startswith("Soft orientation, not a definition: "))
        _check(f"arm {arm} carries the shared frame suffix",
               "Use this only as a gentle tonal/conceptual guide while following the task exactly."
               in p)
        _check(f"arm {arm} ends with the same Task block", p.endswith("Task:\nWrite about love."))


def test_shared_frame_identical_only_core_differs():
    # everything except the {conditioning} core must be byte-identical across arms
    prompts = _with_fake(lambda: G.build_prompts("Write about love.", "love"))
    frames = set()
    for arm, p in prompts.items():
        mid = p.split("\n\nTask:\n")[0]
        # strip the arm core out of the shared frame -> what remains must match across arms
        core = mid[len("Soft orientation, not a definition: "):]
        core = core[:-len(". Use this only as a gentle tonal/conceptual guide "
                          "while following the task exactly.")]
        frame = mid.replace(core, "{CORE}")
        frames.add(frame)
    _check("shared frame is byte-identical across all arms (only core differs)", len(frames) == 1)


def test_only_conditioning_slot_differs():
    prompts = _with_fake(lambda: G.build_prompts("Write about love.", "love"))
    # strip the shared wrapper head + task tail -> the middle (conditioning) must differ across arms
    mids = {arm: p.split("\n\nTask:\n")[0] for arm, p in prompts.items()}
    _check("conditioning texts differ across arms", len(set(mids.values())) == len(G.ARMS))


def test_banner_present():
    out = _with_fake(lambda: G.render_demo("Write about love.", "love"))
    _check("banner present (top + bottom)", out.count(G.BANNER) >= 2)


def test_no_forbidden_claims():
    for kw in ("love", "mercy"):
        out = _with_fake(lambda kw=kw: G.render_demo("Write about it.", kw)).lower()
        for bad in G.FORBIDDEN_CLAIMS:
            _check(f"{kw}: no forbidden claim {bad!r}", bad not in out)


def test_no_generated_answer_field():
    out = _with_fake(lambda: G.render_demo("Write about love.", "love")).lower()
    for tok in ("answer:", "response:", "generated text:", "completion:", "assistant:"):
        _check(f"no generated-answer marker {tok!r}", tok not in out)
    _check("explicit no-generation confirmation present", "no_generated_answer_produced: true" in out)


def test_dictionary_arm_distinct_from_resonance():
    prompts = _with_fake(lambda: G.build_prompts("Write about love.", "love"))
    # distinction is now in CONTENT (no per-arm self-label): D carries the dictionary sense +
    # synonyms; A carries the L2 process synthesis. They must differ.
    _check("D core carries the dictionary sense", "love — deep affection or attachment" in prompts["D"])
    _check("D core lists related senses", "related senses:" in prompts["D"])
    _check("A core is the L2 process synthesis", "is the resolving principle" in prompts["A"])
    _check("A and D differ", prompts["A"] != prompts["D"])
    # no per-arm self-label leaks into any prompt
    for arm, p in prompts.items():
        for label in ("(control", "latent-process reading", "Dictionary/synonym field",
                      "randomized orientation", "scrambled-attachment", "Sound-structure only"):
            _check(f"arm {arm}: no self-label {label!r}", label not in p)


def test_g2p_unavailable_arms_marked_not_crash():
    # 'zznotword' is not in the fake dict -> g2p empty -> A/S/C marked unavailable; R/X/D still built
    prompts = _with_fake(lambda: G.build_prompts("Write.", "zznotword"))
    _check("arm A marked G2P_UNAVAILABLE", "G2P_UNAVAILABLE" in prompts["A"])
    _check("arm X still constructed", "no additional symbolic orientation" in prompts["X"])
    _check("arm D still constructed (frozen table fallback)",
           "no dictionary entry" in prompts["D"] or "related senses:" in prompts["D"])


def test_arm_length_parity_within_25pct():
    # parity harmonization (audit dc407ea): no arm's full-prompt char length may differ from A by
    # >25%, across the demo's built-in dictionary words. No model, no scoring.
    for kw in ("mercy", "love", "anger", "peace"):
        prompts = _with_fake(lambda kw=kw: G.build_prompts("Write about it.", kw))
        la = len(prompts["A"])
        for arm in G.ARMS:
            d = 100.0 * (len(prompts[arm]) - la) / la
            _check(f"{kw}: arm {arm} within +/-25% of A by chars ({d:+.1f}%)", abs(d) <= 25.0)


def test_no_result_files_written(tmp=pathlib.Path(HERE)):
    before = set(p.name for p in tmp.iterdir())
    _with_fake(lambda: G.render_demo("Write about mercy.", "mercy"))
    after = set(p.name for p in tmp.iterdir())
    _check("demo writes no files", before == after)


def test_no_ml_libs_imported():
    _check("no torch/transformers/openai/anthropic imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))


def main():
    print("generation_conditioning_prompt_demo — prompt-construction tests (no model, no generation)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll generation-conditioning prompt-demo tests passed.")


if __name__ == "__main__":
    main()
