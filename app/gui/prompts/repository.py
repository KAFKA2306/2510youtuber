"""Prompt repository backed by SQLite metadata and YAML snapshots."""
from __future__ import annotations
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence
from sqlmodel import Session, SQLModel, select
from app.gui.prompts.models import Prompt, PromptVersion
class PromptRepository:
    """Manages prompt metadata and on-disk revisions."""
    def __init__(self, session_factory: Callable[[], Session], base_path: Path) -> None:
        self._session_factory = session_factory
        self._base_path = base_path
        self._live_dir = base_path / "live"
        self._history_dir = base_path / "history"
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._live_dir.mkdir(parents=True, exist_ok=True)
        self._history_dir.mkdir(parents=True, exist_ok=True)
    @contextmanager
    def _session(self) -> Iterator[Session]:
        with self._session_factory() as session:
            yield session
    def initialize(self) -> None:
        """Ensure database tables exist for prompt metadata."""
        engine = None
        with self._session_factory() as session:
            engine = session.get_bind()
        if engine is None:
            raise RuntimeError("Prompt repository requires a bound engine")
        SQLModel.metadata.create_all(engine)
    def list_prompts(self) -> list[Prompt]:
        with self._session() as session:
            statement = select(Prompt).order_by(Prompt.updated_at.desc())
            return list(session.exec(statement))
    def get_prompt(self, prompt_id: str) -> Prompt:
        with self._session() as session:
            prompt = session.get(Prompt, prompt_id)
            if prompt is None:
                raise KeyError(f"Prompt '{prompt_id}' not found")
            return prompt
    def list_versions(self, prompt_id: str) -> list[PromptVersion]:
        with self._session() as session:
            statement = (
                select(PromptVersion)
                .where(PromptVersion.prompt_id == prompt_id)
                .order_by(PromptVersion.version.desc())
            )
            return list(session.exec(statement))
    def get_version(self, prompt_id: str, version: int) -> PromptVersion:
        with self._session() as session:
            statement = (
                select(PromptVersion)
                .where(
                    (PromptVersion.prompt_id == prompt_id)
                    & (PromptVersion.version == version)
                )
                .limit(1)
            )
            result = session.exec(statement).first()
            if result is None:
                raise KeyError(f"Prompt '{prompt_id}' version '{version}' not found")
            return result
    def save_version(
        self,
        prompt_id: str,
        content: str,
        *,
        author: str,
        message: str,
        tags: Sequence[str] | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> PromptVersion:
        tags_list = sorted({tag.strip() for tag in (tags or []) if tag.strip()})
        timestamp = datetime.now(timezone.utc)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._session() as session:
            prompt = session.get(Prompt, prompt_id)
            if prompt is None:
                prompt = Prompt(
                    id=prompt_id,
                    name=name or prompt_id,
                    description=description,
                    tags=tags_list,
                    latest_version=0,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                session.add(prompt)
                session.flush()
            else:
                if name:
                    prompt.name = name
                if description is not None:
                    prompt.description = description
                prompt_tags = set(prompt.tags or [])
                prompt_tags.update(tags_list)
                prompt.tags = sorted(prompt_tags)
            version_number = (prompt.latest_version or 0) + 1
            history_relative = Path("history") / prompt_id / f"{version_number:04d}.yml"
            self._write_files(prompt_id, version_number, content)
            prompt.latest_version = version_number
            prompt.updated_at = timestamp
            version = PromptVersion(
                prompt_id=prompt_id,
                version=version_number,
                message=message,
                author=author,
                tags=tags_list,
                checksum=checksum,
                content_path=str(history_relative),
                created_at=timestamp,
            )
            session.add(version)
            session.commit()
            session.refresh(version)
            session.refresh(prompt)
            return version
    def load_content(self, version: PromptVersion) -> str:
        path = self._resolve_path(version.content_path)
        if not path.exists():
            raise FileNotFoundError(f"Prompt content missing at {path}")
        return path.read_text(encoding="utf-8")
    def latest(self, prompt_id: str) -> tuple[PromptVersion | None, str | None]:
        versions = self.list_versions(prompt_id)
        if not versions:
            return None, None
        latest_version = versions[0]
        return latest_version, self.load_content(latest_version)
    def _write_files(self, prompt_id: str, version: int, content: str) -> None:
        history_dir = self._history_dir / prompt_id
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / f"{version:04d}.yml"
        history_file.write_text(content, encoding="utf-8")
        live_file = self._live_dir / f"{prompt_id}.yml"
        live_file.write_text(content, encoding="utf-8")
    def _resolve_path(self, relative: str) -> Path:
        return self._base_path / relative
    def load_multiple(self, prompt_ids: Iterable[str]) -> dict[str, str]:
        """Load the current content for multiple prompts."""
        contents: dict[str, str] = {}
        for prompt_id in prompt_ids:
            try:
                version, content = self.latest(prompt_id)
            except KeyError:
                version = None
                content = None
            if version is not None and content is not None:
                contents[prompt_id] = content
        return contents
