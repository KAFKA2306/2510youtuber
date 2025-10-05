"""Google Sheets操作モジュール

実行ログとプロンプト管理のためのGoogle Sheets操作を提供します。
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config_prompts.settings import settings
from app.prompts import get_sheet_prompt_defaults

logger = logging.getLogger(__name__)


class SheetsManager:
    """Google Sheets操作クラス"""

    def __init__(self):
        self.service = None
        self.sheet_id = settings.google_sheet_id
        self._connect()

    def _connect(self):
        """Google Sheets APIに接続"""
        try:
            creds_dict = settings.google_credentials_json
            if not creds_dict:
                logger.warning("Google credentials not configured - Sheets integration disabled")
                self.service = None
                return

            credentials = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )

            self.service = build("sheets", "v4", credentials=credentials)
            logger.info("Google Sheets connection established")
            self.setup_sheets()

        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            self.service = None

    def _rate_limit_retry(self, func, *args, **kwargs):
        """レート制限対応のリトライ機能付き実行

        Note: self.service が None の場合は呼び出し前にチェックすること
        """
        import random
        import time

        # Safety check: service が None の場合は即座にエラー
        if not self.service:
            raise RuntimeError("Sheets service not available")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                # API呼び出し間隔を空ける
                time.sleep(0.1 + random.uniform(0, 0.1))
                return result

            except HttpError as e:
                if e.resp.status == 429 and attempt < max_retries - 1:  # Rate limit
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.warning(f"Rate limit hit, waiting {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Sheets API error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                raise

        return None

    def create_run(self, mode: str = "daily") -> str:
        """新しい実行記録を作成

        Args:
            mode: 実行モード (daily/special/test)

        Returns:
            生成された run_id

        """
        if not self.service:
            logger.warning("Sheets service not available, returning dummy run_id")
            return str(uuid.uuid4())[:8]

        run_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        # runsシートに新しい行を追加
        values = [
            [
                run_id,  # run_id
                "processing",  # status
                now,  # started_at
                "",  # finished_at
                "",  # duration_sec
                mode,  # mode
                "",  # prompt_a
                "",  # search_results_json
                "",  # script_text
                "",  # audio_urls_json
                "",  # stt_text
                "",  # subtitle_srt
                "",  # video_url
                "",  # title
                "",  # description
                "",  # sources
                "",  # thumbnail_url
                "",  # first_comment
                "",  # error_log
            ]
        ]

        try:
            self._rate_limit_retry(
                self.service.spreadsheets().values().append,
                spreadsheetId=self.sheet_id,
                range="runs!A:S",
                valueInputOption="RAW",
                body={"values": values},
            ).execute()

            logger.info(f"Created new run: {run_id} (mode: {mode})")
            return run_id

        except Exception as e:
            logger.error(f"Failed to create run: {e}")
            raise

    def update_run(self, run_id: str, **fields) -> bool:
        """実行記録を更新

        Args:
            run_id: 更新対象のrun_id
            **fields: 更新するフィールド

        Returns:
            更新成功時True

        """
        # Sheets serviceが利用不可の場合は早期リターン
        if not self.service:
            logger.debug(f"Sheets service unavailable, skipping update for run {run_id}")
            return False

        try:
            # 既存データを取得して対象行を特定
            result = self._rate_limit_retry(
                self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range="runs!A:S"
            ).execute()

            rows = result.get("values", [])
            target_row_index = None

            # run_idで対象行を検索
            for i, row in enumerate(rows):
                if len(row) > 0 and row[0] == run_id:
                    target_row_index = i
                    break

            if target_row_index is None:
                logger.error(f"Run ID not found: {run_id}")
                return False

            # 既存行データを取得（足りないカラムは空文字で埋める）
            current_row = rows[target_row_index]
            while len(current_row) < 19:  # 19カラムまで埋める
                current_row.append("")

            # フィールドごとに更新
            field_mapping = {
                "status": 1,
                "finished_at": 3,
                "duration_sec": 4,
                "mode": 5,
                "prompt_a": 6,
                "search_results_json": 7,
                "script_text": 8,
                "audio_urls_json": 9,
                "stt_text": 10,
                "subtitle_srt": 11,
                "video_url": 12,
                "title": 13,
                "description": 14,
                "sources": 15,
                "thumbnail_url": 16,
                "first_comment": 17,
                "error_log": 18,
            }

            for field, value in fields.items():
                if field in field_mapping:
                    col_index = field_mapping[field]

                    # JSONオブジェクトは文字列化
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    elif value is None:
                        value = ""

                    str_value = str(value)
                    # Google Sheets cell limit is 50,000 characters
                    # 安全のため48000文字に制限し、トランケートメッセージを追加
                    max_chars = 48000
                    if len(str_value) > max_chars:
                        truncate_msg = f"\n\n[TRUNCATED: Original length was {len(str_value)} characters]"
                        str_value = str_value[: max_chars - len(truncate_msg)] + truncate_msg
                        logger.warning(
                            f"Field '{field}' truncated from {len(str(value))} to {len(str_value)} characters"
                        )

                    current_row[col_index] = str_value

            # 自動で finished_at を設定
            if fields.get("status") == "completed" and "finished_at" not in fields:
                current_row[3] = datetime.now().isoformat()

            # Sheets serviceが利用不可の場合は早期リターン
            if not self.service:
                logger.debug(f"Sheets service unavailable, skipping update for run {run_id}")
                return False

            # 更新実行
            range_name = f"runs!A{target_row_index + 1}:S{target_row_index + 1}"
            self._rate_limit_retry(
                self.service.spreadsheets().values().update,
                spreadsheetId=self.sheet_id,
                range=range_name,
                valueInputOption="RAW",
                body={"values": [current_row]},
            ).execute()

            logger.info(f"Updated run {run_id}: {list(fields.keys())}")
            return True

        except Exception as e:
            logger.error(f"Failed to update run {run_id}: {e}")
            return False

    def load_prompts(self, mode: str = "daily") -> Dict[str, str]:
        """プロンプトテンプレートを読み込み（モード対応・キャッシュ対応）

        Args:
            mode: 実行モード (daily/special/test) - モード別プロンプトの選択に使用

        Returns:
            プロンプトの辞書 {prompt_a: "...", prompt_b: "...", ...}
        """
        prompt_manager = settings.prompt_manager

        # Sheets接続がない場合、キャッシュを試す
        if not self.service:
            logger.warning("Sheets service not available, trying cache...")
            # Try to load from cache if method exists
            if hasattr(prompt_manager, "load_prompts_from_cache"):
                cached_prompts = prompt_manager.load_prompts_from_cache(mode)
                if cached_prompts:
                    logger.info(f"Using cached prompts for mode '{mode}'")
                    return cached_prompts
            logger.warning("No cache available, returning default prompts")
            return self._get_default_prompts()

        try:
            result = self._rate_limit_retry(
                self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range="prompts!A1:E10"
            ).execute()

            rows = result.get("values", [])
            if len(rows) >= 2:
                headers = rows[0]

                # モード別プロンプトの検索
                mode_row_index = self._find_mode_row(rows, mode)
                values = rows[mode_row_index] if mode_row_index else rows[1]

                # ヘッダーと値をマッピング
                prompts = {}
                for i, header in enumerate(headers):
                    if i < len(values) and values[i]:
                        prompts[header] = values[i]

                # デフォルトプロンプトで不足分を補完
                default_prompts = self._get_default_prompts()
                for key in ["prompt_a", "prompt_b", "prompt_c", "prompt_d"]:
                    if key not in prompts or not prompts[key]:
                        prompts[key] = default_prompts.get(key, "")

                logger.info(f"Loaded {len(prompts)} prompts from Sheets for mode '{mode}'")

                # キャッシュに保存 (if method exists)
                if hasattr(prompt_manager, "save_prompts_to_cache"):
                    prompt_manager.save_prompts_to_cache(mode, prompts)

                return prompts
            else:
                logger.warning("Prompts sheet is empty or malformed, trying cache...")
                if hasattr(prompt_manager, "load_prompts_from_cache"):
                    cached_prompts = prompt_manager.load_prompts_from_cache(mode)
                    if cached_prompts:
                        return cached_prompts
                return self._get_default_prompts()

        except Exception as e:
            logger.error(f"Failed to load prompts from Sheets: {e}, trying cache...")
            # Sheets失敗時はキャッシュフォールバック
            if hasattr(prompt_manager, "load_prompts_from_cache"):
                cached_prompts = prompt_manager.load_prompts_from_cache(mode)
                if cached_prompts:
                    logger.info(f"Using cached prompts as fallback for mode '{mode}'")
                    return cached_prompts
            logger.warning("No cache available, returning default prompts")
            return self._get_default_prompts()

    def _find_mode_row(self, rows: List[List[str]], mode: str) -> Optional[int]:
        """モードに対応する行を検索

        Args:
            rows: スプレッドシートの行データ
            mode: 実行モード

        Returns:
            対応する行のインデックス（見つからない場合はNone）
        """
        mode_column_index = 0  # "mode"列は最初の列と仮定

        for i, row in enumerate(rows[1:], start=1):  # ヘッダー行をスキップ
            if len(row) > mode_column_index and row[mode_column_index].lower() == mode.lower():
                logger.info(f"Found mode-specific prompts for '{mode}' at row {i+1}")
                return i

        return None

    def update_prompt(self, prompt_name: str, prompt_content: str, mode: str = "daily") -> bool:
        """プロンプトを更新（動的プロンプト管理）

        Args:
            prompt_name: プロンプト名 (prompt_a, prompt_b, etc.)
            prompt_content: 新しいプロンプト内容
            mode: 対象モード

        Returns:
            更新成功時True
        """
        if not self.service:
            logger.warning("Sheets service not available")
            return False

        try:
            # 既存データを取得
            result = self._rate_limit_retry(
                self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range="prompts!A1:E10"
            ).execute()

            rows = result.get("values", [])
            if not rows:
                logger.error("Prompts sheet is empty")
                return False

            headers = rows[0]
            prompt_col_index = None

            # プロンプト列を検索
            for i, header in enumerate(headers):
                if header == prompt_name:
                    prompt_col_index = i
                    break

            if prompt_col_index is None:
                logger.error(f"Prompt '{prompt_name}' not found in headers")
                return False

            # モード行を検索
            mode_row_index = self._find_mode_row(rows, mode)
            if mode_row_index is None:
                logger.warning(f"Mode '{mode}' not found, updating default row")
                mode_row_index = 1

            # 行を更新
            while len(rows[mode_row_index]) <= prompt_col_index:
                rows[mode_row_index].append("")

            rows[mode_row_index][prompt_col_index] = prompt_content

            # スプレッドシートに書き戻し
            col_letter = chr(65 + prompt_col_index)  # A, B, C...
            range_name = f"prompts!{col_letter}{mode_row_index + 1}"

            self._rate_limit_retry(
                self.service.spreadsheets().values().update,
                spreadsheetId=self.sheet_id,
                range=range_name,
                valueInputOption="RAW",
                body={"values": [[prompt_content]]},
            ).execute()

            logger.info(f"Updated {prompt_name} for mode '{mode}'")
            return True

        except Exception as e:
            logger.error(f"Failed to update prompt: {e}")
            return False

    def record_prompt_used(self, run_id: str, prompt_name: str, prompt_content: str) -> bool:
        """実行時に使用したプロンプトを記録

        Args:
            run_id: 実行ID
            prompt_name: プロンプト名 (prompt_a, prompt_b, etc.)
            prompt_content: 使用したプロンプト内容

        Returns:
            記録成功時True
        """
        # run に prompt_a カラムがあるので、そこに記録
        field_name = prompt_name
        return self.update_run(run_id, **{field_name: prompt_content})

    def get_prompt_analytics(self) -> Dict[str, Any]:
        """プロンプトの使用分析データを取得

        Returns:
            プロンプトごとの使用統計
        """
        if not self.service:
            logger.warning("Sheets service not available")
            return {}

        try:
            # runs シートから最近の実行データを取得
            result = self._rate_limit_retry(
                self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range="runs!A:S"
            ).execute()

            rows = result.get("values", [])
            if len(rows) <= 1:
                return {"total_runs": 0, "prompts": {}}

            headers = rows[0]
            data_rows = rows[1:]

            # 統計情報を収集
            analytics = {
                "total_runs": len(data_rows),
                "successful_runs": sum(1 for row in data_rows if len(row) > 1 and row[1] == "completed"),
                "failed_runs": sum(1 for row in data_rows if len(row) > 1 and row[1] == "failed"),
                "prompts": {},
                "mode_distribution": {},
            }

            # モード別の集計
            mode_col_index = headers.index("mode") if "mode" in headers else 5
            for row in data_rows:
                if len(row) > mode_col_index:
                    mode = row[mode_col_index]
                    analytics["mode_distribution"][mode] = analytics["mode_distribution"].get(mode, 0) + 1

            logger.info(f"Analyzed {analytics['total_runs']} runs")
            return analytics

        except Exception as e:
            logger.error(f"Failed to get prompt analytics: {e}")
            return {}

    def create_prompt_version(self, prompt_name: str, version_note: str = "") -> bool:
        """プロンプトのバージョン管理（履歴保存）

        Args:
            prompt_name: プロンプト名
            version_note: バージョンメモ

        Returns:
            保存成功時True
        """
        if not self.service:
            logger.warning("Sheets service not available")
            return False

        try:
            # prompt_history シートを作成（存在しない場合）
            spreadsheet = self._rate_limit_retry(self.service.spreadsheets().get, spreadsheetId=self.sheet_id).execute()

            existing_sheets = [sheet["properties"]["title"] for sheet in spreadsheet["sheets"]]

            if "prompt_history" not in existing_sheets:
                self._create_sheet(
                    "prompt_history",
                    ["timestamp", "prompt_name", "mode", "prompt_content", "version_note", "created_by"],
                )

            # 現在のプロンプトを取得
            current_prompts = self.load_prompts("daily")
            if prompt_name not in current_prompts:
                logger.error(f"Prompt '{prompt_name}' not found")
                return False

            # 履歴に追加
            from datetime import datetime

            now = datetime.now().isoformat()

            history_row = [
                now,
                prompt_name,
                "daily",  # デフォルトモード
                current_prompts[prompt_name],
                version_note,
                "system",
            ]

            self._rate_limit_retry(
                self.service.spreadsheets().values().append,
                spreadsheetId=self.sheet_id,
                range="prompt_history!A:F",
                valueInputOption="RAW",
                body={"values": [history_row]},
            ).execute()

            logger.info(f"Saved version of {prompt_name} to history")
            return True

        except Exception as e:
            logger.error(f"Failed to create prompt version: {e}")
            return False

    def _get_default_prompts(self) -> Dict[str, str]:
        """デフォルトプロンプトを返す - 強化版（Radical Think）"""
        return get_sheet_prompt_defaults()

    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """最近の実行記録を取得

        Args:
            limit: 取得件数上限

        Returns:
            実行記録のリスト

        """
        try:
            result = self._rate_limit_retry(
                self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range="runs!A:S"
            ).execute()

            rows = result.get("values", [])
            if len(rows) <= 1:  # ヘッダー行のみ
                return []

            headers = rows[0] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []

            # 最新の記録から順に取得
            recent_runs = []
            for row in reversed(data_rows[-limit:]):
                run_data = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        run_data[header] = row[i]
                    else:
                        run_data[header] = ""
                recent_runs.append(run_data)

            return recent_runs

        except Exception as e:
            logger.error(f"Failed to get recent runs: {e}")
            return []

    def setup_sheets(self) -> bool:
        """Sheetsの初期セットアップ（シート作成等）

        Returns:
            セットアップ成功時True

        """
        try:
            # シート一覧を取得
            spreadsheet = self._rate_limit_retry(self.service.spreadsheets().get, spreadsheetId=self.sheet_id).execute()

            existing_sheets = [sheet["properties"]["title"] for sheet in spreadsheet["sheets"]]

            # 必要なシートが存在するかチェック
            required_sheets = {
                "runs": [
                    "run_id",
                    "status",
                    "started_at",
                    "finished_at",
                    "duration_sec",
                    "mode",
                    "prompt_a",
                    "search_results_json",
                    "script_text",
                    "audio_urls_json",
                    "stt_text",
                    "subtitle_srt",
                    "video_url",
                    "title",
                    "description",
                    "sources",
                    "thumbnail_url",
                    "first_comment",
                    "error_log",
                ],
                "prompts": ["mode", "prompt_a", "prompt_b", "prompt_c", "prompt_d"],
            }

            for sheet_name, headers in required_sheets.items():
                if sheet_name not in existing_sheets:
                    logger.info(f"Creating sheet: {sheet_name}")
                    self._create_sheet(sheet_name, headers)

            return True

        except Exception as e:
            logger.error(f"Failed to setup sheets: {e}")
            return False

    def _create_sheet(self, sheet_name: str, headers: List[str]):
        """新しいシートを作成

        Args:
            sheet_name: シート名
            headers: ヘッダー行

        """
        # シートを追加
        request_body = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}

        self._rate_limit_retry(
            self.service.spreadsheets().batchUpdate, spreadsheetId=self.sheet_id, body=request_body
        ).execute()

        # ヘッダー行を追加
        self._rate_limit_retry(
            self.service.spreadsheets().values().update,
            spreadsheetId=self.sheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()

        # プロンプトシートの場合、デフォルトモードを追加
        if sheet_name == "prompts":
            self._initialize_default_prompt_modes()

        logger.info(f"Created sheet '{sheet_name}' with headers")

    def _initialize_default_prompt_modes(self):
        """プロンプトシートにデフォルトモードを初期化"""
        try:
            default_prompts = self._get_default_prompts()

            # 各モードのデフォルトプロンプトを設定
            modes_data = [
                [
                    "daily",
                    default_prompts["prompt_a"],
                    default_prompts["prompt_b"],
                    default_prompts["prompt_c"],
                    default_prompts["prompt_d"],
                ],
                ["special", "", "", "", ""],  # 空白（dailyから継承）
                ["test", "", "", "", ""],  # 空白（dailyから継承）
            ]

            self._rate_limit_retry(
                self.service.spreadsheets().values().update,
                spreadsheetId=self.sheet_id,
                range="prompts!A2:E4",
                valueInputOption="RAW",
                body={"values": modes_data},
            ).execute()

            logger.info("Initialized default prompt modes (daily, special, test)")

        except Exception as e:
            logger.error(f"Failed to initialize default prompt modes: {e}")


# グローバルインスタンス
sheets_manager = SheetsManager() if settings.google_sheet_id else None


def get_sheets() -> Optional[SheetsManager]:
    """Sheets管理インスタンスを取得"""
    return sheets_manager


# 簡易アクセス関数
def create_run(mode: str = "daily") -> str:
    """実行記録作成の簡易関数"""
    if sheets_manager:
        return sheets_manager.create_run(mode)
    else:
        # フォールバック: ランダムID生成
        import time

        return f"fallback_{int(time.time())}"


def update_run(run_id: str, **fields) -> bool:
    """実行記録更新の簡易関数"""
    if sheets_manager:
        return sheets_manager.update_run(run_id, **fields)
    else:
        logger.warning(f"Sheets not available, skipping update for {run_id}")
        return False


def load_prompts(mode: str = "daily") -> Dict[str, str]:
    """プロンプト読み込みの簡易関数

    Args:
        mode: 実行モード (daily/special/test)

    Returns:
        プロンプトの辞書
    """
    if sheets_manager:
        return sheets_manager.load_prompts(mode)
    else:
        logger.warning("Sheets not available, using default prompts")
        return SheetsManager()._get_default_prompts()
