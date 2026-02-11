"""Routes for prompt management in the GUI backend."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from app.gui.api import deps, schemas
from app.gui.prompts.repository import PromptRepository
router = APIRouter()
@router.get("/", response_model=list[schemas.PromptSummarySchema])
async def list_prompts(
    repository: PromptRepository = Depends(deps.get_prompt_repository),
) -> list[schemas.PromptSummarySchema]:
    prompts = repository.list_prompts()
    return [schemas.PromptSummarySchema.from_model(prompt) for prompt in prompts]
@router.get("/{prompt_id}", response_model=schemas.PromptDetailResponse)
async def get_prompt(
    prompt_id: str,
    repository: PromptRepository = Depends(deps.get_prompt_repository),
) -> schemas.PromptDetailResponse:
    try:
        prompt = repository.get_prompt(prompt_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    versions = repository.list_versions(prompt_id)
    version_summaries = [schemas.PromptVersionSchema.from_model(version) for version in versions]
    latest_version_detail = None
    if versions:
        latest_version = versions[0]
        content = repository.load_content(latest_version)
        latest_version_detail = schemas.PromptVersionDetailSchema.from_model(latest_version, content)
    return schemas.PromptDetailResponse(
        prompt=schemas.PromptSummarySchema.from_model(prompt),
        latest_version=latest_version_detail,
        versions=version_summaries,
    )
@router.get(
    "/{prompt_id}/versions",
    response_model=list[schemas.PromptVersionSchema],
)
async def list_versions(
    prompt_id: str,
    repository: PromptRepository = Depends(deps.get_prompt_repository),
) -> list[schemas.PromptVersionSchema]:
    try:
        repository.get_prompt(prompt_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    versions = repository.list_versions(prompt_id)
    return [schemas.PromptVersionSchema.from_model(version) for version in versions]
@router.get(
    "/{prompt_id}/versions/{version}",
    response_model=schemas.PromptVersionDetailSchema,
)
async def get_version(
    prompt_id: str,
    version: int,
    repository: PromptRepository = Depends(deps.get_prompt_repository),
) -> schemas.PromptVersionDetailSchema:
    try:
        prompt_version = repository.get_version(prompt_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    content = repository.load_content(prompt_version)
    return schemas.PromptVersionDetailSchema.from_model(prompt_version, content)
@router.post(
    "/{prompt_id}/versions",
    response_model=schemas.PromptVersionDetailSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    prompt_id: str,
    payload: schemas.PromptVersionCreateRequest,
    repository: PromptRepository = Depends(deps.get_prompt_repository),
) -> schemas.PromptVersionDetailSchema:
    version = repository.save_version(
        prompt_id=prompt_id,
        content=payload.content,
        author=payload.author,
        message=payload.message,
        tags=payload.tags,
        name=payload.name,
        description=payload.description,
    )
    content = repository.load_content(version)
    return schemas.PromptVersionDetailSchema.from_model(version, content)
