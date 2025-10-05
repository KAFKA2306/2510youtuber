"""Continuous improvement loop for video quality tweaks.

Runs verification, targeted tests, and optional workflow executions in cycles
so you can iterate on motion/background/subtitle changes without manual orchestration.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List

DEFAULT_TEST_COMMANDS: List[List[str]] = [
    ["pytest", "tests/unit/test_video_generator_motion.py", "-q"],
]

DEFAULT_VERIFY_COMMANDS: List[List[str]] = [
    ["uv", "run", "python", "-m", "app.core.verify"],
]

WORKFLOW_COMMAND = ["uv", "run", "python3", "-m", "app.main", "daily"]


@dataclass
class StepResult:
    name: str
    command: List[str]
    success: bool
    stderr: str
    stdout: str
    duration: float


def run_command(command: Iterable[str], name: str) -> StepResult:
    start = time.perf_counter()
    process = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    duration = time.perf_counter() - start
    return StepResult(
        name=name,
        command=list(command),
        success=process.returncode == 0,
        stdout=process.stdout.strip(),
        stderr=process.stderr.strip(),
        duration=duration,
    )


def format_result(result: StepResult) -> str:
    status = "✅" if result.success else "❌"
    header = f"{status} {result.name} ({result.duration:.2f}s)"
    details = []
    if result.stdout:
        details.append(result.stdout)
    if result.stderr:
        details.append(result.stderr)
    body = "\n".join(details)
    if body:
        body = textwrap.indent(body, "    ")
        return f"{header}\n{body}"
    return header


def continuous_loop(iterations: int, run_workflow: bool, sleep_seconds: float) -> int:
    overall_exit = 0
    for current in range(1, iterations + 1):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n=== Iteration {current}/{iterations} :: {timestamp} ===")

        steps: List[StepResult] = []

        for command in DEFAULT_VERIFY_COMMANDS:
            steps.append(run_command(command, name="verify_config"))

        for command in DEFAULT_TEST_COMMANDS:
            steps.append(run_command(command, name="unit_tests"))

        if run_workflow:
            steps.append(run_command(WORKFLOW_COMMAND, name="workflow_run"))

        for result in steps:
            print(format_result(result))
            if not result.success:
                overall_exit = 1

        if current < iterations and sleep_seconds:
            time.sleep(sleep_seconds)

    return overall_exit


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run continuous verification/test loops for video improvements.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of improvement loops to run (default: 1).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep between iterations (default: 0).",
    )
    parser.add_argument(
        "--run-workflow",
        action="store_true",
        help="Execute the full daily workflow each iteration (slower).",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return continuous_loop(args.iterations, args.run_workflow, args.sleep)


if __name__ == "__main__":
    raise SystemExit(main())
