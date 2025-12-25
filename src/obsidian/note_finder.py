"""Find and search existing notes in Obsidian vault."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

logger = logging.getLogger('obsidian_telegram_bot')


class NoteFinder:
    """Search and find related notes in the vault."""

    def __init__(self, vault_path: str):
        """
        Initialize note finder.

        Args:
            vault_path: Path to Obsidian vault
        """
        self.vault_path = Path(vault_path)

    async def find_related_notes(
        self,
        tags: List[str],
        entities: Optional[List[str]] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find notes related to given tags and entities.

        Args:
            tags: List of tags to search for
            entities: Optional list of entities to search for
            max_results: Maximum number of results to return

        Returns:
            List of note info dictionaries with 'title', 'path', 'tags', 'score'
        """
        if not tags and not entities:
            return []

        try:
            logger.debug(f"Searching for related notes - Tags: {tags}, Entities: {entities}")

            related_notes = []

            # Scan all markdown files
            for note_path in self.vault_path.rglob('*.md'):
                # Skip hidden files
                if any(part.startswith('.') for part in note_path.parts):
                    continue

                # Read note content
                try:
                    content = note_path.read_text(encoding='utf-8')
                except Exception as e:
                    logger.warning(f"Could not read {note_path}: {e}")
                    continue

                # Calculate relevance score
                score = self._calculate_relevance_score(
                    content=content,
                    tags=tags,
                    entities=entities or []
                )

                if score > 0:
                    # Extract note info
                    note_info = {
                        'title': self._extract_title(content, note_path),
                        'path': str(note_path.relative_to(self.vault_path)),
                        'tags': self._extract_tags(content),
                        'score': score
                    }
                    related_notes.append(note_info)

            # Sort by score (highest first) and limit results
            related_notes.sort(key=lambda x: x['score'], reverse=True)
            results = related_notes[:max_results]

            logger.debug(f"Found {len(results)} related notes")
            return results

        except Exception as e:
            logger.error(f"Error finding related notes: {e}")
            return []

    def _calculate_relevance_score(
        self,
        content: str,
        tags: List[str],
        entities: List[str]
    ) -> float:
        """
        Calculate relevance score for a note.

        Args:
            content: Note content
            tags: Tags to match
            entities: Entities to match

        Returns:
            Relevance score (higher is more relevant)
        """
        score = 0.0
        content_lower = content.lower()

        # Score for matching tags (case-insensitive)
        for tag in tags:
            tag_lower = tag.lower()

            # Check for tag in frontmatter or inline
            if f"#{tag_lower}" in content_lower or f"- {tag_lower}" in content_lower:
                score += 2.0  # High weight for tag matches

        # Score for matching entities
        for entity in entities:
            entity_lower = entity.lower()

            # Count occurrences
            count = content_lower.count(entity_lower)
            if count > 0:
                score += min(count * 0.5, 2.0)  # Cap at 2.0 per entity

        return score

    def _extract_title(self, content: str, file_path: Path) -> str:
        """
        Extract title from note content.

        Args:
            content: Note content
            file_path: Path to the note file

        Returns:
            Note title
        """
        # Try to find H1 heading
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        # Try frontmatter title
        match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).strip().strip('"\'')

        # Fallback to filename
        return file_path.stem

    def _extract_tags(self, content: str) -> List[str]:
        """
        Extract tags from note content.

        Args:
            content: Note content

        Returns:
            List of tags found in the note
        """
        tags = set()

        # Extract from frontmatter
        in_frontmatter = False
        in_tags_section = False

        for line in content.split('\n'):
            if line.strip() == '---':
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    in_frontmatter = False
                    in_tags_section = False
                continue

            if in_frontmatter:
                if line.strip().startswith('tags:'):
                    in_tags_section = True
                    continue
                elif in_tags_section and line.startswith('  - '):
                    tag = line.strip('  - ').strip()
                    tags.add(tag)
                elif in_tags_section and not line.startswith('  '):
                    in_tags_section = False

        # Extract inline tags (#tag)
        inline_tags = re.findall(r'#([\w-]+)', content)
        tags.update(inline_tags)

        return list(tags)

    async def search_content(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search note content for a query string.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of matching notes
        """
        if not query or len(query) < 3:
            return []

        try:
            query_lower = query.lower()
            matches = []

            for note_path in self.vault_path.rglob('*.md'):
                if any(part.startswith('.') for part in note_path.parts):
                    continue

                try:
                    content = note_path.read_text(encoding='utf-8')
                    content_lower = content.lower()

                    if query_lower in content_lower:
                        matches.append({
                            'title': self._extract_title(content, note_path),
                            'path': str(note_path.relative_to(self.vault_path))
                        })

                        if len(matches) >= max_results:
                            break

                except Exception as e:
                    logger.warning(f"Could not read {note_path}: {e}")
                    continue

            logger.debug(f"Found {len(matches)} notes matching '{query}'")
            return matches

        except Exception as e:
            logger.error(f"Error searching content: {e}")
            return []
