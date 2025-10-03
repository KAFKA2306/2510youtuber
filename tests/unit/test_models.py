"""データモデルのユニットテスト"""

import pytest


@pytest.mark.unit
def test_news_item_creation(sample_news_item):
    """NewsItemが正しく作成できるか確認"""
    from app.models import NewsItem

    news = NewsItem(**sample_news_item)

    assert news.title == sample_news_item["title"]
    assert news.url == sample_news_item["url"]
    assert news.summary == sample_news_item["summary"]
    assert news.source == sample_news_item["source"]
    assert news.impact_level == sample_news_item["impact_level"]
    assert news.category == sample_news_item["category"]


@pytest.mark.unit
def test_news_item_high_impact(sample_news_item):
    """NewsItemのhigh impact判定が正しいか確認"""
    from app.models import NewsItem

    news = NewsItem(**sample_news_item)

    assert news.is_high_impact is True, "impact_level='high'なのにis_high_impactがFalse"


@pytest.mark.unit
def test_news_collection_creation(sample_news_items):
    """NewsCollectionが正しく作成できるか確認"""
    from app.models import NewsCollection

    collection = NewsCollection(
        items=sample_news_items,
        mode="test"
    )

    assert collection.mode == "test"
    assert collection.total_count == len(sample_news_items)
    assert collection.has_high_impact is True


@pytest.mark.unit
def test_script_segment_creation(sample_script_segments):
    """ScriptSegmentが正しく作成できるか確認"""
    from app.models import ScriptSegment

    segment_data = sample_script_segments[0]
    segment = ScriptSegment(
        speaker=segment_data["speaker"],
        text=segment_data["text"]
    )

    assert segment.speaker == segment_data["speaker"]
    assert segment.text == segment_data["text"]
    assert segment.char_count == len(segment_data["text"])


@pytest.mark.unit
def test_quality_score_creation():
    """QualityScoreが正しく作成できるか確認"""
    from app.models import QualityScore

    score = QualityScore(
        wow_score=8.5,
        surprise_score=9.0,
        emotion_score=8.0,
        clarity_score=8.5,
        retention_prediction=54.0,
        japanese_purity=97.5
    )

    assert score.wow_score == 8.5
    assert score.surprise_score == 9.0
    assert score.is_passing() is True
    assert score.is_excellent is True


@pytest.mark.unit
def test_quality_score_passing_threshold():
    """QualityScoreの合格判定閾値が正しいか確認"""
    from app.models import QualityScore

    # 合格スコア
    passing_score = QualityScore(
        wow_score=7.0,
        surprise_score=7.0,
        emotion_score=7.0,
        clarity_score=7.0,
        retention_prediction=50.0,
        japanese_purity=90.0
    )
    assert passing_score.is_passing() is True

    # 不合格スコア
    failing_score = QualityScore(
        wow_score=5.0,
        surprise_score=5.0,
        emotion_score=5.0,
        clarity_score=5.0,
        retention_prediction=40.0,
        japanese_purity=85.0
    )
    assert failing_score.is_passing() is False


@pytest.mark.unit
def test_wow_metrics_creation():
    """WOWMetricsが正しく作成できるか確認"""
    from app.models import WOWMetrics

    metrics = WOWMetrics(
        curiosity_gap_score=8.5,
        emotional_intensity=7.8,
        surprise_factor=9.0,
        personal_relevance=7.5,
        contrarian_angle=6.0
    )

    assert metrics.curiosity_gap_score == 8.5
    assert metrics.emotional_intensity == 7.8
    assert metrics.surprise_factor == 9.0
    assert metrics.personal_relevance == 7.5
    assert metrics.contrarian_angle == 6.0
