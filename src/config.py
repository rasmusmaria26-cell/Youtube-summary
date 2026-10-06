"""Configuration management for AI News Summarizer."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration parameters loaded from environment."""

    # Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # YouTube
    youtube_channel_id: str = ""
    youtube_proxy: str = ""
    youtube_cookie_path: str = ""

    # GitHub
    github_token: str = ""
    github_owner: str = ""
    github_repo: str = ""
    github_branch: str = "main"

    # Execution controls
    max_videos_per_run: int = 3
    max_chunk_size: int = 30000
    log_level: str = "INFO"
    dry_run: bool = False

    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    data_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data")
    processed_videos_path: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "processed_videos.json"
    )
    summaries_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "summaries"
    )


def _parse_bool(val: str | None, default: bool = False) -> bool:
    """Parse string representation of boolean."""
    if val is None:
        return default
    return val.strip().lower() in {"true", "1", "yes", "y", "t", "on"}


def _parse_int(val: str | None, default: int) -> int:
    """Parse string representation of integer with fallback."""
    if not val:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def load_config(env_file: Path | str | None = None) -> Config:
    """Load configuration from environment variables and optional .env file."""
    if env_file:
        load_dotenv(dotenv_path=env_file, override=True)
    else:
        load_dotenv(override=True)

    return Config(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
        youtube_channel_id=os.getenv("YOUTUBE_CHANNEL_ID", "").strip(),
        youtube_proxy=(os.getenv("YOUTUBE_PROXY", "") or os.getenv("HTTPS_PROXY", "")).strip(),
        youtube_cookie_path=os.getenv("YOUTUBE_COOKIE_PATH", "cookies.txt").strip(),
        github_token=os.getenv("GITHUB_TOKEN", "").strip(),
        github_owner=os.getenv("GITHUB_OWNER", "").strip(),
        github_repo=os.getenv("GITHUB_REPO", "").strip(),
        github_branch=os.getenv("GITHUB_BRANCH", "main").strip() or "main",
        max_videos_per_run=_parse_int(os.getenv("MAX_VIDEOS_PER_RUN"), 3),
        max_chunk_size=_parse_int(os.getenv("MAX_CHUNK_SIZE"), 30000),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        dry_run=_parse_bool(os.getenv("DRY_RUN"), False),
    )


def validate_config(config: Config) -> tuple[bool, list[str]]:
    """
    Validate that mandatory configuration parameters are populated.
    Returns (is_valid, list_of_error_messages).
    """
    errors: list[str] = []

    if not config.youtube_channel_id:
        errors.append("YOUTUBE_CHANNEL_ID is not configured.")

    if not config.gemini_api_key:
        errors.append("GEMINI_API_KEY is not configured.")

    if not config.dry_run:
        if not config.github_token:
            errors.append("GITHUB_TOKEN is required when DRY_RUN is false.")
        if not config.github_owner:
            errors.append("GITHUB_OWNER is required when DRY_RUN is false.")
        if not config.github_repo:
            errors.append("GITHUB_REPO is required when DRY_RUN is false.")

    return len(errors) == 0, errors
