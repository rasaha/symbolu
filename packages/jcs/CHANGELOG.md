# Changelog — ugence-jcs

All notable changes to this distribution are recorded here.

## 0.1.0 — unreleased

### Added

* Initial extraction of the RFC 8785 (JCS) + Action-Profile canonicalizer from
  `cer_v0_3/cleanroom/canon.py` into an independently installable, standard-library-only,
  authority-neutral leaf distribution: `canonical_string`, `canonical_bytes`, and the
  canonicalization error taxonomy (`JcsError`, `BareNumberError`,
  `NonFiniteNumberError`, `NonNFCError`, `UnsupportedTypeError`,
  `DuplicateSetElementError`) with their `category` keys unchanged.
* Byte-preservation vector suite capturing the canonical output of the
  pre-extraction implementation.
* Action-Profile behaviour suite (UTF-16 member ordering, escaping, bare-number
  rejection, set-path ordering and duplicate rejection, NFC validation without
  rewriting).
* Leaf-boundary suite: static import scan plus an isolated-subprocess import probe,
  a zero-runtime-dependency assertion, and an assertion that the package defines no
  authority vocabulary.
* `verify_jcs_distribution.py`: wheel/sdist build, wheel content audit, `--no-index`
  clean-venv install, frozen-vector reproduction and cross-process determinism.

### Changed (in the consuming repository, not in this distribution)

* `cer_v0_3/cleanroom/canon.py` became a re-export of `ugence_jcs.canon`, and
  `cer_v0_3/cleanroom/errors.py` re-exports the canonicalization taxonomy, with
  `CleanRoomError` bound to `JcsError`. The clean-room byte stream and the frozen
  CER V0.2 identity digests are unchanged.
* `cer_v0_3/tests/test_forbidden_imports.py` permits exactly one first-party import
  (`ugence_jcs`) and adds two tests re-proving that the extracted leaf is itself
  free of reference code and stdlib-only.

### Not changed

* The production CER identity path (`cer_v0_3/envelope.py` →
  `action_gate_ref.projection` + frozen `cer_v0_2`) is untouched and is not
  switched to this distribution.
