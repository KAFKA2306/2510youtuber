"""Command execution strategies for GUI jobs."""

from __future__ import annotations

import asyncio
import os
import selectors
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Protocol

from app.gui.core.settings import GuiSettings
from app.gui.jobs.registry import Command


class LogWriter(Protocol):
    async def write_event(self, payload: Mapping[str, Any]) -> None:  # pragma: no cover - protocol definition
        ...


def _read_streams(
    process: subprocess.Popen[str],
    writer: Callable[[Mapping[str, Any]], None],
) -> None:
    selector = selectors.DefaultSelector()
    streams = {
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
    for name, stream in list(streams.items()):
        if stream is None:
            streams.pop(name)
            continue
        selector.register(stream, selectors.EVENT_READ, name)

    while selector.get_map():
        for key, _ in selector.select():
            stream_name = key.data
            stream = key.fileobj
            line = stream.readline()
            if line:
                writer(
                    {
                        "stream": stream_name,
                        "message": line.rstrip("\n"),
                    }
                )
            else:
                selector.unregister(stream)
                stream.close()


def _spawn_process_blocking(
    command: Iterable[str],
    *,
    cwd: Path | None,
    env: Dict[str, str] | None,
    writer: Callable[[Mapping[str, Any]], None],
) -> int:
    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        bufsize=1,
    )
    try:
        _read_streams(process, writer)
        return process.wait()
    finally:
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()


async def _run_subprocess(
    command: Iterable[str],
    *,
    cwd: Path | None,
    env: Dict[str, str] | None,
    writer: LogWriter,
) -> int:
    loop = asyncio.get_running_loop()

    def emit(payload: Mapping[str, Any]) -> None:
        future = asyncio.run_coroutine_threadsafe(writer.write_event(dict(payload)), loop)
        future.result()

    return await asyncio.to_thread(
        _spawn_process_blocking,
        command,
        cwd=cwd,
        env=env,
        writer=emit,
    )


def _resolve_cwd(command: Command) -> Path | None:
    if not command.working_directory:
        return None
    path = Path(command.working_directory)
    return path if path.is_absolute() else Path.cwd() / path


async def run_python_module(
    *,
    command: Command,
    params: Mapping[str, str],
    settings: GuiSettings,
    writer: LogWriter,
) -> int:
    module = command.module
    if not module:
        raise ValueError("Python module runner requires a 'module' field")
    args = command.render_args(params)
    if settings.logging.verbose and "--verbose" not in args:
        args.append("--verbose")
    executable = sys.executable
    cmd = [executable, "-m", module, *args]
    return await _run_subprocess(cmd, cwd=_resolve_cwd(command), env=os.environ.copy(), writer=writer)


async def run_process(
    *,
    command: Command,
    params: Mapping[str, str],
    settings: GuiSettings,
    writer: LogWriter,
) -> int:
    rendered = command.render_command(params)
    if not rendered:
        raise ValueError("Process runner requires a 'command' list")
    if settings.logging.verbose and "--verbose" not in rendered:
        rendered = [*rendered, "--verbose"]
    env = os.environ.copy()
    return await _run_subprocess(rendered, cwd=_resolve_cwd(command), env=env, writer=writer)


RUNNERS: Dict[str, callable] = {
    "python_module": run_python_module,
    "process": run_process,
}


async def execute_command(*, command: Command, params: Mapping[str, str], settings: GuiSettings, writer) -> int:
    runner = RUNNERS.get(command.runner)
    if not runner:
        raise ValueError(f"Unknown runner '{command.runner}'")
    return await runner(command=command, params=params, settings=settings, writer=writer)
