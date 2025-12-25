"""Ollama AI provider implementation for local LLMs."""

import json
import logging
from typing import Dict, List, Any, Optional
import time

import ollama

from .base import AIProvider, AIProviderError
from . import prompts
from src.utils.logger import get_eval_logger


logger = logging.getLogger('obsidian_telegram_bot')
eval_logger = get_eval_logger()


class OllamaProvider(AIProvider):
    """AI provider using Ollama for local LLMs."""

    def __init__(self, base_url: str, model: str, config: Dict[str, Any]):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama server URL
            model: Model name to use (e.g., 'llama3.1:8b', 'mistral')
            config: AI configuration dictionary
        """
        super().__init__(config)
        self.client = ollama.Client(host=base_url)
        self.model = model
        self.temperature = config.get('ollama', {}).get('temperature', 0.7)

        logger.info(f"Initialized Ollama provider with model: {model} at {base_url}")

        # Test connection
        try:
            self.client.list()
            logger.info("Successfully connected to Ollama server")
        except Exception as e:
            logger.warning(f"Could not connect to Ollama server: {e}")

    async def analyze_content(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze content using Ollama and return structured suggestions.

        Args:
            content: The content to analyze
            context: Additional context

        Returns:
            Dictionary with analysis results

        Raises:
            AIProviderError: If analysis fails
        """
        start_time = time.time()

        try:
            # Truncate content if too long
            original_length = len(content)
            content = self._truncate_content(content)
            was_truncated = len(content) < original_length

            # Build the analysis prompt
            prompt = prompts.build_analysis_prompt(content, context)
            content_type = context.get('content_type', 'unknown') if context else 'unknown'

            logger.info(
                f"[Ollama] Analyzing {content_type} - "
                f"Model: {self.model}, "
                f"Length: {len(content)} chars{' (truncated)' if was_truncated else ''}"
            )

            # Call Ollama API
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={'temperature': self.temperature}
            )

            # Extract response text
            response_text = response['response']

            # Calculate metrics
            elapsed_time = time.time() - start_time
            total_duration_s = response.get('total_duration', 0) / 1e9  # nanoseconds to seconds
            eval_count = response.get('eval_count', 0)
            eval_duration = response.get('eval_duration', 1)
            tokens_per_second = eval_count / eval_duration * 1e9 if eval_duration else 0

            logger.info(
                f"[Ollama] Response - "
                f"Time: {elapsed_time:.2f}s, "
                f"Speed: {tokens_per_second:.1f} tok/s, "
                f"Tokens: {eval_count}"
            )

            # Parse JSON response
            analysis = self._parse_json_response(response_text)

            # Console log - summary
            logger.info(
                f"[Ollama] Analysis Complete - "
                f"Title: '{analysis.get('title', 'N/A')[:50]}', "
                f"Tags: {len(analysis.get('tags', []))} ({', '.join(analysis.get('tags', [])[:3])}), "
                f"Folder: '{analysis.get('suggested_folder', 'N/A')}'"
            )

            # Detailed evaluation log
            eval_data = {
                "operation": "analyze_content",
                "provider": "ollama",
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
                    "model_time_seconds": total_duration_s,
                    "tokens_evaluated": eval_count,
                    "tokens_per_second": round(tokens_per_second, 2),
                    "prompt_eval_count": response.get('prompt_eval_count', 0),
                    "load_duration_seconds": response.get('load_duration', 0) / 1e9
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

        except ollama.ResponseError as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[Ollama] API error after {elapsed_time:.2f}s: {e}")

            # Log error to evaluation
            error_data = {
                "operation": "analyze_content",
                "provider": "ollama",
                "model": self.model,
                "error": str(e),
                "error_type": "ResponseError",
                "elapsed_time_seconds": elapsed_time
            }
            eval_logger.error(json.dumps(error_data, ensure_ascii=False))

            raise AIProviderError(f"Ollama API error: {e}")
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[Ollama] Provider error after {elapsed_time:.2f}s: {e}")

            # Log error to evaluation
            error_data = {
                "operation": "analyze_content",
                "provider": "ollama",
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
        Generate a summary using Ollama.

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

            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={'temperature': self.temperature}
            )

            summary = response['response'].strip()
            logger.debug(f"Generated summary: {summary[:100]}...")

            return summary

        except ollama.ResponseError as e:
            logger.error(f"Ollama API error during summarization: {e}")
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
        Suggest tags using Ollama.

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

            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={'temperature': self.temperature}
            )

            tags_text = response['response'].strip()
            tags = [tag.strip() for tag in tags_text.split(',')]

            logger.debug(f"Suggested tags: {tags}")
            return tags[:max_tags]

        except ollama.ResponseError as e:
            logger.error(f"Ollama API error during tag suggestion: {e}")
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
        Suggest a folder using Ollama.

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

            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={'temperature': self.temperature}
            )

            folder = response['response'].strip().strip('"\'')
            logger.debug(f"Suggested folder: {folder}")

            return folder

        except ollama.ResponseError as e:
            logger.error(f"Ollama API error during folder suggestion: {e}")
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
        Find connections using Ollama.

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

            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={'temperature': self.temperature}
            )

            response_text = response['response'].strip()

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

        except ollama.ResponseError as e:
            logger.error(f"Ollama API error during connection finding: {e}")
            raise AIProviderError(f"Connection finding failed: {e}")
        except Exception as e:
            logger.error(f"Connection finding error: {e}")
            raise AIProviderError(f"Connection finding failed: {e}")

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from Ollama's response, with fallback.

        Args:
            response_text: Raw response text

        Returns:
            Parsed dictionary

        Raises:
            AIProviderError: If parsing fails completely
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

            # Final attempt: look for { } boundaries
            start = response_text.find('{')
            end = response_text.rfind('}')
            if start >= 0 and end > start:
                try:
                    json_str = response_text[start:end+1]
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            # Fallback: return default structure
            logger.warning("Failed to parse JSON response from Ollama, using fallback")

            # Log parsing failure to evaluation
            parse_error_data = {
                "operation": "parse_json_response",
                "provider": "ollama",
                "error": "JSON parsing failed",
                "raw_response": response_text[:500] + "..." if len(response_text) > 500 else response_text,
                "fallback_used": True
            }
            eval_logger.warning(json.dumps(parse_error_data, ensure_ascii=False))

            return prompts.FALLBACK_ANALYSIS
