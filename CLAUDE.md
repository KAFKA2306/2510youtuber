# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an automated YouTube video generation system that creates high-engagement financial news videos using AI agents. The system uses CrewAI with 7 specialized agents to generate scripts optimized for viewer retention (50%+ target), synthesizes multi-speaker Japanese audio, generates videos with B-roll footage, and uploads to YouTube.

## Essential Commands

### Development
```bash
# Run full workflow (news → script → video → upload)
uv run python3 -m app.main daily

# Test CrewAI script generation only (recommended for testing)
uv run python3 test_crewai_flow.py

# Verify API keys and environment
uv run python -m app.verify

# Generate analytics report (feedback loop)
python scripts/analytics_report.py

# Lint code
uv run ruff check .

# Format code
uv run ruff format .
```

### Testing
```bash
# Run all tests
pytest

# Run only fast unit tests (no external APIs)
pytest tests/unit -v

# Run integration tests (mocked APIs)
pytest tests/integration -v

# Run by marker
pytest -m unit           # Unit tests only
pytest -m crewai         # CrewAI-related tests
pytest -m "not slow"     # Skip slow tests

# Run single test file
pytest tests/unit/test_config.py -v

# Run with coverage
pytest --cov=app --cov-report=html
```

## Architecture Overview

### Core Workflow (10 Steps)
The main workflow in `app/main.py` executes these steps sequentially:

1. **News Collection** (`search_news.py`) - Perplexity AI → NewsAPI → fallback dummy news
2. **Script Generation** (`crew/flows.py`) - 7 CrewAI agents generate dialogue script
3. **Script Quality Check** (`japanese_quality.py`) - Validates Japanese purity 95%+
4. **Audio Synthesis** (`tts.py`) - ElevenLabs → VOICEVOX → OpenAI → gTTS → Coqui → pyttsx3
5. **STT for Alignment** (`stt.py`) - Whisper transcription of generated audio
6. **Subtitle Alignment** (`align_subtitles.py`) - Match script to actual audio timing
7. **B-roll Generation** (`services/media/`) - Stock footage matching + visual effects
8. **Video Rendering** (`video.py`) - FFmpeg compositing with subtitles
9. **Metadata Generation** (`metadata.py`) - Title, description, tags
10. **YouTube Upload** (`youtube.py`) - Automated upload with OAuth
11. **Feedback Logging** (`metadata_storage.py`) - Log execution to JSONL + Google Sheets (3 tabs)

### CrewAI Agent Pipeline (7 Agents)
Located in `app/crew/`:

1. **Deep News Analyzer** - Finds hidden insights and surprising facts
2. **Curiosity Gap Researcher** - Designs viewer engagement hooks
3. **Emotional Story Architect** - Structures narrative arc
4. **Script Writer** - Generates initial dialogue (3 speakers: 田中, 鈴木, ナレーター)
5. **Engagement Optimizer** - Maximizes retention with pattern interrupts
6. **Quality Guardian** - Validates WOW score 8.0+, metrics, pacing
7. **Japanese Purity Polisher** - Removes English artifacts, ensures 95%+ Japanese

Agents run in sequence, with parallel execution for agents 1-3 when `crew.parallel_analysis: true`.

**Critical Implementation Detail**: All CrewAI agents use `litellm` with Google AI Studio (NOT Vertex AI). The `flows.py` module explicitly removes Vertex AI environment variables to prevent misrouting. Agent prompts are in `app/config/prompts/*.yaml` files.

### API Key Rotation System
`app/api_rotation.py` implements resilient API handling:

- **Gemini**: Rotates through 5 keys on 429 errors (5-min wait per key, 10-min cooldown after all keys exhausted)
- **Perplexity**: Similar rotation with backoff
- **TTS**: 6-level fallback cascade (see TTS section)

The system tracks per-key cooldowns and automatically resumes when rate limits reset.

### Configuration System
**Unified Pydantic-based configuration**:

- **System**: `app/config/settings.py` reads `config.yaml`
- **Usage**: `from app.config import settings` (or legacy `cfg` alias)
- **Unified settings**: CrewAI, video, quality thresholds, API keys
- **Location**: `config.yaml` at project root
- **Environment variables**: Loaded via `python-dotenv` from `secret/.env`

**Important**: All configuration changes go to `config.yaml`. Environment variables are only for secrets (API keys, credentials).

### Data Models
`app/models/` contains Pydantic models:

