"""AI prompt templates for content analysis."""

from typing import Dict, List, Optional, Any


def build_analysis_prompt(
    content: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build a comprehensive content analysis prompt for AI.

    Args:
        content: The content to analyze
        context: Additional context (source, existing folders, etc.)

    Returns:
        Formatted prompt string
    """
    context = context or {}
    source = context.get('source', 'Telegram')
    content_type = context.get('content_type', 'text')
    existing_folders = context.get('existing_folders', [])

    folders_info = ""
    if existing_folders:
        folders_info = f"\n- Existing folders in vault: {', '.join(existing_folders[:20])}"
        if len(existing_folders) > 20:
            folders_info += " (and more...)"

    prompt = f"""You are an intelligent assistant helping organize information for an INTP researcher who collects lots of information but needs help with structure and connections.

Content to analyze:
{content}

Context:
- Source: {source}
- Content type: {content_type}{folders_info}

Please analyze this content and provide a structured response in JSON format with the following fields:

{{
  "title": "A concise, descriptive title (3-8 words)",
  "summary": "A 2-3 sentence summary capturing the key points and insights",
  "tags": ["tag1", "tag2", "tag3"],
  "suggested_folder": "Recommended folder path (e.g., 'Knowledge/Tech', 'Ideas', 'Inbox')",
  "connections": ["Connection or theme 1", "Connection or theme 2"],
  "entities": ["Entity1", "Entity2", "Entity3"]
}}

Guidelines:
- Title: Should be specific and searchable, not generic
- Summary: Focus on WHY this is interesting, not just WHAT it is
- Tags: Use broad, reusable categories (3-5 tags). Think about future findability.
- Folder: Match existing folders when appropriate, or suggest new ones for distinct topics. Use paths like "Category/Subcategory" for better organization.
- Connections: Identify themes, concepts, or questions this relates to. Help the user see patterns across their collected information.
- Entities: Extract key people, organizations, technologies, or concepts mentioned

For an INTP organizing notes:
- Prioritize conceptual connections over rigid categorization
- Suggest tags that enable graph-view discovery
- Identify abstract patterns and cross-domain links
- Support building a "second brain" with interconnected knowledge

Respond ONLY with valid JSON, no additional text."""

    return prompt


def build_summary_prompt(content: str, max_length: Optional[int] = None) -> str:
    """
    Build a prompt for content summarization.

    Args:
        content: Content to summarize
        max_length: Maximum summary length in words

    Returns:
        Formatted prompt string
    """
    length_guidance = f" in approximately {max_length} words" if max_length else ""

    return f"""Summarize the following content{length_guidance}. Focus on the main insights, key arguments, or important information. Make it useful for future reference.

Content:
{content}

Provide a clear, concise summary that captures the essence of the content."""


def build_tags_prompt(content: str, max_tags: int = 5) -> str:
    """
    Build a prompt for tag suggestion.

    Args:
        content: Content to tag
        max_tags: Maximum number of tags

    Returns:
        Formatted prompt string
    """
    return f"""Suggest {max_tags} tags for the following content. Tags should be:
- Broad enough to be reusable across multiple notes
- Specific enough to be meaningful for filtering
- Focused on concepts, domains, and themes rather than specific details

Content:
{content}

Respond with ONLY a comma-separated list of tags, nothing else.
Example: technology, machine-learning, philosophy, productivity"""


def build_folder_prompt(
    content: str,
    available_folders: Optional[List[str]] = None
) -> str:
    """
    Build a prompt for folder suggestion.

    Args:
        content: Content to categorize
        available_folders: Existing folders in vault

    Returns:
        Formatted prompt string
    """
    folders_context = ""
    if available_folders:
        folders_list = ", ".join(available_folders[:30])
        folders_context = f"\n\nExisting folders: {folders_list}"
        if len(available_folders) > 30:
            folders_context += " (and more...)"
        folders_context += "\n\nPrefer using existing folders when they match, or suggest a new folder path if this content represents a distinct topic."

    return f"""Suggest the best folder location for this content in an Obsidian vault.{folders_context}

Content:
{content}

Respond with ONLY the folder path (e.g., "Knowledge/Technology" or "Ideas" or "Inbox"). Nothing else."""


def build_connections_prompt(
    content: str,
    existing_notes: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Build a prompt for finding connections to existing notes.

    Args:
        content: Content to analyze
        existing_notes: List of existing notes with titles and tags

    Returns:
        Formatted prompt string
    """
    notes_context = ""
    if existing_notes:
        notes_list = "\n".join([
            f"- {note.get('title', 'Untitled')} (tags: {', '.join(note.get('tags', []))})"
            for note in existing_notes[:20]
        ])
        notes_context = f"\n\nSome existing notes in the vault:\n{notes_list}"
        if len(existing_notes) > 20:
            notes_context += "\n(and more...)"

    return f"""Identify potential connections or related themes for this new content.{notes_context}

New content:
{content}

Suggest 2-4 conceptual connections, themes, or questions this content relates to. Focus on abstract patterns and ideas rather than exact matches.

Respond with a JSON array of strings:
["Connection or theme 1", "Connection or theme 2", "Connection or theme 3"]"""


# Fallback responses for when AI is unavailable
FALLBACK_ANALYSIS = {
    "title": "Untitled Note",
    "summary": "Content saved from Telegram (AI analysis unavailable)",
    "tags": ["inbox", "unprocessed"],
    "suggested_folder": "Inbox",
    "connections": [],
    "entities": []
}
