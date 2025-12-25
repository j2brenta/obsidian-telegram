"""Note creation and formatting for Obsidian."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import re

logger = logging.getLogger('obsidian_telegram_bot')


class NoteCreator:
    """Creates formatted Obsidian notes from analyzed content."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize note creator.

        Args:
            config: Application configuration
        """
        self.config = config
        self.obsidian_config = config.get('obsidian', {})
        self.filename_strategy = self.obsidian_config.get('filename_strategy', 'hybrid')
        self.tag_format = self.obsidian_config.get('frontmatter', {}).get('tag_format', 'yaml')

    def create_note(
        self,
        analysis: Dict[str, Any],
        content: str,
        metadata: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        Create a formatted Obsidian note.

        Args:
            analysis: AI analysis results (title, tags, summary, etc.)
            content: Original message content
            metadata: Additional metadata (source, timestamp, user_id, etc.)

        Returns:
            Tuple of (note_content, filename)
        """
        timestamp = metadata.get('timestamp', datetime.now())

        # Generate filename
        filename = self._generate_filename(
            title=analysis.get('title', 'Untitled'),
            timestamp=timestamp
        )

        # Build frontmatter
        frontmatter = self._build_frontmatter(analysis, metadata)

        # Build main content
        note_body = self._build_note_body(analysis, content, metadata)

        # Combine
        note_content = f"{frontmatter}\n{note_body}"

        logger.debug(f"Created note: {filename}")
        return note_content, filename

    def _generate_filename(self, title: str, timestamp: datetime) -> str:
        """
        Generate filename based on configured strategy.

        Args:
            title: Note title
            timestamp: Creation timestamp

        Returns:
            Filename (without .md extension)
        """
        date_str = timestamp.strftime('%Y-%m-%d')
        time_str = timestamp.strftime('%H%M%S')

        # Sanitize title for filename
        safe_title = self._sanitize_for_filename(title)

        if self.filename_strategy == 'timestamp':
            # Format: 2025-01-15-142030.md
            return f"{date_str}-{time_str}"

        elif self.filename_strategy == 'ai_title':
            # Format: note-title-from-ai.md
            return title

        else:  # hybrid (default)
            # Format: 2025-01-15-note-title-from-ai.md
            return f"{date_str} - {title}"

    def _sanitize_for_filename(self, text: str) -> str:
        """
        Sanitize text for use in filename.

        Args:
            text: Raw text

        Returns:
            Sanitized text suitable for filename
        """
        # Convert to lowercase
        text = text.lower()

        # Replace spaces and special chars with hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_]+', '-', text)
        text = re.sub(r'-+', '-', text)

        # Remove leading/trailing hyphens
        text = text.strip('-')

        # Limit length
        max_length = 60
        if len(text) > max_length:
            text = text[:max_length].rstrip('-')

        return text or 'untitled'

    def _build_frontmatter(
        self,
        analysis: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Build YAML frontmatter for the note.

        Args:
            analysis: AI analysis results
            metadata: Additional metadata

        Returns:
            Formatted frontmatter string
        """
        timestamp = metadata.get('timestamp', datetime.now())
        source = metadata.get('source', 'telegram')
        source_type = metadata.get('source_type', 'text')

        lines = ['---']

        # Basic metadata
        lines.append(f"created: {timestamp.strftime('%Y-%m-%dT%H:%M:%S')}")
        lines.append(f"source: {source}")
        lines.append(f"source_type: {source_type}")

        # Add user info if available
        if metadata.get('user_id'):
            lines.append(f"telegram_user_id: {metadata['user_id']}")
        if metadata.get('username'):
            lines.append(f"telegram_username: {metadata['username']}")

        # Tags
        tags = analysis.get('tags', [])
        if tags:
            if self.tag_format == 'yaml':
                lines.append('tags:')
                for tag in tags:
                    lines.append(f"  - {tag}")
            # If inline, tags will be added in the body instead

        # Suggested folder
        suggested_folder = analysis.get('suggested_folder')
        if suggested_folder:
            lines.append(f"suggested_folder: {suggested_folder}")

        # AI metadata
        if analysis.get('analysis_successful'):
            lines.append(f"ai_analyzed: true")
            lines.append(f"ai_provider: {analysis.get('ai_provider', 'unknown')}")

        # Additional metadata
        if metadata.get('has_media'):
            lines.append(f"has_media: true")
        if metadata.get('media_type'):
            lines.append(f"media_type: {metadata['media_type']}")
        if metadata.get('has_ocr'):
            lines.append(f"has_ocr: true")
        if metadata.get('article_url'):
            lines.append(f"article_url: {metadata['article_url']}")

        lines.append('---')

        return '\n'.join(lines)

    def _build_note_body(
        self,
        analysis: Dict[str, Any],
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Build the main body of the note.

        Args:
            analysis: AI analysis results
            content: Original content
            metadata: Additional metadata

        Returns:
            Formatted note body
        """
        lines = []

        # Title
        title = analysis.get('title', 'Untitled Note')
        lines.append(f"\n# {title}\n")

        # If using inline tags, add them here
        if self.tag_format == 'inline' and analysis.get('tags'):
            tag_str = ' '.join([f"#{tag}" for tag in analysis['tags']])
            lines.append(f"{tag_str}\n")

        # Main content
        lines.append(content)
        lines.append("")

        # Media attachments
        if metadata.get('media_attachments'):
            lines.append("## Attachments\n")
            for attachment in metadata['media_attachments']:
                # Obsidian embed syntax
                lines.append(f"![[{attachment}]]\n")

        # OCR text (if different from main content)
        if metadata.get('ocr_text') and metadata.get('source_type') in ['photo', 'document']:
            lines.append("## Extracted Text (OCR)\n")
            lines.append(metadata['ocr_text'])
            lines.append("")

        # AI Analysis section
        if analysis.get('analysis_successful'):
            lines.append("---\n")
            lines.append("## AI Analysis\n")

            summary = analysis.get('summary')
            if summary:
                lines.append(f"**Summary**: {summary}\n")

            entities = analysis.get('entities')
            if entities:
                entities_str = ', '.join(entities)
                lines.append(f"**Key Entities**: {entities_str}\n")

            connections = analysis.get('connections')
            if connections:
                lines.append("**Suggested Connections**:")
                for connection in connections:
                    lines.append(f"- {connection}")
                lines.append("")

        # Footer with metadata
        lines.append("---\n")
        timestamp = metadata.get('timestamp', datetime.now())
        lines.append(f"**Source**: {metadata.get('source', 'Telegram')}")
        if metadata.get('source_type'):
            lines.append(f" ({metadata['source_type']})")
        lines.append(f"\n**Received**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        return '\n'.join(lines)

    def create_preview(
        self,
        analysis: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Create a preview message to send back to Telegram.

        Args:
            analysis: AI analysis results
            metadata: Additional metadata

        Returns:
            Formatted preview text
        """
        lines = []

        lines.append("✓ *Saved to Obsidian*\n")

        title = analysis.get('title', 'Untitled')
        lines.append(f"*Title*: {title}")

        folder = analysis.get('suggested_folder')
        if folder:
            lines.append(f"*Folder*: {folder}")

        tags = analysis.get('tags', [])
        if tags:
            tags_str = ', '.join([f"#{tag}" for tag in tags])
            lines.append(f"*Tags*: {tags_str}")

        summary = analysis.get('summary')
        if summary:
            lines.append(f"\n*Summary*: {summary}")

        connections = analysis.get('connections')
        if connections and len(connections) > 0:
            lines.append(f"\n*Related to*: {connections[0]}")

        # AI provider info
        if not analysis.get('analysis_successful'):
            lines.append("\n_Note: AI analysis was unavailable_")

        return '\n'.join(lines)
