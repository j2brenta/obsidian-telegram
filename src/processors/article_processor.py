"""Article fetching and processing from URLs."""

import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from newspaper import Article
    import requests
    from bs4 import BeautifulSoup
    from readability import Document
    ARTICLE_LIBS_AVAILABLE = True
except ImportError:
    ARTICLE_LIBS_AVAILABLE = False
    logging.warning("Article processing libraries not available")


logger = logging.getLogger('obsidian_telegram_bot')


class ArticleProcessorError(Exception):
    """Raised when article processing fails."""
    pass


class ArticleProcessor:
    """Process web articles from URLs."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize article processor.

        Args:
            config: Application configuration
        """
        self.config = config
        self.article_config = config.get('media', {}).get('article_summary', {})
        self.enabled = self.article_config.get('enabled', True)
        self.fetch_full_text = self.article_config.get('fetch_full_text', True)
        self.max_length = self.article_config.get('max_length', 500)

        if self.enabled and not ARTICLE_LIBS_AVAILABLE:
            logger.warning("Article processing enabled but libraries not available")
            self.enabled = False

    async def process_url(self, url: str) -> Dict[str, Any]:
        """
        Fetch and process an article from URL.

        Args:
            url: Article URL

        Returns:
            Dictionary with:
                - title: str
                - text: str (full article text)
                - summary: str
                - author: Optional[str]
                - publish_date: Optional[datetime]
                - url: str
                - success: bool
                - error: Optional[str]
        """
        if not self.enabled:
            logger.debug("Article processing disabled")
            return {
                'url': url,
                'success': False,
                'error': 'Article processing disabled'
            }

        try:
            logger.info(f"Fetching article: {url}")

            # Try newspaper3k first (more robust)
            result = await self._fetch_with_newspaper(url)

            if result['success']:
                return result

            # Fallback to readability
            logger.debug("Newspaper failed, trying readability...")
            result = await self._fetch_with_readability(url)

            return result

        except Exception as e:
            logger.error(f"Article processing failed for {url}: {e}")
            return {
                'url': url,
                'success': False,
                'error': str(e)
            }

    async def _fetch_with_newspaper(self, url: str) -> Dict[str, Any]:
        """
        Fetch article using newspaper3k library.

        Args:
            url: Article URL

        Returns:
            Article data dictionary
        """
        try:
            article = Article(url)
            article.download()
            article.parse()

            # Optionally use NLP for summary
            try:
                article.nlp()
                summary = article.summary
            except:
                summary = None

            # Clean up text
            text = article.text.strip()

            # Create summary if needed
            if not summary and text:
                summary = self._create_simple_summary(text)

            result = {
                'title': article.title or 'Untitled Article',
                'text': text,
                'summary': summary or '',
                'author': ', '.join(article.authors) if article.authors else None,
                'publish_date': article.publish_date,
                'top_image': article.top_image,
                'url': url,
                'success': True
            }

            logger.info(f"Successfully fetched article: {result['title']}")
            return result

        except Exception as e:
            logger.debug(f"Newspaper fetch failed: {e}")
            return {
                'url': url,
                'success': False,
                'error': f"Newspaper fetch failed: {e}"
            }

    async def _fetch_with_readability(self, url: str) -> Dict[str, Any]:
        """
        Fetch article using readability-lxml library.

        Args:
            url: Article URL

        Returns:
            Article data dictionary
        """
        try:
            # Fetch HTML
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ObsidianTelegramBot/1.0)'
            })
            response.raise_for_status()

            # Parse with readability
            doc = Document(response.content)
            soup = BeautifulSoup(doc.summary(), 'html.parser')

            # Extract text
            text = soup.get_text(separator='\n', strip=True)

            # Extract title
            title = doc.title() or self._extract_title_from_html(response.content)

            # Create summary
            summary = self._create_simple_summary(text)

            result = {
                'title': title or 'Untitled Article',
                'text': text,
                'summary': summary,
                'author': None,
                'publish_date': None,
                'url': url,
                'success': True
            }

            logger.info(f"Successfully fetched article with readability: {result['title']}")
            return result

        except Exception as e:
            logger.debug(f"Readability fetch failed: {e}")
            return {
                'url': url,
                'success': False,
                'error': f"Readability fetch failed: {e}"
            }

    def _create_simple_summary(self, text: str) -> str:
        """
        Create a simple summary by taking first few sentences.

        Args:
            text: Full article text

        Returns:
            Summary text
        """
        # Split into sentences (simple approach)
        sentences = re.split(r'[.!?]+', text)

        # Clean and filter
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        # Take first 3 sentences or until max_length
        summary_parts = []
        total_length = 0

        for sentence in sentences[:5]:
            if total_length + len(sentence) > self.max_length:
                break
            summary_parts.append(sentence)
            total_length += len(sentence)

        summary = '. '.join(summary_parts)
        if summary and not summary.endswith('.'):
            summary += '.'

        return summary

    def _extract_title_from_html(self, html_content: bytes) -> Optional[str]:
        """
        Extract title from HTML content.

        Args:
            html_content: Raw HTML bytes

        Returns:
            Extracted title or None
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Try various title sources
            if soup.title:
                return soup.title.string.strip()

            # Try Open Graph title
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                return og_title['content'].strip()

            # Try h1
            h1 = soup.find('h1')
            if h1:
                return h1.get_text(strip=True)

            return None

        except Exception as e:
            logger.debug(f"Could not extract title from HTML: {e}")
            return None

    @staticmethod
    def extract_urls(text: str) -> list[str]:
        """
        Extract URLs from text.

        Args:
            text: Text to search

        Returns:
            List of found URLs
        """
        url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
        urls = re.findall(url_pattern, text)
        return urls

    async def format_article_for_note(
        self,
        article_data: Dict[str, Any]
    ) -> str:
        """
        Format article data for inclusion in a note.

        Args:
            article_data: Article data from process_url

        Returns:
            Formatted markdown text
        """
        if not article_data.get('success'):
            return f"[Could not fetch article: {article_data.get('error', 'Unknown error')}]"

        lines = []

        # Article header
        lines.append(f"## {article_data['title']}\n")

        # Metadata
        if article_data.get('author'):
            lines.append(f"**Author**: {article_data['author']}")

        if article_data.get('publish_date'):
            date_str = article_data['publish_date'].strftime('%Y-%m-%d')
            lines.append(f"**Published**: {date_str}")

        lines.append(f"**URL**: {article_data['url']}\n")

        # Summary (if available)
        if article_data.get('summary'):
            lines.append(f"### Summary\n")
            lines.append(f"{article_data['summary']}\n")

        # Full text (if configured and available)
        if self.fetch_full_text and article_data.get('text'):
            lines.append(f"### Article Text\n")
            # Limit length to avoid huge notes
            text = article_data['text']
            if len(text) > 5000:
                text = text[:5000] + "\n\n[Article truncated...]"
            lines.append(text)

        return '\n'.join(lines)
