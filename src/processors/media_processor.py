"""Media processing - images, voice, video."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import tempfile

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.warning("pytesseract or PIL not available - OCR will be disabled")


logger = logging.getLogger('obsidian_telegram_bot')


class MediaProcessorError(Exception):
    """Raised when media processing fails."""
    pass


class MediaProcessor:
    """Process media files from Telegram (images, voice, video)."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize media processor.

        Args:
            config: Application configuration
        """
        self.config = config
        self.media_config = config.get('media', {})
        self.ocr_enabled = self.media_config.get('ocr', {}).get('enabled', True)
        self.ocr_language = self.media_config.get('ocr', {}).get('language', 'eng')

        if self.ocr_enabled and not TESSERACT_AVAILABLE:
            logger.warning("OCR enabled in config but pytesseract not available")
            self.ocr_enabled = False

    async def process_image(
        self,
        file_path: str,
        file_data: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Process an image file - extract OCR text.

        Args:
            file_path: Path to downloaded image file
            file_data: Optional raw file data

        Returns:
            Dictionary with:
                - ocr_text: str
                - has_text: bool
                - confidence: float (0-100)
                - error: Optional[str]
        """
        if not self.ocr_enabled:
            logger.debug("OCR disabled, skipping image processing")
            return {
                'ocr_text': '',
                'has_text': False,
                'confidence': 0.0
            }

        try:
            logger.debug(f"Processing image for OCR: {file_path}")

            # Open image
            img = Image.open(file_path)

            # Perform OCR
            ocr_text = pytesseract.image_to_string(
                img,
                lang=self.ocr_language
            )

            # Get confidence data
            try:
                data = pytesseract.image_to_data(
                    img,
                    output_type=pytesseract.Output.DICT,
                    lang=self.ocr_language
                )
                confidences = [c for c in data['conf'] if c != -1]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            except Exception as e:
                logger.debug(f"Could not get OCR confidence: {e}")
                avg_confidence = 0

            # Clean up text
            ocr_text = ocr_text.strip()
            has_text = bool(ocr_text)

            logger.info(f"OCR completed - Found text: {has_text}, Confidence: {avg_confidence:.1f}%")

            return {
                'ocr_text': ocr_text,
                'has_text': has_text,
                'confidence': avg_confidence
            }

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return {
                'ocr_text': '',
                'has_text': False,
                'confidence': 0.0,
                'error': str(e)
            }

    async def process_voice(
        self,
        file_path: str,
        duration: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process a voice message - transcribe to text.

        Note: Basic implementation returns metadata.
        For actual transcription, integrate Whisper API or similar.

        Args:
            file_path: Path to voice file
            duration: Duration in seconds

        Returns:
            Dictionary with:
                - transcription: str
                - duration: int
                - error: Optional[str]
        """
        # Placeholder for voice transcription
        # To implement full transcription, integrate:
        # - OpenAI Whisper API
        # - Google Speech-to-Text
        # - Local Whisper model

        logger.info(f"Voice message received (duration: {duration}s)")
        logger.warning("Voice transcription not yet implemented - returning placeholder")

        return {
            'transcription': f"[Voice message - {duration}s]",
            'duration': duration or 0,
            'error': 'Transcription not implemented'
        }

    async def process_video(
        self,
        file_path: str,
        duration: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process a video file - extract metadata.

        Args:
            file_path: Path to video file
            duration: Duration in seconds

        Returns:
            Dictionary with video metadata
        """
        logger.info(f"Video received (duration: {duration}s)")

        return {
            'duration': duration or 0,
            'file_path': file_path
        }

    async def download_telegram_file(
        self,
        file,
        bot
    ) -> tuple[Path, bytes]:
        """
        Download a file from Telegram.

        Args:
            file: Telegram File object
            bot: Telegram bot instance

        Returns:
            Tuple of (file_path, file_data)
        """
        try:
            # Download file
            file_data = await file.download_as_bytearray()

            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_ext = Path(file.file_path).suffix if hasattr(file, 'file_path') else ''
            filename = f"telegram_{timestamp}{file_ext}"

            # Save to temp file
            temp_dir = Path(tempfile.gettempdir())
            file_path = temp_dir / filename

            file_path.write_bytes(bytes(file_data))

            logger.debug(f"Downloaded Telegram file: {filename}")
            return file_path, bytes(file_data)

        except Exception as e:
            logger.error(f"Failed to download Telegram file: {e}")
            raise MediaProcessorError(f"File download failed: {e}")

    def generate_media_filename(
        self,
        original_filename: Optional[str] = None,
        media_type: str = 'file'
    ) -> str:
        """
        Generate a unique filename for media.

        Args:
            original_filename: Original filename from Telegram
            media_type: Type of media (photo, video, voice, etc.)

        Returns:
            Generated filename
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if original_filename:
            # Keep original extension
            ext = Path(original_filename).suffix
            base_name = Path(original_filename).stem[:30]  # Limit length
            return f"telegram_{media_type}_{timestamp}_{base_name}{ext}"
        else:
            # Default extensions by type
            extensions = {
                'photo': '.jpg',
                'video': '.mp4',
                'voice': '.ogg',
                'audio': '.mp3',
                'document': ''
            }
            ext = extensions.get(media_type, '')
            return f"telegram_{media_type}_{timestamp}{ext}"
