"""Data aggregation helpers for the dashboard endpoints."""

from __future__ import annotations

import csv
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from pydantic import ValidationError

from app.models.workflow import WorkflowResult

from .models import (
    ArtifactKind,
    DashboardMetrics,
    DashboardSummary,
    ExternalLink,
    MediaAsset,
    RunArtifacts,
    RunMetrics,
)

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".yaml", ".yml", ".srt", ".vtt"}


@dataclass(slots=True)
class MetadataSnapshot:
    """Subset of metadata history values used by the dashboard."""

    run_id: str
    timestamp: Optional[datetime]
    mode: Optional[str]
    title: Optional[str]
    description: Optional[str]
    video_url: Optional[str]
    view_count: Optional[int]
    like_count: Optional[int]
    comment_count: Optional[int]
    ctr: Optional[float]
    avg_view_duration: Optional[float]


class DashboardService:
    """Collects artefact and QA metric information for the GUI."""

    def __init__(self, execution_log_path: Path, metadata_history_path: Path, *, history_limit: int = 200) -> None:
        self._execution_log_path = execution_log_path
        self._metadata_history_path = metadata_history_path
        self._history_limit = history_limit

    def get_artifacts(self, *, limit: int = 10) -> List[RunArtifacts]:
        """Return artefact bundles for the most recent workflow runs."""

        results = self._load_results(limit)
        metadata_index = {entry.run_id: entry for entry in self._load_metadata(limit=self._history_limit)}
        artefacts: List[RunArtifacts] = []
        for result in results:
            artefacts.append(self._build_run_artifacts(result, metadata_index.get(result.run_id)))
        return artefacts

    def get_metrics(self, *, limit: int = 20) -> DashboardMetrics:
        """Return QA metrics for recent runs along with aggregate summary."""

        results = self._load_results(limit)
        metadata_index = {entry.run_id: entry for entry in self._load_metadata(limit=self._history_limit)}
        runs: List[RunMetrics] = [self._build_run_metrics(result, metadata_index.get(result.run_id)) for result in results]
        summary = self._compute_summary(runs)
        return DashboardMetrics(summary=summary, runs=runs)

    def _load_results(self, limit: int) -> List[WorkflowResult]:
        if not self._execution_log_path.exists():
            return []
        buffer: deque[str] = deque(maxlen=limit)
        with self._execution_log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    buffer.append(line)
        results: List[WorkflowResult] = []
        for entry in reversed(buffer):
            try:
                results.append(WorkflowResult.model_validate_json(entry))
            except ValidationError:
                continue
        return results

    def _load_metadata(self, *, limit: int) -> List[MetadataSnapshot]:
        if not self._metadata_history_path.exists():
            return []
        rows: deque[dict[str, str]] = deque(maxlen=limit)
        with self._metadata_history_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append(row)
        snapshots: List[MetadataSnapshot] = []
        for row in rows:
            snapshots.append(
                MetadataSnapshot(
                    run_id=row.get("run_id", ""),
                    timestamp=_parse_timestamp(row.get("timestamp")),
                    mode=row.get("mode"),
                    title=row.get("title"),
                    description=row.get("description"),
                    video_url=row.get("video_url"),
                    view_count=_parse_int(row.get("view_count")),
                    like_count=_parse_int(row.get("like_count")),
                    comment_count=_parse_int(row.get("comment_count")),
                    ctr=_parse_percentage(row.get("ctr")),
                    avg_view_duration=_parse_duration(row.get("avg_view_duration")),
                )
            )
        return snapshots

    def _build_run_artifacts(self, result: WorkflowResult, metadata: MetadataSnapshot | None) -> RunArtifacts:
        created_at = metadata.timestamp if metadata else _infer_timestamp_from_run_id(result.run_id)
        title = result.title or (metadata.title if metadata else None)
        description = result.video_review_summary or (metadata.description if metadata else None)
        artefact = RunArtifacts(
            run_id=result.run_id,
            title=title,
            description=description,
            mode=result.mode,
            created_at=created_at,
            thumbnail_path=result.thumbnail_path,
        )
        video_url = result.video_url or (metadata.video_url if metadata else None)
        if video_url:
            artefact.external_links.append(ExternalLink(label="YouTube", url=video_url, kind="youtube"))
        if result.video_path or video_url:
            artefact.video = MediaAsset(
                kind=ArtifactKind.VIDEO,
                label=title or (Path(result.video_path).name if result.video_path else result.run_id),
                path=result.video_path,
                url=video_url,
                thumbnail_path=result.thumbnail_path,
            )
        seen_paths: set[str] = set()
        if artefact.video and artefact.video.path:
            seen_paths.add(artefact.video.path)
        artifact_paths = [artifact.path for artifact in getattr(result, "generated_artifacts", []) if artifact.path]
        if not artifact_paths:
            artifact_paths = list(result.generated_files or [])
        for path in _iter_unique_files(artifact_paths):
            suffix = Path(path).suffix.lower()
            label = Path(path).name
            if suffix in AUDIO_EXTENSIONS and path not in seen_paths:
                artefact.audio.append(MediaAsset(kind=ArtifactKind.AUDIO, label=label, path=path))
                seen_paths.add(path)
            elif suffix in TEXT_EXTENSIONS and path not in seen_paths:
                artefact.text.append(MediaAsset(kind=ArtifactKind.TEXT, label=label, path=path))
                seen_paths.add(path)
            elif suffix in VIDEO_EXTENSIONS and artefact.video is None:
                artefact.video = MediaAsset(
                    kind=ArtifactKind.VIDEO,
                    label=label,
                    path=path,
                    url=video_url,
                    thumbnail_path=result.thumbnail_path,
                )
                seen_paths.add(path)
        return artefact

    def _build_run_metrics(self, result: WorkflowResult, metadata: MetadataSnapshot | None) -> RunMetrics:
        created_at = metadata.timestamp if metadata else _infer_timestamp_from_run_id(result.run_id)
        title = result.title or (metadata.title if metadata else None)
        metrics = RunMetrics(
            run_id=result.run_id,
            title=title,
            mode=result.mode,
            created_at=created_at,
            success=result.success,
            wow_score=result.wow_score,
            quality_score=result.quality_score,
            curiosity_gap_score=result.curiosity_gap_score,
            surprise_points=result.surprise_points,
            emotion_peaks=result.emotion_peaks,
            visual_instructions=result.visual_instructions,
            retention_prediction=result.retention_prediction,
            japanese_purity=result.japanese_purity,
            video_review_summary=result.video_review_summary,
            video_review_actions=list(result.video_review_actions or []),
        )
        if metadata:
            metrics.view_count = metadata.view_count
            metrics.like_count = metadata.like_count
            metrics.comment_count = metadata.comment_count
            metrics.ctr = metadata.ctr
            metrics.avg_view_duration = metadata.avg_view_duration
        return metrics

    def _compute_summary(self, runs: Iterable[RunMetrics]) -> DashboardSummary:
        runs_list = list(runs)
        total = len(runs_list)
        successes = sum(1 for run in runs_list if run.success)
        return DashboardSummary(
            total_runs=total,
            successful_runs=successes,
            average_wow_score=_mean(run.wow_score for run in runs_list),
            average_quality_score=_mean(run.quality_score for run in runs_list),
            average_retention_prediction=_mean(run.retention_prediction for run in runs_list),
            average_view_count=_mean(run.view_count for run in runs_list),
            average_ctr=_mean(run.ctr for run in runs_list),
        )


def _mean(values: Iterable[Optional[float | int]]) -> Optional[float]:
    numeric_values: List[float] = []
    for value in values:
        if value is None:
            continue
        numeric_values.append(float(value))
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_percentage(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    cleaned = value.strip().rstrip("%")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_duration(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    cleaned = value.strip().lower()
    if cleaned.endswith("s"):
        cleaned = cleaned[:-1]
    try:
        return float(cleaned)
    except ValueError:
        return None


def _infer_timestamp_from_run_id(run_id: str) -> Optional[datetime]:
    fragments = run_id.split("_")
    candidates = [fragments[-1], run_id]
    for candidate in candidates:
        for fmt in ("%Y%m%d_%H%M%S", "%Y%m%d-%H%M%S", "%Y-%m-%d-%H-%M-%S"):
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    return None


def _iter_unique_files(files: Optional[Iterable[str]]) -> Iterator[str]:
    seen: set[str] = set()
    if not files:
        return
    for path in files:
        if not path or path in seen:
            continue
        seen.add(path)
        yield path
