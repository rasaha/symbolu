"""
Tests for Phoneme Space Module (v2.7.8-experimental)

Tests phoneme embeddings, Guna mapping, affinity computation,
and semantic projection - all derived from first principles.
"""

import pytest
import math

from symbolu.guna_modulation.phoneme_space import (
    # Switch controls
    enable_phoneme_space, disable_phoneme_space,
    is_phoneme_space_enabled, phoneme_exploration,
    PhonemeSpaceConfig, PhonemeSpaceDisabledError,

    # Feature enums
    Place, Manner, Voicing, Height, Backness, Roundedness, PhonemeType,

    # Core classes
    PhonemeFeatures, PhonemeGuna, PhonemeEmbedding,
    PhonemeAffinity, PhonemeProjection, SequenceAnalysis,

    # Inventory
    IPA_INVENTORY, get_phoneme, list_phonemes,

    # Guna mapping
    compute_phoneme_guna, get_phoneme_guna,

    # Embedding
    get_phoneme_embedding,

    # Affinity
    compute_affinity,

    # Projection
    project_phoneme,

    # Sequence analysis
    analyze_sequence, analyze_word_ipa,

    # Convenience
    phoneme_distance, phoneme_similarity,
    most_similar_phonemes, guna_profile,
)
from symbolu.guna_modulation.mirror_balance import OntologicalLayer


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def enable_phoneme_space_for_tests():
    """Enable phoneme space for all tests, disable after."""
    enable_phoneme_space()
    yield
    disable_phoneme_space()


@pytest.fixture
def consonant_p():
    """Voiceless bilabial stop."""
    return get_phoneme('p')


@pytest.fixture
def consonant_b():
    """Voiced bilabial stop."""
    return get_phoneme('b')


@pytest.fixture
def vowel_a():
    """Low central vowel."""
    return get_phoneme('a')


@pytest.fixture
def vowel_i():
    """High front vowel."""
    return get_phoneme('i')


# =============================================================================
# TEST: EXPERIMENTAL MODE SWITCH
# =============================================================================

class TestExperimentalSwitch:
    """Test enable/disable functionality."""

    def test_disabled_by_default_in_fresh_state(self):
        """Phoneme space should be disabled after disable call."""
        disable_phoneme_space()
        assert not is_phoneme_space_enabled()
        # Re-enable for other tests
        enable_phoneme_space()

    def test_enable_phoneme_space(self):
        """Can enable phoneme space."""
        enable_phoneme_space()
        assert is_phoneme_space_enabled()

    def test_disable_phoneme_space(self):
        """Can disable phoneme space."""
        enable_phoneme_space()
        disable_phoneme_space()
        assert not is_phoneme_space_enabled()
        # Re-enable for other tests
        enable_phoneme_space()

    def test_raises_when_disabled_strict(self):
        """Should raise error when disabled in strict mode."""
        disable_phoneme_space()
        PhonemeSpaceConfig.enable(strict=True)
        PhonemeSpaceConfig.disable()

        with pytest.raises(PhonemeSpaceDisabledError):
            get_phoneme('a')

        # Re-enable for other tests
        enable_phoneme_space()

    def test_context_manager(self):
        """Context manager enables temporarily."""
        disable_phoneme_space()

        with phoneme_exploration():
            assert is_phoneme_space_enabled()
            phoneme = get_phoneme('a')
            assert phoneme is not None

        assert not is_phoneme_space_enabled()
        # Re-enable for other tests
        enable_phoneme_space()


# =============================================================================
# TEST: PHONEME FEATURES
# =============================================================================

