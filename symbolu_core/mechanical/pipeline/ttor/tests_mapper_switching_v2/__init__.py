"""
TTOR Mapper Switching v2.0 Test Suite

Enforces canonical mapper activation rules:
- HRM: (tier != LOWER) and (entropy_mix > 0.40)
- LCM: (tier == LOWER) and (entropy_mix > 0.50)
- LAM: (long_arc_tension > 0.50) or temporal_patterns_detected or
       (domain in ["therapy", "identity", "spiritual"] and entropy_mix > 0.60)
"""
