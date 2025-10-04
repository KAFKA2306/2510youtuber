"""Agent performance review and improvement loop for CrewAI agents.

This module evaluates each agent's task output after a Crew run, stores the
results, and surfaces actionable feedback to future runs so that agents keep
improving automatically.
"""

from __future__ import annotations

import json
import re
import logging
import os
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from app.config.settings import settings
from app.crew.tools.ai_clients import GeminiClient
from app.prompt_cache import get_prompt_manager
from app.logging_config import WorkflowLogger

logger = logging.getLogger(__name__)
workflow_logger = WorkflowLogger(__name__)


class AgentReviewResult(BaseModel):
    """Structured review outcome for a single agent execution."""

    agent_key: str
    agent_role: str
    task_name: str
    score: float = Field(ge=0, le=10)
    verdict: str
    strengths: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    compliance: Dict[str, str] = Field(default_factory=dict)
    raw_feedback: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda dt: dt.isoformat()}}

    def focus_lines(self, max_items: int = 3) -> List[str]:
        """Build short focus lines combining strengths and action items."""
        lines: List[str] = []
        if self.strengths:
            lines.append(f"強みを維持: {self.strengths[0]}")
        for item in self.action_items:
            if len(lines) >= max_items:
                break
            lines.append(f"改善: {item}")
        return lines[:max_items]


class AgentReviewStorage:
    """Persistence layer for agent reviews."""

    def __init__(self, storage_path: str = "data/agent_reviews.json") -> None:
        self.storage_path = storage_path
        self._data: Dict[str, Dict[str, object]] = self._load()

    def _load(self) -> Dict[str, Dict[str, object]]:
        if not os.path.exists(self.storage_path):
            return {}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                if isinstance(data, dict):
                    return data
        except (OSError, ValueError) as exc:
            logger.warning("Failed to load agent review storage: %s", exc)
        return {}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)

    def append(self, result: AgentReviewResult) -> None:
        payload = result.model_dump(mode="json")
        agent_bucket = self._data.setdefault(result.agent_key, {"history": []})
        history: List[dict] = agent_bucket.setdefault("history", [])  # type: ignore[assignment]
        history.append(payload)
        # Keep the history bounded to avoid unbounded file growth.
        if len(history) > 100:
            del history[:-100]

        recent_scores = [entry.get("score", 0) for entry in history[-5:]]
        avg_score = round(sum(recent_scores) / len(recent_scores), 2) if recent_scores else 0.0
        agent_bucket["rolling_average"] = avg_score
        focus = self._collect_focus_from_history(history)
        if focus:
            agent_bucket["latest_focus"] = focus
        agent_bucket["last_verdict"] = result.verdict
        agent_bucket["last_updated"] = result.created_at.isoformat()

    def get_focus_notes(self, agent_key: str, max_items: int = 3) -> Optional[str]:
        agent_bucket = self._data.get(agent_key)
        if not agent_bucket:
            return None
        history: List[dict] = list(agent_bucket.get("history", []))  # type: ignore[assignment]
        focus_lines = self._collect_focus_from_history(history, max_items)

        if len(focus_lines) < max_items:
            self._prepend_strength_focus(history, focus_lines)

        if not focus_lines:
            return None
        return "\n".join(focus_lines[:max_items])

    @staticmethod
    def _collect_focus_from_history(history: List[dict], max_items: int = 3) -> List[str]:
        focus_lines: List[str] = []
        for entry in reversed(history):
            action_items = entry.get("action_items", [])
            if isinstance(action_items, list):
                for item in action_items:
                    text = str(item).strip()
                    if text and text not in focus_lines:
                        focus_lines.append(f"改善: {text}")
                        if len(focus_lines) >= max_items:
                            return focus_lines
        return focus_lines

    @staticmethod
    def _prepend_strength_focus(history: Iterable[dict], focus_lines: List[str]) -> None:
        for entry in reversed(list(history)):
            strengths = entry.get("strengths", [])
            if not isinstance(strengths, list):
                continue
            for strength in strengths:
                text = str(strength).strip()
                if not text:
                    continue
                note = f"強みを維持: {text}"
                if note in focus_lines:
                    continue
                focus_lines.insert(0, note)
                return


class AgentReviewCycle:
    """Runs agent output reviews and feeds results back into future prompts."""

    def __init__(
        self,
        storage: Optional[AgentReviewStorage] = None,
        model: Optional[str] = None,
        temperature: float = 0.35,
    ) -> None:
        self.storage = storage or AgentReviewStorage()
        self.prompt_manager = get_prompt_manager()
        self._agents_config = self.prompt_manager.load("agents.yaml").get("agents", {})
        self._role_to_key: Dict[str, str] = {
            str(cfg.get("role", "")).lower(): key for key, cfg in self._agents_config.items()
        }
        self.enabled = self._is_enabled()
        self._client: Optional[GeminiClient]
        resolved_model = model or settings.gemini_models.get("agent_review")

        if self.enabled:
            self._client = GeminiClient(model=resolved_model, temperature=temperature)
        else:
            self._client = None

    def _is_enabled(self) -> bool:
        if os.getenv("DISABLE_AGENT_REVIEW", "").lower() in {"1", "true", "yes"}:
            return False
        candidate_keys = [
            settings.api_keys.get("gemini"),
            os.getenv("GEMINI_API_KEY"),
        ]
        candidate_keys.extend(os.getenv(f"GEMINI_API_KEY_{i}") for i in range(2, 10))
        return any(filter(None, candidate_keys))

    def prepare_improvement_notes(self) -> Dict[str, str]:
        """Expose latest focus snippets for each agent."""
        notes: Dict[str, str] = {}
        for agent_key in self._agents_config.keys():
            focus = self.storage.get_focus_notes(agent_key)
            if focus:
                notes[agent_key] = focus
        return notes

    def run(self, tasks: Dict[str, "Task"]) -> Dict[str, AgentReviewResult]:
        """Execute post-run reviews for the provided tasks."""
        if not self.enabled:
            logger.debug("Agent review cycle disabled or Gemini key missing; skipping.")
            return {}
        if not self._client:
            return {}

        results: Dict[str, AgentReviewResult] = {}
        for task_name, task in tasks.items():
            agent_key = self._resolve_agent_key(task)
            if not agent_key:
                logger.debug("No agent_key metadata for task %s; skipping review", task_name)
                continue
            if not getattr(task, "output", None):
                logger.debug("Task %s has no output; skipping review", task_name)
                continue
            task_output = getattr(task.output, "raw", None)
            if not task_output:
                logger.debug("Task %s output is empty; skipping review", task_name)
                continue
            agent_config = self._agents_config.get(agent_key, {})
            try:
                review = self._evaluate_single(agent_key, task_name, task, str(task_output), agent_config)
            except Exception as exc:  # pragma: no cover - logged for visibility
                logger.warning("Agent review failed for %s (%s): %s", agent_key, task_name, exc)
                continue
            if review:
                self.storage.append(review)
                results[agent_key] = review
        if results:
            self.storage.save()
        return results

    def _resolve_agent_key(self, task: "Task") -> Optional[str]:
        config_value = None
        if isinstance(getattr(task, "config", None), dict):
            config_value = task.config.get("agent_key")
        if config_value:
            return str(config_value)
        agent_role = str(getattr(task.agent, "role", "")).lower()
        return self._role_to_key.get(agent_role)

    def _evaluate_single(
        self,
        agent_key: str,
        task_name: str,
        task: "Task",
        task_output: str,
        agent_config: Dict[str, object],
    ) -> Optional[AgentReviewResult]:
        if not self._client:
            return None

        # エージェント開始ログ
        workflow_logger.agent_start(agent_key, task_name)

        # Geminiへ評価リクエスト
        prompt = self._build_prompt(agent_key, task_name, task, task_output, agent_config)
        response_text = self._client.generate_structured(prompt)

        # GeminiClientがdictを返す場合とstrを返す場合を吸収
        if isinstance(response_text, dict):
            response = response_text
        else:
            # 出力解析ログ
            workflow_logger.logger.debug(
                f"Parsing output from {agent_key} ({len(response_text)} chars)"
            )
            response = parse_json_from_gemini(str(response_text), agent_key)

        # 正規化
        processed = self._normalize_response(response)

        # エージェント終了ログ
        workflow_logger.agent_end(agent_key, len(response_text))

        return AgentReviewResult(
            agent_key=agent_key,
            agent_role=str(agent_config.get("role", getattr(task.agent, "role", agent_key))),
            task_name=task_name,
            score=processed.get("score", 0.0),
            verdict=processed.get("verdict", ""),
            strengths=processed.get("strengths", []),
            issues=processed.get("issues", []),
            action_items=processed.get("action_items", []),
            compliance=processed.get("compliance", {}),
            raw_feedback=response_text,
        )

    def _build_prompt(
        self,
        agent_key: str,
        task_name: str,
        task: "Task",
        task_output: str,
        agent_config: Dict[str, object],
    ) -> str:
        role = agent_config.get("role", getattr(task.agent, "role", agent_key))
        goal = agent_config.get("goal", "")
        backstory = agent_config.get("backstory", "")
        focus = self.storage.get_focus_notes(agent_key)
        rubrics = self.prompt_manager.load("evaluation_rubrics.yaml").get("evaluation_rubrics", {})
        rubric_lines = []
        for rubric_name, items in rubrics.items():
            readable = rubric_name.replace("_", " ")
            formatted_items = "\n        - ".join(str(item) for item in items)
            rubric_lines.append(
                f"    {readable}:\n        - {formatted_items}" if formatted_items else f"    {readable}: (no entries)"
            )
        rubric_block = "\n".join(rubric_lines)
        focus_block = focus if focus else "(前回の改善フォーカスはありません)"

        description = getattr(task, "description", "")
        expected_output = getattr(task, "expected_output", "")

        prompt_lines = [
            "あなたはCrewAIシステムのメタレビュアーです。各エージェントのタスク出力を評価し、",
            "エージェントが目標に貢献したか、どこを改善すべきかを明確にしてください。",
            "",
            "# Agent Profile",
            f"- Agent Key: {agent_key}",
            f"- Role: {role}",
            f"- Goal: {goal}",
            f"- Backstory: {backstory}",
            "",
            "# Task Metadata",
            f"- Task Name: {task_name}",
            f'- Task Description: """{description}"""',
            f'- Expected Output: """{expected_output}"""',
            "",
            "# Agent Output",
            f'"""{task_output}"""',
            "",
            "# Previous Focus Items",
            focus_block,
            "",
            "# Evaluation Rubrics",
            rubric_block,
            "",
            "# Evaluation Requirements",
            "- Score the usefulness of the agent's output on a 0-10 scale (10 = outstanding impact).",
            "- Identify concrete strengths.",
            "- Identify the most critical issues or gaps.",
            "- Provide 1-3 clear action items that would improve the next iteration.",
            "- Note whether the agent addressed the previous focus items.",
            "",
            "Respond ONLY with valid JSON using the following schema:",
            "{",
            '  "score": float between 0 and 10,',
            '  "verdict": "short headline level summary",',
            '  "strengths": ["bullet"],',
            '  "issues": ["bullet"],',
            '  "action_items": ["bullet"],',
            '  "compliance": {',
            '      "previous_focus_addressed": "yes" | "partial" | "no",',
            '      "notes": "short note"',
            "  }",
            "}",
        ]
        return "\n".join(prompt_lines)

