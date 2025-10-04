"""台本生成モジュール

ニュース要約から対談形式の台本を生成します。
3段階品質チェックシステムに対応しています。
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List

import google.generativeai as genai

from .api_rotation import get_rotation_manager
from .config import cfg

logger = logging.getLogger(__name__)

# 3段階品質チェックシステムのインポート
try:
    from .script_quality import three_stage_generator

    HAS_QUALITY_CHECK = three_stage_generator is not None
    if HAS_QUALITY_CHECK:
        logger.info("3-stage quality check system is available")
except ImportError:
    HAS_QUALITY_CHECK = False
    logger.warning("3-stage quality check system not available")

# 日本語品質チェックシステムのインポート
try:
    from .japanese_quality import check_script_japanese_purity, improve_japanese_quality

    HAS_JAPANESE_QUALITY_CHECK = True
    logger.info("Japanese quality check system is available")
except ImportError:
    HAS_JAPANESE_QUALITY_CHECK = False
    logger.warning("Japanese quality check system not available")


class ScriptGenerator:
    """台本生成クラス"""

    def __init__(self):
        self.client = None
        self._setup_client()

    def _setup_client(self):
        """Gemini APIクライアントを初期化

        Note: キー登録は main.py の initialize_api_infrastructure() で実行済み
        """
        try:
            # Rotation managerは既に初期化されていることを前提
            # キー登録は不要（main.pyで実行済み）
            self.client = None
            logger.info("Script generator ready (using shared rotation manager)")

        except Exception as e:
            logger.error(f"Failed to initialize script generator: {e}")
            raise

    def generate_dialogue(
        self,
        news_items: List[Dict[str, Any]],
        prompt_b: str = None,
        target_duration_minutes: int = 8,
        use_quality_check: bool = True,
        use_enhanced_template: bool = True,
    ) -> str:
        """ニュース項目から対談台本を生成

        Args:
            news_items: ニュース項目のリスト
            prompt_b: 台本生成用プロンプト（Noneの場合は強化テンプレート使用）
            target_duration_minutes: 目標動画長（分、デフォルト8分に変更）
            use_quality_check: 3段階品質チェックを使用するか
            use_enhanced_template: 強化テンプレート（kafkaスタイル）を使用するか

        Returns:
            対談形式の台本テキスト

        """
        # 強化テンプレートの使用 (disabled - script_templates removed)
        if use_enhanced_template and prompt_b is None:
            logger.warning("Enhanced template disabled (script_templates module removed)")
            use_enhanced_template = False
            if prompt_b is None:
                prompt_b = self._get_default_prompt()
        # 3段階品質チェックを使用（有効な場合）
        if use_quality_check and HAS_QUALITY_CHECK:
            logger.info("Using 3-stage quality check system")
            try:
                result = three_stage_generator.generate_high_quality_script(
                    news_items, prompt_b, target_duration_minutes
                )

                if result["success"]:
                    logger.info(
                        f"3-stage generation succeeded: "
                        f"Quality={result['quality_score']}/10, "
                        f"Iterations={result['iterations']}"
                    )
                    final_script = result["final_script"]

                    # 日本語品質チェック＆改善
                    final_script = self._ensure_pure_japanese(final_script)

                    return final_script
                else:
                    logger.warning(f"3-stage generation failed: {result.get('error')}, falling back to standard")
            except Exception as e:
                logger.warning(f"3-stage generation error: {e}, falling back to standard")

        # 標準的な生成プロセス
        try:
            news_summary = self._format_news_for_script(news_items)
            full_prompt = self._build_script_prompt(news_summary, prompt_b, target_duration_minutes)
            script = self._call_gemini_for_script(full_prompt)
            cleaned_script = self._clean_script(script)

            if self._validate_script_quality(cleaned_script, target_duration_minutes):
                logger.info(f"Generated script: {len(cleaned_script)} characters")

                # 日本語品質チェック＆改善
                cleaned_script = self._ensure_pure_japanese(cleaned_script)

                return cleaned_script
            else:
                logger.warning("Script quality validation failed, retrying with simplified prompt")
                return self._get_fallback_script_with_api(news_items, target_duration_minutes)

        except Exception as e:
            logger.error(f"Failed to generate script: {e}")
            return self._get_fallback_script_with_api(news_items, target_duration_minutes)

    def _format_news_for_script(self, news_items: List[Dict[str, Any]]) -> str:
        """ニュース項目を台本生成用に整形"""
        formatted_sections = []
        for i, item in enumerate(news_items, 1):
            section = f"""
