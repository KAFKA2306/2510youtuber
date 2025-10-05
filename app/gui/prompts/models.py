"""SQLModel definitions for GUI prompt management."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlmodel import Field, SQLModel


class Prompt(SQLModel, table=True):
    """Prompt metadata describing the latest revision and tags."""

    __tablename__ = "prompts"

    id: str = Field(primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    latest_version: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PromptVersion(SQLModel, table=True):
    """Individual prompt revision stored on disk as YAML."""

    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    prompt_id: str = Field(foreign_key="prompts.id")
    version: int = Field(nullable=False, index=True)
    message: str = Field(default="")
    author: str = Field(default="system")
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    checksum: str = Field(nullable=False)
    content_path: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
