"""Content analyzer - orchestrates AI analysis of messages."""

import logging
from typing import Dict, Any, Optional

from src.ai.base import AIProvider, AIProviderError
from src.ai.prompts import FALLBACK_ANALYSIS


logger = logging.getLogger('obsidian_telegram_bot')


class ContentAnalyzer:
    """Orchestrates content analysis using AI providers."""

    def __init__(self, ai_provider: AIProvider, config: Dict[str, Any]):
        """
        Initialize content analyzer.

        Args:
            ai_provider: AI provider instance (Claude or Ollama)
            config: Full application configuration
        """
        self.ai = ai_provider
        self.config = config
        self.fallback_on_error = config.get('bot', {}).get('fallback_on_ai_error', True)

    async def analyze(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of content.

        Args:
            content: Content to analyze
            context: Additional context (source, content_type, existing_folders, etc.)

        Returns:
            Dictionary with analysis results:
                - title: str
                - summary: str
                - tags: List[str]
                - suggested_folder: str
                - connections: List[str]
                - entities: List[str]
                - ai_provider: str (name of AI provider used)
                - analysis_successful: bool
        """
        context = context or {}

        try:
            logger.info(f"Analyzing content from {context.get('source', 'unknown')} (length: {len(content)} chars)")

            # Call AI for comprehensive analysis
            analysis = await self.ai.analyze_content(content, context)

            # Add metadata
            analysis['ai_provider'] = self._get_provider_name()
            analysis['analysis_successful'] = True

            # Validate and sanitize results
            analysis = self._validate_analysis(analysis)

            return analysis

        except AIProviderError as e:
            logger.error(f"AI analysis failed: {e}")

            if self.fallback_on_error:
                logger.info("Using fallback analysis")
                return self._create_fallback_analysis(content, context)
            else:
                raise

        except Exception as e:
            logger.exception(f"Unexpected error during analysis: {e}")

            if self.fallback_on_error:
                return self._create_fallback_analysis(content, context)
            else:
                raise

    def _validate_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize analysis results.

        Args:
            analysis: Raw analysis from AI

        Returns:
            Validated analysis
        """
        # Ensure all required fields exist
        defaults = {
            'title': 'Untitled Note',
            'summary': '',
            'tags': [],
            'suggested_folder': 'Inbox',
            'connections': [],
            'entities': []
        }

        for key, default_value in defaults.items():
            if key not in analysis or not analysis[key]:
                analysis[key] = default_value

        # Sanitize title (remove invalid characters for filenames)
        analysis['title'] = self._sanitize_title(analysis['title'])

        # Ensure tags is a list
        if isinstance(analysis['tags'], str):
            analysis['tags'] = [tag.strip() for tag in analysis['tags'].split(',')]

        # Limit number of tags
        max_tags = self.config.get('ai', {}).get('analysis', {}).get('max_tags', 5)
        analysis['tags'] = analysis['tags'][:max_tags]

        # Sanitize folder path
        analysis['suggested_folder'] = self._sanitize_folder_path(analysis['suggested_folder'])

        return analysis

    def _sanitize_title(self, title: str) -> str:
        """
        Sanitize title for use in filename.

        Args:
            title: Raw title

        Returns:
            Sanitized title
        """
        if not title or not title.strip():
            return "Untitled Note"

        # Remove or replace invalid filename characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        sanitized = title
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '-')

        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip('. ')

        # Limit length
        max_length = 100
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].strip()

        return sanitized or "Untitled Note"

    def _sanitize_folder_path(self, folder: str) -> str:
        """
        Sanitize folder path.

        Args:
            folder: Raw folder path

        Returns:
            Sanitized folder path
        """
        if not folder or not folder.strip():
            return "Inbox"

        # Remove leading/trailing slashes
        folder = folder.strip('/')

        # Remove invalid characters
        invalid_chars = ['\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            folder = folder.replace(char, '-')

        return folder or "Inbox"

    def _create_fallback_analysis(
        self,
        content: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a basic fallback analysis when AI fails.

        Args:
            content: Original content
            context: Context information

        Returns:
            Fallback analysis dictionary
        """
        from datetime import datetime

        # Use first line or first 50 chars as title
        lines = content.strip().split('\n')
        first_line = lines[0] if lines else content[:50]
        title = first_line[:100] if first_line else "Note from Telegram"

        analysis = FALLBACK_ANALYSIS.copy()
        analysis.update({
            'title': self._sanitize_title(title),
            'summary': f"Content received from {context.get('source', 'Telegram')} on {datetime.now().strftime('%Y-%m-%d')}",
            'ai_provider': 'fallback',
            'analysis_successful': False
        })

        return analysis

    def _get_provider_name(self) -> str:
        """Get the name of the current AI provider."""
        provider_class = self.ai.__class__.__name__
        if 'Claude' in provider_class:
            return 'claude'
        elif 'Ollama' in provider_class:
            return 'ollama'
        else:
            return 'unknown'
