"""GitHub REST API client for committing markdown summaries."""

import base64
import logging
import time
from typing import Any
import requests

logger = logging.getLogger("ai_news")


class GitHubAPIError(Exception):
    """Raised when GitHub REST API interactions fail."""
    pass


class GitHubFileExistsError(GitHubAPIError):
    """Raised when target file already exists in repository and overwrite is disabled."""
    pass


class GitHubClient:
    """Client for uploading and committing files via GitHub REST API."""

    def __init__(
        self,
        owner: str,
        repo: str,
        token: str,
        branch: str = "main",
        timeout: int = 15,
    ) -> None:
        if not owner or not repo:
            raise ValueError("GITHUB_OWNER and GITHUB_REPO must be specified.")
        if not token or not token.strip():
            raise ValueError("GITHUB_TOKEN must be specified.")

        self.owner = owner.strip()
        self.repo = repo.strip()
        self.token = token.strip()
        self.branch = branch.strip() or "main"
        self.timeout = timeout
        self.base_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AI-News-Summarizer",
        })

    def _sanitize_message(self, message: str) -> str:
        """Strip sensitive token from error message strings."""
        if self.token and self.token in message:
            return message.replace(self.token, "[REDACTED]")
        return message

    def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> requests.Response:
        """Execute HTTP request with exponential backoff on transient errors."""
        last_exception: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                # Retry on 5xx server errors or rate limit 429
                if response.status_code in {429, 500, 502, 503, 504}:
                    logger.warning(
                        "GitHub API transient status %d on attempt %d/%d",
                        response.status_code,
                        attempt,
                        max_retries,
                    )
                    if attempt < max_retries:
                        time.sleep(2**attempt)
                        continue
                return response
            except requests.RequestException as e:
                last_exception = e
                logger.warning(
                    "GitHub API network error on attempt %d/%d: %s",
                    attempt,
                    max_retries,
                    self._sanitize_message(str(e)),
                )
                if attempt < max_retries:
                    time.sleep(2**attempt)
                else:
                    break

        raise GitHubAPIError(
            self._sanitize_message(
                f"GitHub API request failed after {max_retries} attempts: {last_exception}"
            )
        )

    def get_file(self, repo_path: str) -> dict[str, Any] | None:
        """
        Check if a file exists in the repository.
        Returns file metadata dict (including 'sha') if found, or None if 404 Not Found.
        """
        clean_path = repo_path.strip().lstrip("/")
        url = f"{self.base_url}/contents/{clean_path}"
        params = {"ref": self.branch}

        response = self._request_with_retry("GET", url, params=params)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            err_msg = self._sanitize_message(
                f"Failed to check file status at {clean_path}: {response.status_code} - {response.text}"
            )
            logger.error(err_msg)
            raise GitHubAPIError(err_msg)

    def commit_file(
        self,
        repo_path: str,
        content: str,
        commit_message: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """
        Create or update a file in the GitHub repository.

        Args:
            repo_path: Target relative path in repo (e.g. summaries/2026/10/summary.md)
            content: Raw UTF-8 string content to write
            commit_message: Git commit message
            overwrite: Whether to overwrite existing file (default: False)

        Returns:
            API response JSON detailing the commit.
        """
        clean_path = repo_path.strip().lstrip("/")
        url = f"{self.base_url}/contents/{clean_path}"

        # Check existing file
        existing_file = self.get_file(clean_path)
        sha: str | None = None

        if existing_file is not None:
            if not overwrite:
                raise GitHubFileExistsError(
                    f"File already exists at '{clean_path}' and overwrite is disabled."
                )
            sha = existing_file.get("sha")

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        payload: dict[str, Any] = {
            "message": commit_message,
            "content": encoded_content,
            "branch": self.branch,
        }
        if sha:
            payload["sha"] = sha

        response = self._request_with_retry("PUT", url, json=payload)

        if response.status_code in {200, 201}:
            logger.info("Successfully committed file to GitHub: %s", clean_path)
            return response.json()
        else:
            err_msg = self._sanitize_message(
                f"Failed to commit file to GitHub at {clean_path}: {response.status_code} - {response.text}"
            )
            logger.error(err_msg)
            raise GitHubAPIError(err_msg)