- `script.py`: `ScriptSegment`, `WOWMetrics`, `Script` (dialogue structure)
- `news.py`: `NewsItem` (news article data)
- `workflow.py`: `StepStatus`, `StepResult`, `WorkflowSummary` (execution tracking)

All models use Pydantic v2 with validation. Scripts are structured as lists of `ScriptSegment` with speaker, text, timestamps, visual instructions.

### Media Processing Pipeline
`app/services/media/`:

- `stock_footage_manager.py`: Downloads clips from Pixabay/Pexels, caches 24h
- `visual_matcher.py`: Matches script keywords to appropriate stock footage
- `broll_generator.py`: FFmpeg composition with crossfade transitions

B-roll clips are selected based on visual instructions in script segments. The system applies ken-burns effects, color grading, and smooth transitions.

### File Archival System
`app/services/file_archival.py` - **NEW**: Manages persistent storage of workflow outputs

**Directory Structure:**
```
output/{timestamp}_{run_id}_{sanitized_title}/
  ├── video.mp4
  ├── audio.wav
  ├── thumbnail.png
  ├── script.txt
  └── subtitles.srt
```

**Key Features:**
- **Automatic archival**: All workflow files copied to organized directories after generation
- **Predictable paths**: Files grouped by run_id with timestamp and sanitized title
- **No data loss**: Files persist after YouTube upload (previous issue: temp files disappeared)
- **Recovery support**: `list_archived_workflows()` lists all past runs
- **Optional cleanup**: Configurable retention policy (default: keep forever)

**Implementation (TDD approach following t-wada):**
- Tests written first: `tests/unit/test_file_archival.py` (13 tests, 100% pass)
- `FileArchivalManager` class handles all file organization
- Integrated with `GenerateVideoStep` in workflow
- Files automatically archived after video generation completes

**Usage:**
```python
from app.services.file_archival import FileArchivalManager

manager = FileArchivalManager()
archived = manager.archive_workflow_files(
    run_id="abc123",
    timestamp="20251003_150000",
    title="Video Title",
    files={"video": "/tmp/video.mp4", "audio": "/tmp/audio.wav"}
)
# Returns: {"video": "output/.../video.mp4", "audio": "output/.../audio.wav"}
```

## Quality Assurance System

### Japanese Purity Check
`app/japanese_quality.py` enforces Japanese-only output:

- **Target**: 95%+ Japanese characters (configurable in `config.yaml`)
- **Phase 3 fix**: Agent 6-7 prompts modified to prevent output contamination with English metadata ("json", "wow_score", "Task", etc.)
- **Enforcement point**: After Agent 7 (Japanese Purity Polisher) completes

If purity check fails, the script is rejected and regeneration may be triggered.

### WOW Score Metrics
Scripts must achieve minimum thresholds (defined in `config.yaml`):

- WOW score: 8.0+ (10-point scale)
- Surprise points: 5+
- Emotion peaks: 5+
- Curiosity gaps: 3+
- Visual instructions: 15+
- Concrete numbers: 10+

These metrics are calculated by Agent 6 (Quality Guardian) and validated before proceeding.

### Video Generation Stability
**Phase 3 fix** in `app/video.py`:

- Previously, FFmpeg parameters (`crf`, `preset`, `vcodec`) were duplicated between quality settings and explicit arguments, causing failures
- **Solution**: All three video generation code paths (main, fallback, test) now exclusively use `**self._get_quality_settings()` without additional explicit parameters
- Quality presets: `low`, `medium`, `high`, `ultra` (defined in `config.yaml`)

## Common Development Patterns

### Adding a New CrewAI Agent
1. Add agent definition to `app/config/prompts/agents.yaml`
2. Create corresponding task in `app/config/prompts/<task_type>.yaml`
3. Update `app/crew/agents.py` to instantiate the agent
4. Update `app/crew/tasks.py` to create the task
5. Update `app/crew/flows.py` to include in crew sequence

### Modifying Quality Thresholds
Edit `config.yaml`:
```yaml
quality_thresholds:
  wow_score_min: 8.0              # Decrease if too strict
  japanese_purity_min: 95.0       # Minimum Japanese %
  retention_prediction_min: 50.0  # Target viewer retention
```

### TTS System and Speaker Consistency
**Architecture**: 6-level fallback chain with speaker-specific voice mapping (`app/tts/providers.py`)

