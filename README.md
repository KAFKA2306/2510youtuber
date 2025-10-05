# 2510youtuber

Automated YouTube video generation system using AI agents.

## Quick Links

- **Project Instructions**: [`CLAUDE.md`](CLAUDE.md)
- **Documentation**: [`docs/`](docs/)
- **Configuration**: [`config.yaml`](config.yaml)
- **Agent Prompts**: [`app/config/prompts/`](app/config/prompts/)
- **Serena Memories**: [`.serena/memories/`](.serena/memories/)

## Directory Structure

```
├── app/                    # Main application code
│   ├── crew/               # CrewAI agents, tasks, flows
│   ├── config/             # Configuration system
│   ├── models/             # Pydantic data models
│   └── services/media/     # Video/audio processing
├── tests/                  # Test suites
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── config.yaml             # Main configuration
└── CLAUDE.md               # Development guide
```

## Essential Commands

```bash
# Run full workflow
uv run python3 -m app.main daily

# Iterate verification loop (tests + optional workflow)
python scripts/tasks.py improve --iterations 3

# Inspect analytics & logs
python scripts/tasks.py analytics
python scripts/tasks.py logs

# Test script generation
uv run python3 test_crewai_flow.py

# Run tests
pytest tests/unit -v

# Lint & format
uv run ruff check .
uv run ruff format .
```

See [`CLAUDE.md`](CLAUDE.md) for detailed documentation.
