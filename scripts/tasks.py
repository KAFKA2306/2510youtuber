#!/usr/bin/env python3
"""Unified CLI entry point for analytics, log analysis, improvement loops, and video reviews."""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import textwrap
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING

# Ensure the application package is importable when running as a script
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:  # pragma: no cover
    from app.analytics import FeedbackAnalyzer


@dataclass
class StepResult:
    """Result for a single subprocess execution."""

    name: str
    command: List[str]
    success: bool
    stderr: str
    stdout: str
    duration: float


DEFAULT_TEST_COMMANDS: List[List[str]] = [
    ["pytest", "tests/unit/test_video_generator_motion.py", "-q"],
]

DEFAULT_VERIFY_COMMANDS: List[List[str]] = [
    ["uv", "run", "python", "-m", "app.verify"],
]

WORKFLOW_COMMAND = ["uv", "run", "python3", "-m", "app.main", "daily"]


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def handle_analytics(args: argparse.Namespace) -> int:
    """Generate analytics reports based on the requested mode."""

    from app.analytics import FeedbackAnalyzer

    analyzer: "FeedbackAnalyzer" = FeedbackAnalyzer()
    limit = max(1, args.limit)

    if args.hooks:
        print("🎯 Hook Strategy Performance\n")
        hook_perf = analyzer.analyze_hook_performance(limit=limit)
        for hook, stats in hook_perf.items():
            print(f"{hook}:")
            print(f"  動画数: {stats['count']}")
            print(f"  平均WOW: {stats['avg_wow']:.2f}")
            print(f"  平均リテンション: {stats['avg_retention']:.1f}%")
            print()
        return 0

    if args.topics:
        print("📚 Topic Distribution\n")
        topics = analyzer.analyze_topic_distribution(limit=limit)
        for topic, count in topics.items():
            print(f"  {topic}: {count} 本")
        print()
        return 0

    # Default: weekly report
    print(analyzer.generate_weekly_report(limit=limit))
    return 0


# ---------------------------------------------------------------------------
# Log analysis helpers
# ---------------------------------------------------------------------------

def _load_metadata_from_structured(structured_path: Path) -> Dict[str, object]:
    metadata_file = structured_path.with_name("metadata.json")
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _run_timestamp(run_dir: Path) -> float:
    metadata_file = run_dir / "metadata.json"
    timestamps: List[datetime] = []
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metadata = {}
        for key in ("updated_at", "created_at"):
            parsed = _parse_iso_timestamp(metadata.get(key))
            if parsed:
                timestamps.append(parsed)

    if timestamps:
        return max(timestamps).timestamp()

    structured = run_dir / "events.jsonl"
    if structured.exists():
        return structured.stat().st_mtime

    text_log = run_dir / "workflow.log"
    if text_log.exists():
        return text_log.stat().st_mtime

    return run_dir.stat().st_mtime


def _discover_latest_structured(log_dir: Path) -> Optional[Path]:
    runs_dir = log_dir / "runs"
    if not runs_dir.exists():
        return None

    run_dirs = [path for path in runs_dir.iterdir() if path.is_dir()]
    if not run_dirs:
        return None

    run_dirs.sort(key=_run_timestamp)
    for run_dir in reversed(run_dirs):
        candidate = run_dir / "events.jsonl"
        if candidate.exists():
            return candidate
    return None


def _discover_latest_text(log_dir: Path) -> Optional[Path]:
    runs_dir = log_dir / "runs"
    candidates: List[Tuple[float, Path]] = []

    if runs_dir.exists():
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            text_log = run_dir / "workflow.log"
            if text_log.exists():
                candidates.append((_run_timestamp(run_dir), text_log))

    for text_log in log_dir.glob("workflow_*.log"):
        candidates.append((text_log.stat().st_mtime, text_log))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def analyze_structured_log(structured_path: Path) -> Dict[str, object]:
    stats = {
        "steps": [],
        "agents": defaultdict(lambda: {"success": 0, "failed": 0}),
        "api_calls": defaultdict(int),
        "errors": [],
        "metadata": _load_metadata_from_structured(structured_path),
    }

    with structured_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            level = event.get("level")
            if level == "ERROR":
                stats["errors"].append(event.get("message"))

            event_type = event.get("event")
            if event_type == "step_end":
                stats["steps"].append(
                    {
                        "name": event.get("step"),
                        "status": (event.get("status") or "").upper(),
                        "duration": event.get("duration"),
                    }
                )
            elif event_type == "agent_end":
                agent = event.get("agent")
                status = (event.get("status") or "").upper()
                if agent:
                    if status == "SUCCESS":
                        stats["agents"][agent]["success"] += 1
                    else:
                        stats["agents"][agent]["failed"] += 1
            elif event_type == "api_call":
                api_name = event.get("api")
                if api_name:
                    stats["api_calls"][api_name] += 1

    return stats


