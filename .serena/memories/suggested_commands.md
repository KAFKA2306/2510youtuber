# Suggested Commands

## Development
```bash
# Run full workflow (news → script → video → upload)
uv run python3 -m app.main daily

# Test CrewAI script generation only (recommended for testing)
uv run python3 test_crewai_flow.py

# Verify API keys and environment
uv run python -m app.verify
```

## Linting and Formatting
```bash
# Lint code
uv run ruff check .

# Format code
uv run ruff format .
```

## Testing
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

## TTS Management
```bash
# Start VOICEVOX Nemo server (free, unlimited TTS)
./scripts/voicevox_manager.sh start

# Stop VOICEVOX
./scripts/voicevox_manager.sh stop

# Check status
./scripts/voicevox_manager.sh status
```

## Standard Linux Commands
- `ls` - list files
- `cd` - change directory
- `git` - version control
- `grep` - search text
- `find` - find files
