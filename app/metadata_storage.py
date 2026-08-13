"""メタデータ記録・管理モジュール + フィードバックループ統合.

生成されたメタデータをローカルJSONL + Google Sheetsに記録し、
YouTube統計と組み合わせて継続的改善のためのフィードバックループを提供します。
"""

import csv
import importlib
import importlib.util
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.config.paths import ProjectPaths

from .models.workflow import WorkflowResult

logger = logging.getLogger(__name__)


def _load_sheets_manager():
    module_name = "app.sheets"
    if importlib.util.find_spec(module_name) is None:
        return None
    module = importlib.import_module(module_name)
    return getattr(module, "sheets_manager", None)


class MetadataStorage:
    """メタデータ記録・管理クラス."""

    def __init__(self, csv_path: str = None, jsonl_path: str = None):
        """初期化.

        Args:
            csv_path: CSVファイルのパス（デフォルト: data/metadata_history.csv）
            jsonl_path: JSONLファイルのパス（デフォルト: output/execution_log.jsonl）
        """
        self.csv_path = csv_path or self._get_default_csv_path()
        self.jsonl_path = jsonl_path or self._get_default_jsonl_path()
        self.sheets_manager = None
        self._ensure_csv_exists()
        self._ensure_jsonl_dir()
        self._initialize_sheets()

    def _get_default_jsonl_path(self) -> str:
        """デフォルトJSONLパスを取得."""
        output_dir = ProjectPaths.OUTPUT_DIR
        output_dir.mkdir(exist_ok=True)
        return str(output_dir / "execution_log.jsonl")

    def _get_default_csv_path(self) -> str:
        """デフォルトCSVパスを取得."""
        data_dir = ProjectPaths.DATA_DIR
        data_dir.mkdir(exist_ok=True)
        return str(data_dir / "metadata_history.csv")

    def _ensure_csv_exists(self):
        """CSVファイルが存在しない場合は作成."""
        if not os.path.exists(self.csv_path):
            headers = [
                "timestamp",
                "run_id",
                "mode",
                "title",
                "description",
                "tags",
                "category",
                "thumbnail_text",
                "seo_keywords",
                "target_audience",
                "estimated_watch_time",
                "news_count",
                "news_topics",
                "video_url",
                "view_count",
                "like_count",
                "comment_count",
                "ctr",
                "avg_view_duration",
            ]

            with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()

            logger.info(f"Created metadata CSV: {self.csv_path}")

    def _ensure_jsonl_dir(self):
        """JSONLディレクトリが存在することを確認."""
        Path(self.jsonl_path).parent.mkdir(parents=True, exist_ok=True)

    def _initialize_sheets(self):
        """Google Sheets接続を初期化."""
        manager = _load_sheets_manager()
        self.sheets_manager = manager
        if manager and getattr(manager, "service", None):
            logger.info("Google Sheets connection available for metadata storage")
        else:
            logger.warning("Google Sheets not available, using CSV only")

    def save_metadata(
        self,
        metadata: Dict[str, Any],
        run_id: str = None,
        mode: str = "daily",
        news_items: List[Dict] = None,
    ) -> bool:
        """メタデータをCSVとGoogle Sheetsに保存.

        Args:
            metadata: 保存するメタデータ
            run_id: 実行ID
            mode: 実行モード
            news_items: ニュース項目（トピック抽出用）

        Returns:
            保存成功時True
        """
        timestamp = datetime.now().isoformat()
        run_id = run_id or f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # ニューストピックを抽出
        news_topics = self._extract_news_topics(news_items) if news_items else ""

        # CSV用データ
        csv_row = {
            "timestamp": timestamp,
            "run_id": run_id,
            "mode": mode,
            "title": metadata.get("title", ""),
            "description": metadata.get("description", "")[:500],  # 短縮版
            "tags": json.dumps(metadata.get("tags", []), ensure_ascii=False),
            "category": metadata.get("category", ""),
            "thumbnail_text": metadata.get("thumbnail_text", ""),
            "seo_keywords": json.dumps(metadata.get("seo_keywords", []), ensure_ascii=False),
            "target_audience": metadata.get("target_audience", ""),
            "estimated_watch_time": metadata.get("estimated_watch_time", ""),
            "news_count": metadata.get("news_count", 0),
            "news_topics": news_topics,
            "video_url": "",  # 後で更新
            "view_count": "",
            "like_count": "",
            "comment_count": "",
            "ctr": "",
            "avg_view_duration": "",
        }

        # ローカルCSVに保存
        self._save_to_csv(csv_row)

        # Google Sheetsに保存
        if self.sheets_manager:
            self._save_to_sheets(metadata, run_id, mode, news_topics)

        logger.info(f"Saved metadata for run {run_id}")
        return True

    def _save_to_csv(self, row: Dict[str, Any]):
        """CSVに行を追加."""
        headers = list(row.keys())

        with open(self.csv_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writerow(row)

        logger.debug(f"Saved metadata to CSV: {self.csv_path}")

    def _save_to_sheets(self, metadata: Dict[str, Any], run_id: str, mode: str, news_topics: str):
        """Google Sheetsのmetadataシートに保存."""
        if not self.sheets_manager or not self.sheets_manager.service:
            return

        timestamp = datetime.now().isoformat()

        values = [
            [
                timestamp,
                run_id,
                mode,
                metadata.get("title", ""),
                metadata.get("description", "")[:1000],  # Sheets用は長め
                json.dumps(metadata.get("tags", []), ensure_ascii=False),
                metadata.get("category", ""),
                metadata.get("thumbnail_text", ""),
                json.dumps(metadata.get("seo_keywords", []), ensure_ascii=False),
                metadata.get("target_audience", ""),
                metadata.get("estimated_watch_time", ""),
                metadata.get("news_count", 0),
                news_topics,
            ]
        ]

        # metadataシートに追加（シートが存在しない場合は後で作成）
        self.sheets_manager._rate_limit_retry(
            self.sheets_manager.service.spreadsheets().values().append,
            spreadsheetId=self.sheets_manager.sheet_id,
            range="metadata!A:M",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

        logger.info(f"Saved metadata to Google Sheets for run {run_id}")

    def _extract_news_topics(self, news_items: List[Dict]) -> str:
        """ニュース項目からトピックを抽出."""
        if not news_items:
            return ""

        topics = []
        for item in news_items[:3]:  # 最大3件
            title = item.get("title", "")
            # 最初の30文字を取得
            topic = title[:30] + ("..." if len(title) > 30 else "")
            topics.append(topic)

        return " | ".join(topics)

    def load_history(self, limit: int = 100, mode: str = None, min_views: int = None) -> List[Dict[str, Any]]:
        """過去のメタデータ履歴を読み込み.

        Args:
            limit: 取得件数上限
            mode: フィルタするモード（None=全て）
            min_views: 最小視聴回数（None=フィルタなし）

        Returns:
            メタデータ履歴のリスト
        """
        try:
            history = []

            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # モードフィルタ
                    if mode and row.get("mode") != mode:
                        continue

                    # 視聴回数フィルタ
                    if min_views is not None:
                        try:
                            views = int(row.get("view_count", 0) or 0)
                            if views < min_views:
                                continue
                        except ValueError:
                            continue

                    # JSONフィールドをパース
                    row["tags"] = json.loads(row.get("tags", "[]"))
                    row["seo_keywords"] = json.loads(row.get("seo_keywords", "[]"))

                    history.append(row)

                    if len(history) >= limit:
                        break

            logger.info(f"Loaded {len(history)} metadata records from history")
            return history

        except FileNotFoundError:
            logger.warning(f"Metadata history file not found: {self.csv_path}")
            return []

    def get_successful_titles(self, min_views: int = 1000, limit: int = 50) -> List[str]:
        """成功したタイトルを取得（視聴回数ベース）.

        Args:
            min_views: 最小視聴回数
            limit: 取得件数上限

        Returns:
            成功したタイトルのリスト
        """
        history = self.load_history(limit=limit * 2, min_views=min_views)

        # 視聴回数でソート
        sorted_history = sorted(history, key=lambda x: int(x.get("view_count", 0) or 0), reverse=True)

        titles = [record["title"] for record in sorted_history[:limit] if record.get("title")]

        logger.info(f"Retrieved {len(titles)} successful titles (min {min_views} views)")
        return titles

    def analyze_top_keywords(self, limit: int = 20) -> Dict[str, int]:
        """上位パフォーマンスの動画からキーワードを分析.

        Args:
            limit: 分析する動画数

        Returns:
            キーワードと出現回数の辞書
        """
        history = self.load_history(limit=limit * 2)

        # 視聴回数でソート
        sorted_history = sorted(history, key=lambda x: int(x.get("view_count", 0) or 0), reverse=True)

        keyword_count = {}

        for record in sorted_history[:limit]:
            # タイトルからキーワードを抽出
            title = record.get("title", "")
            keywords = self._extract_title_keywords(title)

            for keyword in keywords:
                keyword_count[keyword] = keyword_count.get(keyword, 0) + 1

            # タグも集計
            tags = record.get("tags", [])
            for tag in tags:
                keyword_count[tag] = keyword_count.get(tag, 0) + 1

        # 出現回数でソート
        sorted_keywords = dict(sorted(keyword_count.items(), key=lambda x: x[1], reverse=True)[:20])

        logger.info(f"Analyzed keywords from top {limit} videos")
        return sorted_keywords

    def _extract_title_keywords(self, title: str) -> List[str]:
        """タイトルからキーワードを抽出."""
        import re

        keywords = []

        # 経済関連キーワード
        patterns = [
            r"日経平均",
            r"株価",
            r"円安",
            r"円高",
            r"金利",
            r"利上げ",
            r"GDP",
            r"インフレ",
            r"日銀",
            r"FRB",
            r"暴落",
            r"急騰",
            r"速報",
            r"緊急",
        ]

        for pattern in patterns:
            if re.search(pattern, title):
                keywords.append(pattern)

        # パーセンテージや数字
        percent_match = re.search(r"\d+[%％]", title)
        if percent_match:
            keywords.append("数字強調")

        return keywords

    def log_execution(self, workflow_result: "WorkflowResult") -> bool:
        """ワークフロー実行結果をJSONL + Sheets に記録.

        Args:
            workflow_result: WorkflowResultインスタンス

        Returns:
            成功時True
        """
        # 1. JSONLに完全データを保存（分析用）
        self._save_to_jsonl(workflow_result)

        # 2. Google Sheetsに人間向けフォーマットで保存
        if self.sheets_manager and self.sheets_manager.service:
            self._sync_to_sheets(workflow_result)

        logger.info(f"Logged execution for run {workflow_result.run_id}")
        return True

    def _save_to_jsonl(self, result: "WorkflowResult"):
        """JSONLに追加（append-only log）."""
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(result.model_dump_json() + "\n")
        logger.debug(f"Saved to JSONL: {self.jsonl_path}")

    def _sync_to_sheets(self, result: "WorkflowResult"):
        """Google Sheetsの3タブに同期."""
        if not self.sheets_manager or not self.sheets_manager.service:
            return

        # Tab 1: Performance Dashboard（人間向けサマリー）
        dashboard_row = self._format_dashboard_row(result)
        self._append_to_sheet("performance_dashboard", dashboard_row)

        # Tab 2: Quality Metrics（品質詳細）
        quality_row = self._format_quality_row(result)
        self._append_to_sheet("quality_metrics", quality_row)

        # Tab 3: Production Insights（実行詳細）
        production_row = self._format_production_row(result)
        self._append_to_sheet("production_insights", production_row)

        logger.info(f"Synced to Sheets: {result.run_id}")

    def _format_dashboard_row(self, result: "WorkflowResult") -> List[Any]:
        """Tab 1: Performance Dashboard用にフォーマット."""
        video_num = self._extract_video_number(result.run_id)
        date_str = datetime.now().strftime("%Y-%m-%d")
        hook_type = result.hook_type or self._classify_hook(result)
        topic = result.topic or "一般"

        # YouTube link
        yt_link = f"https://youtube.com/watch?v={result.video_id}" if result.video_id else ""

        # Feedback data (populated later)
        fb = result.youtube_feedback
        views_24h = fb.views_24h if fb else None
        retention = fb.avg_view_percentage if fb else result.retention_prediction
        ctr = fb.ctr if fb else None
        comments = " / ".join(fb.top_comments[:3]) if fb and fb.top_comments else ""

        return [
            date_str,
            f"#{video_num:04d}",
            result.title or "",
            topic,
            hook_type,
            f"{result.wow_score:.1f}" if result.wow_score else "",
            f"{retention:.1f}%" if retention else "",
            self._format_number(views_24h) if views_24h else "",
            f"{ctr:.2f}%" if ctr else "",
            comments,
            result.status_icon,
            yt_link,
        ]

    def _format_quality_row(self, result: "WorkflowResult") -> List[Any]:
        """Tab 2: Quality Metrics用にフォーマット."""
        video_num = self._extract_video_number(result.run_id)
        return [
            f"#{video_num:04d}",
            f"{result.wow_score:.1f}" if result.wow_score else "",
            result.surprise_points or "",
            result.emotion_peaks or "",
            result.curiosity_gap_score or "",
            result.visual_instructions or "",
            f"{result.japanese_purity:.1f}%" if result.japanese_purity else "",
            result.script_grade,
            "",  # Agent iterations (TODO: extract from processing_history)
        ]

    def _format_production_row(self, result: "WorkflowResult") -> List[Any]:
        """Tab 3: Production Insights用にフォーマット."""
        video_num = self._extract_video_number(result.run_id)
        total_time = self._format_duration(result.execution_time_seconds)
        total_cost = f"${result.total_cost:.2f}" if result.total_cost else ""
        api_breakdown = self._format_api_costs(result.api_costs)

        return [
            f"#{video_num:04d}",
            "Unknown",  # News source (TODO: extract)
            total_time,
            "Unknown",  # TTS provider (TODO: extract)
            "",  # Video gen time (TODO: extract)
            total_cost,
            api_breakdown,
            result.error or "None",
        ]

    def _classify_hook(self, result: "WorkflowResult") -> str:
        """フック戦略を分類（script先頭から推定）."""
        # Note: WorkflowResultにはscript textがないので、
        # 実際はmain.pyからhook_typeを設定すべき
        return "その他"

    def _extract_video_number(self, run_id: str) -> int:
        """run_idから動画番号を抽出（sequential）."""
        # Simple approach: count JSONL lines
        try:
            if os.path.exists(self.jsonl_path):
                with open(self.jsonl_path, "r") as f:
                    return sum(1 for _ in f) + 1
            return 1
        except Exception:
            return 1

    def _format_number(self, num: int) -> str:
        """数字を人間向けフォーマット (1.2K, 15.3K)."""
        if num >= 1000:
            return f"{num/1000:.1f}K"
        return str(num)

    def _format_duration(self, seconds: float) -> str:
        """秒を分秒フォーマット (3m 24s)."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs:02d}s"

    def _format_api_costs(self, api_costs: Dict[str, float]) -> str:
        """API別コストをフォーマット."""
        if not api_costs:
            return ""
        parts = [f"{k}: ${v:.2f}" for k, v in api_costs.items()]
        return ", ".join(parts)

    def _append_to_sheet(self, sheet_name: str, row: List[Any]):
        """指定シートに行を追加."""
        range_name = f"{sheet_name}!A:Z"
        self.sheets_manager._rate_limit_retry(
            self.sheets_manager.service.spreadsheets().values().append,
            spreadsheetId=self.sheets_manager.sheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": [row]},
        ).execute()

    def update_video_stats(
        self,
        run_id: str,
        video_url: str = None,
        view_count: int = None,
        like_count: int = None,
        comment_count: int = None,
        ctr: float = None,
        avg_view_duration: float = None,
    ):
        """動画の統計情報を更新.

        Args:
            run_id: 更新対象のrun_id
            video_url: 動画URL
            view_count: 視聴回数
            like_count: いいね数
            comment_count: コメント数
            ctr: クリック率
            avg_view_duration: 平均視聴時間
        """
        # CSVを読み込み
        rows = []
        updated = False

        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

            for row in reader:
                if row["run_id"] == run_id:
                    # 更新
                    if video_url is not None:
                        row["video_url"] = video_url
                    if view_count is not None:
                        row["view_count"] = str(view_count)
                    if like_count is not None:
                        row["like_count"] = str(like_count)
                    if comment_count is not None:
                        row["comment_count"] = str(comment_count)
                    if ctr is not None:
                        row["ctr"] = f"{ctr:.2f}%"
                    if avg_view_duration is not None:
                        row["avg_view_duration"] = f"{avg_view_duration:.1f}s"

                    updated = True
                    logger.info(f"Updated stats for run {run_id}")

                rows.append(row)

        if updated:
            # CSVに書き戻し
            with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)


# グローバルインスタンス
metadata_storage = MetadataStorage()


def save_metadata(
    metadata: Dict[str, Any],
    run_id: str = None,
    mode: str = "daily",
    news_items: List[Dict] = None,
) -> bool:
    """メタデータ保存の簡易関数."""
    return metadata_storage.save_metadata(metadata, run_id, mode, news_items)


def load_history(limit: int = 100, mode: str = None) -> List[Dict[str, Any]]:
    """履歴読み込みの簡易関数."""
    return metadata_storage.load_history(limit, mode)


def get_successful_titles(min_views: int = 1000) -> List[str]:
    """成功タイトル取得の簡易関数."""
    return metadata_storage.get_successful_titles(min_views)


if __name__ == "__main__":
    # テスト
    print("Testing metadata storage...")

    storage = MetadataStorage()

    # テストデータ
    test_metadata = {
        "title": "【速報】日経平均10%急騰！その理由と今後の展開",
        "description": "本日の日経平均株価の急騰について解説します...",
        "tags": ["経済ニュース", "株価", "日経平均", "投資"],
        "category": "News & Politics",
        "thumbnail_text": "10%急騰",
        "seo_keywords": ["日経平均", "株価急騰", "経済ニュース"],
        "target_audience": "投資家",
        "estimated_watch_time": "15分",
        "news_count": 3,
    }

    test_news = [
        {"title": "日経平均が年初来高値を更新"},
        {"title": "米国株も連日の高値"},
    ]

    # 保存テスト
    print("\n=== 保存テスト ===")
    success = storage.save_metadata(test_metadata, "test_001", "daily", test_news)
    print(f"Save result: {success}")

    # 読み込みテスト
    print("\n=== 履歴読み込みテスト ===")
    history = storage.load_history(limit=5)
    print(f"Loaded {len(history)} records")
    if history:
        print(f"Latest: {history[0]['title'][:50]}...")

    # キーワード分析テスト
    print("\n=== キーワード分析テスト ===")
    keywords = storage.analyze_top_keywords(limit=10)
    print(f"Top keywords: {list(keywords.keys())[:5]}")

    print("\nTest completed.")
