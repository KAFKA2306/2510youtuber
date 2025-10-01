"""
Google Sheets操作モジュール

実行ログとプロンプト管理のためのGoogle Sheets操作を提供します。
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.config import cfg

logger = logging.getLogger(__name__)

class SheetsManager:
    """Google Sheets操作クラス"""

    def __init__(self):
        self.service = None
        self.sheet_id = cfg.google_sheet_id
        self._connect()

    def _connect(self):
        """Google Sheets APIに接続"""
        try:
            creds_dict = cfg.google_credentials_json
            if not creds_dict:
                raise ValueError("Google credentials not configured")

            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )

            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Google Sheets connection established")

        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise

    def _rate_limit_retry(self, func, *args, **kwargs):
        """レート制限対応のリトライ機能付き実行"""
        import time
        import random

        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                # API呼び出し間隔を空ける
                time.sleep(0.1 + random.uniform(0, 0.1))
                return result

            except HttpError as e:
                if e.resp.status == 429 and attempt < max_retries - 1:  # Rate limit
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
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
        run_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        # runsシートに新しい行を追加
        values = [[
            run_id,           # run_id
            "processing",     # status
            now,             # started_at
            "",              # finished_at
            "",              # duration_sec
            mode,            # mode
            "",              # prompt_a
            "",              # search_results_json
            "",              # script_text
            "",              # audio_urls_json
            "",              # stt_text
            "",              # subtitle_srt
            "",              # video_url
            "",              # title
            "",              # description
            "",              # sources
            "",              # thumbnail_url
            "",              # first_comment
            ""               # error_log
        ]]

        try:
            self._rate_limit_retry(
                self.service.spreadsheets().values().append,
                spreadsheetId=self.sheet_id,
                range="runs!A:S",
                valueInputOption="RAW",
                body={"values": values}
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
        try:
            # 既存データを取得して対象行を特定
            result = self._rate_limit_retry(
                self.service.spreadsheets().values().get,
                spreadsheetId=self.sheet_id,
                range="runs!A:S"
            ).execute()

            rows = result.get('values', [])
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
                'status': 1,
                'finished_at': 3,
                'duration_sec': 4,
                'mode': 5,
                'prompt_a': 6,
                'search_results_json': 7,
                'script_text': 8,
                'audio_urls_json': 9,
                'stt_text': 10,
                'subtitle_srt': 11,
                'video_url': 12,
                'title': 13,
                'description': 14,
                'sources': 15,
                'thumbnail_url': 16,
                'first_comment': 17,
                'error_log': 18
            }

            for field, value in fields.items():
                if field in field_mapping:
                    col_index = field_mapping[field]

                    # JSONオブジェクトは文字列化
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    elif value is None:
                        value = ""

                    current_row[col_index] = str(value)

            # 自動で finished_at を設定
            if fields.get('status') == 'completed' and 'finished_at' not in fields:
                current_row[3] = datetime.now().isoformat()

            # 更新実行
            range_name = f"runs!A{target_row_index + 1}:S{target_row_index + 1}"
            self._rate_limit_retry(
                self.service.spreadsheets().values().update,
                spreadsheetId=self.sheet_id,
                range=range_name,
                valueInputOption="RAW",
                body={"values": [current_row]}
            ).execute()

            logger.info(f"Updated run {run_id}: {list(fields.keys())}")
            return True

        except Exception as e:
            logger.error(f"Failed to update run {run_id}: {e}")
            return False

    def load_prompts(self) -> Dict[str, str]:
        """プロンプトテンプレートを読み込み

        Returns:
            プロンプトの辞書 {prompt_a: "...", prompt_b: "...", ...}
        """
        try:
            result = self._rate_limit_retry(
                self.service.spreadsheets().values().get,
                spreadsheetId=self.sheet_id,
                range="prompts!A1:E2"
            ).execute()

            rows = result.get('values', [])
            if len(rows) >= 2:
                headers = rows[0]
                values = rows[1]

                # ヘッダーと値をマッピング
                prompts = {}
                for i, header in enumerate(headers):
                    if i < len(values):
                        prompts[header] = values[i]

                logger.info(f"Loaded {len(prompts)} prompts")
                return prompts
            else:
                logger.warning("Prompts sheet is empty or malformed")
                return self._get_default_prompts()

        except Exception as e:
            logger.error(f"Failed to load prompts: {e}")
            return self._get_default_prompts()

    def _get_default_prompts(self) -> Dict[str, str]:
        """デフォルトプロンプトを返す"""
        return {
            "prompt_a": """
