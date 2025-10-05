# GUI Backend Setup & Operation Guide

This guide walks through preparing and running the FastAPI backend that powers the optional desktop GUI. Follow these steps after completing the base project setup in [`docs/SETUP.md`](SETUP.md).

## 1. Prerequisites

- Python 3.11 or newer with the `uv` package manager available.
- FFmpeg 4.4 or newer (needed once jobs launch video workflows).
- The repository cloned locally with `.env` secrets configured as described in the main setup guide.

## 2. Install dependencies

```bash
uv sync
cp secret/.env.example secret/.env  # populate API keys afterwards
```

> Tip: `uv sync` ensures FastAPI, SQLModel, and other GUI dependencies referenced by the backend are available.

## 3. Launch the FastAPI backend

Run Uvicorn against the application factory defined in `app/gui/api/main.py`:

```bash
uv run uvicorn app.gui.api.main:app --host 127.0.0.1 --port 8000 --reload
```

- `main.py` dynamically locates the project root so imports such as `app.gui.api.routes` resolve without extra `PYTHONPATH` tweaks.
- The server starts on `http://127.0.0.1:8000`; the root path returns `404` by design, so use `/docs` (Swagger UI) or `/commands` directly for verification.

To check that the app is live:

```bash
curl http://127.0.0.1:8000/docs
```

## 4. Understand exposed endpoints

The backend mounts routers for commands, jobs, prompts, settings, and dashboard metrics. Key entry points include:

- `GET /commands` — lists available workflows backed by `config/gui/commands.yml`.
- `POST /jobs` — enqueues a workflow and tails execution logs under `logs/gui_jobs/`.
- `GET /prompts` and `POST /prompts` — manage prompt templates stored in SQLite at `state/gui/prompts.db` and synced files under `data/prompts/`.
- `GET /settings` / `PUT /settings` — load or persist preferences, combining defaults in `config/gui/settings.yml` with overrides in `state/gui/preferences.yml`.

See the FastAPI schema via `/docs` for request/response details.

## 5. Configure commands and preferences

1. Edit `config/gui/commands.yml` to add or adjust GUI-triggered workflows. Each entry declares the runner (`python_module` or `process`), module/command, and optional parameters presented in the UI.
2. Update defaults in `config/gui/settings.yml` to change execution mode, concurrency, logging verbosity, or notification toggles surfaced to the frontend.
3. User overrides are persisted automatically in `state/gui/preferences.yml` when the `/settings` API receives updates.

## 6. Data and log locations

The dependency wiring in `app/gui/api/deps.py` creates required directories on demand and keeps state scoped under the repository root. Notable paths:

- `logs/gui_jobs/` — JSONL execution logs per job.
- `state/gui/prompts.db` — SQLite database backing prompt metadata.
- `data/prompts/` — prompt file storage (live and historical versions).
- `output/execution_log.jsonl` and `data/metadata_history.csv` — dashboard data sources consumed by `/dashboard/*` routes.

Ensure these directories remain writable; they are ignored by Git so runtime artifacts stay local.

## 7. Integrating a frontend shell

The repository currently exposes only the backend services. A desktop shell (e.g., Tauri + SvelteKit) or browser frontend should:

1. Call `GET /commands` to render launchable workflows.
2. Submit `POST /jobs` with selected parameters and poll/stream logs from `/jobs/{id}` and `/jobs/{id}/logs`.
3. Persist user selections through `/settings` and visualize aggregated data via `/dashboard` endpoints.

The backend is stateless aside from the on-disk stores listed above, so any frontend framework capable of HTTP/WebSocket calls can integrate without additional adapters.

---

With these steps, you can spin up the GUI backend, customize available workflows, and connect a frontend client tailored to your operators.
