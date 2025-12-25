"""Logging configuration for the Telegram-Obsidian bot."""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[1;31m', # Bold Red
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'

    def format(self, record):
        # Add color to levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Format the message
        result = super().format(record)

        # Reset levelname for other handlers
        record.levelname = levelname

        return result


class BotLogger:
    """Centralized logging configuration."""

    _instance: Optional[logging.Logger] = None

    @classmethod
    def setup(cls, config: dict) -> logging.Logger:
        """
        Set up logging with file rotation and console output.

        Args:
            config: Configuration dictionary with logging settings

        Returns:
            Configured logger instance
        """
        if cls._instance is not None:
            return cls._instance

        # Get logging configuration
        log_config = config.get('logging', {})
        log_file = log_config.get('file', 'logs/bot.log')
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        max_bytes = log_config.get('max_size_mb', 10) * 1024 * 1024
        backup_count = log_config.get('backup_count', 5)
        console_output = log_config.get('console_output', True)

        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create logger
        logger = logging.getLogger('obsidian_telegram_bot')
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Prevent propagation to root logger to avoid duplicate messages
        logger.propagate = False

        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()

        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        colored_formatter = ColoredFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

        # Console handler with colors
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, log_level, logging.INFO))
            console_handler.setFormatter(colored_formatter)
            logger.addHandler(console_handler)

        cls._instance = logger
        logger.info(f"Logging initialized - Level: {log_level}, File: {log_file}")

        return logger

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Get the logger instance."""
        if cls._instance is None:
            raise RuntimeError("Logger not initialized. Call setup() first.")
        return cls._instance


def get_logger() -> logging.Logger:
    """Convenience function to get the logger."""
    return BotLogger.get_logger()


class EvaluationLogger:
    """Separate logger for detailed AI evaluation and model performance tracking."""

    _instance: Optional[logging.Logger] = None

    @classmethod
    def setup(cls) -> logging.Logger:
        """
        Set up evaluation logger with daily rotation.

        Returns:
            Configured evaluation logger instance
        """
        if cls._instance is not None:
            return cls._instance

        # Create evaluation logger
        eval_logger = logging.getLogger('obsidian_telegram_bot.evaluation')
        eval_logger.setLevel(logging.DEBUG)
        eval_logger.propagate = False

        # Remove existing handlers
        eval_logger.handlers.clear()

        # Create logs/eval directory
        eval_dir = Path('logs/eval')
        eval_dir.mkdir(parents=True, exist_ok=True)

        # Create daily log file with date in filename
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = eval_dir / f'{today}-eval.log'

        # Detailed formatter for evaluation
        detailed_formatter = logging.Formatter(
            '\n{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "data": %(message)s}',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # File handler (no rotation, one file per day)
        file_handler = logging.FileHandler(
            log_file,
            mode='a',
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        eval_logger.addHandler(file_handler)

        cls._instance = eval_logger
        eval_logger.info('"message": "Evaluation logging started", "file": "' + str(log_file) + '"')

        return eval_logger

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Get the evaluation logger instance."""
        if cls._instance is None:
            return cls.setup()
        return cls._instance


def get_eval_logger() -> logging.Logger:
    """Convenience function to get the evaluation logger."""
    return EvaluationLogger.get_logger()
