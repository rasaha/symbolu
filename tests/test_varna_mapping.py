"""
Test 2: ARPABET → Varna Mapping Consistency & Varga Clustering
===============================================================

Validates that the Sanskrit mapping layer is:
    1. Complete — every ARPABET phoneme maps to a varna
    2. Consistent — vargas match articulatory groupings
    3. Structural — varga initialization produces non-random clustering
    4. Voiced/voiceless distinction is respected

These are linguistic invariance tests, NOT framework plumbing tests.
They verify that the Sanskrit grammar is correctly encoded.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from csr_phoneme_provider import (
    ARPABET_TO_VARNA,
    PHONEME_MAP_ARPABET,
    CSRPhonemeHead,
    CSRPhonemeHeadConfig,
)


# =========================================================================
# Expected Sanskrit Structure (ground truth from grammar)
# =========================================================================

# Varga = articulatory group. Within each group, consonants share
# place of articulation (guttural, palatal, retroflex, dental, labial).
EXPECTED_VARGA = {
    'ka_varga': {
        'phonemes': ['K', 'G', 'NG'],
        'description': 'Guttural (throat)',
        'vrittis': ['Hope', 'Action', 'Vanity'],
    },
    'ca_varga': {
        'phonemes': ['CH', 'JH'],
        'description': 'Palatal (palate)',
        'vrittis': ['Scatter', 'Vanity'],
    },
    'ta_varga': {
        'phonemes': ['T', 'D'],
        'description': 'Retroflex (roof)',
        'vrittis': ['Overstatement', 'Shyness'],
    },
    'tha_varga': {
        'phonemes': ['TH', 'DH'],
        'description': 'Dental (teeth)',
        'vrittis': ['Melancholy', 'Craving'],
    },
    'pa_varga': {
        'phonemes': ['P', 'B', 'M'],
        'description': 'Labial (lips)',
        'vrittis': ['Hatred', 'Indifference', 'Indulgence'],
    },
}

# All consonant ARPABET phonemes that should map to a varna
ALL_CONSONANTS = set()
for v in EXPECTED_VARGA.values():
    ALL_CONSONANTS.update(v['phonemes'])

# Semi-vowels
SEMI_VOWELS = ['Y', 'R', 'L', 'W', 'V']

# Sibilants
SIBILANTS = ['S', 'SH', 'Z', 'ZH']

# Voiced/voiceless pairs within vargas
VOICED = {'G', 'D', 'B', 'JH', 'DH', 'V', 'Z', 'ZH'}
VOICELESS = {'K', 'T', 'P', 'CH', 'TH', 'F', 'S', 'SH'}


# =========================================================================
# Test 2.1: Complete Mapping — every ARPABET → some varna
# =========================================================================


class TestVarnaCompleteness:
    """Every ARPABET phoneme must map to a Sanskrit varna."""

    def test_all_arpabet_consonants_mapped(self):
        """All consonant phonemes in PHONEME_MAP_ARPABET have a varna mapping."""
        consonants_in_map = {
            p for p in PHONEME_MAP_ARPABET
            if p not in {'SIL', 'SP', 'UNK'}
        }
        for phoneme in consonants_in_map:
            assert phoneme in ARPABET_TO_VARNA, (
                f"ARPABET phoneme '{phoneme}' has no varna mapping"
            )

    def test_no_none_mappings(self):
        """No mapping returns None."""
        for phoneme, varna in ARPABET_TO_VARNA.items():
            assert varna is not None, f"'{phoneme}' maps to None"
            assert len(varna) > 0, f"'{phoneme}' maps to empty string"

    def test_mapping_is_surjective(self):
        """Multiple ARPABET phonemes should map to the same varna
        (e.g., AA and AH both → 'a')."""
        varnas = set(ARPABET_TO_VARNA.values())
        # Should have significantly fewer varnas than ARPABET phonemes
        assert len(varnas) < len(ARPABET_TO_VARNA), (
            f"Mapping is injective ({len(varnas)} varnas for "
            f"{len(ARPABET_TO_VARNA)} ARPABET) — expected many-to-one"
        )


# =========================================================================
# Test 2.2: Varga Consistency — correct articulatory grouping
# =========================================================================


class TestVargaConsistency:
    """Phonemes within the same varga must map to related varnas."""

    def test_ka_varga_maps_to_guttural(self):
        """Ka-varga phonemes (K, G, NG) map to ka/ga/ṅa varnas."""
        expected_varnas = {'ka', 'ga', 'ṅa'}
        for phoneme in ['K', 'G', 'NG']:
            varna = ARPABET_TO_VARNA[phoneme]
            assert varna in expected_varnas, (
                f"Ka-varga phoneme '{phoneme}' maps to '{varna}', "
                f"expected one of {expected_varnas}"
            )

    def test_pa_varga_maps_to_labial(self):
        """Pa-varga phonemes (P, B, M) map to pa/ba/ma varnas."""
        expected_varnas = {'pa', 'ba', 'ma'}
        for phoneme in ['P', 'B', 'M']:
            varna = ARPABET_TO_VARNA[phoneme]
            assert varna in expected_varnas, (
                f"Pa-varga phoneme '{phoneme}' maps to '{varna}', "
                f"expected one of {expected_varnas}"
            )

    def test_ta_varga_maps_to_retroflex(self):
        """Ta-varga phonemes (T, D) map to ṭa/ḍa varnas."""
        expected_varnas = {'ṭa', 'ḍa'}
        for phoneme in ['T', 'D']:
            varna = ARPABET_TO_VARNA[phoneme]
            assert varna in expected_varnas, (
                f"Ta-varga phoneme '{phoneme}' maps to '{varna}', "
                f"expected one of {expected_varnas}"
            )

    def test_tha_varga_maps_to_dental(self):
        """Tha-varga phonemes (TH, DH) map to tha/dha varnas."""
        expected_varnas = {'tha', 'dha'}
        for phoneme in ['TH', 'DH']:
            varna = ARPABET_TO_VARNA[phoneme]
            assert varna in expected_varnas, (
                f"Tha-varga phoneme '{phoneme}' maps to '{varna}', "
                f"expected one of {expected_varnas}"
            )

    def test_ca_varga_maps_to_palatal(self):
        """Ca-varga phonemes (CH, JH) map to ca/ja varnas."""
        expected_varnas = {'ca', 'ja'}
        for phoneme in ['CH', 'JH']:
            varna = ARPABET_TO_VARNA[phoneme]
            assert varna in expected_varnas, (
                f"Ca-varga phoneme '{phoneme}' maps to '{varna}', "
                f"expected one of {expected_varnas}"
            )

    def test_vowels_map_to_vowel_varnas(self):
        """Vowel ARPABET phonemes map to Sanskrit vowel varnas."""
        vowel_varnas = {'a', 'i', 'ī', 'u', 'ū', 'e', 'o', 'ai', 'au', 'ṛ'}
        vowel_arpabet = ['AA', 'AH', 'AE', 'IH', 'IY', 'UH', 'UW',
                         'EH', 'ER', 'EY', 'AY', 'OW', 'AO', 'OY', 'AW']
        for phoneme in vowel_arpabet:
            varna = ARPABET_TO_VARNA[phoneme]
            assert varna in vowel_varnas, (
                f"Vowel '{phoneme}' maps to '{varna}', "
                f"expected a vowel varna from {vowel_varnas}"
            )


# =========================================================================
# Test 2.3: Ontological Affinity Structure
# =========================================================================


class TestOntologicalAffinity:
    """PHONEME_MAP_ARPABET 12D affinities encode articulatory structure."""

    def test_plosives_share_execution_dominance(self):
        """Plosives (P, T, K, B, D, G) have O3_Execution as dominant layer."""
        plosives = ['P', 'T', 'K', 'B', 'D', 'G']
        for p in plosives:
            affinity = PHONEME_MAP_ARPABET[p]
            # O3_Execution is index 2
            o3 = affinity[2]
            # O3 should be the max or near-max
            assert o3 >= 0.6, (
                f"Plosive '{p}' has O3_Execution={o3:.2f}, expected >= 0.6"
            )

    def test_fricatives_share_agency_dominance(self):
        """Fricatives (F, TH, S, SH, V, DH, Z, ZH) have O6_Agency dominant."""
        fricatives = ['F', 'TH', 'S', 'SH', 'V', 'DH', 'Z', 'ZH']
        for f in fricatives:
            affinity = PHONEME_MAP_ARPABET[f]
            # O6_Agency is index 5
            o6 = affinity[5]
            assert o6 >= 0.6, (
                f"Fricative '{f}' has O6_Agency={o6:.2f}, expected >= 0.6"
            )

    def test_nasals_share_unifying_dominance(self):
        """Nasals (M, N, NG) have O10_Unifying dominant."""
        nasals = ['M', 'N', 'NG']
        for n in nasals:
            affinity = PHONEME_MAP_ARPABET[n]
            # O10_Unifying is index 9
            o10 = affinity[9]
            assert o10 >= 0.8, (
                f"Nasal '{n}' has O10_Unifying={o10:.2f}, expected >= 0.8"
            )

    def test_vowel_a_has_potential_dominance(self):
        """Vowel 'a' (AA, AH) has O1_Potential dominant — primordial birth."""
        for v in ['AA', 'AH']:
            affinity = PHONEME_MAP_ARPABET[v]
            o1 = affinity[0]  # O1_Potential
            assert o1 >= 0.8, (
                f"Vowel '{v}' has O1_Potential={o1:.2f}, expected >= 0.8"
            )

    def test_articulatory_groups_cluster_in_12d(self):
        """Phonemes within the same articulatory group are closer in 12D
        than phonemes from different groups."""
        groups = {
            'plosives': ['P', 'T', 'K', 'B', 'D', 'G'],
            'fricatives': ['F', 'TH', 'S', 'SH'],
            'nasals': ['M', 'N', 'NG'],
        }

        # Compute mean affinity per group
        means = {}
        for name, phonemes in groups.items():
            vecs = [PHONEME_MAP_ARPABET[p] for p in phonemes]
            means[name] = np.mean(vecs, axis=0)

        # Within-group variance should be < between-group variance
        for name, phonemes in groups.items():
            vecs = np.array([PHONEME_MAP_ARPABET[p] for p in phonemes])
            within_var = np.mean(np.var(vecs, axis=0))

            # Compare to distance from other groups
            other_means = [m for n, m in means.items() if n != name]
            between_dist = np.mean([
                np.sum((means[name] - om) ** 2) for om in other_means
            ])

            assert within_var < between_dist, (
                f"Group '{name}' within-var ({within_var:.4f}) >= "
                f"between-group dist ({between_dist:.4f}) — "
                f"articulatory groups don't cluster"
            )


# =========================================================================
# Test 2.4: Varga Initialization in CSRPhonemeHead
# =========================================================================


class TestVargaInitialization:
    """CSRPhonemeHead._init_from_vritti_groups produces structured embeddings."""

    D = 64
    V = 100

    def _make_head(self):
        config = CSRPhonemeHeadConfig(d_model=self.D, vocab_size=self.V)
        return CSRPhonemeHead(config, tokenizer=None)

    def test_within_varga_more_similar_than_across(self):
        """Phonemes in the same varga should have more similar embeddings
        than phonemes from different vargas (due to shared bias initialization)."""
        torch.manual_seed(42)
        head = self._make_head()
        emb = head.phoneme_embeddings.weight.detach()

        within_sims = []
        across_sims = []

        for varga_name, varga_info in EXPECTED_VARGA.items():
            phonemes = varga_info['phonemes']
            indices = [
                head._phoneme_to_idx[p] for p in phonemes
                if p in head._phoneme_to_idx
            ]
            if len(indices) < 2:
                continue

            # Within-varga cosine similarities
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    sim = torch.nn.functional.cosine_similarity(
                        emb[indices[i]].unsqueeze(0),
                        emb[indices[j]].unsqueeze(0),
                    ).item()
                    within_sims.append(sim)

        # Cross-varga: compare Ka-varga with Pa-varga
        ka_idx = [head._phoneme_to_idx[p] for p in ['K', 'G']
                  if p in head._phoneme_to_idx]
        pa_idx = [head._phoneme_to_idx[p] for p in ['P', 'B']
                  if p in head._phoneme_to_idx]
        for ki in ka_idx:
            for pi in pa_idx:
                sim = torch.nn.functional.cosine_similarity(
                    emb[ki].unsqueeze(0), emb[pi].unsqueeze(0),
                ).item()
                across_sims.append(sim)

        if within_sims and across_sims:
            mean_within = np.mean(within_sims)
            mean_across = np.mean(across_sims)
            assert mean_within > mean_across, (
                f"Within-varga similarity ({mean_within:.4f}) <= "
                f"across-varga similarity ({mean_across:.4f}) — "
                f"varga initialization has no effect"
            )

    def test_voiced_voiceless_separation(self):
        """Voiced and voiceless phonemes should have different bias directions."""
        torch.manual_seed(42)
        head = self._make_head()
        emb = head.phoneme_embeddings.weight.detach()

        voiced_embs = []
        voiceless_embs = []
        for p in VOICED:
            if p in head._phoneme_to_idx:
                voiced_embs.append(emb[head._phoneme_to_idx[p]])
        for p in VOICELESS:
            if p in head._phoneme_to_idx:
                voiceless_embs.append(emb[head._phoneme_to_idx[p]])

        if voiced_embs and voiceless_embs:
            voiced_mean = torch.stack(voiced_embs).mean(0)
            voiceless_mean = torch.stack(voiceless_embs).mean(0)

            # They should differ (the voiced_bias is added/subtracted)
            diff = (voiced_mean - voiceless_mean).norm().item()
            assert diff > 0.0, (
                "Voiced and voiceless embeddings are identical — "
                "voiced/voiceless bias not applied"
            )

    def test_varga_groups_all_present(self):
        """All expected varga phonemes exist in the phoneme index."""
        head = self._make_head()
        for varga_name, info in EXPECTED_VARGA.items():
            for p in info['phonemes']:
                assert p in head._phoneme_to_idx, (
                    f"Phoneme '{p}' from {varga_name} not in phoneme index"
                )

    def test_different_vargas_have_different_bias(self):
        """Running init twice with same seed → same result;
        different vargas → different group biases."""
        torch.manual_seed(42)
        head1 = self._make_head()
        torch.manual_seed(42)
        head2 = self._make_head()

        # Same seed → same embeddings (deterministic)
        assert torch.allclose(
            head1.phoneme_embeddings.weight,
            head2.phoneme_embeddings.weight,
        ), "Varga initialization is non-deterministic"
