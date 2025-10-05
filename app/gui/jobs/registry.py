"""Command registry for GUI-triggered jobs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import yaml


@dataclass(frozen=True)
class CommandParameter:
    """Definition for a command parameter exposed in the GUI."""

    name: str
    label: str
    required: bool = False
    default: Optional[str] = None


@dataclass(frozen=True)
class Command:
    """Runnable command definition loaded from YAML."""

    id: str
    name: str
    runner: str
    description: str = ""
    args: List[str] | None = None
    module: Optional[str] = None
    command: List[str] | None = None
    working_directory: Optional[str] = None
    parameters: tuple[CommandParameter, ...] = ()

    def render_args(self, values: Mapping[str, Any]) -> List[str]:
        rendered: List[str] = []
        for arg in self.args or []:
            rendered.append(arg.format(**values))
        return rendered

    def render_command(self, values: Mapping[str, Any]) -> List[str]:
        rendered: List[str] = []
        for token in self.command or []:
            rendered.append(token.format(**values))
        return rendered


class CommandRegistry:
    """In-memory registry of runnable commands."""

    def __init__(self, commands: Iterable[Command]):
        self._commands: Dict[str, Command] = {command.id: command for command in commands}

    def list(self) -> List[Command]:
        return list(self._commands.values())

    def get(self, command_id: str) -> Command:
        try:
            return self._commands[command_id]
        except KeyError as exc:  # pragma: no cover - defensive programming
            raise KeyError(f"Command '{command_id}' is not registered") from exc

    @classmethod
    def from_yaml(cls, path: Path) -> "CommandRegistry":
        if not path.exists():
            raise FileNotFoundError(f"Command definition file not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "commands" not in data:
            raise ValueError("Command file must contain a 'commands' mapping")
        commands: List[Command] = []
        for raw in data.get("commands", []):
            parameters = tuple(
                CommandParameter(
                    name=param.get("name"),
                    label=param.get("label", param.get("name", "")),
                    required=bool(param.get("required", False)),
                    default=param.get("default"),
                )
                for param in raw.get("parameters", [])
            )
            commands.append(
                Command(
                    id=raw["id"],
                    name=raw.get("name", raw["id"]),
                    description=raw.get("description", ""),
                    runner=raw.get("runner", "process"),
                    args=list(raw.get("args", [])) or None,
                    module=raw.get("module"),
                    command=list(raw.get("command", [])) or None,
                    working_directory=raw.get("working_directory"),
                    parameters=parameters,
                )
            )
        return cls(commands)
