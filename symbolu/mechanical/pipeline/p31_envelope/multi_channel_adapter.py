"""
Multi-Channel Adapter
======================

Adapts output text to different delivery channel formats:
- Chat: Conversational text with markdown support
- API: Structured JSON with metadata
- Voice/SSML: Speech synthesis markup
- Email: HTML with styling
- Report: Formal document format

Integration:
    Used by P31 envelope phase to format output for specific channels.

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import re
import html

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# ENUMS
# =============================================================================


class ChannelType(Enum):
    """Delivery channel types."""
    CHAT = "chat"
    API = "api"
    VOICE = "voice"
    EMAIL = "email"
    REPORT = "report"


class VoiceStyle(Enum):
    """Voice/SSML speaking styles."""
    NEUTRAL = "neutral"
    CHEERFUL = "cheerful"
    EMPATHETIC = "empathetic"
    PROFESSIONAL = "professional"
    CALM = "calm"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class ChannelConfig:
    """Configuration for a specific channel."""
    channel_type: ChannelType
    max_length: Optional[int] = None
    include_metadata: bool = False
    escape_html: bool = True
    voice_style: VoiceStyle = VoiceStyle.NEUTRAL
    speaking_rate: float = 1.0  # 0.5 to 2.0
    custom: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChannelOutput:
    """Output formatted for a specific channel."""
    channel_type: ChannelType
    formatted_text: str
    content_type: str  # MIME type
    metadata: Dict[str, Any] = field(default_factory=dict)
    truncated: bool = False
    original_length: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "channel_type": self.channel_type.value,
            "formatted_text": self.formatted_text,
            "content_type": self.content_type,
            "metadata": self.metadata,
            "truncated": self.truncated,
            "original_length": self.original_length,
        }


# =============================================================================
# MULTI-CHANNEL ADAPTER
# =============================================================================


class MultiChannelAdapter:
    """
    Adapts text output to different delivery channel formats.

    Provides deterministic, template-based formatting without LLM calls.
    """

    # Default channel configurations
    DEFAULT_CONFIGS = {
        ChannelType.CHAT: ChannelConfig(
            channel_type=ChannelType.CHAT,
            max_length=4000,
            include_metadata=False,
            escape_html=False,
        ),
        ChannelType.API: ChannelConfig(
            channel_type=ChannelType.API,
            max_length=None,
            include_metadata=True,
            escape_html=False,
        ),
        ChannelType.VOICE: ChannelConfig(
            channel_type=ChannelType.VOICE,
            max_length=3000,
            include_metadata=False,
            escape_html=True,
            voice_style=VoiceStyle.NEUTRAL,
            speaking_rate=1.0,
        ),
        ChannelType.EMAIL: ChannelConfig(
            channel_type=ChannelType.EMAIL,
            max_length=None,
            include_metadata=False,
            escape_html=True,
        ),
        ChannelType.REPORT: ChannelConfig(
            channel_type=ChannelType.REPORT,
            max_length=None,
            include_metadata=True,
            escape_html=True,
        ),
    }

    # SSML break times for punctuation
    SSML_BREAKS = {
        ".": "500ms",
        "!": "500ms",
        "?": "500ms",
        ",": "200ms",
        ";": "300ms",
        ":": "250ms",
        "—": "400ms",
        "...": "600ms",
    }

    def __init__(self, configs: Optional[Dict[ChannelType, ChannelConfig]] = None):
        """
        Initialize multi-channel adapter.

        Args:
            configs: Custom channel configurations.
        """
        self.configs = {**self.DEFAULT_CONFIGS}
        if configs:
            self.configs.update(configs)

    def adapt(
        self,
        text: str,
        channel: ChannelType,
        config: Optional[ChannelConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChannelOutput:
        """
        Adapt text for a specific channel.

        Args:
            text: Text to adapt.
            channel: Target channel type.
            config: Optional custom config for this adaptation.
            metadata: Optional metadata to include.

        Returns:
            ChannelOutput with formatted text.
        """
        cfg = config or self.configs.get(channel, self.DEFAULT_CONFIGS[ChannelType.CHAT])
        original_length = len(text)

        # Format based on channel type
        if channel == ChannelType.CHAT:
            formatted, content_type = self._format_chat(text, cfg)
        elif channel == ChannelType.API:
            formatted, content_type = self._format_api(text, cfg, metadata)
        elif channel == ChannelType.VOICE:
            formatted, content_type = self._format_voice(text, cfg)
        elif channel == ChannelType.EMAIL:
            formatted, content_type = self._format_email(text, cfg)
        elif channel == ChannelType.REPORT:
            formatted, content_type = self._format_report(text, cfg, metadata)
        else:
            formatted, content_type = text, "text/plain"

        # Apply length limit if configured
        truncated = False
        if cfg.max_length and len(formatted) > cfg.max_length:
            formatted = self._truncate(formatted, cfg.max_length, channel)
            truncated = True

        # Build output metadata
        output_metadata: Dict[str, Any] = {}
        if cfg.include_metadata and metadata:
            output_metadata = metadata.copy()
        output_metadata["channel"] = channel.value
        output_metadata["adapter_version"] = VERSION

        return ChannelOutput(
            channel_type=channel,
            formatted_text=formatted,
            content_type=content_type,
            metadata=output_metadata,
            truncated=truncated,
            original_length=original_length,
        )

    def _format_chat(
        self,
        text: str,
        config: ChannelConfig,
    ) -> Tuple[str, str]:
        """Format for chat interface (markdown-friendly)."""
        # Clean up excessive whitespace
        formatted = re.sub(r'\n{3,}', '\n\n', text)

        # Ensure proper paragraph breaks
        formatted = formatted.strip()

        return formatted, "text/markdown"

    def _format_api(
        self,
        text: str,
        config: ChannelConfig,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """Format for API response (JSON structure)."""
        import json

        response = {
            "text": text,
            "success": True,
            "version": VERSION,
        }

        if config.include_metadata and metadata:
            response["metadata"] = metadata

        formatted = json.dumps(response, indent=2, ensure_ascii=False)
        return formatted, "application/json"

    def _format_voice(
        self,
        text: str,
        config: ChannelConfig,
    ) -> Tuple[str, str]:
        """Format for voice/SSML output."""
        # Escape HTML entities
        if config.escape_html:
            escaped = html.escape(text)
        else:
            escaped = text

        # Convert punctuation to SSML breaks
        ssml_text = self._add_ssml_breaks(escaped)

        # Apply speaking rate
        rate = config.speaking_rate
        if rate != 1.0:
            rate_percent = int(rate * 100)
            ssml_text = f'<prosody rate="{rate_percent}%">{ssml_text}</prosody>'

        # Apply voice style
        style = config.voice_style
        if style != VoiceStyle.NEUTRAL:
            ssml_text = f'<mstts:express-as style="{style.value}">{ssml_text}</mstts:express-as>'

        # Wrap in speak tags
        ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts">
{ssml_text}
</speak>"""

        return ssml, "application/ssml+xml"

    def _format_email(
        self,
        text: str,
        config: ChannelConfig,
    ) -> Tuple[str, str]:
        """Format for email (HTML with styling)."""
        # Escape HTML
        if config.escape_html:
            escaped = html.escape(text)
        else:
            escaped = text

        # Convert newlines to paragraphs
        paragraphs = escaped.split('\n\n')
        html_paragraphs = [f"<p>{p.replace(chr(10), '<br/>')}</p>" for p in paragraphs if p.strip()]

        # Build HTML email template
        email_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        p {{
            margin: 0 0 16px 0;
        }}
    </style>