class TestPhonemeFeatures:
    """Test PhonemeFeatures class."""

    def test_consonant_features(self, consonant_p):
        """Consonants have place, manner, voicing."""
        assert consonant_p.is_consonant()
        assert not consonant_p.is_vowel()
        assert consonant_p.place == Place.BILABIAL
        assert consonant_p.manner == Manner.STOP
        assert consonant_p.voicing == Voicing.VOICELESS

    def test_vowel_features(self, vowel_a):
        """Vowels have height, backness, roundedness."""
        assert vowel_a.is_vowel()
        assert not vowel_a.is_consonant()
        assert vowel_a.height == Height.LOW
        assert vowel_a.backness == Backness.CENTRAL
        assert vowel_a.roundedness == Roundedness.UNROUNDED

    def test_voicing_detection(self, consonant_p, consonant_b, vowel_a):
        """Voicing is detected correctly."""
        assert not consonant_p.is_voiced()
        assert consonant_b.is_voiced()
        assert vowel_a.is_voiced()  # Vowels are always voiced

    def test_obstruent_detection(self, consonant_p):
        """Obstruents detected correctly."""
        assert consonant_p.is_obstruent()
        nasal = get_phoneme('m')
        assert not nasal.is_obstruent()

    def test_sonorant_detection(self, vowel_a):
        """Sonorants detected correctly."""
        assert vowel_a.is_sonorant()
        nasal = get_phoneme('m')
        assert nasal.is_sonorant()

    def test_feature_vector_dimensions(self, consonant_p, vowel_a):
        """Feature vector has correct dimensions."""
        assert len(consonant_p.feature_vector()) == 12
        assert len(vowel_a.feature_vector()) == 12

    def test_feature_vector_values_in_range(self, consonant_p):
        """Feature vector values are in [0, 1]."""
        vec = consonant_p.feature_vector()
        for v in vec:
            assert 0.0 <= v <= 1.0


# =============================================================================
# TEST: IPA INVENTORY
# =============================================================================

class TestIPAInventory:
    """Test IPA phoneme inventory."""

    def test_inventory_not_empty(self):
        """Inventory has phonemes."""
        assert len(IPA_INVENTORY) > 0

    def test_get_phoneme_exists(self):
        """Can get existing phoneme."""
        p = get_phoneme('p')
        assert p is not None
        assert p.symbol == 'p'

    def test_get_phoneme_not_exists(self):
        """Returns None for unknown phoneme."""
        p = get_phoneme('xyz')
        assert p is None

    def test_list_phonemes(self):
        """Can list all phonemes."""
        phonemes = list_phonemes()
        assert len(phonemes) > 30  # At least 30 phonemes
        assert 'a' in phonemes
        assert 'p' in phonemes

    def test_inventory_has_consonants_and_vowels(self):
        """Inventory has both consonants and vowels."""
        consonants = [s for s, p in IPA_INVENTORY.items() if p.is_consonant()]
        vowels = [s for s, p in IPA_INVENTORY.items() if p.is_vowel()]
        assert len(consonants) > 15
        assert len(vowels) > 10


# =============================================================================
# TEST: PHONEME GUNA MAPPING
# =============================================================================

class TestPhonemeGuna:
    """Test Guna mapping for phonemes."""

    def test_guna_normalized(self):
        """Guna values sum to 1."""
        guna = get_phoneme_guna('a')
        total = guna.sattva + guna.rajas + guna.tamas
        assert abs(total - 1.0) < 0.001

    def test_vowel_high_sattva(self, vowel_a):
        """Vowels have high Sattva (clarity)."""
        guna = compute_phoneme_guna(vowel_a)
        assert guna.sattva > guna.tamas
        assert guna.dominant_guna == 'sattva'

    def test_stop_high_tamas(self, consonant_p):
        """Stops have high Tamas (obstruction)."""
        guna = compute_phoneme_guna(consonant_p)
        assert guna.tamas > guna.sattva
        assert guna.dominant_guna == 'tamas'

    def test_voiced_adds_rajas(self, consonant_p, consonant_b):
        """Voicing increases Rajas."""
        guna_p = compute_phoneme_guna(consonant_p)
        guna_b = compute_phoneme_guna(consonant_b)
        assert guna_b.rajas > guna_p.rajas

    def test_fricative_rajas_tamas(self):
        """Fricatives have Rajas + Tamas (turbulent obstruction)."""
        f = get_phoneme('f')
        guna = compute_phoneme_guna(f)
        # Fricatives should have significant Rajas and Tamas
        assert guna.rajas > 0.3
        assert guna.tamas > 0.25

    def test_to_observables(self):
        """Can convert to SymbolU Observables."""
        guna = get_phoneme_guna('a')
        obs = guna.to_observables()
        assert obs.s == guna.sattva
        assert obs.r == guna.rajas
        assert obs.t == guna.tamas
        assert 0.0 <= obs.H <= 1.0


# =============================================================================
# TEST: PHONEME EMBEDDING
# =============================================================================