**Speaker configuration** (`config.yaml`):
- **武宏** (玄野武宏) - VOICEVOX ID:11, OpenAI:onyx, pyttsx3:rate=140 - Male economic analyst
- **つむぎ** (春日部つむぎ) - VOICEVOX ID:8, OpenAI:nova, pyttsx3:rate=160 - Female reporter
- **ナレーター** - VOICEVOX ID:3, OpenAI:alloy, pyttsx3:rate=150 - Neutral narrator

**Fallback chain**:
1. ElevenLabs (uses `voice_id` from config) - Highest quality, paid
2. VOICEVOX (speaker-specific IDs) - High quality, free ⭐
3. OpenAI TTS (voice mapping) - Good quality, paid
4. gTTS (speed variation only) - Decent quality, free
5. Coqui (no speaker differentiation) - Low quality, free
6. pyttsx3 (rate variation) - Lowest quality, free

**Initial setup** (no API keys): VOICEVOX provides high-quality speaker differentiation for free

**Adding a new TTS provider**:
1. Create provider class in `app/tts/providers.py` inheriting from `TTSProvider`
2. Implement `_try_synthesize()` with speaker name handling via `voice_config["name"]`
3. Add to chain in `create_tts_chain()` function
4. Update `config.yaml` with provider-specific settings

### Working with FFmpeg
- All FFmpeg operations use subprocess with timeout protection
- Quality settings centralized in `_get_quality_settings()` methods
- **Never** manually specify `crf`, `preset`, or `vcodec` alongside quality settings dict
- Test video generation with: `pytest tests/test_stock_footage.py -v`

## File Structure Conventions

- `app/` - Main application code
  - `crew/` - CrewAI agents, tasks, flows
  - `config/` - New Pydantic-based configuration
  - `config_prompts/` - Legacy prompt system (being migrated)
  - `models/` - Pydantic data models
  - `services/media/` - Video/audio processing services
- `tests/` - Test suites (see `tests/README.md` for details)
  - `unit/` - Fast, no external dependencies
  - `integration/` - Mocked external APIs
  - `e2e/` - Real API calls (requires `--run-e2e` flag)
  - `api/` - API stability tests
- `output/` - Generated videos, scripts, audio (gitignored)
- `cache/` - Temporary downloads, API responses (gitignored)
- `secret/` - `.env` files with API keys (gitignored)

## Environment Variables

Required API keys (set in `secret/.env`):

```bash
# Required
GEMINI_API_KEY=AIza-your-key
ELEVENLABS_API_KEY=your-key    # or VOICEVOX_API_KEY

# Recommended (with rotation)
GEMINI_API_KEY_2=AIza-key-2
GEMINI_API_KEY_3=AIza-key-3
PERPLEXITY_API_KEY=pplx-your-key

# Optional but improves quality
PIXABAY_API_KEY=your-key
PEXELS_API_KEY=your-key
YOUTUBE_CLIENT_SECRETS_FILE=path/to/credentials.json
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

## Important Implementation Notes

### CrewAI + LiteLLM + Gemini
- The system MUST use Google AI Studio (Generative AI SDK), NOT Vertex AI
- `flows.py` removes all Vertex-related environment variables before CrewAI initialization
- API key rotation happens at the `litellm.completion` call level, not via environment variables
- Each agent can use different models (configured in `config.yaml` under `crew.agents`)

### Speaker Format Enforcement
Scripts MUST follow this format:
```
田中: セリフテキスト
鈴木: セリフテキスト
ナレーター: セリフテキスト
```

Agent 7 (Japanese Purity Polisher) enforces this format. Any deviation breaks TTS processing.

### Video Generation Failure Points
Common causes:
1. Parameter duplication (`crf`, `preset` specified twice)
2. Missing audio files (TTS failure)
3. Insufficient disk space for temp files
4. FFmpeg not installed or wrong version

Always check `ffmpeg -version` shows version 4.4+ for subtitle rendering support.

### Testing Strategy
- **Unit tests** (`tests/unit/`): Mock all external APIs, test pure logic
- **Integration tests** (`tests/integration/`): Use fixtures, test component interaction
- **E2E tests** (`tests/e2e/`): Real APIs, costs money, requires `--run-e2e` flag
- **Always run unit tests before commit**: `pytest tests/unit -v`

## Troubleshooting Quick Reference

### "Could not clean all English" warnings
- **Cause**: Agent 6/7 outputting metadata in English (Phase 3 issue)
- **Fix**: Update `app/config/prompts/quality_check.yaml` with explicit JSON-only output instructions
- **Check**: `grep "最終出力は、以下のJSON形式のみ" app/config/prompts/quality_check.yaml`

### FFmpeg "crf or preset" errors
- **Cause**: Duplicate parameter specification in video generation
- **Fix**: Ensure only `**self._get_quality_settings()` is used, no explicit quality params
- **Check**: `grep -A 2 "\*\*self._get_quality_settings()" app/video.py`

### Agent creation failures
- **Cause**: Missing `GEMINI_API_KEY` or incorrect format
- **Fix**: Verify with `uv run python -m app.verify`
- **Check**: `.env` file exists in `secret/` directory

### TTS quota exhausted
- **Cause**: ElevenLabs free tier used up (10k chars/month)
- **Fix**: System auto-falls back to gTTS/VOICEVOX
- **Permanent fix**: Start VOICEVOX Nemo server (free, unlimited): `./scripts/voicevox_manager.sh start`

### Rate limit 429 errors
- **Cause**: Gemini/Perplexity API rate limits hit
- **Fix**: System automatically rotates keys and waits
- **Prevent**: Add more rotation keys (`GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, etc.)