def analyze_text_log(log_file: Path) -> Dict[str, object]:
    stats = {
        "steps": [],
        "agents": defaultdict(lambda: {"success": 0, "failed": 0}),
        "api_calls": defaultdict(int),
        "errors": [],
        "metadata": {},
    }

    with log_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            if "▶ STEP:" in line:
                step = line.split("STEP:")[1].strip()
                stats["steps"].append({"name": step, "status": "INFO", "duration": None})

            if "🤖 Agent" in line:
                agent_name = line.split("[")[1].split("]")[0]
                if "✅" in line:
                    stats["agents"][agent_name]["success"] += 1
                elif "❌" in line:
                    stats["agents"][agent_name]["failed"] += 1

            if "🌐 API" in line:
                api_part = line.split("API [")[-1]
                api_name = api_part.split("]")[0]
                stats["api_calls"][api_name] += 1

            if "ERROR" in line:
                stats["errors"].append(line.strip())

    return stats


def print_log_summary(stats: Dict[str, object]) -> None:
    metadata = stats.get("metadata") or {}
    steps: Iterable[Dict[str, object]] = stats.get("steps", [])  # type: ignore[assignment]

    print("\n" + "=" * 60)
    print("📊 LOG ANALYSIS SUMMARY")
    print("=" * 60)

    if metadata:
        session_id = metadata.get("session_id")
        workflow_run_id = metadata.get("workflow_run_id")
        status = metadata.get("status")
        created_at = metadata.get("created_at")
        updated_at = metadata.get("updated_at")
        print("Session:", session_id or "(unknown)")
        if workflow_run_id:
            print("Workflow Run:", workflow_run_id)
        if status:
            print("Status:", status)
        if created_at:
            print("Started:", created_at)
        if updated_at:
            print("Updated:", updated_at)

    print(f"\n✅ Steps recorded: {len(list(steps))}")
    for step in steps:
        status = step.get("status") or "INFO"
        icon = "✅" if status == "SUCCESS" else ("❌" if status == "FAILED" else "•")
        duration = step.get("duration")
        duration_text = f" - {duration:.2f}s" if isinstance(duration, (int, float)) else ""
        print(f"  {icon} {step.get('name')} {duration_text}")

    agents = stats.get("agents", {})  # type: ignore[assignment]
    print("\n🤖 Agents:")
    for agent, counts in agents.items():
        success = counts.get("success", 0)
        failed = counts.get("failed", 0)
        total = success + failed
        print(f"  - {agent}: {success}/{total} succeeded")

    api_calls = stats.get("api_calls", {})  # type: ignore[assignment]
    total_calls = sum(api_calls.values())
    print(f"\n🌐 API Calls: {total_calls} total")
    for api, count in api_calls.items():
        print(f"  - {api}: {count} calls")

    errors = stats.get("errors", [])  # type: ignore[assignment]
    print(f"\n❌ Errors: {len(errors)}")
    for error in errors[:5]:
        print(f"  - {str(error)[:80]}...")


def resolve_default_log() -> Tuple[Optional[Path], bool]:
    log_dir = Path("logs")
    structured = _discover_latest_structured(log_dir)
    if structured:
        return structured, True
    text_log = _discover_latest_text(log_dir)
    if text_log:
        return text_log, False
    return None, False


def handle_logs(args: argparse.Namespace) -> int:
    prefer_structured = True
    target: Optional[Path] = None

    if args.target:
        target_input = Path(args.target)
        if target_input.is_dir():
            metadata_file = target_input / "metadata.json"
            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                    structured_path = Path(metadata.get("paths", {}).get("structured", ""))
                    if structured_path.exists():
                        target = structured_path
                    else:
                        target = target_input / "workflow.log"
                        prefer_structured = False
                except json.JSONDecodeError:
                    target = target_input / "workflow.log"
                    prefer_structured = False
            else:
                target = target_input
                prefer_structured = target_input.suffix == ".jsonl"
        else:
            target = target_input
            prefer_structured = target.suffix == ".jsonl"
    else:
        target, prefer_structured = resolve_default_log()

    if not target or not target.exists():
        raise SystemExit("No log files found under logs/.")

    if prefer_structured and target.suffix == ".jsonl":
        summary = analyze_structured_log(target)
    else:
        summary = analyze_text_log(target)

    print_log_summary(summary)
    return 0


# ---------------------------------------------------------------------------
# Continuous improvement helpers
# ---------------------------------------------------------------------------

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