【ニュース{i}】{item.get("title", "無題")}
出典: {item.get("source", "不明")} ({item.get("url", "")})
影響度: {item.get("impact_level", "medium")}
カテゴリ: {item.get("category", "経済")}

要約:
{item.get("summary", "")}

重要ポイント:
"""
            key_points = item.get("key_points", [])
            for point in key_points:
                section += f"- {point}\n"
            formatted_sections.append(section)
        return "\n".join(formatted_sections)

    def _build_script_prompt(self, news_summary: str, base_prompt: str, target_duration: int) -> str:
        """台本生成用の詳細プロンプトを構築"""
        target_chars = target_duration * 300
        full_prompt = f"""
{base_prompt}

【今回のニュース情報】
{news_summary}

【台本作成要件】
1. 目標時間: {target_duration}分（約{target_chars}文字）
2. 構成: オープニング → ニュース解説 → まとめ
3. 話者: 田中氏（経済専門家）、鈴木氏（金融アナリスト）
4. トーン: 専門的だが理解しやすい、時々軽妙な掛け合い

【重要な制約】
- 出典を必ず明記（「○○によると」「○○の報道では」等）
- 数値やデータは具体的に言及
- 推測と事実を明確に区別
- 聞き手の理解を助ける解説を含める
- 自然な会話の流れを保つ

【言語に関する重要な指示】
- すべての内容を純粋な日本語で記述してください
- 英語の単語や表現を使用しないでください
- 専門用語は理解しやすい日本語で説明を加えてください
- AI、GDP、ITなどの一般的な略語のみ使用可能
- 視聴者が理解できない英語が混じらないように注意してください

【台本フォーマット】
田中: [発言内容]
鈴木: [発言内容]

【構成例】
1. オープニング（2-3分）: 今日のトピック紹介
2. ニュース1解説（8-10分）: 詳細分析と背景
3. ニュース2解説（8-10分）: 詳細分析と背景
4. ニュース3解説（5-7分）: 簡潔な解説
5. 全体まとめ（3-5分）: 今日のポイント整理

現在の日時: {datetime.now().strftime("%Y年%m月%d日 %H時")}

