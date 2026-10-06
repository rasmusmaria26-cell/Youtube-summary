"""Tests for Markdown generation."""

from src.markdown_generator import generate_markdown
from src.summarizer import NewsSummary, TopicSummary
from src.youtube import VideoMetadata


def test_generate_markdown_complete():
    summary = NewsSummary(
        title="OpenAI Releases New Frontier Model",
        summary="A major leap forward in AI reasoning and multi-step planning.",
        topics=[
            TopicSummary(
                title="Reasoning Engine 2.0",
                summary="The new model outperforms human experts on PhD level benchmarks.",
                why_it_matters="Reduces hallucinations in mission-critical applications.",
            )
        ],
        key_takeaways=[
            "Zero-shot reasoning accuracy reached 92%",
            "Context window expanded to 2M tokens",
        ],
        companies_mentioned=["OpenAI", "Microsoft"],
        technologies_mentioned=["GPT-5", "RLHF"],
        notes="Presenter predicts price reductions next quarter.",
    )

    metadata = VideoMetadata(
        video_id="xyz987",
        title="OpenAI Just Released Something Huge",
        published_date="2026-10-06T15:00:00Z",
        video_url="https://www.youtube.com/watch?v=xyz987",
        channel_name="AI Explained",
    )

    md = generate_markdown(summary, metadata)

    assert "# OpenAI Releases New Frontier Model" in md
    assert "- **Published:** 2026-10-06" in md
    assert "- **Channel:** AI Explained" in md
    assert "- **Video:** [Watch on YouTube](https://www.youtube.com/watch?v=xyz987)" in md
    assert "## Summary" in md
    assert "A major leap forward in AI reasoning" in md
    assert "### 1. Reasoning Engine 2.0" in md
    assert "**Why it matters:** Reduces hallucinations" in md
    assert "## Key Takeaways" in md
    assert "- Zero-shot reasoning accuracy reached 92%" in md
    assert "## Companies Mentioned" in md
    assert "- OpenAI" in md
    assert "- Microsoft" in md
    assert "## Technologies Mentioned" in md
    assert "- GPT-5" in md
    assert "## Notes" in md
    assert "Presenter predicts price reductions next quarter." in md


def test_generate_markdown_fallback_empty_fields():
    summary = NewsSummary(
        title="",
        summary="Brief summary.",
        topics=[],
        key_takeaways=[],
        companies_mentioned=[],
        technologies_mentioned=[],
        notes="",
    )

    metadata = VideoMetadata(
        video_id="empty1",
        title="Default Fallback Title",
        published_date="invalid-date",
        video_url="https://www.youtube.com/watch?v=empty1",
        channel_name="Tech Channel",
    )

    md = generate_markdown(summary, metadata)
    assert "# Default Fallback Title" in md
    assert "## Major Developments" in md
    assert "No distinct sub-topics categorized." in md
    assert "None explicitly highlighted." in md
