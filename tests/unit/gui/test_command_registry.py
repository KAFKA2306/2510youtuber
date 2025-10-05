from __future__ import annotations

from pathlib import Path

from app.gui.jobs.registry import CommandRegistry


def test_registry_loads_commands(tmp_path: Path) -> None:
    config = tmp_path / "commands.yml"
    config.write_text(
        """
commands:
  - id: demo
    name: Demo
    runner: process
    command:
      - echo
      - hello
""".strip(),
        encoding="utf-8",
    )
    registry = CommandRegistry.from_yaml(config)
    command = registry.get("demo")
    assert command.command == ["echo", "hello"]
    assert command.runner == "process"