## Code Style

- **Linting**: Ruff with line length 120
- **Imports**: `isort` with `app` as first-party
- **Per-file ignores**: See `pyproject.toml` for specific file exemptions
- **Type hints**: Preferred but not enforced everywhere
- **Docstrings**: Use for public APIs, modules should have module-level docstrings
- **Logging**: Use Python logging, not print statements

## Feedback Loop System

**NEW**: Automated continuous improvement system that tracks execution metrics and provides insights.

### Quick Start

```bash
# Run workflow (auto-logs to JSONL + Sheets)
uv run python3 -m app.main daily

# View analytics
python scripts/analytics_report.py           # Weekly report
python scripts/analytics_report.py --hooks   # Hook performance
python scripts/analytics_report.py --topics  # Topic distribution
```

### Data Flow

```
Workflow → WorkflowResult → JSONL Log + Google Sheets (3 tabs)
                                  ↓
                            Analytics Engine
                                  ↓
                       Insights & Recommendations
```

### Storage

- **JSONL**: `output/execution_log.jsonl` - Complete execution data for analytics
- **Google Sheets**: 3 tabs (performance_dashboard, quality_metrics, production_insights)
- **Legacy CSV**: `data/metadata_history.csv` - Still maintained for backward compatibility

### Tracked Metrics

- **Quality**: WOW score, Japanese purity, retention prediction, surprise points, emotion peaks
- **Strategy**: Hook type (衝撃的事実/疑問提起/意外な数字), topic classification
- **Performance**: Execution time, API costs breakdown, step durations
- **Feedback**: YouTube views, CTR, retention, top comments (updated via cron)

### Key Files

- `app/models/workflow.py` - Extended `WorkflowResult` + `YouTubeFeedback` models
- `app/metadata_storage.py` - Integrated logging with Sheets formatting
- `app/analytics.py` - `FeedbackAnalyzer` for pattern detection
- `scripts/analytics_report.py` - CLI reporting tool
- `docs/FEEDBACK_LOOP.md` - Complete documentation

**Design Principle**: Minimal integration, zero breaking changes. Extends existing `WorkflowResult` and `MetadataStorage` rather than creating new infrastructure.

## References

- **Project overview**: `docs/README.md` - クイックスタート・概要
- **Setup guide**: `docs/SETUP.md` - 環境構築（API keys等）
- **Architecture**: `docs/ARCHITECTURE.md` - システム構成・ワークフロー
- **Features**: `docs/FEATURES.md` - 全機能詳細（Stock Footage, Feedback Loop等）
- **API management**: `docs/API_REFERENCE.md` - APIレート制限・ローテーション
- **Data management**: `docs/DATA_MANAGEMENT.md` - Google Sheets連携・メタデータ管理
- **CrewAI details**: `docs/README_CREWAI.md` - エージェント詳細
- **VOICEVOX**: `docs/VOICEVOX.md` - TTS設定・話者ID
- **Troubleshooting**: `docs/TROUBLESHOOTING.md` - トラブルシューティング
- **Test documentation**: `tests/README.md` - テスト構成
- **Main config**: `config.yaml` - 統合設定ファイル
- **Pytest config**: `pytest.ini` - テスト設定
