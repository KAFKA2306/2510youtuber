# Task Completion Checklist

When a task is completed, follow these steps:

## 1. Code Quality
```bash
# Lint code
uv run ruff check .

# Format code
uv run ruff format .
```

## 2. Testing
```bash
# Always run unit tests before commit
pytest tests/unit -v

# For CrewAI changes
pytest -m crewai -v

# For video/media changes
pytest tests/test_stock_footage.py -v

# For integration tests
pytest tests/integration -v
```

## 3. Verification (if modifying configuration or API integration)
```bash
# Verify API keys and environment
uv run python -m app.verify
```

## 4. Configuration Updates
If modifying configuration:
- Update `config.yaml` (new system)
- Document any `.env` requirements in `secret/.env`
- Update both systems if legacy code still depends on environment variables

## 5. Documentation
- Update docstrings for modified public APIs
- Update `CLAUDE.md` if changing essential commands or patterns
- Update relevant docs in `docs/` directory if architecture changes

## 6. Commit Guidelines
- Run linting and unit tests before committing
- Write clear commit messages
- Do not commit `output/`, `cache/`, or `secret/` directories (gitignored)

## 7. Special Considerations

### CrewAI Agent Changes
- Update agent definitions in `app/config/prompts/agents.yaml`
- Update corresponding tasks in `app/config/prompts/<task_type>.yaml`
- Update `app/crew/agents.py` and `app/crew/tasks.py`
- Update `app/crew/flows.py` to include in crew sequence

### FFmpeg/Video Changes
- Test with: `pytest tests/test_stock_footage.py -v`
- Verify FFmpeg version: `ffmpeg -version` (need 4.4+)
- Never duplicate `crf`, `preset`, `vcodec` parameters

### Quality Threshold Changes
- Edit `config.yaml` under `quality_thresholds:`
- Test impact on script generation: `uv run python3 test_crewai_flow.py`
