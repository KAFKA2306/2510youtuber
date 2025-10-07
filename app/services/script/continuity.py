"""Continuity context utilities for script generation prompts."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class FeedbackSummary:
    """Parsed feedback information for a single video."""

    video_id: Optional[str]
    analytics: Dict[str, Any]
    positive_comments: List[str]
    negative_comments: List[str]

    @property
    def retention_rate(self) -> Optional[float]:
        value = self.analytics.get("retention_rate")
        return float(value) if value is not None else None

    @property
    def like_ratio(self) -> Optional[float]:
        likes = self.analytics.get("likes") or 0
        views = self.analytics.get("views") or 0
        if views:
            return likes / views
        return None


@dataclass
class MetadataSummary:
    """Parsed metadata information from CSV log."""

    title: Optional[str]
    description: Optional[str]
    news_topics: Optional[str]

    def short_description(self, limit: int = 50) -> Optional[str]:
        if not self.description:
            return None
        text = _canonicalize_text(self.description)
        return _truncate(text, limit)


@dataclass
class AIReviewSummary:
    """Structured summary derived from the latest AI video review."""

    summary: Optional[str]
    positive_highlights: List[str]
    improvement_suggestions: List[str]
    retention_risks: List[str]
    next_video_actions: List[str]

    def headline(self) -> Optional[str]:
        return _truncate(_canonicalize_text(self.summary), 80) if self.summary else None

    def top_improvements(self, limit: int = 2) -> List[str]:
        return [_truncate_negative(item) for item in self.improvement_suggestions[:limit]]

    def top_actions(self, limit: int = 2) -> List[str]:
        return [_truncate(_canonicalize_text(item), 35) for item in self.next_video_actions[:limit]]

    def top_risks(self, limit: int = 1) -> List[str]:
        return [_truncate_negative(item) for item in self.retention_risks[:limit]]


class ContinuityContextBuilder:
    """Builds continuity guidance derived from previous video results."""

    def __init__(
        self,
        metadata_csv_path: Optional[Path] = None,
        feedback_json_path: Optional[Path] = None,
    ) -> None:
        project_root = Path(__file__).resolve().parents[3]
        data_dir = project_root / "data"

        self.metadata_csv_path = Path(metadata_csv_path or data_dir / "metadata_history.csv")
        self.feedback_json_path = Path(feedback_json_path or data_dir / "video_feedback.yaml")

    def build_prompt_snippet(self) -> str:
        metadata = self._load_latest_metadata()
        feedback_store = self._load_feedback_store()
        feedback = self._load_latest_feedback(feedback_store)
        ai_review = self._load_latest_ai_review(feedback_store)

        lines: List[str] = []

        if metadata:
            snippet = metadata.short_description()
            title = metadata.title or "前回の動画"
            if snippet:
                lines.append(f"前回動画:「{title}」- {snippet}")
            else:
                lines.append(f"前回動画:「{title}」の流れを一言振り返る。")

        if feedback:
            metrics = []
            if feedback.retention_rate is not None:
                metrics.append(f"保持率{feedback.retention_rate:.0f}%")
            like_ratio = feedback.like_ratio
            if like_ratio is not None:
                metrics.append(f"高評価率{like_ratio * 100:.1f}%")

            if metrics:
                lines.append("視聴データ: " + "、".join(metrics) + "。")

            positive = feedback.positive_comments[0] if feedback.positive_comments else None
            negative = feedback.negative_comments[0] if feedback.negative_comments else None

            if positive:
                lines.append(f"好評コメント: 「{_truncate_positive(positive)}」。")
            if negative:
                lines.append(f"改善ヒント: 「{_truncate_negative(negative)}」。")

        if ai_review:
            headline = ai_review.headline()
            if headline:
                lines.append(f"AIレビュー要約: {headline}。")

            improvements = ai_review.top_improvements()
            if improvements:
                lines.append("改善アクション候補: " + " / ".join(improvements))

            risks = ai_review.top_risks()
            if risks:
                lines.append("離脱リスク警告: " + " / ".join(risks))

            next_actions = ai_review.top_actions()
            if next_actions:
                lines.append("次の動画で試すべき施策: " + " / ".join(next_actions))

        if not lines:
            return ""

        lines.append(
            "冒頭8秒で前回の手応えを軽く触れてから新しいテーマへ繋げ、改善アイデアを実装→検証するループを明示して連続視聴を促してください。"
        )
        return "\n".join(lines)

    def _load_latest_metadata(self) -> Optional[MetadataSummary]:
        if not self.metadata_csv_path.exists():
            return None

        try:
            with self.metadata_csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                last_row: Optional[Dict[str, Any]] = None
                for row in reader:
                    last_row = row

            if not last_row:
                return None

            return MetadataSummary(
                title=last_row.get("title"),
                description=last_row.get("description"),
                news_topics=last_row.get("news_topics"),
            )
        except Exception:
            return None

    def _load_feedback_store(self) -> Optional[Dict[str, Any]]:
        if not self.feedback_json_path.exists():
            return None

        try:
            with self.feedback_json_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and data:
                return data
        except Exception:
            return None
        return None

    def _select_latest_feedback_entry(self, data: Dict[str, Any]) -> Optional[tuple[str, Dict[str, Any]]]:
        try:
            video_id, payload = max(
                data.items(),
                key=lambda item: _parse_timestamp(item[1].get("updated_at") or item[1].get("created_at")),
            )
            if isinstance(payload, dict):
                return video_id, payload
        except Exception:
            return None
        return None

    def _load_latest_feedback(self, data: Optional[Dict[str, Any]]) -> Optional[FeedbackSummary]:
        if not data:
            return None

        selected = self._select_latest_feedback_entry(data)
        if not selected:
            return None

        video_id, payload = selected

        analytics = payload.get("analytics", {}) if isinstance(payload, dict) else {}
        manual_feedback = payload.get("manual_feedback", []) if isinstance(payload, dict) else []

        positive_comments: List[str] = []
        negative_comments: List[str] = []
        for entry in manual_feedback:
            if not isinstance(entry, dict):
                continue
            comment = entry.get("comment")
            if not comment:
                continue
            if entry.get("positive"):
                positive_comments.append(comment)
            else:
                negative_comments.append(comment)

        return FeedbackSummary(
            video_id=video_id,
            analytics=analytics,
            positive_comments=positive_comments,
            negative_comments=negative_comments,
        )

    def _load_latest_ai_review(self, data: Optional[Dict[str, Any]]) -> Optional[AIReviewSummary]:
        if not data:
            return None

        selected = self._select_latest_feedback_entry(data)
        if not selected:
            return None

        _, payload = selected

        ai_review = payload.get("ai_review")
        if not isinstance(ai_review, dict):
            return None

        return AIReviewSummary(
            summary=ai_review.get("feedback", {}).get("summary")
            if isinstance(ai_review.get("feedback"), dict)
            else ai_review.get("summary"),
            positive_highlights=_ensure_list(_extract_feedback_field(ai_review, "positive_highlights")),
            improvement_suggestions=_ensure_list(_extract_feedback_field(ai_review, "improvement_suggestions")),
            retention_risks=_ensure_list(_extract_feedback_field(ai_review, "retention_risks")),
            next_video_actions=_ensure_list(_extract_feedback_field(ai_review, "next_video_actions")),
        )


def get_continuity_prompt_snippet() -> str:
    """Return a short snippet describing previous results for prompt continuity."""
    builder = ContinuityContextBuilder()
    return builder.build_prompt_snippet()


def _ensure_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if value is None:
        return []
    return [str(value)]


def _extract_feedback_field(ai_review: Dict[str, Any], field: str) -> Any:
    feedback_block = ai_review.get("feedback")
    if isinstance(feedback_block, dict) and field in feedback_block:
        return feedback_block[field]
    return ai_review.get(field)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _canonicalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text)
    return collapsed.strip()


def _parse_timestamp(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


def _truncate_positive(comment: str) -> str:
    return _truncate(_canonicalize_text(comment), 40)


def _truncate_negative(comment: str) -> str:
    return _truncate(_canonicalize_text(comment), 40)
