"""Tests for continuity context builder used in prompt generation."""

import json
from pathlib import Path

from app.services.script.continuity import ContinuityContextBuilder


def _write_metadata_csv(path: Path) -> None:
    header = (
        "timestamp,run_id,mode,title,description,tags,category,thumbnail_text,"
        "seo_keywords,target_audience,estimated_watch_time,news_count,news_topics,"
        "video_url,view_count,like_count,comment_count,ctr,avg_view_duration\n"
    )
    first_row = (
        "2025-10-02T12:00:00,run_a,daily,旧タイトル,説明A,"
        "["
        """投資"""
        "]"
        ",News,テキストA,"
        "["
        """投資"""
        "]"
        ","
        "投資家,12分,2,旧トピック,https://youtu.be/old,1000,50,10,5%,300\n"
    )
    latest_row = (
        "2025-10-03T09:00:00,run_b,daily,最新の動画タイトル,視聴者がリスク対策をもっと知りたいとコメントしました,"
        "["
        """経済"""
        "],News,テキストB,"
        "["
        """経済"""
        "]"
        ",投資家,12分,3,最新トピック,"
        "https://youtu.be/latest,2000,120,25,6%,360\n"
    )
    path.write_text(header + first_row + latest_row, encoding="utf-8")


def _write_feedback_json(path: Path) -> None:
    payload = {
        "video_old": {
            "created_at": "2025-10-02T10:00:00",
            "updated_at": "2025-10-02T11:00:00",
            "analytics": {"views": 1500, "likes": 70, "retention_rate": 62.5},
            "manual_feedback": [
                {"positive": True, "comment": "旧動画もわかりやすかった"},
            ],
        },
        "video_latest": {
            "created_at": "2025-10-03T09:30:00",
            "updated_at": "2025-10-03T09:45:00",
            "analytics": {"views": 2400, "likes": 180, "retention_rate": 74.2},
            "manual_feedback": [
                {"positive": True, "comment": "グラフの解説が助かった"},
                {"positive": False, "comment": "リスクの対策も知りたい"},
            ],
            "ai_review": {
                "feedback": {
                    "summary": "終盤のテンポが落ちて中盤以降の離脱率が上昇",
                    "positive_highlights": ["冒頭の要約が明確"],
                    "improvement_suggestions": ["中盤にBロールを追加", "重要指標のテロップを増やす"],
                    "retention_risks": ["グラフが静止して変化が少ない"],
                    "next_video_actions": ["30秒ごとに視覚要素を切り替える"],
                },
                "model_name": "gemini-2.5-flash-preview-09-2025",
            },
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_build_prompt_snippet_includes_metadata_and_feedback(tmp_path):
    metadata_path = tmp_path / "metadata_history.csv"
    feedback_path = tmp_path / "video_feedback.json"
    _write_metadata_csv(metadata_path)
    _write_feedback_json(feedback_path)

    builder = ContinuityContextBuilder(metadata_path, feedback_path)
    snippet = builder.build_prompt_snippet()

    assert "前回動画" in snippet
    assert "最新の動画タイトル" in snippet
    assert "保持率74%" in snippet
    assert "好評コメント" in snippet
    assert "改善ヒント" in snippet
    assert "AIレビュー要約" in snippet
    assert "改善アクション候補" in snippet
    assert "次の動画で試すべき施策" in snippet
    assert "冒頭8秒" in snippet
    assert "実装→検証" in snippet


def test_build_prompt_snippet_empty_when_no_sources(tmp_path):
    metadata_path = tmp_path / "missing.csv"
    feedback_path = tmp_path / "missing.json"

    builder = ContinuityContextBuilder(metadata_path, feedback_path)
    assert builder.build_prompt_snippet() == ""
