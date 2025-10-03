# Code Style and Conventions

## Linting and Formatting
- **Tool**: Ruff
- **Line Length**: 120 characters
- **Target Version**: Python 3.10+
- **Import Sorting**: isort with `app` as first-party

## Ruff Configuration
- **Selected Rules**: E (errors), F (pyflakes), W (warnings), I (import sorting)
- **Ignored Rules**: E501 (line length), E402 (import position), E722 (bare except)

## Per-File Ignores (pyproject.toml)
- `__init__.py`: F401 (unused imports)
- `tests/**/*.py`: F841 (unused variables)
- `app/thumbnail*.py`: F401, F811, F841 (PIL warnings)
- `app/tts.py`: F811, F841 (asyncio redefinition)
- `app/utils.py`: F821 (timezone undefined)
- `app/web.py`: F821 (Flask undefined)
- `app/youtube.py`: F841 (unused response)
- `app/video_feedback.py`: F811 (get_theme_manager redefinition)
- `app/crew/tools/ai_clients.py`: F811 (List redefinition)
- `app/japanese_quality.py`: F841 (allowed_pattern unused)
- `app/services/media/broll_generator.py`: F841 (result unused)
- `app/verify.py`: E402 (import position)

## Coding Conventions
- **Type Hints**: Preferred but not enforced everywhere
- **Docstrings**: Required for public APIs; modules should have module-level docstrings
- **Logging**: Use Python `logging` module, NOT print statements
- **Data Models**: Use Pydantic v2 with validation
- **Configuration**: 
  - New code: Use `from app.config import cfg` (Pydantic-based, reads `config.yaml`)
  - Legacy: Environment variables via `app/config_old.py`

## Naming Conventions
- **Japanese Speaker Names**: 田中, 鈴木, ナレーター
- **Script Format**: `田中: セリフテキスト` (speaker: dialogue)
- **File Organization**: `app/` for main code, `tests/` for tests
