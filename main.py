"""Main entry point for the Obsidian Telegram Bot."""

import sys
import logging
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import ConfigLoader, ConfigurationError
from src.utils.logger import BotLogger
from src.processors.content_analyzer import ContentAnalyzer
from src.processors.media_processor import MediaProcessor
from src.processors.article_processor import ArticleProcessor
from src.obsidian.vault_manager import VaultManager
from src.obsidian.note_creator import NoteCreator
from src.obsidian.note_finder import NoteFinder
from src.bot.handlers import MessageHandlers
from src.bot.telegram_client import TelegramBot


def main():
    """Main entry point."""
    try:
        # Load configuration
        print("Loading configuration...")
        config_loader = ConfigLoader()
        config = config_loader.load()

        # Setup logging
        logger = BotLogger.setup(config)
        logger.info("=" * 60)
        logger.info("Obsidian Telegram Bot Starting")
        logger.info("=" * 60)

        # Display configuration
        ai_provider = config.get('ai', {}).get('provider', 'unknown')
        vault_path = config.get('obsidian', {}).get('vault_path', 'unknown')
        logger.info(f"AI Provider: {ai_provider}")
        logger.info(f"Obsidian Vault: {vault_path}")

        # Initialize AI provider
        logger.info("Initializing AI provider...")
        ai_provider_instance = config_loader.get_ai_provider()

        # Initialize components
        logger.info("Initializing components...")

        vault_manager = VaultManager(
            vault_path=config['obsidian']['vault_path'],
            config=config
        )

        note_creator = NoteCreator(config=config)

        note_finder = NoteFinder(
            vault_path=config['obsidian']['vault_path']
        )

        content_analyzer = ContentAnalyzer(
            ai_provider=ai_provider_instance,
            config=config
        )

        media_processor = MediaProcessor(config=config)

        article_processor = ArticleProcessor(config=config)

        message_handlers = MessageHandlers(
            content_analyzer=content_analyzer,
            vault_manager=vault_manager,
            note_creator=note_creator,
            note_finder=note_finder,
            media_processor=media_processor,
            article_processor=article_processor,
            config=config
        )

        # Create Telegram bot
        logger.info("Initializing Telegram bot...")
        bot = TelegramBot(
            bot_token=config['telegram']['bot_token'],
            message_handlers=message_handlers,
            config=config
        )

        # Run bot
        logger.info("Starting bot...")
        logger.info("Bot is ready to receive messages!")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        bot.run()

    except ConfigurationError as e:
        print(f"\n❌ Configuration Error: {e}\n")
        print("Please check your .env and config.yaml files.")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nShutting down bot...")
        logging.info("Bot stopped by user")
        sys.exit(0)

    except Exception as e:
        logging.exception(f"Fatal error: {e}")
        print(f"\n❌ Fatal Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
