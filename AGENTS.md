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

## Outcome-first task interpretation (Altitude / Depth / Range / Speed)

- **Altitude:** Interpret a task as a verifiable user outcome, not only the named intermediate step. Infer the smallest justified acceptance criteria from the request and current repository state; do not silently expand scope or override explicit instructions.
- **Depth:** Use primary/current evidence and real domain tools and methods. Verify the actual postcondition independently of agent self-report, preferably on the exact changed revision or target runtime.
- **Range:** Combine code, data, tests, runtime/UI, and domain expertise when that materially improves the outcome, while respecting canonical owners and avoiding duplicate systems.
- **Speed:** Complete authorized read-only and reversible work through implementation, focused checks, and read-back without unnecessary approval loops. Bound retries and stop at the proven outcome.
- These principles never bypass repository-specific security, privacy, permission, publication, spending, destructive-action, or release boundaries. State verified results and any remaining `UNVERIFIED` layers.
