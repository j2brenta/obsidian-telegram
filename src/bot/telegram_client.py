"""Telegram bot client setup and initialization."""

import logging
from typing import Dict, Any

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)

from .handlers import MessageHandlers


logger = logging.getLogger('obsidian_telegram_bot')


class TelegramBot:
    """Telegram bot client wrapper."""

    def __init__(
        self,
        bot_token: str,
        message_handlers: MessageHandlers,
        config: Dict[str, Any]
    ):
        """
        Initialize Telegram bot.

        Args:
            bot_token: Telegram bot token
            message_handlers: Message handlers instance
            config: Application configuration
        """
        self.bot_token = bot_token
        self.handlers = message_handlers
        self.config = config
        self.application: Application = None

    def create_application(self) -> Application:
        """
        Create and configure the Telegram application.

        Returns:
            Configured Application instance
        """
        logger.info("Creating Telegram bot application")

        # Create application
        self.application = Application.builder().token(self.bot_token).build()

        # Register command handlers
        self.application.add_handler(
            CommandHandler("start", self.handlers.handle_start_command)
        )

        # Register message handlers
        # Text messages (without photo, voice, etc.)
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handlers.handle_text_message
            )
        )

        # Photo messages
        self.application.add_handler(
            MessageHandler(
                filters.PHOTO,
                self.handlers.handle_photo_message
            )
        )

        # Voice messages
        self.application.add_handler(
            MessageHandler(
                filters.VOICE,
                self.handlers.handle_voice_message
            )
        )

        logger.info("Telegram bot handlers registered")

        return self.application

    async def start(self) -> None:
        """Start the bot with polling."""
        if not self.application:
            self.create_application()

        logger.info("Starting Telegram bot with polling...")

        # Start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=['message']
        )

        logger.info("Bot is now running. Press Ctrl+C to stop.")

    async def stop(self) -> None:
        """Stop the bot."""
        if self.application:
            logger.info("Stopping Telegram bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Bot stopped successfully")

    def run(self) -> None:
        """Run the bot (blocking)."""
        if not self.application:
            self.create_application()

        logger.info("Running Telegram bot...")

        # Run with polling (blocking)
        self.application.run_polling(
            drop_pending_updates=True,
            allowed_updates=['message']
        )
