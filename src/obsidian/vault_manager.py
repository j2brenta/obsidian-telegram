"""Obsidian vault file operations manager."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger('obsidian_telegram_bot')


class VaultError(Exception):
    """Raised when vault operations fail."""
    pass


class VaultManager:
    """Manages file operations in the Obsidian vault."""

    def __init__(self, vault_path: str, config: Dict[str, Any]):
        """
        Initialize vault manager.

        Args:
            vault_path: Absolute path to Obsidian vault
            config: Application configuration
        """
        self.vault_path = Path(vault_path)
        self.config = config

        # Get configuration
        obsidian_config = config.get('obsidian', {})
        self.incoming_folder = obsidian_config.get('incoming_folder', 'Incoming')
        self.media_folder = config.get('media', {}).get('media_folder', '_attachments')

        # Validate vault path
        if not self.vault_path.exists():
            raise VaultError(f"Vault path does not exist: {self.vault_path}")

        logger.info(f"Initialized vault manager - Vault: {self.vault_path}")

    async def save_note(
        self,
        note_content: str,
        filename: str,
        subfolder: Optional[str] = None
    ) -> Path:
        """
        Save a note to the vault.

        Args:
            note_content: Markdown content of the note
            filename: Filename (with or without .md extension)
            subfolder: Optional subfolder within incoming folder

        Returns:
            Path to the saved note

        Raises:
            VaultError: If save operation fails
        """
        try:
            # Ensure filename has .md extension
            if not filename.endswith('.md'):
                filename = f"{filename}.md"

            # Determine target folder
            if subfolder:
                target_folder = self.vault_path / self.incoming_folder / subfolder
            else:
                target_folder = self.vault_path / self.incoming_folder

            # Create folder if it doesn't exist
            target_folder.mkdir(parents=True, exist_ok=True)

            # Handle filename conflicts
            note_path = target_folder / filename
            note_path = self._resolve_filename_conflict(note_path)

            # Write the note
            note_path.write_text(note_content, encoding='utf-8')

            logger.info(f"Note saved: {note_path.relative_to(self.vault_path)}")
            return note_path

        except Exception as e:
            logger.error(f"Failed to save note: {e}")
            raise VaultError(f"Could not save note: {e}")

    async def save_attachment(
        self,
        file_data: bytes,
        filename: str
    ) -> Path:
        """
        Save a media attachment to the vault.

        Args:
            file_data: Binary file data
            filename: Filename for the attachment

        Returns:
            Path to the saved attachment (relative to vault for linking)

        Raises:
            VaultError: If save operation fails
        """
        try:
            # Create attachments folder
            attachments_folder = self.vault_path / self.media_folder
            attachments_folder.mkdir(parents=True, exist_ok=True)

            # Handle filename conflicts
            file_path = attachments_folder / filename
            file_path = self._resolve_filename_conflict(file_path)

            # Write file
            file_path.write_bytes(file_data)

            # Return relative path for Obsidian linking
            relative_path = file_path.relative_to(self.vault_path)

            logger.info(f"Attachment saved: {relative_path}")
            return relative_path

        except Exception as e:
            logger.error(f"Failed to save attachment: {e}")
            raise VaultError(f"Could not save attachment: {e}")

    def get_existing_folders(self, max_depth: int = 3) -> List[str]:
        """
        Scan vault for existing folders.

        Args:
            max_depth: Maximum folder depth to scan

        Returns:
            List of folder paths relative to vault root
        """
        folders = []

        try:
            # Walk the vault directory
            for item in self.vault_path.rglob('*'):
                if item.is_dir():
                    # Skip hidden folders and system folders
                    if any(part.startswith('.') for part in item.parts):
                        continue

                    # Calculate depth
                    relative_path = item.relative_to(self.vault_path)
                    depth = len(relative_path.parts)

                    if depth <= max_depth:
                        folders.append(str(relative_path))

            logger.debug(f"Found {len(folders)} folders in vault")
            return sorted(folders)

        except Exception as e:
            logger.warning(f"Could not scan vault folders: {e}")
            return []

    def _resolve_filename_conflict(self, file_path: Path) -> Path:
        """
        Resolve filename conflicts by appending a number.

        Args:
            file_path: Desired file path

        Returns:
            Available file path (may be modified if conflict exists)
        """
        if not file_path.exists():
            return file_path

        # Extract name and extension
        name = file_path.stem
        extension = file_path.suffix
        parent = file_path.parent

        # Try appending numbers
        counter = 1
        while True:
            new_path = parent / f"{name}-{counter}{extension}"
            if not new_path.exists():
                logger.debug(f"Resolved filename conflict: {file_path.name} -> {new_path.name}")
                return new_path
            counter += 1

            # Safety limit
            if counter > 1000:
                raise VaultError("Could not resolve filename conflict after 1000 attempts")

    def get_incoming_folder_path(self) -> Path:
        """Get the full path to the incoming folder."""
        return self.vault_path / self.incoming_folder

    def get_media_folder_path(self) -> Path:
        """Get the full path to the media folder."""
        return self.vault_path / self.media_folder
