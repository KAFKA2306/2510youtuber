"""FastAPI application entry point for the GUI backend."""
from __future__ import annotations
import sys
from pathlib import Path
from fastapi import FastAPI
if __package__ in {None, ""}:
    current_path = Path(__file__).resolve()
    for candidate in current_path.parents:
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            project_root = candidate
            break
    else:
        project_root = current_path.parents[-1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
from app.gui.api.routes import commands, dashboard, jobs, prompts, settings
def create_app() -> FastAPI:
    app = FastAPI(title="Crew GUI API", version="0.1.0")
    app.include_router(commands.router, prefix="/commands", tags=["commands"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
    app.include_router(settings.router, prefix="/settings", tags=["settings"])
    app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
    return app
app = create_app()
