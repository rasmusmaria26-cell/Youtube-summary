"""Transcript extraction, cleaning, and chunking module."""

import logging
import re
from typing import Any, Iterable

logger = logging.getLogger("ai_news")


try:
    from youtube_transcript_api import (
        YouTubeTranscriptApi,
        YouTubeTranscriptApiException,
    )
except ImportError:
    YouTubeTranscriptApi = None  # type: ignore
    YouTubeTranscriptApiException = Exception  # type: ignore


class TranscriptUnavailableError(Exception):
    """Raised when a transcript cannot be retrieved for a video."""

    def __init__(self, video_id: str, reason: str) -> None:
        self.video_id = video_id
        self.reason = reason
        super().__init__(f"Transcript unavailable for video {video_id}: {reason}")


def _extract_text_from_snippets(snippets: Any) -> list[str]:
    """Extract string texts from fetched transcript snippet objects or dictionaries."""
    lines: list[str] = []
    for item in snippets:
        if isinstance(item, dict):
            text = item.get("text", "")
        elif hasattr(item, "text"):
            text = getattr(item, "text", "")
        else:
            text = str(item)

        if text:
            lines.append(text.strip())
    return lines


def extract_transcript(
    video_id: str,
    languages: Iterable[str] = ("en", "en-US", "en-GB"),
    proxy: str | None = None,
    cookie_path: str | None = None,
) -> str:
    """
    Retrieve transcript for a given video ID using youtube-transcript-api.
    Prefers manually created transcripts, falling back to auto-generated.

    Args:
        video_id: YouTube video ID string
        languages: Preferred languages in descending order
        proxy: Optional HTTP/HTTPS proxy URL
        cookie_path: Optional path to Mozilla/Netscape cookies.txt

    Returns:
        Raw extracted transcript text.

    Raises:
        TranscriptUnavailableError: If transcript cannot be extracted.
    """
    if YouTubeTranscriptApi is None:
        logger.error("youtube-transcript-api is not installed.")
        raise TranscriptUnavailableError(video_id, "Missing youtube-transcript-api package")

    lang_list = list(languages)
    logger.info("Attempting to retrieve transcript for video: %s (languages=%s)", video_id, lang_list)

    try:
        from pathlib import Path
        import requests
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}

        if cookie_path and Path(cookie_path).is_file():
            import http.cookiejar
            try:
                jar = http.cookiejar.MozillaCookieJar(cookie_path)
                jar.load(ignore_discard=True, ignore_expires=True)
                session.cookies = jar
                logger.info("Loaded YouTube cookies from: %s", cookie_path)
            except Exception as ce:
                logger.warning("Failed to load cookie file %s: %s", cookie_path, ce)

        # Support both modern (1.2+) instance-based API and legacy static method
        try:
            ytt = YouTubeTranscriptApi(http_client=session)
            transcript_list = ytt.list(video_id)
        except (AttributeError, TypeError):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        target_transcript = None

        # 1. Prefer manual transcript
        try:
            target_transcript = transcript_list.find_manually_created_transcript(lang_list)
            logger.debug("Found manually created transcript for %s", video_id)
        except Exception:
            pass

        # 2. Fall back to auto-generated transcript
        if target_transcript is None:
            try:
                target_transcript = transcript_list.find_generated_transcript(lang_list)
                logger.debug("Found generated transcript for %s", video_id)
            except Exception:
                pass

        # 3. Fall back to generic find_transcript
        if target_transcript is None:
            try:
                target_transcript = transcript_list.find_transcript(lang_list)
                logger.debug("Found general transcript for %s", video_id)
            except Exception:
                pass

        if target_transcript is None:
            raise TranscriptUnavailableError(
                video_id, f"No English transcript found in {lang_list}"
            )

        snippets = target_transcript.fetch()
        text_lines = _extract_text_from_snippets(snippets)
        if not text_lines:
            raise TranscriptUnavailableError(video_id, "Transcript returned empty content")

        raw_transcript = "\n".join(text_lines)
        logger.info(
            "Successfully retrieved transcript for video %s (%d raw lines)",
            video_id,
            len(text_lines),
        )
        return raw_transcript

    except TranscriptUnavailableError:
        raise
    except YouTubeTranscriptApiException as e:
        logger.error("ERROR: Transcript unavailable for video %s: %s", video_id, e)
        raise TranscriptUnavailableError(video_id, str(e)) from e
    except Exception as e:
        logger.error("ERROR: Unexpected transcript error for video %s: %s", video_id, e)
        raise TranscriptUnavailableError(video_id, str(e)) from e


def clean_transcript(raw_text: str) -> str:
    """
    Clean raw transcript:
    - Removes timestamp markers and audio tags like [Music], [Applause]
    - Removes duplicate consecutive lines/fragments
    - Normalizes excessive whitespace
    - Formats into readable paragraph blocks
    """
    if not raw_text or not raw_text.strip():
        return ""

    lines = raw_text.splitlines()
    cleaned_lines: list[str] = []
    prev_line = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Filter audio tags like [Music], [Applause], (music), etc.
        filtered = re.sub(r"\[(Music|Applause|Laughter|Cheering|Silence|Loud music)\]", "", stripped, flags=re.I)
        filtered = re.sub(r"\((Music|Applause|Laughter|Cheering|Silence|Loud music)\)", "", filtered, flags=re.I)
        filtered = filtered.strip()
        if not filtered:
            continue

        # Normalize whitespace inside line
        normalized = re.sub(r"\s+", " ", filtered)

        # Skip immediately identical consecutive lines (common in auto captions)
        if normalized.lower() == prev_line.lower():
            continue

        cleaned_lines.append(normalized)
        prev_line = normalized

    if not cleaned_lines:
        return ""

    # Group into readable paragraphs (approx 4-6 sentences or ~600 chars per paragraph)
    paragraphs: list[str] = []
    current_para: list[str] = []
    current_length = 0

    for line in cleaned_lines:
        current_para.append(line)
        current_length += len(line)

        # Break paragraph if ends with period/question/exclamation and long enough
        if line.endswith((".", "?", "!")) and current_length > 400:
            paragraphs.append(" ".join(current_para))
            current_para = []
            current_length = 0
        elif current_length > 800:
            paragraphs.append(" ".join(current_para))
            current_para = []
            current_length = 0

    if current_para:
        paragraphs.append(" ".join(current_para))

    return "\n\n".join(paragraphs)


def chunk_transcript(cleaned_text: str, max_chunk_size: int = 30000) -> list[str]:
    """
    Split a large transcript into logical chunks not exceeding max_chunk_size.
    Splits along paragraph or sentence boundaries to preserve context.
    """
    if not cleaned_text:
        return []

    if len(cleaned_text) <= max_chunk_size:
        return [cleaned_text]

    paragraphs = cleaned_text.split("\n\n")
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_size = 0

    for para in paragraphs:
        para_len = len(para) + 2  # account for \n\n

        # If a single paragraph is larger than max_chunk_size, split by sentences
        if para_len > max_chunk_size:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0

            sentences = re.split(r"(?<=[.!?])\s+", para)
            sent_chunk: list[str] = []
            sent_size = 0

            for sent in sentences:
                if sent_size + len(sent) + 1 > max_chunk_size:
                    if sent_chunk:
                        chunks.append(" ".join(sent_chunk))
                        sent_chunk = []
                        sent_size = 0
                sent_chunk.append(sent)
                sent_size += len(sent) + 1

            if sent_chunk:
                chunks.append(" ".join(sent_chunk))
            continue

        if current_size + para_len > max_chunk_size:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_size = para_len
        else:
            current_chunk.append(para)
            current_size += para_len

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks
