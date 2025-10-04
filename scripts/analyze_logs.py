"""ログファイルを解析して統計情報を表示"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _load_metadata_from_structured(structured_path: Path) -> Dict[str, object]:
    metadata_file = structured_path.with_name("metadata.json")
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _discover_latest_structured(log_dir: Path) -> Optional[Path]:
    runs_dir = log_dir / "runs"
    if not runs_dir.exists():
        return None
    candidates = sorted(runs_dir.glob("*/events.jsonl"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def _discover_latest_text(log_dir: Path) -> Optional[Path]:
    runs_dir = log_dir / "runs"
    candidates: List[Path] = []
    if runs_dir.exists():
        candidates.extend(runs_dir.glob("*/workflow.log"))
    candidates.extend(log_dir.glob("workflow_*.log"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates[-1]


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


def print_summary(stats: Dict[str, object]) -> None:
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


if __name__ == "__main__":
    target: Optional[Path] = None
    prefer_structured = True

    if len(sys.argv) > 1:
        target_input = Path(sys.argv[1])
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

    print_summary(summary)
