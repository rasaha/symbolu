"""
Text Modes
===========

Different text output modes.
"""

from enum import Enum


class TextMode(Enum):
    """Output text modes."""
    PLAIN = "plain"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


class TextModeFormatter:
    """Formats output for different modes."""
    
    def format(self, content: str, mode: TextMode) -> str:
        """Format content for specified mode."""
        if mode == TextMode.MARKDOWN:
            return self._to_markdown(content)
        elif mode == TextMode.HTML:
            return self._to_html(content)
        elif mode == TextMode.JSON:
            return self._to_json(content)
        return content
    
    def _to_markdown(self, content: str) -> str:
        return content
    
    def _to_html(self, content: str) -> str:
        return f"<pre>{content}</pre>"
    
    def _to_json(self, content: str) -> str:
        import json
        return json.dumps({"content": content})
