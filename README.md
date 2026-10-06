# Automated AI News Video Summarizer → GitHub

An autonomous backend pipeline that monitors a YouTube AI news channel, extracts new video transcripts, summarizes major developments with Google Gemini, generates structured Markdown reports, and commits them directly to a GitHub repository via the GitHub REST API.

---

## 📌 Architecture & Workflow

```text
YouTube Channel (RSS)
       │
       ▼
Detect New Video (Duplicate check vs data/processed_videos.json)
       │
       ▼
Extract & Clean Transcript (youtube-transcript-api)
       │
       ▼
Gemini AI Analysis (google-genai structured JSON synthesis)
       │
       ▼
Generate Markdown Summary (summaries/YYYY/MM/YYYY-MM-DD-title.md)
       │
       ▼
Commit to GitHub (GitHub REST API)
       │
       ▼
Update Processed State (Atomic persistence)
```

---

## ✨ Features

- **Automated YouTube Monitoring:** Monitors YouTube channel releases via fast, lightweight Atom RSS XML feeds (`/feeds/videos.xml?channel_id=...`).
- **Resilient Transcript Extraction:** Fetches English transcripts (favoring manual captions, falling back to auto-generated). Cleans audio noise (`[Music]`, `[Applause]`), removes stutter duplicates, and reformats into coherent paragraphs.
- **Large Transcript Chunking:** Automatically segments transcripts exceeding configurable chunk limits (`MAX_CHUNK_SIZE`) and performs multi-stage intermediate synthesis before generating the final report.
- **Deep Gemini AI Analysis:** Instructs Google Gemini to behave as an expert AI news analyst, strictly extracting supported facts, identifying model releases, breaking down major developments, and distinguishing presenter opinions and predictions from announcements.
- **Structured Schema Validation:** Enforces strict Pydantic JSON schemas with automated recovery retry if model output requires correction.
- **Direct GitHub REST API Upload:** Directly commits Markdown files using GitHub's REST API—eliminating the need for Git binaries inside containers or runner environments.
- **Robust Idempotency & Duplicate Prevention:** Retains processed video history in `data/processed_videos.json`. Only marks a video as processed **after** both Gemini synthesis and GitHub upload succeed.
- **Local Dry Run Mode:** Test the entire pipeline locally without modifying GitHub or updating state (`DRY_RUN=true`).
- **GitHub Actions Automation:** Scheduled cron workflow runs once or twice daily to keep your AI news repository continuously updated with zero manual overhead.

---

## 📂 Project Structure

```text
ai-news-automation/
├── src/
│   ├── __init__.py
│   ├── config.py             # Centralized environment & settings management
│   ├── github.py             # GitHub REST API client with retry logic
│   ├── main.py               # Main CLI orchestrator & pipeline runner
│   ├── markdown_generator.py # Formats structured summary into Markdown
│   ├── summarizer.py         # Google Gemini integration & JSON validation
│   ├── transcript.py         # Transcript fetching, cleaning & chunking
│   ├── utils.py              # Logging, secret masking, slug & state helpers
│   └── youtube.py            # YouTube Atom RSS feed fetcher & parser
├── data/
│   └── processed_videos.json # Processed video ID tracking
├── summaries/                # Local archive of generated summaries
│   └── .gitkeep
├── tests/
│   ├── test_config.py
│   ├── test_github.py
│   ├── test_main.py
│   ├── test_markdown.py
│   ├── test_summarizer.py
│   ├── test_transcript.py
│   ├── test_utils.py
│   └── test_youtube.py
├── .github/
│   └── workflows/
│       └── ai-news.yml       # GitHub Actions scheduled workflow
├── .env.example              # Environment variables template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Setup & Local Execution

### 1. Prerequisites
- **Python 3.11+**
- A **Google Gemini API Key** ([Google AI Studio](https://aistudio.google.com/))
- A **GitHub Personal Access Token** (classic token with `repo` scope, or fine-grained token with `Contents: Read and write`)
- A target **YouTube Channel ID** (e.g. `UC_x5XG1OV2P6uZZ5FSM9Ttw` for Google DeepMind)

### 2. Clone and Setup Environment

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```env
# Google Gemini API
GEMINI_API_KEY=AIzaSyYourActualKeyHere
GEMINI_MODEL=gemini-2.5-flash

# YouTube Channel ID to monitor
YOUTUBE_CHANNEL_ID=UC_x5XG1OV2P6uZZ5FSM9Ttw

# GitHub Integration
GITHUB_TOKEN=ghp_YourGitHubPersonalAccessToken
GITHUB_OWNER=your-github-username
GITHUB_REPO=your-ai-news-repo
GITHUB_BRANCH=main

# Automation Tuning
MAX_VIDEOS_PER_RUN=3
MAX_CHUNK_SIZE=30000
LOG_LEVEL=INFO

# Set to true for safe local testing without committing to GitHub
DRY_RUN=false
```

### 4. Running Locally

#### Dry Run Mode (Safe testing)
Set `DRY_RUN=true` in `.env` or pass via environment:

```bash
python -m src.main
```

Output:
```text
Checking YouTube channel...
Found 1 new video(s).

[1/1] Processing:
Gemini 2.5 Architecture & Capabilities
✓ Transcript retrieved
✓ Transcript cleaned
✓ Gemini summary generated
✓ Markdown generated
✓ Uploaded to GitHub (Dry Run - skipped)
✓ Marked as processed (Dry Run - skipped)

Processed: 1
Skipped: 0
Failed: 0
Done.
```

#### Production Run
Ensure `DRY_RUN=false`. The script will upload the generated markdown to `summaries/YYYY/MM/YYYY-MM-DD-video-title-id.md` on GitHub and mark the video in `data/processed_videos.json`.

---

## 🤖 GitHub Actions Scheduled Execution

The project includes `.github/workflows/ai-news.yml` configured to run twice daily at **06:00 and 18:00 UTC** and on-demand via the **Run workflow** button.

### Required GitHub Secrets & Variables

Navigate to **Repository Settings** → **Secrets and variables** → **Actions**:

#### Repository Secrets
| Secret Name | Description |
|---|---|
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `GITHUB_TOKEN` | Automatically provided by Actions (`${{ secrets.GITHUB_TOKEN }}`), or a custom Personal Access Token if pushing across repositories |

#### Repository Variables (or Secrets)
| Variable Name | Description | Default |
|---|---|---|
| `YOUTUBE_CHANNEL_ID` | The channel ID to monitor | *Required* |
| `GEMINI_MODEL` | Gemini model identifier | `gemini-2.5-flash` |
| `MAX_VIDEOS_PER_RUN` | Max videos to summarize per execution | `3` |

### Workflow Permissions
The workflow requires repository write permission to update `data/processed_videos.json` and local summaries. This is pre-configured in `.github/workflows/ai-news.yml`:
```yaml
permissions:
  contents: write
```

---

## 🧪 Running Unit Tests

Run the full pytest suite locally:

```bash
python -m pytest -v
```

All 34 unit and integration tests use mocks and do not require external API keys or active internet access.

---

## 🛡️ Security & Idempotency Notes

1. **Secret Masking:** Logging automatically intercepts and redacts API keys and tokens before emitting messages.
2. **Atomic State Storage:** `processed_videos.json` is updated atomically using temporary swap files to prevent file corruption during sudden job termination.
3. **No Redundant Processing:** Re-running the script at any time will skip previously cataloged videos without generating duplicates or consuming unnecessary API quota.
