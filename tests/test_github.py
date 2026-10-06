"""Tests for GitHub REST API client."""

import base64
import pytest
from unittest.mock import MagicMock, patch
from src.github import GitHubClient, GitHubFileExistsError, GitHubAPIError


@pytest.fixture
def gh_client():
    return GitHubClient(
        owner="test-owner",
        repo="ai-news",
        token="ghp_test_token123",
        branch="main",
    )


def test_client_headers(gh_client):
    headers = gh_client.session.headers
    assert headers["Authorization"] == "Bearer ghp_test_token123"
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_get_file_found(gh_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"name": "test.md", "sha": "abc123sha"}

    with patch.object(gh_client.session, "request", return_value=mock_resp):
        result = gh_client.get_file("summaries/test.md")
        assert result is not None
        assert result["sha"] == "abc123sha"


def test_get_file_not_found(gh_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch.object(gh_client.session, "request", return_value=mock_resp):
        result = gh_client.get_file("summaries/nonexistent.md")
        assert result is None


def test_commit_file_new_success(gh_client):
    # Mock get_file returning None (file doesn't exist)
    with patch.object(gh_client, "get_file", return_value=None):
        mock_put_resp = MagicMock()
        mock_put_resp.status_code = 201
        mock_put_resp.json.return_value = {"content": {"name": "summary.md"}}

        with patch.object(gh_client.session, "request", return_value=mock_put_resp) as mock_req:
            res = gh_client.commit_file(
                repo_path="summaries/summary.md",
                content="# Hello Markdown",
                commit_message="Add summary",
            )
            assert res["content"]["name"] == "summary.md"

            # Verify payload sent to PUT
            call_kwargs = mock_req.call_args[1]
            payload = call_kwargs["json"]
            assert payload["message"] == "Add summary"
            assert payload["branch"] == "main"
            decoded_content = base64.b64decode(payload["content"]).decode("utf-8")
            assert decoded_content == "# Hello Markdown"


def test_commit_file_already_exists_raises(gh_client):
    # Mock get_file returning existing metadata
    with patch.object(gh_client, "get_file", return_value={"sha": "existing_sha"}):
        with pytest.raises(GitHubFileExistsError):
            gh_client.commit_file(
                repo_path="summaries/summary.md",
                content="# Hello Markdown",
                commit_message="Add summary",
                overwrite=False,
            )