</head>
<body>
{''.join(html_paragraphs)}
</body>
</html>"""

        return email_html, "text/html"

    def _format_report(
        self,
        text: str,
        config: ChannelConfig,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """Format for formal report."""
        # Escape HTML
        if config.escape_html:
            escaped = html.escape(text)
        else:
            escaped = text

        # Convert newlines to paragraphs
        paragraphs = escaped.split('\n\n')
        html_paragraphs = [f"<p>{p.replace(chr(10), '<br/>')}</p>" for p in paragraphs if p.strip()]

        # Build metadata section if available
        meta_section = ""
        if config.include_metadata and metadata:
            meta_items = []
            for key, value in metadata.items():
                if value is not None:
                    meta_items.append(f"<dt>{html.escape(str(key))}</dt><dd>{html.escape(str(value))}</dd>")
            if meta_items:
                meta_section = f"""<section class="metadata">
    <h2>Document Information</h2>
    <dl>{''.join(meta_items)}</dl>
</section>"""

        # Build formal report template
        report_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Times New Roman', Times, serif;
            line-height: 1.8;
            color: #222;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px;
        }}
        h1 {{ font-size: 24px; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        h2 {{ font-size: 18px; color: #555; margin-top: 30px; }}
        p {{ margin: 0 0 20px 0; text-align: justify; }}
        .metadata {{ background: #f5f5f5; padding: 15px; margin-bottom: 30px; }}
        .metadata dt {{ font-weight: bold; float: left; clear: left; width: 150px; }}
        .metadata dd {{ margin-left: 160px; margin-bottom: 5px; }}
    </style>
</head>
<body>
<h1>Report</h1>
{meta_section}
<section class="content">
{''.join(html_paragraphs)}
</section>
</body>
</html>"""

        return report_html, "text/html"

    def _add_ssml_breaks(self, text: str) -> str:
        """Add SSML break elements for punctuation."""
        result = text

        # Add breaks after punctuation
        for punct, duration in self.SSML_BREAKS.items():
            pattern = re.escape(punct) + r'(?=\s|$)'
            replacement = f'{punct}<break time="{duration}"/>'
            result = re.sub(pattern, replacement, result)

        return result

    def _truncate(self, text: str, max_length: int, channel: ChannelType) -> str:
        """Truncate text to max length with appropriate suffix."""
        if channel == ChannelType.VOICE:
            # For SSML, need to close tags properly
            # Find a good break point
            break_point = text.rfind('<break', 0, max_length - 50)
            if break_point == -1:
                break_point = max_length - 50
            truncated = text[:break_point]
            # Close any open tags
            if '</speak>' not in truncated:
                truncated += '</speak>'
            return truncated

        elif channel == ChannelType.API:
            # For JSON, truncate the text field value
            import json
            try:
                data = json.loads(text)
                if 'text' in data:
                    data['text'] = data['text'][:max_length - 100] + "..."
                    data['truncated'] = True
                return json.dumps(data, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                return text[:max_length - 3] + "..."

        elif channel in (ChannelType.EMAIL, ChannelType.REPORT):
            # For HTML, truncate before closing body tag
            body_end = text.rfind('</body>')
            if body_end > 0 and body_end > max_length:
                # Find a paragraph break
                p_end = text.rfind('</p>', 0, max_length - 100)
                if p_end > 0:
                    return text[:p_end + 4] + '\n<p><em>[Content truncated]</em></p>\n</body>\n</html>'
            return text[:max_length]

        # Default: simple truncation
        return text[:max_length - 3] + "..."


# =============================================================================
# SINGLETON
# =============================================================================

_adapter: Optional[MultiChannelAdapter] = None


def get_multi_channel_adapter() -> MultiChannelAdapter:
    """Get or create singleton MultiChannelAdapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = MultiChannelAdapter()
    return _adapter


def adapt_for_channel(
    text: str,
    channel: ChannelType,
    metadata: Optional[Dict[str, Any]] = None,
) -> ChannelOutput:
    """
    Convenience function to adapt text for a channel.

    Args:
        text: Text to adapt.
        channel: Target channel type.
        metadata: Optional metadata to include.

    Returns:
        ChannelOutput with formatted text.
    """
    return get_multi_channel_adapter().adapt(text, channel, metadata=metadata)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "ChannelType",
    "VoiceStyle",
    "ChannelConfig",
    "ChannelOutput",
    "MultiChannelAdapter",
    "get_multi_channel_adapter",
    "adapt_for_channel",
]