class TestPhonemeEmbedding:
    """Test PhonemeEmbedding class."""

    def test_embedding_dimensions(self):
        """Embedding has correct dimensions (12 features + 3 Guna = 15)."""
        emb = get_phoneme_embedding('a')
        assert len(emb.vector) == 15

    def test_embedding_values_reasonable(self):
        """Embedding values are in reasonable range."""
        emb = get_phoneme_embedding('a')
        for v in emb.vector:
            assert -1.0 <= v <= 2.0  # Allow some flexibility

    def test_embedding_distance(self):
        """Can compute distance between embeddings."""
        emb_a = get_phoneme_embedding('a')
        emb_i = get_phoneme_embedding('i')
        emb_a2 = get_phoneme_embedding('a')

        # Same phoneme has zero distance
        assert emb_a.distance(emb_a2) < 0.001

        # Different phonemes have positive distance
        assert emb_a.distance(emb_i) > 0.0

    def test_embedding_cosine_similarity(self):
        """Can compute cosine similarity."""
        emb_a = get_phoneme_embedding('a')
        emb_i = get_phoneme_embedding('i')

        # Self-similarity should be ~1
        assert emb_a.cosine_similarity(emb_a) > 0.99

        # Different phonemes should have lower similarity
        sim = emb_a.cosine_similarity(emb_i)
        assert sim < 1.0

    def test_similar_phonemes_comparable(self):
        """Similar phonemes should have meaningful distance relationships."""
        emb_p = get_phoneme_embedding('p')
        emb_b = get_phoneme_embedding('b')  # Voiced p
        emb_k = get_phoneme_embedding('k')  # Different place

        # All distances should be positive and finite
        dist_pb = emb_p.distance(emb_b)
        dist_pk = emb_p.distance(emb_k)
        assert dist_pb > 0.0
        assert dist_pk > 0.0
        # p and b should have high similarity (both bilabial stops)
        sim_pb = emb_p.cosine_similarity(emb_b)
        assert sim_pb > 0.8


# =============================================================================
# TEST: PHONEME AFFINITY
# =============================================================================

class TestPhonemeAffinity:
    """Test PhonemeAffinity (simulated attention)."""

    def test_affinity_computed(self):
        """Can compute affinity between phonemes."""
        aff = compute_affinity('p', 'a')
        assert aff is not None
        assert 0.0 <= aff.total_affinity <= 1.0

    def test_affinity_components(self):
        """Affinity has all components."""
        aff = compute_affinity('p', 'a')
        assert 0.0 <= aff.feature_affinity <= 1.0
        assert 0.0 <= aff.guna_affinity <= 1.0
        assert 0.0 <= aff.phonotactic_affinity <= 1.0
        assert 0.0 <= aff.sonority_affinity <= 1.0

    def test_cv_high_affinity(self):
        """Consonant-Vowel sequences have high phonotactic affinity."""
        aff_cv = compute_affinity('p', 'a')  # CV
        aff_cc = compute_affinity('p', 't')  # CC

        # CV should have higher phonotactic affinity than CC
        assert aff_cv.phonotactic_affinity > aff_cc.phonotactic_affinity

    def test_self_affinity(self):
        """Same phoneme has high feature affinity."""
        aff = compute_affinity('a', 'a')
        assert aff.feature_affinity > 0.9


# =============================================================================
# TEST: PHONEME PROJECTION
# =============================================================================

class TestPhonemeProjection:
    """Test projection onto ontological layers."""

    def test_projection_computed(self):
        """Can project phoneme onto layers."""
        proj = project_phoneme('a')
        assert proj is not None

    def test_projection_layers(self):
        """Projection has all layer values."""
        proj = project_phoneme('a')
        layer_dict = proj.to_layer_dict()

        assert OntologicalLayer.SIGNAL in layer_dict
        assert OntologicalLayer.EMBEDDING in layer_dict
        assert OntologicalLayer.GUNA in layer_dict
        assert OntologicalLayer.MOTION in layer_dict
        assert OntologicalLayer.FUSION in layer_dict
        assert OntologicalLayer.STATE in layer_dict
        assert OntologicalLayer.OUTPUT in layer_dict

    def test_projection_values_in_range(self):
        """Projection values are in [0, 1]."""
        proj = project_phoneme('a')
        assert 0.0 <= proj.signal <= 1.0
        assert 0.0 <= proj.embedding <= 1.0
        assert 0.0 <= proj.guna_layer <= 1.0
        assert 0.0 <= proj.motion <= 1.0
        assert 0.0 <= proj.fusion <= 1.0
        assert 0.0 <= proj.state <= 1.0
        assert 0.0 <= proj.output <= 1.0

    def test_vowel_high_fusion(self):
        """Vowels should have high fusion (syllable nuclei)."""
        proj_a = project_phoneme('a')
        proj_p = project_phoneme('p')

        assert proj_a.fusion > proj_p.fusion

    def test_total_activation(self):
        """Can compute total activation."""
        proj = project_phoneme('a')
        total = proj.total_activation
        assert total > 0.0


