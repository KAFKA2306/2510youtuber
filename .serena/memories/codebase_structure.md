# Codebase Structure

## Directory Layout
```
/home/kafka/projects/2510youtuber/
├── app/                    # Main application code
│   ├── crew/               # CrewAI agents, tasks, flows
│   ├── config/             # New Pydantic-based configuration
│   ├── config_prompts/     # Legacy prompt system (being migrated)
│   ├── models/             # Pydantic data models
│   └── services/media/     # Video/audio processing services
├── tests/                  # Test suites
│   ├── unit/               # Fast, no external dependencies
│   ├── integration/        # Mocked external APIs
│   ├── e2e/                # Real API calls (requires --run-e2e flag)
│   └── api/                # API stability tests
├── scripts/                # Utility scripts (e.g., voicevox_manager.sh)
├── docs/                   # Documentation
├── output/                 # Generated videos, scripts, audio (gitignored)
├── cache/                  # Temporary downloads, API responses (gitignored)
├── secret/                 # .env files with API keys (gitignored)
├── data/                   # Data files
├── config.yaml             # Main configuration (new system)
├── pyproject.toml          # Project dependencies and tool config
├── pytest.ini              # Pytest configuration
└── CLAUDE.md               # Project instructions for Claude Code
```

## Key Modules

### Core Workflow (`app/`)
- `main.py` - Main 10-step workflow orchestrator
- `search_news.py` - News collection (Perplexity AI → NewsAPI)
- `script_gen.py` - Script generation wrapper
- `tts.py` - Text-to-speech (6-level fallback cascade)
- `stt.py` - Speech-to-text (Whisper)
- `align_subtitles.py` - Subtitle alignment
- `video.py` - Video rendering (FFmpeg)
- `metadata.py` - Title, description, tags generation
- `youtube.py` - YouTube upload
- `japanese_quality.py` - Japanese purity validation (95%+)
- `api_rotation.py` - API key rotation for rate limiting
- `verify.py` - API key verification

### CrewAI Pipeline (`app/crew/`)
- `flows.py` - CrewAI workflow orchestration
- `agents.py` - 7 agent definitions
- `tasks.py` - Agent task definitions
- `tools/` - Custom tools for agents

### Configuration (`app/config/`)
- `settings.py` - Pydantic-based settings (reads `config.yaml`)
- `prompts/*.yaml` - Agent prompts (agents.yaml, analysis.yaml, etc.)

### Data Models (`app/models/`)
- `script.py` - ScriptSegment, WOWMetrics, Script
- `news.py` - NewsItem
- `workflow.py` - StepStatus, StepResult, WorkflowSummary

### Media Processing (`app/services/media/`)
- `stock_footage_manager.py` - Downloads from Pixabay/Pexels
- `visual_matcher.py` - Matches keywords to footage
- `broll_generator.py` - FFmpeg composition with transitions
