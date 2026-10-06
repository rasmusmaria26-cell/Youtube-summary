"""Tests for transcript cleaning, chunking, and handling."""

import pytest
from unittest.mock import MagicMock, patch
from src.transcript import (
    TranscriptUnavailableError,
    clean_transcript,
    chunk_transcript,
    extract_transcript,
)


def test_clean_transcript_audio_tags_and_whitespace():
    raw = """
    [Music]
    Welcome everyone to today's AI news update.
    Welcome everyone to today's AI news update.
    Today Google released Gemini 2.5.   
    [Applause]
    This model achieves state of the art results.
    """
    cleaned = clean_transcript(raw)
    assert "[Music]" not in cleaned
    assert "[Applause]" not in cleaned
    # Ensure consecutive duplicate line was pruned
    assert cleaned.count("Welcome everyone to today's AI news update.") == 1
    assert "Gemini 2.5." in cleaned
    assert "This model achieves state of the art results." in cleaned


def test_clean_transcript_empty():
    assert clean_transcript("") == ""
    assert clean_transcript("   \n\n  ") == ""


def test_chunk_transcript_small_text():
    text = "Short transcript about AI models and synthetic data."
    chunks = chunk_transcript(text, max_chunk_size=1000)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_transcript_large_text_splits_cleanly():
    para1 = "Paragraph 1 describing new agentic coding frameworks. " * 5
    para2 = "Paragraph 2 discussing multi-modal reasoning capabilities. " * 5
    para3 = "Paragraph 3 outlining open-weights model weights release. " * 5

    full_text = f"{para1}\n\n{para2}\n\n{para3}"

    chunks = chunk_transcript(full_text, max_chunk_size=len(para1) + 20)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= len(para1) + 50


def test_extract_transcript_unavailable_raises():
    with patch("src.transcript.YouTubeTranscriptApi") as mock_ytt:
        instance = MagicMock()
        mock_ytt.return_value = instance
        # Simulate exception when listing transcripts
        from youtube_transcript_api import TranscriptsDisabled
        instance.list.side_effect = TranscriptsDisabled("test_id")

        with pytest.raises(TranscriptUnavailableError) as exc_info:
            extract_transcript("test_id")

        assert "test_id" in str(exc_info.value)