上記の要件に従って、自然で情報価値の高い対談台本を作成してください。
特に、視聴者が理解しやすいよう、すべて日本語で明瞭に記述してください。
"""
        return full_prompt

    def _call_gemini_for_script(self, prompt: str, max_retries: int = 3) -> str:
        """台本生成用Gemini API呼び出し（キーローテーション対応）"""
        rotation_manager = get_rotation_manager()

        def api_call_with_key(api_key: str) -> str:
            """単一APIキーでの呼び出し"""
            try:
                # キーごとにクライアントを再設定
                genai.configure(api_key=api_key)
                model_name = cfg.gemini_models.get("script_generation")
                client = genai.GenerativeModel(f"models/{model_name}")

                # リクエストタイムアウトを設定（120秒）
                generation_config = genai.GenerationConfig(
                    temperature=0.9,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                )

                response = client.generate_content(prompt, generation_config=generation_config, timeout=120)
                content = response.text
                logger.debug(f"Generated script length: {len(content)}")
                return content

            except Exception as e:
                error_str = str(e).lower()

                # Rate limitエラーを検出して再raiseして上位でハンドリング
                if any(kw in error_str for kw in ["429", "rate limit", "quota"]):
                    logger.warning(f"Gemini rate limit detected: {e}")
                    raise  # ローテーションマネージャーがハンドリング

                # 504/timeout エラー
                if any(kw in error_str for kw in ["504", "deadline exceeded", "timeout"]):
                    logger.warning(f"Gemini timeout detected: {e}")
                    raise

                # その他のエラー
                logger.warning(f"Gemini API error: {e}")
                raise

        # キーローテーション実行
        try:
            return rotation_manager.execute_with_rotation(
                provider="gemini", api_call=api_call_with_key, max_attempts=max_retries
            )
        except Exception as e:
            logger.error(f"All Gemini API attempts failed: {e}")
            raise Exception("Gemini API failed with all keys")

    def _clean_script(self, raw_script: str) -> str:
        """台本テキストのクリーニング"""
        script = raw_script.strip()
        patterns_to_remove = [
            r"^.*?以下.*?台本.*?[:：]\s*",
            r"^.*?対談.*?[:：]\s*",
            r"^.*?スクリプト.*?[:：]\s*",
        ]
        for pattern in patterns_to_remove:
            script = re.sub(pattern, "", script, flags=re.IGNORECASE | re.MULTILINE)
        script = re.sub(r"田中[氏さん]*[:：]", "田中:", script)
        script = re.sub(r"鈴木[氏さん]*[:：]", "鈴木:", script)
        script = re.sub(r"\n\s*\n\s*\n+", "\n\n", script)
        script = re.sub(r"[^\w\s\n\r！？。、：（）「」『』【】\-\+\*\/\%\$\&\#\.]+", "", script)
        return script.strip()

    def _ensure_pure_japanese(self, script: str) -> str:
        """日本語純度を確保

        英語が混入している場合、自動的に修正します。
        """
        # 設定で無効化されている場合はスキップ
        if not cfg.use_japanese_quality_check:
            logger.info("Japanese quality check is disabled in config")
            return script

        if not HAS_JAPANESE_QUALITY_CHECK:
            logger.warning("Japanese quality check not available, skipping")
            return script

        try:
            # 日本語純度チェック
            purity_result = check_script_japanese_purity(script)

            # 閾値をチェック
            if purity_result["purity_score"] >= cfg.japanese_purity_threshold:
                logger.info(f"Script passes Japanese purity check (score: {purity_result['purity_score']:.1f})")
                return script

            # 改善が必要
            logger.warning(
                f"Script contains {purity_result['total_issues']} English issues, "
                f"purity score: {purity_result['purity_score']:.1f} (threshold: {cfg.japanese_purity_threshold})"
            )

            # 自動改善を試みる
            improvement_result = improve_japanese_quality(script)

            if improvement_result["success"] and improvement_result.get("changes_made"):
                logger.info(
                    f"Japanese quality improved: "
                    f"{improvement_result['original_score']:.1f} -> {improvement_result['new_score']:.1f}"
                )
                return improvement_result["improved_script"]
            else:
                logger.warning("Could not improve Japanese quality, using original")
                return script

        except Exception as e:
            logger.error(f"Japanese quality check failed: {e}")
            return script

    def _validate_script_quality(self, script: str, target_duration: int) -> bool:
        """台本の品質を検証"""
        try:
            min_chars = target_duration * 150  # 緩和: 200 -> 150
            max_chars = target_duration * 500  # 緩和: 400 -> 500
            if not (min_chars <= len(script) <= max_chars):
                logger.warning(f"Script length {len(script)} not in range {min_chars}-{max_chars}")
                return False
            tanaka_lines = len(re.findall(r"^田中:", script, re.MULTILINE))
            suzuki_lines = len(re.findall(r"^鈴木:", script, re.MULTILINE))
            if tanaka_lines < 3 or suzuki_lines < 3:  # 緩和: 5 -> 3
                logger.warning(f"Insufficient dialogue lines: 田中={tanaka_lines}, 鈴木={suzuki_lines}")
                return False
            if max(tanaka_lines, suzuki_lines) == 0:
                return False
            line_ratio = min(tanaka_lines, suzuki_lines) / max(tanaka_lines, suzuki_lines)
            if line_ratio < 0.2:  # 緩和: 0.3 -> 0.2
                logger.warning(f"Unbalanced dialogue ratio: {line_ratio}")
                return False
            # システムエラーメッセージを含んでいないかチェック
            error_patterns = [
                r"システムに問題が発生",
                r"システムエラー",
                r"技術的な問題",
                r"手動での確認をお願いします",
            ]
            for pattern in error_patterns:
                if re.search(pattern, script):
                    logger.warning(f"Script contains error message: {pattern}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Script validation error: {e}")
            return False

    def _get_fallback_script_with_api(self, news_items: List[Dict[str, Any]], target_duration_minutes: int = 30) -> str:
        """APIを使用してフォールバック台本を生成"""
        try:
            logger.info("Generating fallback script with simplified API prompt")
            news_summary = self._format_news_for_script(news_items)

            simplified_prompt = f"""
