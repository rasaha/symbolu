"""
Test Example for MLCR - Ontology Mass Computation
==================================================

This is a sample test to demonstrate the testing structure.
Full test suite would include comprehensive tests for all components.

Run with: pytest test_example_ontology_mass.py -v
"""

from symbolu.mechanical.mlcr import get_ontology_computer


class TestOntologyMassComputation:
    """Test ontology mass computation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.computer = get_ontology_computer()
    
    def test_lower_tier_query(self):
        """Test query that should activate LOWER tier."""
        # Uses keywords: "execute" (layer 1), "process" (layer 1), "structure" (layer 3)
        text = "How do I execute this process and structure the workflow?"
        result = self.computer.compute_mass(text)

        # Should have high lower mass (concrete/factual)
        assert result["lower_mass"] > 0.5, "Lower mass should dominate"
        assert result["dominant_layer"] <= 5, "Dominant layer should be in lower tier"
    
    def test_upper_tier_query(self):
        """Test query that should activate UPPER tier."""
        text = "Why do I keep making the same mistakes?"
        result = self.computer.compute_mass(text)
        
        # Should have high upper mass (abstract/symbolic)
        assert result["upper_mass"] > 0.5, "Upper mass should dominate"
        assert result["dominant_layer"] >= 6, "Dominant layer should be in upper tier"
    
    def test_hybrid_query(self):
        """Test query that should activate HYBRID tier."""
        # Uses keywords: "action" (layer 1), "form" (layer 3), "reason" (layer 6), "purpose" (layer 7)
        text = "What is the reason behind this action and its purpose in shaping the form?"
        result = self.computer.compute_mass(text)

        # Should have mixed distribution
        assert result["lower_mass"] > 0.2, "Should have some lower mass"
        assert result["upper_mass"] > 0.2, "Should have some upper mass"
    
    def test_keyword_matching(self):
        """Test keyword matching."""
        text = "thinking about reasoning"
        result = self.computer.compute_mass(text)
        
        # Should match cognition (layer 4) and reasoning (layer 6)
        matched = result["matched_keywords"]
        layers = [layer for layer, keyword in matched]
        
        assert 4 in layers, "Should match Cognition layer"
        assert 6 in layers, "Should match Reasoning layer"
    
    def test_empty_query(self):
        """Test empty query handling."""
        text = ""
        result = self.computer.compute_mass(text)
        
        # Should default to balanced distribution
        assert result["lower_mass"] == 0.5
        assert result["upper_mass"] == 0.5
    
    def test_layer_labels(self):
        """Test layer label retrieval."""
        assert self.computer.get_layer_label(1) == "Execution"
        assert self.computer.get_layer_label(6) == "Reasoning"
        assert self.computer.get_layer_label(10) == "Absolute"
    
    def test_explanation_generation(self):
        """Test explanation generation."""
        text = "What is the meaning of life?"
        result = self.computer.compute_mass(text)
        explanations = self.computer.explain_mass(result)
        
        assert len(explanations) > 0, "Should generate explanations"
        assert any("Lower Mass" in exp for exp in explanations)
        assert any("Upper Mass" in exp for exp in explanations)


# Run tests if executed directly
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
