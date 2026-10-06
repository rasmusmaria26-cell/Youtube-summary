"""Tests for main pipeline orchestration, idempotency, and error handling."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from src.config import Config
from src.main import run_pipeline
from src.summarizer import NewsSummary, TopicSummary
from src.transcript import TranscriptUnavailableError
from src.youtube import VideoMetadata


def test_pipeline_dry_run_success(tmp_path: Path):
    config = Config(
        youtube_channel_id="UC_TEST",
        gemini_api_key="fake_key",
        dry_run=True,
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        processed_videos_path=tmp_path / "data" / "processed_videos.json",
        summaries_dir=tmp_path / "summaries",
    )

    sample_videos = [
        VideoMetadata(
            video_id="vid_1",
            title="First AI Video",
            published_date="2026-10-06T10:00:00Z",
            video_url="https://youtube.com/watch?v=vid_1",
            channel_name="AI Channel",
        )
    ]

    mock_summary = NewsSummary(
        title="First AI Video",
        summary="A summary of the video.",
        topics=[
            TopicSummary(
                title="Topic 1",
                summary="Details of topic 1",
                why_it_matters="Significance",
            )
        ],
        key_takeaways=["Takeaway 1"],
        companies_mentioned=["Company A"],
        technologies_mentioned=["Tech A"],
        notes="",
    )

    with patch("src.main.fetch_channel_videos", return_value=sample_videos), \
         patch("src.main.extract_transcript", return_value="Sentence 1. Sentence 2."), \
         patch("src.main.GeminiSummarizer.summarize", return_value=mock_summary):

        stats = run_pipeline(config)

        assert stats["processed"] == 1
        assert stats["skipped"] == 0
        assert stats["failed"] == 0

        # In dry run mode, processed_videos.json should NOT be modified
        assert not config.processed_videos_path.exists()


def test_pipeline_skips_already_processed_videos(tmp_path: Path):
    state_file = tmp_path / "data" / "processed_videos.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text('{"processed_videos": ["vid_1"]}', encoding="utf-8")

    config = Config(
        youtube_channel_id="UC_TEST",
        gemini_api_key="fake_key",
        dry_run=True,
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        processed_videos_path=state_file,
        summaries_dir=tmp_path / "summaries",
    )

    sample_videos = [
        VideoMetadata(
            video_id="vid_1",
            title="Already Processed",
            published_date="2026-10-06T10:00:00Z",
            video_url="https://youtube.com/watch?v=vid_1",
            channel_name="AI Channel",
        )
    ]

    with patch("src.main.fetch_channel_videos", return_value=sample_videos):
        stats = run_pipeline(config)
        assert stats["processed"] == 0
        assert stats["skipped"] == 1
        assert stats["failed"] == 0


def test_pipeline_handles_transcript_unavailable_gracefully(tmp_path: Path):
    config = Config(
        youtube_channel_id="UC_TEST",
        gemini_api_key="fake_key",
        dry_run=True,
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        processed_videos_path=tmp_path / "data" / "processed_videos.json",
        summaries_dir=tmp_path / "summaries",
    )

    sample_videos = [
        VideoMetadata(
            video_id="vid_no_transcript",
            title="Video without captions",
            published_date="2026-10-06T10:00:00Z",
            video_url="https://youtube.com/watch?v=vid_no_transcript",
            channel_name="AI Channel",
        )
    ]

    with patch("src.main.fetch_channel_videos", return_value=sample_videos), \
         patch("src.main.extract_transcript", side_effect=TranscriptUnavailableError("vid_no_transcript", "Disabled")):

        stats = run_pipeline(config)
        assert stats["processed"] == 0
        assert stats["skipped"] == 0
        assert stats["failed"] == 1
