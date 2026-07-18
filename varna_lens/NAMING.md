# Naming — canonical (PSE)

> **Status:** authoritative naming decision. **Date:** 2026-06-25.
> Supersedes the earlier "ASG / Acoustic Symbol(ic) Generation" name.

## Decision

The architecture is **PSE — Phoneme Symbolic Engine.**

Rationale (architectural correctness, not branding): the engine's primitive is the **phoneme/varṇa**, reached
by grapheme→phoneme decomposition of text; everything after decomposition is **symbolic** (discrete,
deterministic, rule-based). The engine never processes a waveform, spectrogram, pitch, or prosody — so
"Acoustic" was a misnomer that wrongly implied speech-signal / waveform / acoustic-representation-learning
(wav2vec, HuBERT, Whisper). "Phoneme Symbolic Engine" names the actual primitive (phoneme), the actual
space (symbolic), and the actual artifact (a deterministic engine), and it is scope-neutral across the
engine's uses (analysis, generation, rendering). The sound is only the **indexing mechanism**, not the
substrate.

## Term mapping

| Old | New | Notes |
|---|---|---|
| ASG (Acoustic Symbol/Symbolic Generation/Geometry) | **PSE (Phoneme Symbolic Engine)** | the architecture / umbrella |
| "Acoustic Trajectory" | **"Phoneme Trajectory"** | the Layer-2 schema term |
| `asg_renderer.py` | **`pse_renderer.py`** | `asg_renderer.py` kept as a deprecated re-export shim |
| `ASG_RENDERER_V2_DESIGN.md` | **`PSE_RENDERER_V2_DESIGN.md`** | |
| `ASG_RENDERER_V3_ARCHITECTURE.md` | **`PSE_RENDERER_V3_ARCHITECTURE.md`** | |
| `ASG_VC_BRIEF.md` | **`PSE_VC_BRIEF.md`** | |

## What deliberately does NOT change

- **`varṇa` / `varna_lens` / `lexicon_authoritative.json`** — `varṇa` correctly names the **first, replaceable
  vocabulary**, not the architecture. The engine is vocabulary-agnostic (IPA, language-specific inventories
  could follow); the vocabulary keeps its own name. Do not purge "varṇa."
- **Historical falsification records** (`PREREG_ACOUSTIC_*`, `RESULTS_ACOUSTIC_*`, etc.) — "acoustic" there
  refers to the genuine concept and the experiments as run; they are an immutable record and are left as-is.
- **Scientific claims** — none. This is a naming correction only. It removes the false "acoustic = waveform"
  implication (an accuracy/honesty improvement); it asserts nothing new.

## Naming rule going forward

- **Architecture / engine:** PSE (Phoneme Symbolic Engine).
- **Generation-facing product layer (if named separately):** PSG (Phoneme Symbolic Generation).
- **Vocabulary:** varṇa (one vocabulary among possible future inventories).
- Avoid **PSR** (collides with Predictive State Representation) and **VSG** (binds the architecture to one
  vocabulary).
