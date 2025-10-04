from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field, model_validator
from app.config.settings import settings

_DIALOGUE_PREFIX_PATTERN = re.compile(r"[：:\-―ー\s　]*")
_QUOTE_TRIM_PATTERN = re.compile(r"^[「『]\s*|\s*[」』]$")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class ScriptValidationIssue:
    """Issue discovered while validating the script."""

    line_number: int
    message: str
    content: str
    severity: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "line_number": str(self.line_number),
            "message": self.message,
            "content": self.content,
            "severity": self.severity,
        }


@dataclass
class ScriptValidationResult:
    """Result of normalizing and validating a dialogue script."""

    normalized_script: str
    dialogue_line_count: int
    nonempty_line_count: int
    speaker_counts: Dict[str, int]
    errors: List[ScriptValidationIssue]
    warnings: List[ScriptValidationIssue]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, Any]:  # type: ignore[override]
        return {
            "dialogue_line_count": self.dialogue_line_count,
            "nonempty_line_count": self.nonempty_line_count,
            "speaker_counts": self.speaker_counts,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


class ScriptFormatError(RuntimeError):
    """Raised when a dialogue script fails validation."""

    def __init__(self, result: ScriptValidationResult):
        self.result = result
        summary = _build_error_summary(result)
        super().__init__(summary)


# --- Dialogue + Script ---
class DialogueEntry(BaseModel):
    speaker: str = Field(..., description="話者名 (例: 武宏, つむぎ)")
    line: str = Field(..., description="発話テキスト")

class Script(BaseModel):
    title: str = Field(..., description="スクリプトのタイトル")
    dialogues: List[DialogueEntry] = Field(..., description="対話リスト", min_items=2)

    @model_validator(mode="after")
    def check_distinct_speakers(self) -> "Script":
        speakers = {entry.speaker for entry in self.dialogues}
        if len(speakers) < 2:
            raise ValueError("スクリプトには2人以上の異なる話者が必要です。")
        return self

    def to_text(self) -> str:
        return "\n".join(f"{e.speaker}: {e.line}" for e in self.dialogues)

# --- Quality/Segment/WOW ---
class QualityScore(BaseModel):
    wow_score: float = Field(..., description="WOWスコア")
    japanese_purity_score: float = Field(..., description="日本語純度スコア")

class ScriptSegment(BaseModel):
    speaker: str = Field(..., description="話者名")
    content: str = Field(..., description="セグメント内容")
    start_time: Optional[float] = Field(None, description="開始時間 (秒)")
    end_time: Optional[float] = Field(None, description="終了時間 (秒)")

class WOWMetrics(BaseModel):
    wow_score: float = Field(..., description="WOWスコア")
    iteration: int = Field(..., description="評価イテレーション")


def ensure_dialogue_structure(
    script: str,
    allowed_speakers: Optional[Sequence[str]] = None,
    min_dialogue_ratio: float = 0.5,
    min_dialogue_lines: int = 10,
) -> ScriptValidationResult:
    """Normalize and validate the Crew-generated dialogue script.

    Args:
        script: Raw script text from CrewAI.
        allowed_speakers: Optional list of speaker labels expected in the script.
        min_dialogue_ratio: Minimum ratio of dialogue lines to non-empty lines.
        min_dialogue_lines: Minimum number of dialogue lines required.

    Returns:
        ScriptValidationResult with normalized content and validation details.

    Raises:
        ScriptFormatError: If the script cannot be normalized into a valid dialogue form.
    """
    speakers = _resolve_speakers(allowed_speakers)
    normalized_lines: List[str] = []
    warnings: List[ScriptValidationIssue] = []
    error_candidates: List[ScriptValidationIssue] = []
    dialogue_line_count = 0
    nonempty_line_count = 0
    speaker_counts: Counter[str] = Counter()

    for idx, raw_line in enumerate(script.splitlines(), start=1):
        original_line = raw_line.rstrip("\n")
        stripped = original_line.strip()

        if not stripped:
            normalized_lines.append("")
            continue

        nonempty_line_count += 1

        normalized, speaker, line_warnings = _normalize_dialogue_line(stripped, speakers)
        if speaker:
            dialogue_line_count += 1
            speaker_counts[speaker] += 1
            if line_warnings:
                warnings.extend(ScriptValidationIssue(idx, message, stripped, "warning") for message in line_warnings)
            normalized_lines.append(normalized)
        else:
            normalized_lines.append(original_line)
            error_candidates.append(
                ScriptValidationIssue(idx, "Line is not attributed to a known speaker", stripped, "warning")
            )

    normalized_script = "\n".join(normalized_lines)
    errors: List[ScriptValidationIssue] = []

    if dialogue_line_count < max(min_dialogue_lines, int(nonempty_line_count * min_dialogue_ratio)):
        errors.append(
            ScriptValidationIssue(
                0,
                (
                    "Insufficient dialogue structure: "
                    f"{dialogue_line_count} speaker lines out of {nonempty_line_count} non-empty lines"
                ),
                content="",
                severity="error",
            )
        )
        errors.extend(error_candidates[:5])

    distinct_speakers = sum(1 for count in speaker_counts.values() if count > 0)
    if distinct_speakers < min(2, len(speakers)):
        errors.append(
            ScriptValidationIssue(
                0,
                "Dialogue must include at least two distinct speakers",
                content=", ".join(sorted(k for k, v in speaker_counts.items() if v > 0)) or "(none)",
                severity="error",
            )
        )

    if dialogue_line_count == 0:
        errors.append(
            ScriptValidationIssue(
                0,
                "No recognizable speaker lines were found",
                content="",
                severity="error",
            )
        )

    result = ScriptValidationResult(
        normalized_script=normalized_script,
        dialogue_line_count=dialogue_line_count,
        nonempty_line_count=nonempty_line_count,
        speaker_counts=dict(speaker_counts),
        errors=errors,
        warnings=warnings + [issue for issue in error_candidates if not errors],
    )

    if result.errors:
        raise ScriptFormatError(result)

    return result


def _resolve_speakers(allowed_speakers: Optional[Sequence[str]]) -> List[str]:
    if allowed_speakers:
        resolved = [speaker.strip() for speaker in allowed_speakers if speaker and speaker.strip()]
    else:
        resolved = sorted(settings.tts_voice_configs.keys())
    if not resolved:
        raise ValueError("Allowed speakers list cannot be empty")
    return resolved


def _normalize_dialogue_line(line: str, speakers: Sequence[str]) -> tuple[str, Optional[str], List[str]]:
    """Attempt to normalize a single line into `Speaker: content` format."""
    for speaker in speakers:
        if not line.startswith(speaker):
            continue
        remainder = line[len(speaker) :]
        normalized_content, warnings = _normalize_dialogue_content(remainder)
        if not normalized_content:
            return f"{speaker}:".rstrip(), speaker, ["Speaker line is missing dialogue content"]
        return f"{speaker}: {normalized_content}", speaker, warnings
    return line, None, []


def _normalize_dialogue_content(remainder: str) -> tuple[str, List[str]]:
    """Normalize the content portion of a dialogue line."""
    warnings: List[str] = []
    trimmed = remainder.lstrip()

    if trimmed.startswith((":", "：", "-", "―", "ー")):
        trimmed = _DIALOGUE_PREFIX_PATTERN.sub("", trimmed, count=1)
    elif trimmed.startswith(("「", "『")):
        trimmed = trimmed[1:]
    elif trimmed and not trimmed.startswith(("(", "（", "[", "<")):
        warnings.append("Missing colon after speaker name; inferred dialogue content")

    trimmed = trimmed.strip()
    trimmed = _QUOTE_TRIM_PATTERN.sub("", trimmed)
    trimmed = trimmed.replace("：", ":")
    trimmed = trimmed.strip()
    trimmed = _WHITESPACE_RE.sub(" ", trimmed)

    return trimmed, warnings


def _build_error_summary(result: ScriptValidationResult) -> str:
    base = (
        "Dialogue script validation failed: "
        f"{result.dialogue_line_count}/{result.nonempty_line_count} lines recognized as speaker dialogue."
    )
    if result.errors:
        fragments = []
        for issue in result.errors[:3]:
            prefix = f"L{issue.line_number}: " if issue.line_number else ""
            fragments.append(f"{prefix}{issue.message}")
        if fragments:
            return f"{base} Issues: {', '.join(fragments)}"
    return base