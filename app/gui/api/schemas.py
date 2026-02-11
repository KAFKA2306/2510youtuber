"""Pydantic schemas exposed via the FastAPI layer."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Mapping, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.gui.core.settings import (
    ExecutionSettings,
    GuiSettings,
    GuiSettingsEnvelope,
    LoggingSettings,
    RadioToggle,
)
from app.gui.dashboard.models import DashboardMetrics, RunArtifacts
from app.gui.jobs.manager import JobResponse
from app.gui.prompts.models import Prompt, PromptVersion
class CommandParameterSchema(BaseModel):
    name: str
    label: str
    required: bool = False
    default: Optional[str] = None
class CommandSchema(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    runner: str
    args: list[str] | None = None
    module: Optional[str] = None
    command: list[str] | None = None
    parameters: list[CommandParameterSchema] = Field(default_factory=list)
class JobCreateRequest(BaseModel):
    command_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
class JobListResponse(BaseModel):
    jobs: list[JobResponse]
class JobLogEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    job_id: UUID
    sequence: int
    stream: str
    message: str
    timestamp: datetime
    event: Optional[str] = None
    status: Optional[str] = None
    exit_code: Optional[int] = None
class JobLogResponse(BaseModel):
    entries: list[JobLogEntry]
class GuiSettingsResponse(BaseModel):
    settings: GuiSettings
    radios: Mapping[str, RadioToggle]
    @classmethod
    def from_envelope(cls, envelope: GuiSettingsEnvelope) -> "GuiSettingsResponse":
        return cls(settings=envelope.settings, radios=envelope.radios)
class GuiSettingsUpdate(BaseModel):
    execution: ExecutionSettings
    logging: LoggingSettings
    notifications_enabled: bool = False
    def to_settings(self) -> GuiSettings:
        return GuiSettings(
            execution=self.execution,
            logging=self.logging,
            notifications_enabled=self.notifications_enabled,
        )
class PromptSummarySchema(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    latest_version: int = 0
    created_at: datetime
    updated_at: datetime
    @classmethod
    def from_model(cls, prompt: Prompt) -> "PromptSummarySchema":
        return cls(
            id=prompt.id,
            name=prompt.name,
            description=prompt.description,
            tags=list(prompt.tags or []),
            latest_version=prompt.latest_version,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )
class PromptVersionSchema(BaseModel):
    id: UUID
    prompt_id: str
    version: int
    message: str
    author: str
    tags: list[str] = Field(default_factory=list)
    checksum: str
    created_at: datetime
    @classmethod
    def from_model(cls, version: PromptVersion) -> "PromptVersionSchema":
        return cls(
            id=version.id,
            prompt_id=version.prompt_id,
            version=version.version,
            message=version.message,
            author=version.author,
            tags=list(version.tags or []),
            checksum=version.checksum,
            created_at=version.created_at,
        )
class PromptVersionDetailSchema(PromptVersionSchema):
    content: str
    @classmethod
    def from_model(
        cls,
        version: PromptVersion,
        content: str,
    ) -> "PromptVersionDetailSchema":
        base = PromptVersionSchema.from_model(version)
        return cls(**base.model_dump(), content=content)
class PromptDetailResponse(BaseModel):
    prompt: PromptSummarySchema
    latest_version: PromptVersionDetailSchema | None = None
    versions: list[PromptVersionSchema] = Field(default_factory=list)
class PromptVersionCreateRequest(BaseModel):
    content: str
    message: str = ""
    author: str = "system"
    tags: list[str] = Field(default_factory=list)
    name: Optional[str] = None
    description: Optional[str] = None
class DashboardArtifactsResponse(BaseModel):
    artifacts: list[RunArtifacts]
class DashboardMetricsResponse(DashboardMetrics):
    pass
