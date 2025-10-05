from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.gui.prompts.repository import PromptRepository


@pytest.fixture()
def repository(tmp_path: Path) -> PromptRepository:
    db_path = tmp_path / "prompts.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
    SQLModel.metadata.create_all(engine)

    def session_factory() -> Session:
        return Session(engine)

    base_path = tmp_path / "store"
    return PromptRepository(session_factory=session_factory, base_path=base_path)


def test_save_and_load_prompt(repository: PromptRepository) -> None:
    version = repository.save_version(
        prompt_id="script",
        content="title: Hello",
        author="tester",
        message="initial",
        tags=["finance", "daily"],
        name="Script Prompt",
        description="Main script prompt",
    )

    prompt = repository.get_prompt("script")
    assert prompt.latest_version == 1
    assert prompt.name == "Script Prompt"
    assert prompt.description == "Main script prompt"
    assert sorted(prompt.tags) == ["daily", "finance"]

    loaded = repository.load_content(version)
    assert "title: Hello" in loaded

    second = repository.save_version(
        prompt_id="script",
        content="title: Update",
        author="tester",
        message="update",
        tags=["finance", "update"],
    )
    assert second.version == 2

    prompt = repository.get_prompt("script")
    assert prompt.latest_version == 2
    assert sorted(prompt.tags) == ["daily", "finance", "update"]

    versions = repository.list_versions("script")
    assert [item.version for item in versions] == [2, 1]

    first_version = repository.get_version("script", 1)
    assert repository.load_content(first_version).startswith("title: Hello")


def test_missing_prompt_raises(repository: PromptRepository) -> None:
    with pytest.raises(KeyError):
        repository.get_prompt("unknown")

    with pytest.raises(KeyError):
        repository.get_version("missing", 1)


def test_load_multiple(repository: PromptRepository) -> None:
    repository.save_version(
        prompt_id="one",
        content="a: 1",
        author="tester",
        message="init",
    )
    repository.save_version(
        prompt_id="two",
        content="b: 2",
        author="tester",
        message="init",
    )

    payload = repository.load_multiple(["one", "two", "missing"])
    assert payload["one"].startswith("a: 1")
    assert payload["two"].startswith("b: 2")
    assert "missing" not in payload
