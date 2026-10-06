"""Gemini AI news summarization module using google-genai SDK."""

import json
import logging
import re
import time
from typing import Any
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("ai_news")


class TopicSummary(BaseModel):
    """Structured breakdown of an individual news topic/development."""

    title: str = Field(description="Clear title of the specific AI development")
    summary: str = Field(description="Factual description of what happened")
    why_it_matters: str = Field(description="Explanation of why this development is significant")


class NewsSummary(BaseModel):
    """Complete structured summary schema for AI news videos."""

    title: str = Field(description="Overarching title of the news summary")
    summary: str = Field(description="Concise overall summary covering the video's core news")
    topics: list[TopicSummary] = Field(default_factory=list, description="List of major developments")
    key_takeaways: list[str] = Field(default_factory=list, description="Key bullet points summarizing insights")
    companies_mentioned: list[str] = Field(default_factory=list, description="List of companies or institutions mentioned")
    technologies_mentioned: list[str] = Field(default_factory=list, description="List of specific models, tools, or techniques mentioned")
    notes: str = Field(
        default="",
        description="Any uncertainty, presenter opinions, predictions, or context to distinguish from facts",
    )


class SummarizerError(Exception):
    """Raised when summarization fails or returns irrecoverable invalid output."""
    pass


SYSTEM_INSTRUCTION = """You are an AI news analyst.
Analyze the provided transcript from an AI news video.
Your task is to create an accurate, concise, useful summary for someone who wants to understand the important AI developments without watching the entire video.

Strict Rules:
1. Only use information supported by the transcript.
2. Do NOT invent facts or hallucinate details.
3. Do NOT add external information not mentioned in the transcript.
4. Clearly separate factual reporting from opinions, speculations, or predictions.
5. Ignore greetings, sponsor segments, advertisements, repeated statements, and irrelevant banter.
6. Focus on meaningful AI developments: model releases, research breakthroughs, company announcements, product launches, acquisitions, regulations, and industry shifts.
7. Explain why important developments matter.
8. Distinguish presenter opinions/predictions from verified announcements in the 'notes' field.
9. Return output strictly conforming to the requested JSON schema.
"""


def _clean_json_response(raw_text: str) -> str:
    """Extract raw JSON text from model output, stripping markdown code blocks if present."""
    text = raw_text.strip()
    if text.startswith("```"):
        # Match ```json ... ``` or ``` ... ```
        pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
        match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()

    # If leading/trailing stray non-bracket characters exist, isolate outermost { ... }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]

    return text


