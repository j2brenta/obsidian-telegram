"""Telegram message handlers."""

import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from src.processors.content_analyzer import ContentAnalyzer
from src.processors.media_processor import MediaProcessor
from src.processors.article_processor import ArticleProcessor
from src.obsidian.vault_manager import VaultManager
from src.obsidian.note_creator import NoteCreator
from src.obsidian.note_finder import NoteFinder


logger = logging.getLogger('obsidian_telegram_bot')


class MessageHandlers:
    """Telegram message handlers for the bot."""

    def __init__(
        self,
        content_analyzer: ContentAnalyzer,
        vault_manager: VaultManager,
        note_creator: NoteCreator,
        note_finder: NoteFinder,
        media_processor: MediaProcessor,
        article_processor: ArticleProcessor,
        config: Dict[str, Any]
    ):
        """
        Initialize message handlers.

        Args:
            content_analyzer: Content analyzer instance
            vault_manager: Vault manager instance
            note_creator: Note creator instance
            note_finder: Note finder instance
            media_processor: Media processor instance
            article_processor: Article processor instance
            config: Application configuration
        """
        self.analyzer = content_analyzer
        self.vault = vault_manager
        self.note_creator = note_creator
        self.note_finder = note_finder
        self.media_processor = media_processor
        self.article_processor = article_processor
        self.config = config

        self.allowed_users = config.get('telegram', {}).get('allowed_users')
        self.send_preview = config.get('bot', {}).get('send_preview', True)

    def _reconstruct_text_with_urls(self, text: str, entities) -> str:
        """
        Reconstruct text with inline URLs made visible.

        Converts Telegram entities like [clickable text](hidden_url)
        into Markdown format: [clickable text](url)

        Args:
            text: Original message text
            entities: Message entities from Telegram

        Returns:
            Text with URLs made visible in Markdown format
        """
        # Build list of (offset, length, replacement) tuples
        replacements = []

        for entity in entities:
            if entity.type == 'text_link':
                # Extract the text that was clickable
                entity_text = text[entity.offset:entity.offset + entity.length]
                # Create markdown link
                markdown_link = f"[{entity_text}]({entity.url})"
                replacements.append((entity.offset, entity.length, markdown_link))

        # Sort by offset in reverse so we don't mess up positions
        replacements.sort(key=lambda x: x[0], reverse=True)

        # Apply replacements
        result = text
        for offset, length, replacement in replacements:
            result = result[:offset] + replacement + result[offset + length:]

        return result

    def _check_user_authorization(self, user_id: int) -> bool:
        """
        Check if user is authorized.

        Args:
            user_id: Telegram user ID

        Returns:
            True if authorized
        """
        if self.allowed_users is None:
            return True  # Allow all if not configured

        return user_id in self.allowed_users

    async def handle_text_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle text messages."""
        try:
            user = update.effective_user
            message = update.message

            # Check authorization
            if not self._check_user_authorization(user.id):
                logger.warning(
                    f"Unauthorized access attempt - "
                    f"User ID: {user.id}, "
                    f"Username: @{user.username or 'N/A'}, "
                    f"Name: {user.full_name or 'N/A'}"
                )
                await message.reply_text("Sorry, you are not authorized to use this bot.")
                return

            logger.info(f"Received text message from {user.username or user.id}")

            text = message.text
            timestamp = message.date

            # Extract URLs from text content
            urls_from_text = self.article_processor.extract_urls(text)

            # Extract URLs from message entities (inline links)
            urls_from_entities = []
            if message.entities:
                for entity in message.entities:
                    # URL entity - visible URL in text
                    if entity.type == 'url':
                        url_text = text[entity.offset:entity.offset + entity.length]
                        urls_from_entities.append(url_text)
                    # Text link entity - clickable text with hidden URL
                    elif entity.type == 'text_link':
                        urls_from_entities.append(entity.url)

            # Combine all URLs (remove duplicates)
            urls = list(dict.fromkeys(urls_from_text + urls_from_entities))

            # Reconstruct text with visible URLs for entities
            if message.entities:
                text_with_urls = self._reconstruct_text_with_urls(text, message.entities)
            else:
                text_with_urls = text

            if urls:
                await self._handle_text_with_urls(
                    message,
                    text_with_urls,
                    urls,
                    timestamp,
                    user
                )
            else:
                await self._handle_plain_text(
                    message,
                    text_with_urls,
                    timestamp,
                    user
                )

        except Exception as e:
            logger.exception(f"Error handling text message: {e}")
            await update.message.reply_text(
                "Sorry, an error occurred while processing your message."
            )

    async def _handle_text_with_urls(
        self,
        message,
        text: str,
        urls: list,
        timestamp: datetime,
        user
    ) -> None:
        """Handle text messages containing URLs."""
        logger.info(f"Found {len(urls)} URLs in message")

        # Fetch first article
        article_data = await self.article_processor.process_url(urls[0])

        # Format article for note
        if article_data.get('success'):
            article_content = await self.article_processor.format_article_for_note(article_data)

            # Combine original text and article
            combined_content = f"{text}\n\n---\n\n{article_content}"

            # Use article title if available
            title_hint = article_data.get('title')
        else:
            combined_content = text
            title_hint = None

        # Analyze content
        context_data = {
            'source': 'telegram',
            'content_type': 'article' if article_data.get('success') else 'text_with_url',
            'existing_folders': self.vault.get_existing_folders()
        }

        analysis = await self.analyzer.analyze(combined_content, context_data)

        # Override title if we have article title
        if title_hint:
            analysis['title'] = title_hint

        # Create metadata
        metadata = {
            'timestamp': timestamp,
            'source': 'telegram',
            'source_type': 'article' if article_data.get('success') else 'text',
            'user_id': user.id,
            'username': user.username,
            'article_url': urls[0] if article_data.get('success') else None
        }

        # Create and save note
        note_content, filename = self.note_creator.create_note(
            analysis,
            combined_content,
            metadata
        )

        await self.vault.save_note(note_content, filename)

        # Send preview
        if self.send_preview:
            preview = self.note_creator.create_preview(analysis, metadata)
            await message.reply_text(preview, parse_mode='Markdown')

    async def _handle_plain_text(
        self,
        message,
        text: str,
        timestamp: datetime,
        user
    ) -> None:
        """Handle plain text messages without URLs."""
        # Analyze content
        context_data = {
            'source': 'telegram',
            'content_type': 'text',
            'existing_folders': self.vault.get_existing_folders()
        }

        analysis = await self.analyzer.analyze(text, context_data)

        # Create metadata
        metadata = {
            'timestamp': timestamp,
            'source': 'telegram',
            'source_type': 'text',
            'user_id': user.id,
            'username': user.username
        }

        # Create and save note
        note_content, filename = self.note_creator.create_note(
            analysis,
            text,
            metadata
        )

        await self.vault.save_note(note_content, filename)

        # Send preview
        if self.send_preview:
            preview = self.note_creator.create_preview(analysis, metadata)
            await message.reply_text(preview, parse_mode='Markdown')

    async def handle_photo_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle photo messages with OCR."""
        try:
            user = update.effective_user
            message = update.message

            if not self._check_user_authorization(user.id):
                logger.warning(
                    f"Unauthorized photo upload - "
                    f"User ID: {user.id}, "
                    f"Username: @{user.username or 'N/A'}, "
                    f"Name: {user.full_name or 'N/A'}"
                )
                await message.reply_text("Sorry, you are not authorized.")
                return

            logger.info(f"Received photo from {user.username or user.id}")

            # Get largest photo
            photo = message.photo[-1]

            # Download photo
            file = await photo.get_file()
            file_path, file_data = await self.media_processor.download_telegram_file(
                file,
                context.bot
            )

            # Process OCR
            ocr_result = await self.media_processor.process_image(str(file_path))

            # Save photo to vault
            media_filename = self.media_processor.generate_media_filename(
                media_type='photo'
            )
            saved_path = await self.vault.save_attachment(file_data, media_filename)

            # Combine caption and OCR text
            caption = message.caption or ""
            ocr_text = ocr_result.get('ocr_text', '')

            content = caption
            if ocr_text:
                if caption:
                    content += f"\n\n## Extracted Text\n\n{ocr_text}"
                else:
                    content = ocr_text

            if not content:
                content = "[Image with no text detected]"

            # Analyze
            context_data = {
                'source': 'telegram',
                'content_type': 'photo',
                'existing_folders': self.vault.get_existing_folders()
            }

            analysis = await self.analyzer.analyze(content, context_data)

            # Create metadata
            metadata = {
                'timestamp': message.date,
                'source': 'telegram',
                'source_type': 'photo',
                'user_id': user.id,
                'username': user.username,
                'has_media': True,
                'media_type': 'photo',
                'media_attachments': [str(saved_path)],
                'has_ocr': ocr_result.get('has_text', False),
                'ocr_text': ocr_text if ocr_result.get('has_text') else None
            }

            # Create and save note
            note_content, filename = self.note_creator.create_note(
                analysis,
                content,
                metadata
            )

            await self.vault.save_note(note_content, filename)

            # Send preview
            if self.send_preview:
                preview = self.note_creator.create_preview(analysis, metadata)
                if ocr_result.get('has_text'):
                    preview += f"\n\n_OCR: {len(ocr_text)} characters extracted_"
                await message.reply_text(preview, parse_mode='Markdown')

            # Clean up temp file
            try:
                file_path.unlink()
            except:
                pass

        except Exception as e:
            logger.exception(f"Error handling photo: {e}")
            await update.message.reply_text(
                "Sorry, an error occurred while processing your photo."
            )

    async def handle_voice_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle voice messages (placeholder - transcription not fully implemented)."""
        try:
            user = update.effective_user
            message = update.message

            if not self._check_user_authorization(user.id):
                logger.warning(
                    f"Unauthorized voice message - "
                    f"User ID: {user.id}, "
                    f"Username: @{user.username or 'N/A'}, "
                    f"Name: {user.full_name or 'N/A'}"
                )
                await message.reply_text("Sorry, you are not authorized.")
                return

            logger.info(f"Received voice message from {user.username or user.id}")

            voice = message.voice

            # Note: Voice transcription not fully implemented
            # Would require Whisper API or similar service

            content = f"[Voice message - {voice.duration} seconds]\n\nVoice transcription not yet implemented."

            # Simple analysis
            context_data = {
                'source': 'telegram',
                'content_type': 'voice',
                'existing_folders': self.vault.get_existing_folders()
            }

            analysis = await self.analyzer.analyze(content, context_data)
            analysis['title'] = f"Voice Note - {message.date.strftime('%Y-%m-%d %H:%M')}"

            metadata = {
                'timestamp': message.date,
                'source': 'telegram',
                'source_type': 'voice',
                'user_id': user.id,
                'username': user.username,
                'has_media': True,
                'media_type': 'voice'
            }

            note_content, filename = self.note_creator.create_note(
                analysis,
                content,
                metadata
            )

            await self.vault.save_note(note_content, filename)

            if self.send_preview:
                await message.reply_text(
                    f"✓ Voice note saved\n\n_Note: Transcription not yet implemented_",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.exception(f"Error handling voice message: {e}")
            await update.message.reply_text(
                "Sorry, an error occurred while processing your voice message."
            )

    async def handle_start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start command."""
        user = update.effective_user

        if not self._check_user_authorization(user.id):
            logger.warning(
                f"Unauthorized /start command - "
                f"User ID: {user.id}, "
                f"Username: @{user.username or 'N/A'}, "
                f"Name: {user.full_name or 'N/A'}"
            )
            await update.message.reply_text("Sorry, you are not authorized.")
            return

        welcome_message = f"""
Hello {user.first_name}!

I'm your Obsidian Telegram Bot. Send me any message and I'll save it to your Obsidian vault with AI-powered organization.

*What I can do:*
- Save text messages with smart tagging and categorization
- Extract text from images (OCR)
- Fetch and summarize web articles
- Suggest connections to your existing notes

Just send me anything and I'll handle the rest!
"""

        await update.message.reply_text(welcome_message, parse_mode='Markdown')
