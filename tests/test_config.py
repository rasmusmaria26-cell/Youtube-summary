"""Tests for configuration parsing and validation."""

from src.config import Config, load_config, validate_config, _parse_bool, _parse_int


def test_parse_helpers():
    assert _parse_bool("true") is True
    assert _parse_bool("True") is True
    assert _parse_bool("1") is True
    assert _parse_bool("yes") is True
    assert _parse_bool("false") is False
    assert _parse_bool("0") is False
    assert _parse_bool(None, default=True) is True

    assert _parse_int("10", 3) == 10
    assert _parse_int("invalid", 3) == 3
    assert _parse_int(None, 3) == 3


def test_validate_config_dry_run():
    # In dry run mode, GitHub credentials are optional
    config = Config(
        youtube_channel_id="UC123",
        gemini_api_key="gemini_key",
        dry_run=True,
    )
    is_valid, errors = validate_config(config)
    assert is_valid is True
    assert errors == []


def test_validate_config_production_requires_github():
    # When dry run is false, GitHub credentials are required
    config = Config(
        youtube_channel_id="UC123",
        gemini_api_key="gemini_key",
        dry_run=False,
    )
    is_valid, errors = validate_config(config)
    assert is_valid is False
    assert any("GITHUB_TOKEN" in e for e in errors)
    assert any("GITHUB_OWNER" in e for e in errors)
    assert any("GITHUB_REPO" in e for e in errors)


def test_validate_config_missing_mandatory():
    config = Config(
        youtube_channel_id="",
        gemini_api_key="",
        dry_run=True,
    )
    is_valid, errors = validate_config(config)
    assert is_valid is False
    assert any("YOUTUBE_CHANNEL_ID" in e for e in errors)
    assert any("GEMINI_API_KEY" in e for e in errors)