class GeminiSummarizer:
    """Orchestrates video transcript summarization using Google Gemini."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        if not api_key or not api_key.strip():
            raise ValueError("GEMINI_API_KEY must be provided.")
        self.api_key = api_key.strip()
        self.model = model.strip() or "gemini-2.5-flash"
        self._init_client()

    def _init_client(self) -> None:
        from google import genai
        # Initialize Google GenAI Client
        self.client = genai.Client(api_key=self.api_key)

    def _call_gemini_with_retry(
        self,
        contents: str | list[Any],
        max_retries: int = 3,
        response_schema: Any = None,
    ) -> str:
        """Call Gemini API with exponential backoff on transient errors."""
        from google.genai import types

        config_kwargs: dict[str, Any] = {
            "temperature": 0.2,
            "system_instruction": SYSTEM_INSTRUCTION,
        }

        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        config = types.GenerateContentConfig(**config_kwargs)

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug("Calling Gemini model %s (attempt %d/%d)...", self.model, attempt, max_retries)
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                if not response.text:
                    raise SummarizerError("Gemini returned empty response text.")
                return response.text
            except Exception as e:
                last_error = e
                err_str = str(e)
                # Ensure api key is never in error string
                sanitized_err = err_str.replace(self.api_key, "[REDACTED]")
                logger.warning(
                    "Gemini API attempt %d/%d failed: %s",
                    attempt,
                    max_retries,
                    sanitized_err,
                )
                if attempt < max_retries:
                    sleep_time = 2**attempt
                    time.sleep(sleep_time)
                else:
                    break

        raise SummarizerError(f"Gemini API failed after {max_retries} attempts: {last_error}")

    def summarize_from_video_url(self, video_url: str, video_title: str = "") -> NewsSummary:
        """
        Fallback summarization directly from YouTube video URL via Gemini native video understanding
        when caption scraping is blocked by YouTube's anti-bot filters.
        """
        from google.genai import types

        logger.info("Using Gemini native video understanding for: %s", video_url)
        video_part = types.Part.from_uri(file_uri=video_url, mime_type="video/*")
        prompt = (
            f"Video Title: {video_title}\n\n"
            "Analyze the contents, spoken audio dialogue, and key developments of this video. "
            "Produce the final structured AI news summary adhering strictly to the JSON schema."
        )

        raw_output = self._call_gemini_with_retry([video_part, prompt], response_schema=NewsSummary)
        return self._parse_and_validate(raw_output, f"Video URL: {video_url}", video_title)

    def summarize_chunk(self, chunk_text: str, chunk_index: int, total_chunks: int) -> str:
        """Summarize an intermediate chunk when dealing with very long transcripts."""
        prompt = (
            f"This is section {chunk_index} of {total_chunks} of a longer video transcript.\n"
            "Extract all facts, key announcements, models mentioned, and important statements.\n"
            "Transcript section:\n\n"
            f"{chunk_text}"
        )
        return self._call_gemini_with_retry(prompt)

    def summarize(self, transcript_chunks: list[str], video_title: str = "") -> NewsSummary:
        """
        Produce a validated NewsSummary from transcript chunks.
        If multiple chunks are passed, summarizes them in stages before final structured synthesis.
        """
        if not transcript_chunks:
            raise SummarizerError("No transcript content provided for summarization.")

        # Stage 1: Chunk summarization if transcript was split
        if len(transcript_chunks) == 1:
            content_to_analyze = transcript_chunks[0]
        else:
            logger.info("Processing %d transcript chunks in stages...", len(transcript_chunks))
            intermediate_summaries: list[str] = []
            for idx, chunk in enumerate(transcript_chunks, start=1):
                chunk_summary = self.summarize_chunk(chunk, idx, len(transcript_chunks))
                intermediate_summaries.append(f"--- Chunk {idx} Notes ---\n{chunk_summary}")

            content_to_analyze = (
                f"Video Title: {video_title}\n\n"
                "Intermediate Summaries from long video sections:\n\n"
                + "\n\n".join(intermediate_summaries)
            )

        # Stage 2: Final structured synthesis
        final_prompt = (
            f"Video Title: {video_title}\n\n"
            "Transcript Content:\n"
            f"{content_to_analyze}\n\n"
            "Produce the final structured AI news summary adhering strictly to the JSON schema."
        )

        # Attempt structured generation with Pydantic schema
        raw_output = self._call_gemini_with_retry(final_prompt, response_schema=NewsSummary)

        # Parse & Validate
        parsed_summary = self._parse_and_validate(raw_output, content_to_analyze, video_title)
        return parsed_summary

    def _parse_and_validate(self, raw_output: str, source_content: str, video_title: str) -> NewsSummary:
        """Parse raw output into NewsSummary, with single correction retry if malformed."""
        cleaned_json = _clean_json_response(raw_output)

        err_msg = ""
        try:
            data = json.loads(cleaned_json)
            return NewsSummary.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as parse_err:
            err_msg = str(parse_err)
            logger.warning(
                "Initial Gemini response malformed (%s). Retrying once with error correction prompt...",
                err_msg,
            )

        # Correction Retry
        correction_prompt = (
            "Your previous response failed JSON schema validation.\n"
            f"Error details: {err_msg}\n"
            f"Previous output snippet: {raw_output[:500]}\n\n"
            "Please fix the format and output ONLY valid JSON matching the schema for this content:\n"
            f"{source_content[:4000]}"
        )

        retry_output = self._call_gemini_with_retry(correction_prompt, response_schema=NewsSummary)
        cleaned_retry_json = _clean_json_response(retry_output)

        try:
            data = json.loads(cleaned_retry_json)
            return NewsSummary.model_validate(data)
        except Exception as final_err:
            logger.error("Correction attempt also failed: %s", final_err)
            raise SummarizerError(
                f"Failed to obtain valid JSON summary from Gemini: {final_err}"
            ) from final_err
