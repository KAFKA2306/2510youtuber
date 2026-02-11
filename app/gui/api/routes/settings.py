"""Settings endpoints for the GUI."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.gui.api import schemas
from app.gui.api.deps import get_preferences_store, get_settings
from app.gui.core.settings import GuiSettingsEnvelope, PreferencesStore
router = APIRouter()
@router.get("/", response_model=schemas.GuiSettingsResponse)
async def fetch_settings(
    envelope: GuiSettingsEnvelope = Depends(get_settings),
) -> schemas.GuiSettingsResponse:
    return schemas.GuiSettingsResponse.from_envelope(envelope)
@router.put("/", response_model=schemas.GuiSettingsResponse)
async def update_settings(
    payload: schemas.GuiSettingsUpdate,
    store: PreferencesStore = Depends(get_preferences_store),
) -> schemas.GuiSettingsResponse:
    updated = store.save(payload.to_settings())
    return schemas.GuiSettingsResponse.from_envelope(updated)
