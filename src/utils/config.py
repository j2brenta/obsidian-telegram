"""Configuration management and AI provider factory."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class ConfigLoader:
    """Loads and validates configuration from .env and config.yaml."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the configuration loader.

        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from .env and config.yaml files.

        Returns:
            Complete configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Load environment variables from .env file
        load_dotenv()

        # Load YAML configuration
        try:
            with open(self.config_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config is None:
                    raise ConfigurationError(f"Empty or invalid YAML file: {self.config_path}")
                self.config = yaml_config
        except FileNotFoundError:
            raise ConfigurationError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML syntax: {e}")

        # Validate required environment variables
        self._validate_env_vars()

        # Merge environment variables into config
        self._merge_env_vars()

        return self.config

    def _validate_env_vars(self) -> None:
        """
        Validate that required environment variables are set.

        Raises:
            ConfigurationError: If required variables are missing
        """
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'OBSIDIAN_VAULT_PATH',
        ]

        # Check AI provider and require appropriate API key
        ai_provider = self.config.get('ai', {}).get('provider', 'claude')
        if ai_provider == 'claude':
            required_vars.append('CLAUDE_API_KEY')

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            raise ConfigurationError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                f"Please copy .env.example to .env and fill in your values."
            )

        # Validate vault path exists
        vault_path = Path(os.getenv('OBSIDIAN_VAULT_PATH'))
        if not vault_path.exists():
            raise ConfigurationError(
                f"Obsidian vault path does not exist: {vault_path}\n"
                f"Please create the directory or update OBSIDIAN_VAULT_PATH in .env"
            )

    def _merge_env_vars(self) -> None:
        """Merge environment variables into the configuration dict."""
        self.config['telegram'] = {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'allowed_users': self._parse_allowed_users(),
        }

        self.config['obsidian']['vault_path'] = os.getenv('OBSIDIAN_VAULT_PATH')

        # Override incoming folder if set in env
        if os.getenv('OBSIDIAN_INCOMING_FOLDER'):
            self.config['obsidian']['incoming_folder'] = os.getenv('OBSIDIAN_INCOMING_FOLDER')

        # AI API keys
        self.config['ai']['claude']['api_key'] = os.getenv('CLAUDE_API_KEY', '')
        self.config['ai']['ollama']['base_url'] = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

    def _parse_allowed_users(self) -> Optional[list]:
        """
        Parse comma-separated list of allowed user IDs.

        Returns:
            List of integer user IDs, or None if not set (allow all)
        """
        users_str = os.getenv('TELEGRAM_ALLOWED_USERS', '')
        if not users_str:
            return None

        try:
            return [int(uid.strip()) for uid in users_str.split(',') if uid.strip()]
        except ValueError:
            raise ConfigurationError(
                f"Invalid TELEGRAM_ALLOWED_USERS format: {users_str}\n"
                f"Expected comma-separated list of integers"
            )

    def get_ai_provider(self):
        """
        Factory method to create the appropriate AI provider.

        Returns:
            AIProvider instance (ClaudeProvider or OllamaProvider)

        Raises:
            ConfigurationError: If provider is unknown or cannot be initialized
        """
        from src.ai.base import AIProvider
        from src.ai.claude_provider import ClaudeProvider
        from src.ai.ollama_provider import OllamaProvider

        provider_name = self.config.get('ai', {}).get('provider', 'claude')

        if provider_name == 'claude':
            api_key = self.config['ai']['claude'].get('api_key')
            if not api_key:
                raise ConfigurationError("Claude API key not set in environment")

            return ClaudeProvider(
                api_key=api_key,
                model=self.config['ai']['claude']['model'],
                config=self.config['ai']
            )

        elif provider_name == 'ollama':
            return OllamaProvider(
                base_url=self.config['ai']['ollama']['base_url'],
                model=self.config['ai']['ollama']['model'],
                config=self.config['ai']
            )

        else:
            raise ConfigurationError(
                f"Unknown AI provider: {provider_name}\n"
                f"Valid options: 'claude', 'ollama'"
            )


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Convenience function to load configuration.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Complete configuration dictionary
    """
    loader = ConfigLoader(config_path)
    return loader.load()
