"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class AIProviderError(Exception):
    """Raised when AI provider encounters an error."""
    pass


class AIProvider(ABC):
    """Abstract interface for AI providers (Claude, Ollama, etc.)."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the AI provider.

        Args:
            config: AI configuration dictionary
        """
        self.config = config

    @abstractmethod
    async def analyze_content(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze content and return structured suggestions.

        Args:
            content: The content to analyze (text, transcription, etc.)
            context: Additional context (source, existing folders, etc.)

        Returns:
            Dictionary containing:
                - title: str - Suggested title for the note
                - summary: str - Brief summary of the content
                - tags: List[str] - Suggested tags
                - suggested_folder: str - Recommended folder path
                - connections: List[str] - Potential connections to existing notes
                - entities: List[str] - Extracted entities (people, places, concepts)

        Raises:
            AIProviderError: If analysis fails
        """
        pass

    @abstractmethod
    async def generate_summary(
        self,
        content: str,
        max_length: Optional[int] = None
    ) -> str:
        """
        Generate a summary of the content.

        Args:
            content: The content to summarize
            max_length: Maximum length of summary in words

        Returns:
            Summary text

        Raises:
            AIProviderError: If summarization fails
        """
        pass

    @abstractmethod
    async def suggest_tags(
        self,
        content: str,
        max_tags: int = 5
    ) -> List[str]:
        """
        Suggest tags for the content.

        Args:
            content: The content to tag
            max_tags: Maximum number of tags to return

        Returns:
            List of suggested tags

        Raises:
            AIProviderError: If tag suggestion fails
        """
        pass

    @abstractmethod
    async def suggest_folder(
        self,
        content: str,
        available_folders: Optional[List[str]] = None
    ) -> str:
        """
        Suggest a folder for the content.

        Args:
            content: The content to categorize
            available_folders: List of existing folders in the vault

        Returns:
            Suggested folder path

        Raises:
            AIProviderError: If folder suggestion fails
        """
        pass

    @abstractmethod
    async def find_connections(
        self,
        content: str,
        existing_notes: Optional[List[Dict[str, str]]] = None
    ) -> List[str]:
        """
        Find potential connections to existing notes.

        Args:
            content: The content to analyze
            existing_notes: List of dicts with 'title' and 'tags' keys

        Returns:
            List of connection descriptions

        Raises:
            AIProviderError: If connection finding fails
        """
        pass

    def _truncate_content(self, content: str, max_chars: int = 10000) -> str:
        """
        Truncate content to avoid token limits.

        Args:
            content: Content to truncate
            max_chars: Maximum number of characters

        Returns:
            Truncated content with indicator if truncated
        """
        if len(content) <= max_chars:
            return content

        return content[:max_chars] + "\n\n[Content truncated for analysis...]"
