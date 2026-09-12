# 2510youtuber Agent Contract

This is a legacy YouTube-generation repository kept for reproduction and diagnosis. New features belong in the current successor unless the user explicitly targets this repository.

`AGENTS.md` is the repository-wide agent instruction source. Tool-specific instruction files may only import it.

## Boundaries

Treat LLM output as untrusted. Validate structured output and do not invent dates, numbers, entities, provenance, or factual claims. Keep credentials and private runtime data out of the repository and generated artifacts.

Render and publication are separate claims. A local artifact or upload attempt does not prove remote publication.

## Verification

Use the repository checks for changed code:

```bash
uv run python -m compileall -q app tests
uv run pytest tests/unit -v
uv run ruff check .
uv run ruff format --check .
```

Production flows, external APIs, media generation, and publication require direct evidence only when they are part of the requested outcome.