今日の重要な経済ニュースを3-5件収集し、各項目について以下の情報を含めてください：
- タイトル
- 出典URL（実在するもの）
- 要約（200-300文字）
- 重要ポイント（2-3点）
- 情報源名

信頼性の高い経済メディア（日経、ロイター、Bloomberg等）からの情報を優先してください。
""",

            "prompt_b": """
以下のニュース要約をもとに、二人の専門家による対談形式の台本を作成してください：

要件：
- 田中氏と鈴木氏の自然な対談
- 各ニュースについて根拠を示しながら分析
- 出典を必ず明記
- 聞き手にとって理解しやすい説明
- 総時間25-35分程度（約8000-12000文字）
- 話し言葉調で自然な流れ
""",

            "prompt_c": """
動画のメタデータを生成してください：

台本の内容を元に以下を作成：
- タイトル（70文字以内、SEOを意識）
- 説明文（視聴者の興味を引く、出典情報含む）
- タグ（関連キーワード5-10個）
- 出典情報の整理された一覧

JSON形式で出力してください。
""",

            "prompt_d": """
この動画を聞いている女の子の立場で、最初のコメントを生成してください：

- キャラクター：経済に詳しい毒舌な女の子
- 50-100文字程度
- 動画の内容に関連した軽妙なコメント
- 親しみやすい口調
"""
        }

    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """最近の実行記録を取得

        Args:
            limit: 取得件数上限

        Returns:
            実行記録のリスト
        """
        try:
            result = self._rate_limit_retry(
                self.service.spreadsheets().values().get,
                spreadsheetId=self.sheet_id,
                range="runs!A:S"
            ).execute()

            rows = result.get('values', [])
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
            spreadsheet = self._rate_limit_retry(
                self.service.spreadsheets().get,
                spreadsheetId=self.sheet_id
            ).execute()

            existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]

            # 必要なシートが存在するかチェック
            required_sheets = {
                'runs': [
                    'run_id', 'status', 'started_at', 'finished_at', 'duration_sec',
                    'mode', 'prompt_a', 'search_results_json', 'script_text',
                    'audio_urls_json', 'stt_text', 'subtitle_srt', 'video_url',
                    'title', 'description', 'sources', 'thumbnail_url',
                    'first_comment', 'error_log'
                ],
                'prompts': ['prompt_a', 'prompt_b', 'prompt_c', 'prompt_d']
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
        request_body = {
            'requests': [{
                'addSheet': {
                    'properties': {
                        'title': sheet_name
                    }
                }
            }]
        }

        self._rate_limit_retry(
            self.service.spreadsheets().batchUpdate,
            spreadsheetId=self.sheet_id,
            body=request_body
        ).execute()

        # ヘッダー行を追加
        self._rate_limit_retry(
            self.service.spreadsheets().values().update,
            spreadsheetId=self.sheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [headers]}
        ).execute()

        logger.info(f"Created sheet '{sheet_name}' with headers")

# グローバルインスタンス
sheets_manager = SheetsManager() if cfg.google_sheet_id else None

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

def load_prompts() -> Dict[str, str]:
    """プロンプト読み込みの簡易関数"""
    if sheets_manager:
        return sheets_manager.load_prompts()
    else:
        logger.warning("Sheets not available, using default prompts")
        return SheetsManager()._get_default_prompts()