"""Diagnostic script to verify Gemini and GitHub API credentials."""

import sys
from src.config import load_config
from src.github import GitHubClient
from src.summarizer import GeminiSummarizer


def test_credentials() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    config = load_config()
    print("Testing configured credentials from .env...\n")

    # 1. Test Gemini API
    print("1. Testing Google Gemini API...")
    if not config.gemini_api_key:
        print("   ✗ GEMINI_API_KEY is empty in .env")
    else:
        try:
            summarizer = GeminiSummarizer(
                api_key=config.gemini_api_key,
                model=config.gemini_model,
            )
            test_prompt = ["AI news report: Google announced new updates to Gemini models for developers."]
            summary = summarizer.summarize(test_prompt, video_title="Gemini Verification Test")
            print(f"   ✓ Gemini API connection successful! (Model: {config.gemini_model})")
            print(f"     Generated summary title: \"{summary.title}\"")
        except Exception as e:
            print(f"   ✗ Gemini API error: {e}")

    # 2. Test GitHub Credentials
    print("\n2. Testing GitHub REST API...")
    if not config.github_token:
        print("   ✗ GITHUB_TOKEN is empty in .env")
    elif not config.github_owner or not config.github_repo:
        print("   ✗ GITHUB_OWNER or GITHUB_REPO is empty in .env")
    else:
        try:
            gh = GitHubClient(
                owner=config.github_owner,
                repo=config.github_repo,
                token=config.github_token,
                branch=config.github_branch,
            )
            # Test repo access by querying repo root contents
            res = gh._request_with_retry("GET", gh.base_url)
            if res.status_code == 200:
                repo_data = res.json()
                print(f"   ✓ GitHub connection successful! Target repo: {repo_data.get('full_name')} (Branch: {config.github_branch})")
            else:
                print(f"   ✗ GitHub returned status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"   ✗ GitHub connection error: {e}")

    print("\nDiagnostic check complete.")


if __name__ == "__main__":
    test_credentials()
