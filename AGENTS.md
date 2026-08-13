# 2510youtuber Agent Operating Contract

This repository is the retained 2025-10 YouTube production implementation. The current successor is `KAFKA2306/2511youtuber`.

`AGENTS.md` defines how an autonomous agent may inspect, repair, validate, and close work in this repository. It is not a feature roadmap.

## 1. Mission and Scope

Preserve `2510youtuber` as a reproducible, diagnosable legacy production system.

Default policy:

- repair regressions, corrupted files, broken tests, security issues, and evidence gaps here;
- preserve existing runtime behavior unless the task explicitly requires a behavior change;
- route genuinely new product capability to the successor repository unless the user explicitly requests this repository;
- do not perform broad modernization merely because newer patterns exist elsewhere.

The Contract is both the minimum required result and the maximum allowed scope.

## 2. Source-of-Truth Precedence

When sources disagree, use this order:

1. current repository/runtime observations;
2. current executable Python code, Pydantic models, configuration loaders, and media pipeline;
3. `config.yaml` for declared repository configuration;
4. deterministic tests and current GitHub Actions checks;
5. current persisted artifacts/logs directly relevant to the task;
6. README / CLAUDE / docs / Serena memories;
7. Issue/PR historical prose;
8. inference.

Never let stale documentation override executable reality.

This matters in this repository because historical documentation may describe older JSON-oriented behavior while later commits moved parts of LLM I/O and logging toward YAML. Inspect the current implementation before claiming the active serialization contract.

## 3. Claim Provenance

Every material claim must be treated as one of:

- **VERIFIED** — directly observed from code, command output, artifact, API response, test, or CI.
- **OBSERVED** — explicitly supplied by the user or task contract.
- **INFERRED** — derived from evidence; label it as inference when reporting.
- **UNVERIFIED** — not inspected; do not present as fact.
- **FABRICATED** — forbidden.

A command exit code is not proof of the user-visible outcome. Verify the owning postcondition.

## 4. Canonical Workline Rule

Before creating a branch or PR:

1. inspect open PRs;
2. inspect relevant active branches;
3. inspect the owning Issue if one exists;
4. continue the canonical workline when it already exists;
5. only otherwise create one descriptive branch and one PR.

Do not create competing branches, duplicate PRs, duplicate workflow implementations, or second state/configuration stores for the same outcome.

Superseded branches/PRs must not be revived wholesale when current `main` has diverged. Reconstruct the smallest valid change on current `main` when necessary.

## 5. Contract Before Change

For non-trivial work, identify:

- **Contract** — required behavior and forbidden side effects;
- **Outcome** — observable final state;
- **Acceptance Criteria** — deterministic checks that prove the outcome;
- **Evidence** — exact code, test, artifact, CI run, or remote receipt;
- **Stopping Condition** — fixed point after which more edits are scope expansion.

## 6. Repository Boundaries

Key current surfaces include:

- `app/` — runtime code;
- `app/crew/` — CrewAI orchestration;
- `app/config/` and `config.yaml` — configuration and prompts;
- `app/models/` — structured workflow models;
- `app/services/media/` — audio/image/video processing;
- `app/workflow/` — workflow ports and steps;
- `tests/` — regression evidence;
- `scripts/` — maintenance/analysis utilities;
- `docs/` — explanatory material, lower precedence than executable reality.

Runtime/generated media, credentials, cookies, OAuth material, and local logs must not become accidental public source files.

## 7. Configuration and Secrets

- Keep repository defaults in `config.yaml` and use the current loader path rather than adding competing configuration sources.
- Never hard-code API keys, cookies, YouTube credentials, private webhook URLs, or OAuth tokens.
- `.env` and equivalent credential stores are local/runtime concerns and must stay untracked.
- Do not copy secrets into fixtures, screenshots, logs, prompts, Issue bodies, or PR descriptions.
- Validate configuration through the current implementation before long or external runs.

## 8. LLM I/O Discipline

LLM output is untrusted input.

- Parse and validate with deterministic code before downstream use.
- Prefer the repository's current Pydantic/YAML/structured-output path rather than assumptions copied from historical docs.
- Keep prompt constraints minimal when deterministic validators/formatters can enforce the requirement.
- Never treat an LLM-generated claim as a verified news fact without source verification.
- Preserve enough interaction metadata to diagnose failures, subject to secret/privacy constraints.
- Do not publish fallback text/video while representing it as a successful requested artifact.

If `docs/LLM_OUTPUT_DISCIPLINE.md` disagrees with current code, current code and regression tests win; update the document in a separate bounded task if needed.

## 9. News and Factual Content

For news-derived output:

