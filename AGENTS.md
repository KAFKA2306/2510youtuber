# Repository Guidelines

This repository automates finance-themed YouTube production through a CrewAI workflow. Use the guardrails below to keep agents, media tooling, and analytics dependable.

## Project Structure & Module Organization
- `app/` contains runtime code: `crew/` orchestrates agents, `config/` maps `config.yaml` into Pydantic settings, `models/` defines workflow schemas, and `services/media/` handles footage, audio, and archival.
- `tests/` is split into `unit/`, `integration/`, and `e2e/` suites with shared `fixtures/` and `helpers/`; add new tests beside the closest peer suite.
- `scripts/` offers CLI utilities such as `analytics_report.py`; `docs/` explains architecture; runtime artifacts land in `output/` and `data/` and should stay untracked.

## Build, Test, and Development Commands
- `uv run python3 -m app.main daily` runs the end-to-end daily news → video publication loop.
- `uv run python3 test_crewai_flow.py` exercises CrewAI dialogue generation without rendering video.
- `uv run python -m app.verify` validates configuration and API keys before long runs.
- `pytest` or `pytest tests/unit -v` executes automated suites; add markers to scope slow or remote calls.
- `uv run ruff check .` and `uv run ruff format .` enforce linting and formatting prior to commits.

## Coding Style & Naming Conventions
- Target Python 3.10 with four-space indentation and a 120-character soft limit enforced by Ruff.
- Keep modules, functions, and variables snake_case; reserve PascalCase for classes, Pydantic models, and Crew definitions.
- Let Ruff’s isort rules group imports (`known-first-party = ["app"]`), and document non-obvious workflows with concise docstrings.

## Testing Guidelines
- Pytest uses `--strict-markers`; annotate tests with `@pytest.mark.unit`, `integration`, `e2e`, `crewai`, `slow`, or `requires_api_key` so jobs remain filterable.
- Prefer fast `tests/unit` coverage for new logic, mirror integration boundaries under `tests/integration`, and gate live-service checks behind `requires_api_key`.
- Name tests `test_<module>_<behavior>` and run `pytest --cov=app` when adding major features or refactors.

## Commit & Pull Request Guidelines
- Follow the Conventional Commit style seen in history (`feat: ...`, `fix: ...`), keeping subjects under 72 characters and bodies in English.
- Before opening a PR, run lint + tests, summarize the change set, note affected agents or media services, link tracking issues, and attach logs or screenshots for visual output updates.

## Configuration & Secrets
- Centralize defaults in `config.yaml` and load them through `app/config/settings.py`; do not hard-code secrets or API keys.
- Store credentials in `.env` (ignored by Git) and confirm access with `uv run python -m app.verify` whenever rotating keys or onboarding new agents.
