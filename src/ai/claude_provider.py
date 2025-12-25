"""Claude AI provider implementation."""

import json
import logging
from typing import Dict, List, Any, Optional

import anthropic

from .base import AIProvider, AIProviderError
from . import prompts
from src.utils.logger import get_eval_logger


logger = logging.getLogger('obsidian_telegram_bot')
eval_logger = get_eval_logger()


class ClaudeProvider(AIProvider):
    """AI provider using Anthropic's Claude API."""

    def __init__(self, api_key: str, model: str, config: Dict[str, Any]):
        """
        Initialize Claude provider.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            config: AI configuration dictionary
        """
        super().__init__(config)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = config.get('claude', {}).get('max_tokens', 2000)
        self.temperature = config.get('claude', {}).get('temperature', 0.7)

        logger.info(f"Initialized Claude provider with model: {model}")

    async def analyze_content(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze content using Claude and return structured suggestions.

        Args:
            content: The content to analyze
            context: Additional context

        Returns:
            Dictionary with analysis results

        Raises:
            AIProviderError: If analysis fails
        """
        import time
        start_time = time.time()

        try:
            # Truncate content if too long
            original_length = len(content)
            content = self._truncate_content(content)
            was_truncated = len(content) < original_length

            # Build the analysis prompt
            prompt = prompts.build_analysis_prompt(content, context)
            content_type = context.get('content_type', 'unknown') if context else 'unknown'

            # Call Claude API
            logger.info(
                f"[Claude] Analyzing {content_type} - "
                f"Length: {len(content)} chars{' (truncated)' if was_truncated else ''}"
            )

            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract response text
            response_text = message.content[0].text

            # Calculate API metrics
            elapsed_time = time.time() - start_time
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens

            logger.info(
                f"[Claude] API Response - "
                f"Time: {elapsed_time:.2f}s, "
                f"Tokens: {input_tokens} in / {output_tokens} out"
            )

            # Parse JSON response
            analysis = self._parse_json_response(response_text)

            # Console log - summary
            logger.info(
                f"[Claude] Analysis Complete - "
                f"Title: '{analysis.get('title', 'N/A')[:50]}', "
                f"Tags: {len(analysis.get('tags', []))} ({', '.join(analysis.get('tags', [])[:3])}), "
                f"Folder: '{analysis.get('suggested_folder', 'N/A')}'"
            )

            # Detailed evaluation log
            eval_data = {
                "operation": "analyze_content",
                "provider": "claude",
                "model": self.model,
                "content_type": content_type,
                "input": {
                    "content_length": original_length,
                    "truncated": was_truncated,
                    "content_preview": content[:200] + "..." if len(content) > 200 else content,
                },
                "prompt": {
                    "full_prompt": prompt,
                    "prompt_length": len(prompt)
                },
                "response": {
                    "raw_response": response_text,
                    "response_length": len(response_text)
                },
                "parsed_analysis": analysis,
                "metrics": {
                    "elapsed_time_seconds": elapsed_time,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "cost_estimate_usd": self._estimate_cost(input_tokens, output_tokens)
                },
                "quality_indicators": {
                    "has_title": bool(analysis.get('title')),
                    "has_summary": bool(analysis.get('summary')),
                    "num_tags": len(analysis.get('tags', [])),
                    "has_folder": bool(analysis.get('suggested_folder')),
                    "num_connections": len(analysis.get('connections', [])),
                    "num_entities": len(analysis.get('entities', [])),
                    "parsing_successful": True
                }
            }
            eval_logger.info(json.dumps(eval_data, ensure_ascii=False, indent=2))

            return analysis

        except anthropic.APIError as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[Claude] API error after {elapsed_time:.2f}s: {e}")

            # Log error to evaluation
            error_data = {
                "operation": "analyze_content",
                "provider": "claude",
                "model": self.model,
                "error": str(e),
                "error_type": "APIError",
                "elapsed_time_seconds": elapsed_time
            }
            eval_logger.error(json.dumps(error_data, ensure_ascii=False))

            raise AIProviderError(f"Claude API error: {e}")
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[Claude] Provider error after {elapsed_time:.2f}s: {e}")

            # Log error to evaluation
            error_data = {
                "operation": "analyze_content",
                "provider": "claude",
                "model": self.model,
                "error": str(e),
                "error_type": type(e).__name__,
                "elapsed_time_seconds": elapsed_time
            }
            eval_logger.error(json.dumps(error_data, ensure_ascii=False))

            raise AIProviderError(f"Analysis failed: {e}")

    async def generate_summary(
        self,
        content: str,
        max_length: Optional[int] = None
    ) -> str:
        """
        Generate a summary using Claude.

        Args:
            content: Content to summarize
            max_length: Maximum summary length in words

        Returns:
            Summary text

        Raises:
            AIProviderError: If summarization fails
        """
        try:
            content = self._truncate_content(content)
            prompt = prompts.build_summary_prompt(content, max_length)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            summary = message.content[0].text.strip()
            logger.debug(f"Generated summary: {summary[:100]}...")

            return summary

        except anthropic.APIError as e:
            logger.error(f"Claude API error during summarization: {e}")
            raise AIProviderError(f"Summarization failed: {e}")
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            raise AIProviderError(f"Summarization failed: {e}")

    async def suggest_tags(
        self,
        content: str,
        max_tags: int = 5
    ) -> List[str]:
        """
        Suggest tags using Claude.

        Args:
            content: Content to tag
            max_tags: Maximum number of tags

        Returns:
            List of tags

        Raises:
            AIProviderError: If tag suggestion fails
        """
        try:
            content = self._truncate_content(content)
            prompt = prompts.build_tags_prompt(content, max_tags)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            tags_text = message.content[0].text.strip()
            tags = [tag.strip() for tag in tags_text.split(',')]

            logger.debug(f"Suggested tags: {tags}")
            return tags[:max_tags]

        except anthropic.APIError as e:
            logger.error(f"Claude API error during tag suggestion: {e}")
            raise AIProviderError(f"Tag suggestion failed: {e}")
        except Exception as e:
            logger.error(f"Tag suggestion error: {e}")
            raise AIProviderError(f"Tag suggestion failed: {e}")

    async def suggest_folder(
        self,
        content: str,
        available_folders: Optional[List[str]] = None
    ) -> str:
        """
        Suggest a folder using Claude.

        Args:
            content: Content to categorize
            available_folders: Existing folders

        Returns:
            Suggested folder path

        Raises:
            AIProviderError: If folder suggestion fails
        """
        try:
            content = self._truncate_content(content)
            prompt = prompts.build_folder_prompt(content, available_folders)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            folder = message.content[0].text.strip().strip('"\'')
            logger.debug(f"Suggested folder: {folder}")

            return folder

        except anthropic.APIError as e:
            logger.error(f"Claude API error during folder suggestion: {e}")
            raise AIProviderError(f"Folder suggestion failed: {e}")
        except Exception as e:
            logger.error(f"Folder suggestion error: {e}")
            raise AIProviderError(f"Folder suggestion failed: {e}")

    async def find_connections(
        self,
        content: str,
        existing_notes: Optional[List[Dict[str, str]]] = None
    ) -> List[str]:
        """
        Find connections using Claude.

        Args:
            content: Content to analyze
            existing_notes: Existing notes data

        Returns:
            List of connection descriptions

        Raises:
            AIProviderError: If connection finding fails
        """
        try:
            content = self._truncate_content(content)
            prompt = prompts.build_connections_prompt(content, existing_notes)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            # Try to parse as JSON array
            try:
                connections = json.loads(response_text)
                if isinstance(connections, list):
                    logger.debug(f"Found {len(connections)} connections")
                    return connections
            except json.JSONDecodeError:
                pass

            # Fallback: split by newlines
            connections = [
                line.strip('- ').strip()
                for line in response_text.split('\n')
                if line.strip()
            ]

            logger.debug(f"Found {len(connections)} connections (fallback parsing)")
            return connections

        except anthropic.APIError as e:
            logger.error(f"Claude API error during connection finding: {e}")
            raise AIProviderError(f"Connection finding failed: {e}")
        except Exception as e:
            logger.error(f"Connection finding error: {e}")
            raise AIProviderError(f"Connection finding failed: {e}")

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from Claude's response, with fallback.

        Args:
            response_text: Raw response text

        Returns:
            Parsed dictionary

        Raises:
            AIProviderError: If parsing fails
        """
        try:
            # Try direct JSON parsing
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.find('```', start)
                if end > start:
                    json_str = response_text[start:end].strip()
                    return json.loads(json_str)

            elif '```' in response_text:
                start = response_text.find('```') + 3
                end = response_text.find('```', start)
                if end > start:
                    json_str = response_text[start:end].strip()
                    return json.loads(json_str)

            # Fallback: return default structure
            logger.warning("Failed to parse JSON response, using fallback")

            # Log parsing failure to evaluation
            parse_error_data = {
                "operation": "parse_json_response",
                "provider": "claude",
                "error": "JSON parsing failed",
                "raw_response": response_text[:500] + "..." if len(response_text) > 500 else response_text,
                "fallback_used": True
            }
            eval_logger.warning(json.dumps(parse_error_data, ensure_ascii=False))

            return prompts.FALLBACK_ANALYSIS

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate API cost in USD.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        # Claude Sonnet 4 pricing (as of Dec 2024)
        # Adjust based on your model
        input_price_per_mtok = 3.00  # $3 per million tokens
        output_price_per_mtok = 15.00  # $15 per million tokens

        input_cost = (input_tokens / 1_000_000) * input_price_per_mtok
        output_cost = (output_tokens / 1_000_000) * output_price_per_mtok

        return round(input_cost + output_cost, 6)
