"""FastAPI application entry point for the GUI backend."""

from __future__ import annotations

from fastapi import FastAPI

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
