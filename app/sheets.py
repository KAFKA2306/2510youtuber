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
        """レート制限対応のリトライ機能付き実行"""
        import random
        import time

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
                        logger.warning(f"Field '{field}' truncated from {len(str(value))} to {len(str_value)} characters")

                    current_row[col_index] = str_value

            # 自動で finished_at を設定
            if fields.get("status") == "completed" and "finished_at" not in fields:
                current_row[3] = datetime.now().isoformat()

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
            cached_prompts = prompt_manager.load_prompts_from_cache(mode) # PromptManagerにキャッシュ機能がある場合
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

                # キャッシュに保存
                prompt_manager.save_prompts_to_cache(mode, prompts)

                return prompts
            else:
                logger.warning("Prompts sheet is empty or malformed, trying cache...")
                cached_prompts = prompt_manager.load_prompts_from_cache(mode)
                if cached_prompts:
                    return cached_prompts
                return self._get_default_prompts()

        except Exception as e:
            logger.error(f"Failed to load prompts from Sheets: {e}, trying cache...")
            # Sheets失敗時はキャッシュフォールバック
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
                self.service.spreadsheets().values().get,
                spreadsheetId=self.sheet_id,
                range="prompts!A1:E10"
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
                self.service.spreadsheets().values().get,
                spreadsheetId=self.sheet_id,
                range="runs!A:S"
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
            spreadsheet = self._rate_limit_retry(
                self.service.spreadsheets().get,
                spreadsheetId=self.sheet_id
            ).execute()

            existing_sheets = [sheet["properties"]["title"] for sheet in spreadsheet["sheets"]]

            if "prompt_history" not in existing_sheets:
                self._create_sheet("prompt_history", [
                    "timestamp", "prompt_name", "mode", "prompt_content", "version_note", "created_by"
                ])

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
                "system"
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
        return {
            "prompt_a": """
【超高品質ニュース収集 - Radical Research Protocol】

あなたは世界最高峰の経済アナリストです。今日の市場を動かす本当に重要なニュースを発掘してください。

🎯 収集基準（優先度順）：
1. **市場インパクト**: 株価・為替・商品市場に直接影響を与える情報
2. **時間的価値**: 24時間以内の最新情報を優先
3. **情報の独自性**: 他メディアが見逃している視点・データ
4. **投資家関連性**: 投資判断に直接役立つ具体的な情報
5. **グローバル連鎖**: 日本経済への波及効果が明確な国際情報

📊 必須要素（各ニュース）：
- タイトル: 具体的な数値・固有名詞を含む（例: 「日経平均、3万円突破」）
- 出典URL: 必ず実在する信頼できるメディアのURL
- 要約: 200-400文字、5W1Hを明確に
- 重要ポイント: 3-5点、数値・データを具体的に
- 情報源: Tier1メディア（日経、Reuters、Bloomberg、FT、WSJ等）
- 市場反応: 実際の株価・為替の動き（可能な場合）
- 専門家見解: アナリストコメントがあれば引用

🔍 推奨情報源の優先順位：
Tier 1: Bloomberg, Reuters, 日本経済新聞, Financial Times, Wall Street Journal
Tier 2: CNBC, Nikkei Asia, 東洋経済, ダイヤモンド, Forbes
Tier 3: Yahoo Finance, MarketWatch, Investing.com

⚡ Radical Thinking Points:
- 表面的なニュースではなく、その背後にある構造的変化を捉える
- 複数のニュースを繋げて見えてくるトレンドを意識
- 反対意見・異なる視点も含めて多角的に
- 短期的インパクトと長期的意味の両方を考慮
- データの出所と信頼性を常に検証

収集件数: 3-5件（質を優先、量より質）
""",
            "prompt_b": """
【超高品質台本生成 - Radical Dialogue Creation】

あなたは世界最高のコンテンツクリエイターです。視聴者を惹きつけ、価値を提供する対談を創造してください。

🎭 登場人物の明確化：
- 田中氏: ベテラン経済評論家（マクロ経済・政策に強い、冷静で論理的）
- 鈴木氏: 実践派金融アナリスト（市場・投資に強い、情熱的で具体的）

📝 台本構成の黄金律（8分バージョン = 約2400文字）：
1. オープニング（300字・1分）: 今日のテーマの重要性を端的に
2. メインニュース1（800字・2.5分）: 最重要ニュースを深堀り
3. メインニュース2（700字・2分）: 第二の重要ニュースを分析
4. サブニュース（400字・1.5分）: 補足的な話題を簡潔に
5. クロージング（200字・1分）: 今日のポイントと視聴者へのメッセージ

💡 Radical Dialogue 10の法則：
1. **具体性の法則**: 抽象的な表現NG、必ず数値・固有名詞で語る
2. **対立の法則**: 異なる視点の対立構造を作り、議論を深める
3. **緊張感の法則**: 「実は...」「しかし...」で展開に緊張感を持たせる
4. **共感の法則**: 視聴者の疑問を先読みして答える
5. **リズムの法則**: 短文と長文を交互に、テンポよく
6. **証拠の法則**: すべての主張に出典・データの裏付けを
7. **予測の法則**: 「今後どうなるか」を必ず語る
8. **比較の法則**: 過去のデータ・他国との比較で理解を深める
9. **感情の法則**: 事実+感情表現で人間味を出す（驚き・懸念等）
10. **行動の法則**: 視聴者が何をすべきかのヒントを提供

🎯 必須要素：
- 出典を自然に会話に織り込む（例: 「Bloombergの報道によると」）
- 数値は具体的に（例: 「約2%」ではなく「2.1%」）
- 専門用語は必ず平易な言葉で補足説明
- 視聴者への問いかけ（例: 「皆さんはどう思いますか？」）
- ニュース間の関連性・因果関係を明示

🚫 絶対NGリスト：
- 抽象的な表現（「多くの」→具体的な数字を）
- 根拠のない推測（必ず「〜と言われています」等のソース明記）
- 一方的な意見（必ず複数の視点を）
- 専門用語の説明なし（必ず解説を）
- 淡々とした報告調（感情と人間味を）

⚡ Radical Thinking Points:
- 単なる事実の羅列ではなく、「なぜ？」「どう影響する？」を掘り下げる
- 視聴者が「なるほど！」と膝を打つ洞察を最低3つ盛り込む
- 対談の流れに自然なドラマ性（起承転結）を持たせる
- 最後に視聴者が行動したくなるような締めくくりを

文字数目安: 約2400文字（8分想定）※調整可能
トーン: プロフェッショナルでありながら親しみやすく、熱量がある
""",
            "prompt_c": """
【超高品質メタデータ生成 - Radical SEO Optimization】

あなたは世界最高のYouTube SEOスペシャリストです。クリック率と視聴維持率を最大化するメタデータを作成してください。

🎯 タイトル作成の黄金律（60-70文字）：
1. **数値を含める**: 具体的な数字は注目を集める
2. **固有名詞**: 企業名・人名・地名で具体性を
3. **緊急性**: 「速報」「最新」「今」等のタイムリー感
4. **感情喚起**: 「驚愕」「注意」「チャンス」等（使いすぎ注意）
5. **SEOキーワード**: 主要キーワードを前半30文字以内に

良いタイトル例:
✅ 「日経平均3万円突破！その裏で起きている3つの構造変化【2025年経済展望】」
✅ 「米利下げ観測で円高加速｜投資家が今すぐ確認すべき5つのポイント」
❌ 「今日の経済ニュースまとめ」（抽象的すぎ）
❌ 「株価が上昇しています」（具体性なし）

📄 説明文の戦略（5000文字まで使える）：
構成:
1. **フック**（最初の2行・150文字）: YouTubeが表示する部分、最も重要
2. **内容サマリー**（300文字）: 動画で語られる内容を箇条書きで
3. **タイムスタンプ**（任意）: 長い動画の場合
4. **出典リスト**（必須）: すべての情報源のURL
5. **関連リンク**: 過去動画・参考資料へのリンク
6. **ハッシュタグ**: #経済ニュース #投資 #株式市場 等

フックの黄金パターン:
「【衝撃】〜という事実をご存知ですか？この動画では...」
「投資家必見！〜について徹底解説します」
「なぜ今〜が注目されているのか？3つの理由とは...」

🏷️ タグ戦略（50個まで設定可能）：
優先順位:
1. **メインキーワード**: 経済ニュース、株式投資、為替相場 等
2. **固有名詞**: 企業名、人名、政策名 等
3. **関連キーワード**: 初心者向け、解説、分析 等
4. **ロングテール**: 「日経平均 今後の見通し」等のフレーズ
5. **競合分析**: 同ジャンルの人気動画のタグを研究

📊 JSON出力形式：
```json
{
  "title": "最適化されたタイトル（60-70文字）",
  "description": "完璧な説明文（改行・リンク含む）",
  "tags": ["タグ1", "タグ2", ...],
  "category": "News & Politics",
  "sources": [
    {"name": "情報源名", "url": "https://..."},
    ...
  ],
  "hashtags": ["#ハッシュタグ1", "#ハッシュタグ2", ...],
  "thumbnail_text": "サムネイルに入れるべきテキスト（15文字以内）",
  "hook_line": "最初の2行のフック文"
}
```

⚡ Radical Thinking Points:
- 競合動画の分析結果を反映
- トレンドキーワードを積極的に活用
- クリックしたくなる「情報の空白」を作る
- 視聴者の検索意図を深く理解する
""",
            "prompt_d": """
【超高品質コメント生成 - Radical Engagement Creation】

あなたは世界最高のコミュニティマネージャーです。エンゲージメントを最大化する最初のコメントを作成してください。

👧 キャラクター設定（経済女子・ユイ）：
- 年齢: 20代後半、金融系企業勤務
- 性格: 頭脳明晰だが毒舌、でも愛嬌あり
- 特徴: 数字に強い、トレンドに敏感、時々ツッコミが鋭い
- 口調: 「です・ます」調だが時々砕けた表現
- 絵文字: 適度に使用（使いすぎ注意）

💬 コメント作成の黄金律：
1. **長さ**: 50-120文字（読みやすく、でも薄くない）
2. **内容パターン**:
   - 動画内容への鋭い指摘（80%）
   - 視聴者への問いかけ（20%）
3. **トーン**: 親しみやすいが知的、時に批判的だが建設的

良いコメント例:
✅ 「田中さんの『構造変化』って指摘、めっちゃ的確ですね。でも鈴木さんの楽観論、ちょっと甘すぎません？笑 皆さんはどっち派ですか？」（76文字）
✅ 「3万円突破のニュース、表面的には良いけど、出来高見たら...って感じですよね。冷静に分析してくれてありがとうございます！」（67文字）
✅ 「この円高、想定してた人どれくらいいます？私は完全にノーマークでした💦 田中先生の解説、めちゃくちゃ勉強になります」（64文字）

❌ NGコメント例:
❌ 「勉強になりました！」（薄すぎ）
❌ 「面白かったです」（具体性なし）
❌ 「次回も楽しみにしています」（定型文すぎ）

⚡ Radical Thinking Points:
- 動画の核心を突く一言を
- 視聴者が「返信したくなる」問いかけを入れる
- 適度な批判的視点で議論を活性化
- 数字・具体的な用語を使って専門性を示す
- 共感と知性のバランスを取る

出力形式: プレーンテキスト1行、50-120文字
""",
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
                ["daily", default_prompts["prompt_a"], default_prompts["prompt_b"],
                 default_prompts["prompt_c"], default_prompts["prompt_d"]],
                ["special", "", "", "", ""],  # 空白（dailyから継承）
                ["test", "", "", "", ""],      # 空白（dailyから継承）
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