- record source identity and retrieval/publication timing when the owning workflow supports it;
- prefer primary sources for material factual claims;
- distinguish observed facts from interpretation;
- do not fill missing numbers, dates, names, or causal claims heuristically;
- fail closed when a required fact cannot be verified to the task's acceptance standard.

Generated prose is not itself evidence.

## 10. Media and Publication Boundary

Rendering and publishing are different operations.

Before any YouTube publication:

1. identify the exact final media artifact;
2. verify required media QA and critical checks;
3. verify title/metadata/profile/channel routing;
4. verify that the task explicitly authorizes publication;
5. perform the publish action through the existing repository path;
6. capture the remote receipt/identifier and resulting visibility/state;
7. re-read remote state when possible.

A local render, upload attempt, or API call is not proof of publication.

The README currently requires human review before public release. Do not silently weaken that boundary.

## 11. Fail-Closed Rule

Do not turn failures into apparent success.

The following block the corresponding acceptance criterion:

- syntax/configuration failure;
- parser/schema failure;
- required API/source unavailable;
- media QA critical failure;
- missing final artifact;
- ambiguous publication target;
- missing publication receipt;
- test or verifier crash;
- unverified replacement/fallback artifact.

Fix root causes instead of suppressing failures.

## 12. Minimal Change / Deletion Test

Prefer the smallest change that proves the requested outcome.

Delete from the diff anything that can be removed while all acceptance criteria remain provable.

Avoid:

- speculative refactors;
- dependency upgrades unrelated to the task;
- architecture migrations toward `2511youtuber` patterns without an explicit contract;
- duplicate helper layers;
- future-proofing abstractions;
- unrelated formatting churn.

## 13. Validation Ladder

Use the cheapest deterministic check that can falsify the change, then escalate.

Typical local checks currently include:

```bash
python -m compileall -q app tests
pytest tests/unit -v
uv run ruff check .
uv run ruff format --check .
```

For end-to-end behavior when explicitly required:

```bash
uv run python -m app.main daily
uv run python test_crewai_flow.py
```

Do not run a costly or externally mutating workflow merely because it exists.

Current CI includes:

- `Python syntax safety` — validates `pyproject.toml`, rejects merge-conflict markers, and compiles `app` + `tests` on Python 3.11;
- `News collection async contract` — verifies the synchronous collector runs off the event-loop thread for affected workflow files.

CI success is evidence only for the checks that actually ran on the exact commit SHA.

## 14. Builder / Auditor Separation

### Builder

May inspect and change the minimum code/tests/docs/config needed by the Contract.

### Auditor

Must independently verify:

- the requested outcome exists;
- changed Python is syntactically valid;
- relevant unit/contract tests pass;
- LLM/news/media boundaries were not weakened;
- evidence belongs to the current head SHA;
- no secrets or generated residue entered the diff;
- publication, if requested, has a remote receipt;
- cleanup is complete.

Implementation intent is not audit evidence.

## 15. Git / PR / CI Protocol

1. start from the latest intended `main`;
2. reuse the canonical branch if one exists;
3. otherwise create one descriptive branch;
4. keep the diff bounded;
5. add/update regression evidence with behavior changes;
6. open/update one canonical PR;
7. verify CI on the exact PR head SHA;
8. investigate failures rather than retrying blindly;
9. merge only when acceptance criteria are provable;
10. verify merged `main` and required post-merge CI;
11. close the owning Issue only when its actual outcome is complete;
12. delete the merged/unneeded work branch when the available GitHub surface permits it.

If a host-side safety check rejects a GitHub write, re-fetch current state and retry the exact canonical action once. Do not create a duplicate workline as a workaround.

## 16. Cleanup Is Part of Completion

Before final reporting, inspect for task-created residue:

- temporary media;
- debug logs;
- generated intermediate YAML/JSON/text files;
- untracked credentials;
- stale test fixtures;
- superseded PRs;
- merged/unneeded branches;
- obsolete helper scripts/workflows introduced only for the task.

Do not delete unrelated valid historical work.

If a blocker remains, keep exactly one canonical workline and record the blocker plus exact next action.

## 17. Fixed Point

Stop when:

- requested outcome exists;
- acceptance criteria pass;
- evidence is bound to the current final state;
- required CI/postconditions are verified;
- publication receipt exists if publication was part of the Contract;
- linked Issue/PR state is correct;
- task-created residue is removed or an explicit tooling blocker is recorded;
- no additional change is necessary to prove the outcome.

## 18. Final Report Contract

Report only verified state relevant to the task:

- target repository / Issue / PR URL;
- bounded change;
- tests and CI actually executed;
- PR/commit/merge SHA;
- publication receipt if external state changed;
- cleanup;
- blocker and exact next action if unfinished.

No completion theater. If something was not inspected, say so.
