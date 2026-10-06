"""YouTube RSS Feed monitoring and video metadata extraction."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
import requests

logger = logging.getLogger("ai_news")

ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"


@dataclass
class VideoMetadata:
    """Represents core metadata for a published YouTube video."""

    video_id: str
    title: str
    published_date: str
    video_url: str
    channel_name: str


def parse_feed_xml(xml_content: str | bytes) -> list[VideoMetadata]:
    """
    Parse YouTube Atom RSS XML feed content and extract video metadata.
    """
    if isinstance(xml_content, str):
        xml_bytes = xml_content.encode("utf-8")
    else:
        xml_bytes = xml_content

    if not xml_bytes.strip():
        logger.warning("Empty XML content received from YouTube feed.")
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.error("Failed to parse YouTube RSS XML: %s", e)
        raise ValueError(f"Malformed XML in YouTube RSS feed: {e}") from e

    # Extract default channel name from feed title or author
    default_channel_name = root.findtext(f"{ATOM_NS}title") or "YouTube Channel"
    author_elem = root.find(f"{ATOM_NS}author")
    if author_elem is not None:
        author_name = author_elem.findtext(f"{ATOM_NS}name")
        if author_name:
            default_channel_name = author_name

    videos: list[VideoMetadata] = []
    entries = root.findall(f"{ATOM_NS}entry")

    for entry in entries:
        # Extract Video ID: try <yt:videoId> first, fallback to <id>yt:video:ID</id>
        video_id = entry.findtext(f"{YT_NS}videoId")
        if not video_id:
            raw_id = entry.findtext(f"{ATOM_NS}id") or ""
            if "yt:video:" in raw_id:
                video_id = raw_id.split("yt:video:")[-1].strip()
            elif ":" in raw_id:
                video_id = raw_id.split(":")[-1].strip()

        if not video_id:
            logger.debug("Skipping feed entry without identifiable video ID.")
            continue

        title = (entry.findtext(f"{ATOM_NS}title") or "Untitled Video").strip()
        published = (entry.findtext(f"{ATOM_NS}published") or "").strip()

        # Link
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        link_elem = entry.find(f"{ATOM_NS}link[@rel='alternate']")
        if link_elem is not None and link_elem.get("href"):
            video_url = link_elem.get("href").strip()

        # Channel name for this entry
        entry_author = entry.find(f"{ATOM_NS}author")
        entry_channel_name = default_channel_name
        if entry_author is not None:
            author_name = entry_author.findtext(f"{ATOM_NS}name")
            if author_name:
                entry_channel_name = author_name.strip()

        videos.append(
            VideoMetadata(
                video_id=video_id,
                title=title,
                published_date=published,
                video_url=video_url,
                channel_name=entry_channel_name,
            )
        )

    return videos


def fetch_channel_videos(channel_id: str, timeout: int = 15) -> list[VideoMetadata]:
    """
    Fetch and parse the latest videos from a YouTube channel RSS feed.

    Args:
        channel_id: YouTube Channel ID (e.g. UC_x5XG1OV2P6uZZ5FSM9Ttw)
        timeout: HTTP request timeout in seconds

    Returns:
        List of VideoMetadata objects.
    """
    if not channel_id or not channel_id.strip():
        raise ValueError("A valid YouTube channel ID must be provided.")

    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id.strip()}"
    logger.info("Fetching YouTube RSS feed from: %s", rss_url)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(rss_url, headers=headers, timeout=timeout)

        if response.status_code == 404:
            logger.error("YouTube channel ID %s not found (HTTP 404).", channel_id)
            raise ValueError(f"Channel ID '{channel_id}' not found on YouTube.")

        response.raise_for_status()
        videos = parse_feed_xml(response.content)
        logger.info("Successfully retrieved %d videos from feed.", len(videos))
        return videos

    except requests.RequestException as e:
        logger.error("Network error while requesting YouTube RSS feed: %s", e)
        raise
