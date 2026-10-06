"""Tests for Gemini summarization, schema validation, and recovery."""

import json
import pytest
from unittest.mock import MagicMock, patch
from src.summarizer import (
    GeminiSummarizer,
    NewsSummary,
    SummarizerError,
    TopicSummary,
    _clean_json_response,
)

SAMPLE_VALID_JSON = """
{
  "title": "Major Breakthroughs in Autonomous AI Agents",
  "summary": "DeepMind and OpenAI announced new benchmark results for self-correcting agents.",
  "topics": [
    {
      "title": "Autonomous Coding Agents",
      "summary": "New benchmarks show 85% task completion on complex software engineering issues.",
      "why_it_matters": "Enables developers to delegate entire engineering workflows reliably."
    }
  ],
  "key_takeaways": [
    "SWE-bench completion rate increased to 85%",
    "New architecture combines test-time compute with tree-search"
  ],
  "companies_mentioned": [
    "Google",
    "OpenAI"
  ],
  "technologies_mentioned": [
    "Gemini 2.5",
    "Tree Search"
  ],
  "notes": "Presenter believes 2026 will see mass enterprise adoption."
}
"""


def test_clean_json_response_raw():
    cleaned = _clean_json_response(SAMPLE_VALID_JSON)
    data = json.loads(cleaned)
    assert data["title"] == "Major Breakthroughs in Autonomous AI Agents"


def test_clean_json_response_markdown_blocks():
    wrapped = f"```json\n{SAMPLE_VALID_JSON}\n```"
    cleaned = _clean_json_response(wrapped)
    data = json.loads(cleaned)
    assert len(data["topics"]) == 1


def test_clean_json_response_with_surrounding_text():
    noisy = f"Here is the summary JSON:\n\n{SAMPLE_VALID_JSON}\n\nHope this helps!"
    cleaned = _clean_json_response(noisy)
    data = json.loads(cleaned)
    assert data["companies_mentioned"] == ["Google", "OpenAI"]


def test_news_summary_schema_validation():
    data = json.loads(SAMPLE_VALID_JSON)
    model = NewsSummary.model_validate(data)
    assert model.title == "Major Breakthroughs in Autonomous AI Agents"
    assert len(model.topics) == 1
    assert model.topics[0].why_it_matters.startswith("Enables")


def test_summarizer_successful_flow():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = SAMPLE_VALID_JSON
        mock_client.models.generate_content.return_value = mock_response

        summarizer = GeminiSummarizer(api_key="test_key", model="gemini-2.5-flash")
        result = summarizer.summarize(["Transcript chunk"], video_title="AI Breakthroughs")

        assert isinstance(result, NewsSummary)
        assert result.title == "Major Breakthroughs in Autonomous AI Agents"
        assert len(result.key_takeaways) == 2


def test_summarizer_malformed_retry_recovery():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # First call returns malformed JSON
        bad_response = MagicMock()
        bad_response.text = "This is not valid JSON at all."

        # Second call (recovery) returns valid JSON
        good_response = MagicMock()
        good_response.text = SAMPLE_VALID_JSON

        mock_client.models.generate_content.side_effect = [bad_response, good_response]

        summarizer = GeminiSummarizer(api_key="test_key")
        result = summarizer.summarize(["Transcript chunk"], video_title="Recovery Test")

        assert isinstance(result, NewsSummary)
        assert result.title == "Major Breakthroughs in Autonomous AI Agents"
        assert mock_client.models.generate_content.call_count == 2