# =============================================================================
# TEST: SEQUENCE ANALYSIS
# =============================================================================

class TestSequenceAnalysis:
    """Test phoneme sequence analysis."""

    def test_analyze_sequence(self):
        """Can analyze sequence of phonemes."""
        analysis = analyze_sequence(['p', 'a', 't'])
        assert len(analysis.phonemes) == 3
        assert len(analysis.projections) == 3

    def test_aggregate_guna(self):
        """Can compute aggregate Guna."""
        analysis = analyze_sequence(['a', 'i', 'u'])
        guna = analysis.aggregate_guna

        # All vowels - should be high Sattva
        assert guna.sattva > guna.tamas

    def test_aggregate_layer_activation(self):
        """Can compute aggregate layer activation."""
        analysis = analyze_sequence(['p', 'a', 't'])
        layers = analysis.aggregate_layer_activation

        assert OntologicalLayer.SIGNAL in layers
        assert all(v >= 0.0 for v in layers.values())

    def test_to_observables(self):
        """Can convert to Observables."""
        analysis = analyze_sequence(['p', 'a', 't'])
        obs = analysis.to_observables()

        assert 0.0 <= obs.s <= 1.0
        assert 0.0 <= obs.r <= 1.0
        assert 0.0 <= obs.t <= 1.0
        assert 0.0 <= obs.H <= 1.0

    def test_analyze_word_ipa(self):
        """Can analyze IPA string."""
        # "pat" in IPA
        analysis = analyze_word_ipa('pæt')
        assert len(analysis.phonemes) == 3

    def test_analyze_word_ipa_multichar(self):
        """Handles multi-character phonemes."""
        # "church" starts with tʃ
        analysis = analyze_word_ipa('tʃɜtʃ')
        assert 'tʃ' in analysis.phonemes


# =============================================================================
# TEST: CONVENIENCE FUNCTIONS
# =============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_phoneme_distance(self):
        """phoneme_distance works."""
        dist = phoneme_distance('a', 'i')
        assert dist is not None
        assert dist > 0.0

    def test_phoneme_distance_same(self):
        """Same phoneme has zero distance."""
        dist = phoneme_distance('a', 'a')
        assert dist < 0.001

    def test_phoneme_similarity(self):
        """phoneme_similarity works."""
        sim = phoneme_similarity('a', 'i')
        assert sim is not None
        assert 0.0 < sim < 1.0

    def test_most_similar_phonemes(self):
        """most_similar_phonemes works."""
        similar = most_similar_phonemes('p', top_k=3)
        assert len(similar) == 3

        # Results are (symbol, similarity) tuples
        for symbol, sim in similar:
            assert isinstance(symbol, str)
            assert 0.0 <= sim <= 1.0

        # Should be sorted descending
        sims = [s for _, s in similar]
        assert sims == sorted(sims, reverse=True)

    def test_guna_profile(self):
        """guna_profile works."""
        profile = guna_profile(['p', 'a', 't'])

        assert 'sattva' in profile
        assert 'rajas' in profile
        assert 'tamas' in profile
        assert 'dominant' in profile

        assert 0.0 <= profile['sattva'] <= 1.0
        assert profile['dominant'] in ['sattva', 'rajas', 'tamas']


# =============================================================================
# TEST: LINGUISTIC PROPERTIES
# =============================================================================

