# 2510youtuber Agent Contract

This is a legacy YouTube-generation repository kept for reproduction and diagnosis. New features belong in the current successor unless the user explicitly targets this repository.

`AGENTS.md` is the only repository-wide agent instruction source. Tool-specific instruction files may only import it.

## Rules

- Prefer current user instruction, current executable code/config/tests/runtime, and current upstream docs over historical prose.
- Proceed with read-only and reversible work without unnecessary confirmation.
- Reuse existing config, helpers, workflows, and validation. Prefer deletion and consolidation over new wrappers or state.
- Treat LLM output as untrusted. Validate structured output and do not invent dates, numbers, entities, provenance, or factual claims.
- Keep credentials and private runtime data out of the repository and generated artifacts.
- Render and publication are separate. A local artifact or upload attempt does not prove remote publication.

## Verification

Run the smallest relevant deterministic checks first. Common checks are:

```bash
uv run python -m compileall -q app tests
uv run pytest tests/unit -v
uv run ruff check .
uv run ruff format --check .
```

Broaden into production flows, external APIs, media generation, or publication only when the requested outcome requires them.

A check that did not run is not PASS. CI proves only what it executed.

## Completion

Reuse one canonical Issue/branch/PR per outcome, read back state after writes, and stop when the requested repository or external state is directly verified. Unchecked layers remain `UNVERIFIED`.