以下のニュース情報をもとに、田中氏（経済専門家）と鈴木氏（金融アナリスト）の対談形式の台本を作成してください。

【ニュース情報】
{news_summary}

【重要な指示】
1. 目標文字数: {target_duration_minutes * 300}文字程度
2. 必ず「田中:」と「鈴木:」の形式で対談を記述
3. 各ニュースについて具体的な分析と解説を含める
4. 出典を明記し、データや数値を具体的に言及
5. 投資家や視聴者にとって価値のある情報を提供

【台本形式の例】
田中: 皆さん、こんにちは。{datetime.now().strftime("%Y年%m月%d日")}の経済ニュース分析をお届けします。

鈴木: 今日は重要なニュースがありますね。詳しく見ていきましょう。

台本を作成してください。
"""

            script = self._call_gemini_for_script(simplified_prompt, max_retries=2)
            cleaned_script = self._clean_script(script)

            if len(cleaned_script) > 500:
                logger.info(f"Fallback script generated successfully: {len(cleaned_script)} characters")
                return cleaned_script
            else:
                logger.warning("API fallback failed, using template-based fallback")
                return self._get_template_fallback_script(news_items)

        except Exception as e:
            logger.error(f"API fallback failed: {e}")
            return self._get_template_fallback_script(news_items)

    def _get_template_fallback_script(self, news_items: List[Dict[str, Any]]) -> str:
        """フォールバック用の基本台本（詳細な分析を含む）"""
        current_date = datetime.now().strftime("%Y年%m月%d日")
        script = f"""田中: 皆さん、こんにちは。{current_date}の経済ニュース分析をお届けします。今日は私、田中と、

鈴木: 金融アナリストの鈴木がお送りします。今日は重要なニュースがいくつか入ってきていますね。

田中: そうですね。では早速、今日のトピックを詳しく見ていきましょう。
"""
        for i, item in enumerate(news_items, 1):
            title = item.get("title", f"ニュース{i}")
            summary = item.get("summary", "詳細情報を確認中です。")
            source = item.get("source", "情報源不明")
            key_points = item.get("key_points", [])

            script += f"""
田中: {i}番目のニュースです。{title}について、{source}からの報道です。

鈴木: {summary}

田中: この件について、詳しく分析していきましょう。"""

            if key_points:
                script += "\n\n鈴木: 重要なポイントをまとめますと、"
                for idx, point in enumerate(key_points, 1):
                    if idx == 1:
                        script += f"{point}"
                    elif idx == len(key_points):
                        script += f"、そして{point}という点が挙げられます。"
                    else:
                        script += f"、{point}"

                script += "\n\n田中: なるほど。この動きは市場にどのような影響を与えるでしょうか。"
                script += f"\n\n鈴木: {source}の報道によれば、"

                impact_analysis = self._generate_impact_analysis(item)
                script += impact_analysis
            else:
                script += "\n\n鈴木: この件については、引き続き詳細な情報を収集していく必要がありますね。"

            script += "\n\n田中: 投資家の皆様は、この動向を注視していく必要がありそうですね。\n"

        script += """
鈴木: 今日ご紹介したニュースは、いずれも今後の市場動向を左右する重要なものばかりです。

田中: そうですね。特に短期的な市場の変動には注意が必要です。投資判断は慎重に行ってください。

鈴木: 最新の情報については、信頼できる情報源を定期的にチェックすることをお勧めします。

田中: 本日の経済ニュース分析は以上となります。次回もお楽しみに。

鈴木: ありがとうございました。

田中: ありがとうございました。
"""
        return script

    def _generate_impact_analysis(self, news_item: Dict[str, Any]) -> str:
        """ニュース項目から影響分析を生成"""
        impact_level = news_item.get("impact_level", "medium")
        category = news_item.get("category", "経済")

        if impact_level == "high":
            return f"短期的には市場の変動が予想されます。{category}セクターへの影響が特に大きいと見られており、投資家は注意深く動向を見守る必要があります。"
        elif impact_level == "medium":
            return f"{category}セクターを中心に、一定の影響が見込まれます。中長期的な視点での分析が重要になってきます。"
        else:
            return f"限定的ではありますが、{category}分野における今後の動きに注目が集まっています。"

    def generate_short_script(self, topic: str, duration_minutes: int = 10) -> str:
        """短尺の特定トピック用台本を生成"""
        prompt = f"""