def handle_improvement(args: argparse.Namespace) -> int:
    overall_exit = 0
    for current in range(1, args.iterations + 1):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n=== Iteration {current}/{args.iterations} :: {timestamp} ===")

        steps: List[StepResult] = []

        for command in DEFAULT_VERIFY_COMMANDS:
            steps.append(run_command(command, name="verify_config"))

        for command in DEFAULT_TEST_COMMANDS:
            steps.append(run_command(command, name="unit_tests"))

        if args.run_workflow:
            steps.append(run_command(WORKFLOW_COMMAND, name="workflow_run"))

        for result in steps:
            print(format_result(result))
            if not result.success:
                overall_exit = 1

        if current < args.iterations and args.sleep:
            time.sleep(args.sleep)

    return overall_exit


# ---------------------------------------------------------------------------
# Video review helpers
# ---------------------------------------------------------------------------

def handle_video_review(args: argparse.Namespace) -> int:
    from app.api_rotation import initialize_api_infrastructure
    from app.services.video_review import get_video_review_service

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logger = logging.getLogger(__name__)

    # Initialize API infrastructure (loads API keys)
    try:
        initialize_api_infrastructure()
        logger.info("API infrastructure initialized")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to initialize API infrastructure: %s", exc)

    if len(args.videos) > 1 and args.video_id:
        raise SystemExit("--video-id は単一動画のときのみ指定できます")

    base_metadata = {}
    if args.metadata_json:
        metadata_path = Path(args.metadata_json)
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {args.metadata_json}")
        with metadata_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("Metadata JSON must be an object")
            base_metadata.update(data)

    if args.title:
        base_metadata["title"] = args.title
    if args.duration:
        base_metadata["duration"] = args.duration

    service = get_video_review_service()

    for video in args.videos:
        video_path = Path(video)
        if not video_path.exists():
            logger.error("Video not found: %s", video)
            continue

        video_id = args.video_id if len(args.videos) == 1 else None

        logger.info("Reviewing video: %s", video_path)
        result = service.review_video(
            video_path=str(video_path),
            video_id=video_id,
            metadata=base_metadata or None,
            force_capture=args.force,
        )

        feedback = result.feedback
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            continue

        print("\n" + "=" * 60)
        heading = f"レビュー結果: {video_path.name}"
        print(heading)
        print("=" * len(heading))
        if feedback:
            print(f"要約: {feedback.summary}")
            if feedback.positive_highlights:
                print("\n◎ 良かった点")
                for item in feedback.positive_highlights:
                    print(f"  - {item}")
            if feedback.improvement_suggestions:
                print("\n△ 改善提案")
                for item in feedback.improvement_suggestions:
                    print(f"  - {item}")
            if feedback.retention_risks:
                print("\n⚠ 離脱リスク")
                for item in feedback.retention_risks:
                    print(f"  - {item}")
            if feedback.next_video_actions:
                print("\n▶ 次の動画で試すこと")
                for item in feedback.next_video_actions:
                    print(f"  - {item}")
        else:
            print("フィードバックが取得できませんでした")

        if result.screenshots:
            screenshot_dir = Path(result.screenshots[0].path).parent
            print(f"\nスクリーンショット保存先: {screenshot_dir}")

    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run analytics, log analysis, improvement loops, or video reviews from one CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analytics = subparsers.add_parser("analytics", help="Generate analytics reports")
    analytics.add_argument("--hooks", action="store_true", help="Show hook performance")
    analytics.add_argument("--topics", action="store_true", help="Show topic distribution")
    analytics.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of executions to analyze (default: 50).",
    )
    analytics.set_defaults(func=handle_analytics)

    logs = subparsers.add_parser("logs", help="Analyze workflow logs")
    logs.add_argument(
        "target",
        nargs="?",
        help="File or directory to analyze. Defaults to the latest run under logs/.",
    )
    logs.set_defaults(func=handle_logs)

    improvement = subparsers.add_parser(
        "improve", help="Run continuous verification/test loops for video improvements"
    )
    improvement.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of improvement loops to run (default: 1).",
    )
    improvement.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep between iterations (default: 0).",
    )
    improvement.add_argument(
        "--run-workflow",
        action="store_true",
        help="Execute the full daily workflow each iteration (slower).",
    )
    improvement.set_defaults(func=handle_improvement)

    review = subparsers.add_parser("review", help="Execute the video review workflow")
    review.add_argument("videos", nargs="+", help="レビューする動画ファイルパス")
    review.add_argument("--video-id", help="YouTube動画IDなどの識別子（単一動画時のみ）")
    review.add_argument("--metadata-json", help="タイトル等を含むJSONパス")
    review.add_argument("--title", help="動画タイトル（オプション）")
    review.add_argument("--duration", help="動画尺のメモ（例: 8分12秒）")
    review.add_argument("--force", action="store_true", help="既存スクリーンショットを再生成する")
    review.add_argument("--json", action="store_true", help="結果をJSONで出力する")
    review.set_defaults(func=handle_video_review)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func")
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