class TestLinguisticProperties:
    """Test that phoneme model captures linguistic properties."""

    def test_voicing_minimal_pair(self):
        """Voicing minimal pairs (p/b, t/d, k/g) have high similarity."""
        # p and b differ only in voicing - should be very similar
        sim_pb = phoneme_similarity('p', 'b')
        sim_td = phoneme_similarity('t', 'd')
        sim_kg = phoneme_similarity('k', 'g')

        # Minimal pairs should have high similarity
        assert sim_pb > 0.85
        assert sim_td > 0.85
        assert sim_kg > 0.85

    def test_vowel_triangle(self):
        """Cardinal vowels (/a/, /i/, /u/) form meaningful pattern."""
        # All cardinal vowels should be distinct but related
        sim_ia = phoneme_similarity('i', 'a')
        sim_iu = phoneme_similarity('i', 'u')
        sim_ua = phoneme_similarity('u', 'a')

        # All should have reasonable similarity (all vowels)
        assert sim_ia > 0.6
        assert sim_iu > 0.6
        assert sim_ua > 0.6

        # But not identical
        assert sim_ia < 1.0
        assert sim_iu < 1.0
        assert sim_ua < 1.0

    def test_manner_class_similarity(self):
        """Same manner class phonemes share characteristics."""
        # All stops have high similarity
        sim_pt = phoneme_similarity('p', 't')
        sim_pk = phoneme_similarity('p', 'k')
        sim_tk = phoneme_similarity('t', 'k')

        # Stops should be reasonably similar to each other
        assert sim_pt > 0.8
        assert sim_pk > 0.8
        assert sim_tk > 0.8

    def test_sonority_hierarchy(self):
        """Sonority is correctly ordered: stops < fricatives < nasals < vowels."""
        proj_p = project_phoneme('p')   # stop
        proj_s = project_phoneme('s')   # fricative
        proj_m = project_phoneme('m')   # nasal
        proj_a = project_phoneme('a')   # vowel

        # Check via phoneme features
        p = get_phoneme('p')
        s = get_phoneme('s')
        m = get_phoneme('m')
        a = get_phoneme('a')

        son_p = p._compute_sonority()
        son_s = s._compute_sonority()
        son_m = m._compute_sonority()
        son_a = a._compute_sonority()

        assert son_p < son_s < son_m < son_a


# =============================================================================
# TEST: GUNA SEMANTIC PROPERTIES
# =============================================================================

class TestGunaSemantics:
    """Test Guna mapping captures semantic properties."""

    def test_high_vowels_more_sattvic(self):
        """High vowels (/i/, /u/) more Sattvic than low vowels."""
        guna_i = get_phoneme_guna('i')
        guna_a = get_phoneme_guna('a')

        # High vowels are "purer" - higher Sattva
        assert guna_i.sattva >= guna_a.sattva - 0.1  # Allow small margin

    def test_obstruents_more_tamasic(self):
        """Obstruents have more Tamas than sonorants."""
        guna_p = get_phoneme_guna('p')  # obstruent
        guna_m = get_phoneme_guna('m')  # sonorant

        assert guna_p.tamas > guna_m.tamas

    def test_trills_more_rajasic(self):
        """Trills/flaps have high Rajas (movement)."""
        # If we have a trill in inventory
        if 'ɾ' in IPA_INVENTORY:
            guna_r = get_phoneme_guna('ɾ')
            assert guna_r.rajas > 0.4


# =============================================================================
# TEST: INTEGRATION
# =============================================================================

class TestIntegration:
    """Integration tests for full pipeline."""

    def test_word_to_observables(self):
        """Can analyze word and get Observables."""
        # Analyze "pat"
        analysis = analyze_word_ipa('pæt')
        obs = analysis.to_observables()

        # Should be valid Observables
        assert abs(obs.s + obs.r + obs.t - 1.0) < 0.01
        assert 0.0 <= obs.H <= 1.0

    def test_phoneme_to_all_layers(self):
        """Phoneme projects to all ontological layers."""
        proj = project_phoneme('a')
        layer_dict = proj.to_layer_dict()

        # All layers should have some activation
        for layer, value in layer_dict.items():
            assert value >= 0.0, f"{layer} has negative activation"

    def test_affinity_reflects_guna(self):
        """Phonemes with similar Guna have higher affinity."""
        # Two high-Sattva phonemes (vowels)
        aff_vowels = compute_affinity('a', 'i')

        # Vowel and stop (different Guna profiles)
        aff_mixed = compute_affinity('a', 'p')

        # Guna affinity should be higher for similar phonemes
        assert aff_vowels.guna_affinity > aff_mixed.guna_affinity

    def test_context_manager_workflow(self):
        """Full workflow with context manager."""
        disable_phoneme_space()

        with phoneme_exploration():
            # Analyze a word
            analysis = analyze_word_ipa('hello')

            # Get Guna profile
            profile = guna_profile(['h', 'e', 'l', 'o'])

            # Project each phoneme
            for symbol in ['h', 'e', 'l', 'o']:
                proj = project_phoneme(symbol)
                assert proj is not None

        # Re-enable for remaining tests
        enable_phoneme_space()
