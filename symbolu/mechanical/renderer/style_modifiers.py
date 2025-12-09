"""
Style Modifiers
================

Modifies output style based on DHA tone.
"""

from typing import Dict, Any


class StyleModifiers:
    """Applies style modifications based on tone."""
    
    TONE_STYLES: Dict[str, Dict[str, Any]] = {
        "SWEET_RESONANCE": {
            "warmth": 0.8,
            "directness": 0.7,
            "formality": 0.3
        },
        "GENTLE_MIRROR": {
            "warmth": 0.6,
            "directness": 0.4,
            "formality": 0.5
        },
        "FIRM_COMPASSION": {
            "warmth": 0.5,
            "directness": 0.9,
            "formality": 0.6
        },
        "SILENT_PRESENCE": {
            "warmth": 0.4,
            "directness": 0.2,
            "formality": 0.4
        }
    }
    
    def apply(self, prompt: str, tone: str) -> str:
        """Apply style modifiers to prompt."""
        style = self.TONE_STYLES.get(tone, self.TONE_STYLES["SWEET_RESONANCE"])
        # Add style instructions to prompt
        return prompt + f"\n\nSTYLE: warmth={style['warmth']}, directness={style['directness']}"
