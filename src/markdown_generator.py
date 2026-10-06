"""Markdown generator to convert structured Gemini summaries into clean documents."""

from src.summarizer import NewsSummary
from src.youtube import VideoMetadata
from src.utils import parse_published_date


def generate_markdown(summary: NewsSummary, metadata: VideoMetadata) -> str:
    """
    Generate clean, standardized GitHub-ready Markdown from a structured NewsSummary.

    Args:
        summary: Validated NewsSummary object from Gemini
        metadata: VideoMetadata from YouTube RSS feed

    Returns:
        Formatted Markdown string.
    """
    _, _, formatted_date = parse_published_date(metadata.published_date)

    # Header section
    lines: list[str] = [
        f"# {summary.title or metadata.title}",
        "",
        f"- **Published:** {formatted_date}",
        f"- **Channel:** {metadata.channel_name}",
        f"- **Video:** [Watch on YouTube]({metadata.video_url})",
        "",
        "## Summary",
        summary.summary.strip(),
        "",
        "## Major Developments",
    ]

    # Topics / Developments section
    if summary.topics:
        for idx, topic in enumerate(summary.topics, start=1):
            lines.append(f"### {idx}. {topic.title.strip()}")
            lines.append(topic.summary.strip())
            lines.append("")
            lines.append(f"**Why it matters:** {topic.why_it_matters.strip()}")
            lines.append("")
    else:
        lines.append("No distinct sub-topics categorized.")
        lines.append("")

    # Key Takeaways
    lines.append("## Key Takeaways")
    if summary.key_takeaways:
        for item in summary.key_takeaways:
            lines.append(f"- {item.strip()}")
    else:
        lines.append("- Refer to the main summary above for core highlights.")
    lines.append("")

    # Companies Mentioned
    lines.append("## Companies Mentioned")
    if summary.companies_mentioned:
        for company in summary.companies_mentioned:
            lines.append(f"- {company.strip()}")
    else:
        lines.append("- None explicitly highlighted.")
    lines.append("")

    # Technologies Mentioned
    lines.append("## Technologies Mentioned")
    if summary.technologies_mentioned:
        for tech in summary.technologies_mentioned:
            lines.append(f"- {tech.strip()}")
    else:
        lines.append("- None explicitly highlighted.")
    lines.append("")

    # Notes & Speculation
    lines.append("## Notes")
    notes_content = summary.notes.strip() if summary.notes else "No additional opinions, speculation, or caveats noted."
    lines.append(notes_content)
    lines.append("")

    return "\n".join(lines)
