"""Tests for utilities, filename sanitization, date parsing, and state persistence."""

import json
import logging
from pathlib import Path
from src.utils import (
    SecretMaskingFilter,
    build_summary_filepath,
    load_processed_videos,
    parse_published_date,
    sanitize_filename,
    save_processed_videos,
)


def test_sanitize_filename():
    assert sanitize_filename("OpenAI's New Model: GPT-5 Released!?") == "openais-new-model-gpt-5-released"
    assert sanitize_filename("Simple Title") == "simple-title"
    assert sanitize_filename("   Spaces   and --- Hyphens   ") == "spaces-and-hyphens"
    assert sanitize_filename("") == "untitled-video"
    long_title = "a" * 150
    assert len(sanitize_filename(long_title, max_length=50)) <= 50


def test_parse_published_date():
    y, m, d = parse_published_date("2026-10-06T12:00:00Z")
    assert y == "2026"
    assert m == "10"
    assert d == "2026-10-06"

    # Fallback on invalid format produces current year
    y2, m2, d2 = parse_published_date("not-a-date")
    assert len(y2) == 4
    assert len(m2) == 2


def test_build_summary_filepath():
    path = build_summary_filepath(
        published_date="2026-10-06T12:00:00Z",
        title="AI News Roundup",
        video_id="vid_123",
    )
    posix = path.as_posix()
    assert posix.startswith("summaries/2026/10/2026-10-06-ai-news-roundup-vid_123.md")


def test_processed_videos_persistence(tmp_path: Path):
    file_path = tmp_path / "processed_videos.json"

    # Initially empty
    assert load_processed_videos(file_path) == set()

    # Save IDs
    ids_to_save = {"id1", "id2", "id3"}
    save_processed_videos(file_path, ids_to_save)

    loaded = load_processed_videos(file_path)
    assert loaded == ids_to_save

    # Verify JSON structure
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "processed_videos" in data
    assert data["processed_videos"] == ["id1", "id2", "id3"]


def test_secret_masking_filter():
    secret = "ghp_SuperSecretGitHubToken12345"
    log_filter = SecretMaskingFilter([secret])

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"Connecting with token {secret} to repo",
        args=(),
        exc_info=None,
    )

    log_filter.filter(record)
    assert secret not in record.msg
    assert "[REDACTED]" in record.msg
