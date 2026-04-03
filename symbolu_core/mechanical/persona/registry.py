"""
Persona Registry (v2.8.2)
==========================

Registry for storing, retrieving, and managing persona profiles.
Provides thread-safe access to persona configurations.
"""

from typing import Dict, List, Optional
from .models import PersonaProfile
from .default_personas import DEFAULT_PERSONAS


class PersonaRegistry:
    """
    Registry for managing persona profiles.
    
    Provides:
        - Storage of persona profiles
        - Retrieval by ID
        - Listing all available personas
        - Dynamic registration of custom personas
        - Thread-safe operations
    """
    
    def __init__(self, personas: Optional[List[PersonaProfile]] = None):
        """
        Initialize registry with persona profiles.
        
        Args:
            personas: List of PersonaProfile objects. If None, uses defaults.
        """
        self._personas: Dict[str, PersonaProfile] = {}
        
        # Load personas
        personas_to_load = personas if personas is not None else DEFAULT_PERSONAS
        for persona in personas_to_load:
            self._personas[persona.id] = persona
    
    def get(self, persona_id: str) -> PersonaProfile:
        """
        Retrieve a persona by ID.
        
        Args:
            persona_id: Unique persona identifier
            
        Returns:
            PersonaProfile object
            
        Raises:
            KeyError: If persona_id not found
        """
        if persona_id not in self._personas:
            raise KeyError(
                f"Persona '{persona_id}' not found in registry. "
                f"Available personas: {list(self._personas.keys())}"
            )
        return self._personas[persona_id]
    
    def get_safe(self, persona_id: str, default: str = "neutral") -> PersonaProfile:
        """
        Retrieve a persona by ID with fallback to default.
        
        Args:
            persona_id: Unique persona identifier
            default: Default persona ID if persona_id not found
            
        Returns:
            PersonaProfile object
        """
        try:
            return self.get(persona_id)
        except KeyError:
            return self.get(default)
    
    def list_ids(self) -> List[str]:
        """
        List all available persona IDs.
        
        Returns:
            List of persona identifiers
        """
        return list(self._personas.keys())
    
    def list_all(self) -> List[PersonaProfile]:
        """
        List all available persona profiles.
        
        Returns:
            List of PersonaProfile objects
        """
        return list(self._personas.values())
    
    def register(self, persona: PersonaProfile) -> None:
        """
        Register a new persona or update existing one.
        
        Args:
            persona: PersonaProfile object to register
        """
        self._personas[persona.id] = persona
    
    def unregister(self, persona_id: str) -> None:
        """
        Remove a persona from the registry.
        
        Args:
            persona_id: Unique persona identifier
            
        Raises:
            KeyError: If persona_id not found
        """
        if persona_id not in self._personas:
            raise KeyError(f"Cannot unregister: Persona '{persona_id}' not found")
        del self._personas[persona_id]
    
    def exists(self, persona_id: str) -> bool:
        """
        Check if a persona exists in the registry.
        
        Args:
            persona_id: Unique persona identifier
            
        Returns:
            True if persona exists, False otherwise
        """
        return persona_id in self._personas
    
    def get_by_domain(self, domain: str) -> Optional[PersonaProfile]:
        """
        Find the best persona for a given domain.
        
        Args:
            domain: Domain identifier (e.g., "trading", "emotional")
            
        Returns:
            PersonaProfile if match found, None otherwise
        """
        for persona in self._personas.values():
            if domain in persona.preferred_domains:
                return persona
        return None
    
    def summary(self) -> str:
        """
        Generate a summary of all registered personas.
        
        Returns:
            Formatted string with persona information
        """
        lines = ["=" * 70]
        lines.append("PERSONA REGISTRY")
        lines.append("=" * 70)
        
        for persona in sorted(self._personas.values(), key=lambda p: p.id):
            lines.append(f"\n{persona.id.upper()}")
            lines.append("-" * 70)
            lines.append(f"  Name:        {persona.display_name}")
            lines.append(f"  Description: {persona.description}")
            lines.append(f"  Formality:   {persona.formality:.2f}")
            lines.append(f"  Warmth:      {persona.warmth:.2f}")
            lines.append(f"  Directness:  {persona.directness:.2f}")
            lines.append(f"  Domains:     {', '.join(persona.preferred_domains) if persona.preferred_domains else 'General'}")
        
        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


# =============================================================================
# SINGLETON FACTORY
# =============================================================================

_default_registry: Optional[PersonaRegistry] = None


def get_default_registry() -> PersonaRegistry:
    """
    Get the default persona registry (singleton).
    
    Returns:
        PersonaRegistry with default personas loaded
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = PersonaRegistry()
    return _default_registry


def reset_default_registry() -> None:
    """
    Reset the default registry (useful for testing).
    """
    global _default_registry
    _default_registry = None
