"""Main orchestrator for AI News Video Summarizer."""

import sys
from pathlib import Path
from src.config import Config, load_config, validate_config
from src.github import GitHubClient, GitHubFileExistsError
from src.markdown_generator import generate_markdown
from src.summarizer import GeminiSummarizer, SummarizerError
from src.transcript import (
    TranscriptUnavailableError,
    clean_transcript,
    chunk_transcript,
    extract_transcript,
)
from src.utils import (
    build_summary_filepath,
    load_processed_videos,
    parse_published_date,
    save_processed_videos,
    setup_logging,
)
from src.youtube import VideoMetadata, fetch_channel_videos


def run_pipeline(config: Config) -> dict[str, int]:
    """
    Execute the end-to-end AI news summarization pipeline.

    Returns:
        Summary dict containing counts: {"processed": int, "skipped": int, "failed": int}
    """
    secrets_to_mask = [config.gemini_api_key, config.github_token]
    logger = setup_logging(config.log_level, secrets=secrets_to_mask)

    print("Checking YouTube channel...")
    logger.info("Starting automation run. Channel: %s | DryRun: %s", config.youtube_channel_id, config.dry_run)

    # 1. Validate configuration
    is_valid, validation_errors = validate_config(config)
    if not is_valid:
        for err in validation_errors:
            logger.error("Configuration error: %s", err)
            print(f"Error: {err}")
        return {"processed": 0, "skipped": 0, "failed": len(validation_errors)}

    # 2. Load already processed videos
    processed_ids = load_processed_videos(config.processed_videos_path)
    logger.info("Loaded %d previously processed video IDs from state.", len(processed_ids))

    # 3. Fetch latest videos from YouTube RSS feed
    try:
        videos = fetch_channel_videos(config.youtube_channel_id)
    except Exception as e:
        logger.error("Failed to retrieve videos from YouTube: %s", e)
        print(f"Failed to retrieve videos from YouTube: {e}")
        return {"processed": 0, "skipped": 0, "failed": 1}

    # 4. Filter out already processed videos
    unprocessed_videos = [v for v in videos if v.video_id not in processed_ids]
    skipped_count = len(videos) - len(unprocessed_videos)

    if not unprocessed_videos:
        print("No new videos to process.")
        logger.info("All %d videos from feed are already processed.", len(videos))
        return {"processed": 0, "skipped": skipped_count, "failed": 0}

    # 5. Sort chronologically (oldest to newest) to maintain natural timeline
    unprocessed_videos.sort(key=lambda v: v.published_date)

    # 6. Apply MAX_VIDEOS_PER_RUN throttle
    target_videos = unprocessed_videos[: config.max_videos_per_run]
    additional_skipped = len(unprocessed_videos) - len(target_videos)
    skipped_count += additional_skipped

    total_to_process = len(target_videos)
    print(f"Found {total_to_process} new video(s).")
    logger.info(
        "Processing %d videos (%d deferred by max batch limit).",
        total_to_process,
        additional_skipped,
    )

    # Initialize external clients
    summarizer = GeminiSummarizer(
        api_key=config.gemini_api_key,
        model=config.gemini_model,
    )

    github_client: GitHubClient | None = None
    if not config.dry_run:
        github_client = GitHubClient(
            owner=config.github_owner,
            repo=config.github_repo,
            token=config.github_token,
            branch=config.github_branch,
        )

    processed_count = 0
    failed_count = 0

    for idx, video in enumerate(target_videos, start=1):
        print(f"\n[{idx}/{total_to_process}] Processing:")
        print(f"{video.title}")
        logger.info("--- Processing [%d/%d]: '%s' (ID: %s) ---", idx, total_to_process, video.title, video.video_id)

        try:
            # 7. Transcript Extraction
            raw_transcript = extract_transcript(video.video_id, proxy=config.youtube_proxy)
            print("✓ Transcript retrieved")

            # 8. Clean Transcript
            cleaned_transcript = clean_transcript(raw_transcript)
            if not cleaned_transcript:
                raise TranscriptUnavailableError(video.video_id, "Cleaned transcript is empty")
            print("✓ Transcript cleaned")

            # 9. Chunk if necessary
            chunks = chunk_transcript(cleaned_transcript, max_chunk_size=config.max_chunk_size)

            # 10. Gemini AI Summarization
            summary = summarizer.summarize(chunks, video_title=video.title)
            print("✓ Gemini summary generated")

            # 11. Markdown Generation
            markdown_content = generate_markdown(summary, video)
            print("✓ Markdown generated")

            # 12. Determine target file path
            rel_summary_path = build_summary_filepath(video.published_date, video.title, video.video_id)
            local_summary_file = config.base_dir / rel_summary_path
            posix_repo_path = rel_summary_path.as_posix()

            # Save locally for reference
            local_summary_file.parent.mkdir(parents=True, exist_ok=True)
            with open(local_summary_file, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # 13. GitHub Upload or Dry Run
            if config.dry_run:
                print("✓ Uploaded to GitHub (Dry Run - skipped)")
                print("✓ Marked as processed (Dry Run - skipped)")
                processed_count += 1
                logger.info("Dry run completed for %s. File written locally to %s", video.video_id, local_summary_file)
            else:
                _, _, date_prefix = parse_published_date(video.published_date)
                commit_msg = f"Add AI news summary: {date_prefix} - {video.title}"

                try:
                    github_client.commit_file(
                        repo_path=posix_repo_path,
                        content=markdown_content,
                        commit_message=commit_msg,
                        overwrite=False,
                    )
                    print("✓ Uploaded to GitHub")
                except GitHubFileExistsError:
                    logger.warning("Summary already existed in repo at %s. Proceeding to mark processed.", posix_repo_path)
                    print("✓ Uploaded to GitHub (File already exists)")

                # 14. Mark as processed ONLY after successful upload
                processed_ids.add(video.video_id)
                save_processed_videos(config.processed_videos_path, processed_ids)
                print("✓ Marked as processed")
                processed_count += 1
                logger.info("Successfully processed and recorded video %s.", video.video_id)

        except TranscriptUnavailableError as e:
            first_line = e.reason.strip().splitlines()[0] if e.reason else "Unavailable"
            logger.error("ERROR: Transcript unavailable for video %s: %s", video.video_id, first_line)
            print(f"✗ Skipped: Transcript unavailable ({first_line})")
            failed_count += 1
        except SummarizerError as e:
            logger.error("ERROR: Gemini summarization failed for video %s: %s", video.video_id, e)
            print("✗ Failed: Gemini summarization error")
            failed_count += 1
        except Exception as e:
            logger.error("ERROR: Unexpected failure processing video %s: %s", video.video_id, e)
            print(f"✗ Failed: {e}")
            failed_count += 1

    return {"processed": processed_count, "skipped": skipped_count, "failed": failed_count}


def main() -> None:
    """CLI entrypoint."""
    # Ensure Windows console handles UTF-8 checkmarks safely
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    config = load_config()
    stats = run_pipeline(config)

    print(f"\nProcessed: {stats['processed']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Failed: {stats['failed']}")
    print("Done.")

    if stats["failed"] > 0 and stats["processed"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
