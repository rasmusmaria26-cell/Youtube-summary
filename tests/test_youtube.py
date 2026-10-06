"""Tests for YouTube RSS feed retrieval and XML parsing."""

import pytest
from src.youtube import VideoMetadata, parse_feed_xml, fetch_channel_videos

SAMPLE_YOUTUBE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="http://www.youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw"/>
  <id>yt:channel:UC_x5XG1OV2P6uZZ5FSM9Ttw</id>
  <yt:channelId>UC_x5XG1OV2P6uZZ5FSM9Ttw</yt:channelId>
  <title>Google DeepMind</title>
  <link rel="alternate" href="https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw"/>
  <author>
    <name>Google DeepMind</name>
    <uri>https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw</uri>
  </author>
  <published>2026-01-01T00:00:00+00:00</published>
  <entry>
    <id>yt:video:vid12345</id>
    <yt:videoId>vid12345</yt:videoId>
    <yt:channelId>UC_x5XG1OV2P6uZZ5FSM9Ttw</yt:channelId>
    <title>Gemini 2.5 Architecture &amp; Capabilities</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid12345"/>
    <author>
      <name>Google DeepMind</name>
    </author>
    <published>2026-10-06T10:00:00+00:00</published>
    <updated>2026-10-06T10:00:00+00:00</updated>
  </entry>
  <entry>
    <id>yt:video:vid67890</id>
    <title>Autonomous AI Agents in Production</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid67890"/>
    <published>2026-10-05T14:30:00+00:00</published>
  </entry>
</feed>
"""


def test_parse_feed_xml_valid():
    videos = parse_feed_xml(SAMPLE_YOUTUBE_ATOM_XML)
    assert len(videos) == 2

    v1 = videos[0]
    assert v1.video_id == "vid12345"
    assert v1.title == "Gemini 2.5 Architecture & Capabilities"
    assert v1.published_date == "2026-10-06T10:00:00+00:00"
    assert v1.video_url == "https://www.youtube.com/watch?v=vid12345"
    assert v1.channel_name == "Google DeepMind"

    v2 = videos[1]
    assert v2.video_id == "vid67890"  # Extracted from <id>
    assert v2.title == "Autonomous AI Agents in Production"
    assert v2.published_date == "2026-10-05T14:30:00+00:00"


def test_parse_feed_xml_empty():
    videos = parse_feed_xml("")
    assert videos == []

    videos_spaces = parse_feed_xml("   \n  ")
    assert videos_spaces == []


def test_parse_feed_xml_malformed():
    with pytest.raises(ValueError, match="Malformed XML"):
        parse_feed_xml("<feed><entry>unclosed</feed>")


def test_fetch_channel_videos_validation():
    with pytest.raises(ValueError, match="YouTube channel ID must be provided"):
        fetch_channel_videos("")
