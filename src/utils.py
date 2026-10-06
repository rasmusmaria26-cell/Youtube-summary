"""Utility functions for logging, filename sanitization, and state persistence."""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class SecretMaskingFilter(logging.Filter):
    """Logging filter to mask sensitive API keys or tokens."""

    def __init__(self, secrets: Iterable[str] | None = None) -> None:
        super().__init__()
        self.secrets = [s.strip() for s in (secrets or []) if s and len(s.strip()) > 5]

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.secrets:
            return True

        if isinstance(record.msg, str):
            for secret in self.secrets:
                if secret in record.msg:
                    record.msg = record.msg.replace(secret, "[REDACTED]")

        if record.args:
            args_list = list(record.args) if isinstance(record.args, tuple) else [record.args]
            sanitized_args = []
            for arg in args_list:
                if isinstance(arg, str):
                    for secret in self.secrets:
                        if secret in arg:
                            arg = arg.replace(secret, "[REDACTED]")
                sanitized_args.append(arg)
            record.args = tuple(sanitized_args) if isinstance(record.args, tuple) else sanitized_args[0]
        return True


def setup_logging(level: str = "INFO", secrets: Iterable[str] | None = None) -> logging.Logger:
    """Configure application logging with secret masking to stderr."""
    logger = logging.getLogger("ai_news")
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers if reconfigured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        if secrets:
            handler.addFilter(SecretMaskingFilter(secrets))
        logger.addHandler(handler)
    else:
        for handler in logger.handlers:
            handler.setLevel(numeric_level)
            if secrets:
                handler.addFilter(SecretMaskingFilter(secrets))

    return logger


def sanitize_filename(title: str, max_length: int = 60) -> str:
    """
    Sanitize video title into a safe lowercase hyphenated filename slug.
    Removes unsafe filesystem characters and collapses multiple hyphens.
    """
    if not title:
        return "untitled-video"

    # Lowercase
    cleaned = title.lower()

    # Replace spaces, underscores, and common punctuation with hyphens
    cleaned = re.sub(r"[\s_\\/:\*\?\"<>\|]+", "-", cleaned)

    # Remove all non-alphanumeric and non-hyphen characters
    cleaned = re.sub(r"[^a-z0-9\-]", "", cleaned)

    # Collapse multiple hyphens into a single hyphen
    cleaned = re.sub(r"-+", "-", cleaned)

    # Strip leading and trailing hyphens
    cleaned = cleaned.strip("-")

    # Limit length without splitting words awkwardly if possible
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip("-")

    return cleaned or "untitled-video"


def parse_published_date(date_str: str) -> tuple[str, str, str]:
    """
    Parse published date string (ISO format or similar).
    Returns (year, month, yyyy-mm-dd). Defaults to today on parse error.
    """
    try:
        # Standard ISO 8601 like 2026-10-06T12:00:00+00:00 or 2026-10-06T12:00:00Z
        clean_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        year = f"{dt.year:04d}"
        month = f"{dt.month:02d}"
        date_prefix = f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"
        return year, month, date_prefix
    except Exception:
        now = datetime.now(timezone.utc)
        return f"{now.year:04d}", f"{now.month:02d}", f"{now.year:04d}-{now.month:02d}-{now.day:02d}"


def build_summary_filepath(
    published_date: str,
    title: str,
    video_id: str,
    base_dir: Path | None = None,
) -> Path:
    """
    Build relative or absolute summary path conforming to:
    summaries/YYYY/MM/YYYY-MM-DD-video-title.md

    Includes video_id suffix to guarantee uniqueness against collisions.
    """
    year, month, date_prefix = parse_published_date(published_date)
    slug = sanitize_filename(title)

    filename = f"{date_prefix}-{slug}-{video_id}.md"

    rel_path = Path("summaries") / year / month / filename
    if base_dir:
        return base_dir / rel_path
    return rel_path


def load_processed_videos(filepath: Path) -> set[str]:
    """Load the set of already processed YouTube video IDs."""
    if not filepath.exists():
        return set()

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            video_list = data.get("processed_videos", [])
            return set(video_list)
    except (json.JSONDecodeError, OSError) as e:
        logger = logging.getLogger("ai_news")
        logger.warning("Could not read processed videos file %s: %s. Starting with empty set.", filepath, e)
        return set()


def save_processed_videos(filepath: Path, processed_ids: Iterable[str]) -> None:
    """Save processed video IDs atomically to prevent corrupted files."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_suffix(".tmp")

    payload = {
        "processed_videos": sorted(list(set(processed_ids)))
    }

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    # Atomic replace
    tmp_path.replace(filepath)