def parse_json_from_gemini(response_text: str, agent_key: str) -> dict:
    """
    Geminiレスポンスから柔軟にパース
    script_writer と japanese_purity_polisher はRAW出力を許可
    """
    # RAW出力を許可するエージェント
    RAW_OUTPUT_AGENTS = ["script_writer", "japanese_purity_polisher"]
    
    # RAW出力許可エージェントの場合、JSONパース失敗を許容
    if agent_key in RAW_OUTPUT_AGENTS:
        # プレーンテキストとして返す
        text = response_text.strip()
        if not text.startswith('{') and not text.startswith('['):
            logger.info(f"{agent_key}: RAW text output detected")
            return {"raw_output": text, "success": True}
    
    # JSON パース試行
    try:
        # コードブロック除去
        cleaned = re.sub(r'```json\s*', '', response_text)
        cleaned = re.sub(r'```', '', cleaned)
        
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        if agent_key in RAW_OUTPUT_AGENTS:
            # RAW出力として許容
            return {"raw_output": response_text, "success": True}
        else:
            # 他のエージェントはエラー
            logger.error(f"Failed to parse JSON from {agent_key}: {e}")
            raise


    @staticmethod
    def _normalize_response(payload: Dict[str, object]) -> Dict[str, object]:
        def _as_list(value: object) -> List[str]:
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            # If value is not a list, and it's not a string, convert it to string before stripping
            if not isinstance(value, str):
                value = str(value)
            if value and value.strip():
                return [value.strip()]
            return []

        result: Dict[str, object] = {}
        result["score"] = float(payload.get("score", 0))
        result["verdict"] = str(payload.get("verdict", "")).strip()
        result["strengths"] = _as_list(payload.get("strengths"))
        result["issues"] = _as_list(payload.get("issues"))
        result["action_items"] = _as_list(payload.get("action_items"))
        compliance = payload.get("compliance")
        if isinstance(compliance, dict):
            normalized = {
                "previous_focus_addressed": str(compliance.get("previous_focus_addressed", "")).strip() or "unknown",
                "notes": str(compliance.get("notes", "")).strip(),
            }
        else:
            normalized = {"previous_focus_addressed": "unknown", "notes": ""}
        result["compliance"] = normalized
        return result


try:  # Optional import for type checking without creating a hard runtime dependency
    from crewai import Task  # pylint: disable=ungrouped-imports
except Exception:  # pragma: no cover - runtime guard if CrewAI is unavailable during typing
    Task = object  # type: ignore