以下のトピックについて、{duration_minutes}分程度の対談形式台本を作成してください：

トピック: {topic}

要件:
- 田中氏と鈴木氏の対談形式
- 約{duration_minutes * 300}文字程度
- 専門的だが理解しやすい内容
- 具体的なデータや事例を含める

台本形式:
田中: [発言内容]
鈴木: [発言内容]
"""
        try:
            response = self._call_gemini_for_script(prompt)
            return self._clean_script(response)
        except Exception as e:
            logger.error(f"Failed to generate short script for '{topic}': {e}")
            return self._get_template_fallback_script(
                [
                    {
                        "title": topic,
                        "summary": f"{topic}に関する重要な動向について解説します。",
                        "source": "各種報道",
                        "key_points": [f"{topic}の最新動向", "市場への影響", "今後の展望"],
                        "impact_level": "medium",
                        "category": "経済",
                    }
                ]
            )


# グローバルインスタンス
script_generator = ScriptGenerator() if cfg.gemini_api_key else None


def generate_dialogue(
    news_items: List[Dict[str, Any]], prompt_b: str, target_duration_minutes: int = 30, use_quality_check: bool = True
) -> str:
    """台本生成の簡易関数

    Args:
        news_items: ニュース項目のリスト
        prompt_b: 台本生成用プロンプト
        target_duration_minutes: 目標動画長（分）
        use_quality_check: 3段階品質チェックを使用するか（デフォルト: True）
    """
    if script_generator:
        return script_generator.generate_dialogue(news_items, prompt_b, target_duration_minutes, use_quality_check)
    else:
        logger.warning("Script generator not available, using template fallback")
        return ScriptGenerator()._get_template_fallback_script(news_items)


def generate_short_script(topic: str, duration_minutes: int = 10) -> str:
    """短尺台本生成の簡易関数"""
    if script_generator:
        return script_generator.generate_short_script(topic, duration_minutes)
    else:
        logger.warning("Script generator not available, using template fallback")
        return ScriptGenerator()._get_template_fallback_script(
            [
                {
                    "title": topic,
                    "summary": f"{topic}についての解説です。",
                    "source": "各種報道",
                    "key_points": [f"{topic}の概要", "重要ポイント"],
                    "impact_level": "medium",
                    "category": "経済",
                }
            ]
        )


if __name__ == "__main__":
    print("Testing script generation...")
    if cfg.gemini_api_key:
        test_news = [
            {
                "title": "日経平均株価が年初来高値を更新",
                "summary": "東京株式市場で日経平均株価が前日比2.1%上昇し、年初来高値を更新した。好調な企業決算と海外投資家の買いが支えとなった。",
                "source": "日本経済新聞",
                "url": "https://example.com/news1",
                "key_points": ["年初来高値更新", "2.1%上昇", "好調な企業決算"],
                "impact_level": "high",
                "category": "金融",
            },
            {
                "title": "新興企業の資金調達が過去最高に",
                "summary": "スタートアップ企業による資金調達額が第3四半期で過去最高の1兆円を突破。AI関連企業への投資が特に活発。",
                "source": "TechCrunch Japan",
                "url": "https://example.com/news2",
                "key_points": ["資金調達額過去最高", "1兆円突破", "AI関連投資活発"],
                "impact_level": "medium",
                "category": "企業",
            },
        ]
        try:
            generator = ScriptGenerator()
            test_prompt = """
以下のニュース要約をもとに、二人の専門家による対談形式の台本を作成してください。
自然な会話の流れで、視聴者にとって理解しやすく、情報価値の高い内容にしてください。
"""
            script = generator.generate_dialogue(test_news, test_prompt, 15)
            print(f"Generated script ({len(script)} characters):")
            print("=" * 50)
            print(script[:500] + "..." if len(script) > 500 else script)
            print("=" * 50)
        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Gemini API not configured, skipping test")
